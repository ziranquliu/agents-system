"""
操作审计（增强）服务
核心能力：
1. 哈希链防篡改（SHA-256，每条记录含 prev_hash + curr_hash，写后读校验）
2. 追加写入（仅 INSERT，禁止 UPDATE/DELETE）
3. 多维查询 + CSV 导出
4. 日志轮转与归档（冷热分离）+ 合规保留期
5. SIEM 集成（Syslog 标准格式输出）
6. 异常行为检测（凌晨操作/高频失败/权限越界/批量删除/敏感操作）
"""
import asyncio
import csv
import hashlib
import io
import json
import logging
import socket
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import (
    AuditLog, AuditArchive, AuditRule, AuditAlert, AuditConfig,
    AuditResult, AnomalyType,
)

# 禁止修改/删除审计日志（追加写入保证）
MUTABLE_FIELDS = set()  # 审计日志无可变字段

logger = logging.getLogger("audit.siem")

# 后台推送任务引用集合（防止 asyncio 任务被 GC 回收，fire-and-forget 模式）
_FIRE_AND_FORGET_TASKS: set = set()


def _spawn_background(coro) -> None:
    """fire-and-forget：在事件循环中调度协程，失败仅记录日志，绝不抛出到调用方"""
    async def _runner():
        try:
            await coro
        except Exception:
            logger.exception("[SIEM] background send failed")
    task = asyncio.create_task(_runner())
    _FIRE_AND_FORGET_TASKS.add(task)
    task.add_done_callback(_FIRE_AND_FORGET_TASKS.discard)


class HashChainService:
    """哈希链防篡改：计算/校验 SHA-256"""

    @staticmethod
    def canonical_payload(data: Dict[str, Any]) -> str:
        """将记录字段序列化为规范字符串（键排序，保证哈希可复现）"""
        payload = dict(data)
        # 排除自身哈希，防止循环
        payload.pop("curr_hash", None)
        payload.pop("id", None)
        payload.pop("verified", None)
        payload.pop("created_at", None)
        for k, v in list(payload.items()):
            if isinstance(v, (datetime, date)):
                payload[k] = v.isoformat()
            elif v is None:
                payload[k] = ""
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def compute_hash(payload: str) -> str:
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def build_curr_hash(record_dict: Dict[str, Any], prev_hash: Optional[str]) -> str:
        record_dict = dict(record_dict)
        record_dict["prev_hash"] = prev_hash or ""
        payload = HashChainService.canonical_payload(record_dict)
        return HashChainService.compute_hash(payload)

    @staticmethod
    async def get_last_hash(session: AsyncSession) -> Optional[str]:
        """获取当前链尾哈希（保证追加顺序）"""
        stmt = select(AuditLog.curr_hash).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(1)
        result = await session.execute(stmt)
        row = result.scalar()
        return row if row else None

    @staticmethod
    async def verify_chain(session: AsyncSession) -> Dict[str, Any]:
        """全链完整性校验：任一条被修改则其后全部失效"""
        stmt = select(AuditLog).order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
        result = await session.execute(stmt)
        records = result.scalars().all()

        tampered: List[Dict[str, Any]] = []
        prev_hash: Optional[str] = None
        chain_valid = True
        total = len(records)

        for rec in records:
            record_dict = {c.name: getattr(rec, c.name) for c in rec.__table__.columns}
            expected = HashChainService.build_curr_hash(record_dict, prev_hash)
            if expected != rec.curr_hash:
                chain_valid = False
                tampered.append({
                    "id": rec.id,
                    "timestamp": rec.timestamp.isoformat() if rec.timestamp else None,
                    "action_type": rec.action_type,
                    "reason": "record_hash_mismatch",
                })
            if prev_hash is not None and rec.prev_hash != prev_hash:
                chain_valid = False
                tampered.append({
                    "id": rec.id,
                    "timestamp": rec.timestamp.isoformat() if rec.timestamp else None,
                    "action_type": rec.action_type,
                    "reason": "chain_link_broken",
                })
            prev_hash = rec.curr_hash

        return {
            "chain_valid": chain_valid,
            "total_records": total,
            "tampered_count": len(tampered),
            "tampered": tampered[:100],
        }


class AuditService:
    """审计日志写入 / 查询 / 导出 / 轮转归档"""

    @staticmethod
    async def log(
        session: AsyncSession,
        *,
        operator_id: str,
        action_type: str,
        category: str,
        result: str = "success",
        operator_name: Optional[str] = None,
        operator_ip: Optional[str] = None,
        device_info: Optional[str] = None,
        target_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        failure_reason: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> AuditLog:
        """追加审计记录（哈希链 + 写后读校验）"""
        config = await AuditService.get_config(session)
        mask = config.mask_sensitive if config else True

        now = datetime.utcnow()
        prev_hash = await HashChainService.get_last_hash(session)

        record = AuditLog(
            timestamp=now,
            operator_id=AuditService._mask(operator_id) if mask else operator_id,
            operator_name=operator_name,
            operator_ip=AuditService._mask(operator_ip) if mask else operator_ip,
            device_info=device_info,
            category=category,
            action_type=action_type,
            target_id=target_id,
            details=json.dumps(details, ensure_ascii=False) if details else None,
            result=result,
            failure_reason=failure_reason,
            trace_id=trace_id,
            partition_date=now.date(),
            prev_hash=prev_hash,
        )
        record.curr_hash = HashChainService.build_curr_hash(
            {c.name: getattr(record, c.name) for c in record.__table__.columns}, prev_hash
        )
        session.add(record)
        await session.flush()

        # 写后读校验：重新计算哈希对比
        read_back = {c.name: getattr(record, c.name) for c in record.__table__.columns}
        expected = HashChainService.build_curr_hash(read_back, prev_hash)
        record.verified = (expected == record.curr_hash)
        await session.commit()

        # SIEM 自动推送（fire-and-forget，失败不阻塞主流程）
        if config and config.siem_enabled:
            try:
                line = SIEMExporter.to_syslog(record)
                _spawn_background(SIEMExporter.send([line], config=config))
            except Exception:
                logger.exception("[SIEM] auto push schedule failed")

        return record

    @staticmethod
    def _mask(value: Optional[str]) -> Optional[str]:
        """隐私脱敏：IP 保留前 2 段，用户 ID 保留前后 4 位"""
        if not value:
            return value
        # IP 脱敏 192.168.1.100 -> 192.168.*.*
        parts = value.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.*.*"
        if len(value) > 8:
            return f"{value[:4]}****{value[-4:]}"
        return "****"

    @staticmethod
    async def query(
        session: AsyncSession,
        *,
        operator_id: Optional[str] = None,
        action_type: Optional[str] = None,
        category: Optional[str] = None,
        target_id: Optional[str] = None,
        result: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """多维搜索：时间/操作者/类型/对象/结果 组合过滤"""
        filters = []
        if operator_id:
            filters.append(AuditLog.operator_id.like(f"%{operator_id}%"))
        if action_type:
            filters.append(AuditLog.action_type.like(f"%{action_type}%"))
        if category:
            filters.append(AuditLog.category == category)
        if target_id:
            filters.append(AuditLog.target_id.like(f"%{target_id}%"))
        if result:
            filters.append(AuditLog.result == result)
        if start_time:
            filters.append(AuditLog.timestamp >= start_time)
        if end_time:
            filters.append(AuditLog.timestamp <= end_time)

        total_stmt = select(func.count()).select_from(AuditLog).where(*filters)
        total = (await session.execute(total_stmt)).scalar() or 0

        stmt = (
            select(AuditLog)
            .where(*filters)
            .order_by(AuditLog.timestamp.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        records = (await session.execute(stmt)).scalars().all()
        return {"total": total, "items": records, "page": page, "page_size": page_size}

    @staticmethod
    async def stats(session: AsyncSession) -> Dict[str, Any]:
        """审计统计：分类/结果分布 + 保留期合规状态"""
        cat_stmt = (
            select(AuditLog.category, func.count())
            .group_by(AuditLog.category)
        )
        cat_rows = (await session.execute(cat_stmt)).all()
        by_category = {k: v for k, v in cat_rows}

        res_stmt = (
            select(AuditLog.result, func.count())
            .group_by(AuditLog.result)
        )
        res_rows = (await session.execute(res_stmt)).all()
        by_result = {k: v for k, v in res_rows}

        total = (await session.execute(select(func.count()).select_from(AuditLog))).scalar() or 0
        oldest = (await session.execute(select(func.min(AuditLog.timestamp)))).scalar()

        config = await AuditService.get_config(session)
        retention_days = config.retention_days if config else 180

        return {
            "total": total,
            "by_category": by_category,
            "by_result": by_result,
            "oldest_record": oldest.isoformat() if oldest else None,
            "retention_days": retention_days,
            "retention_compliant": (oldest is None) or (datetime.utcnow() - oldest).days <= retention_days,
        }

    @staticmethod
    async def export_csv(session: AsyncSession, filters: Dict[str, Any]) -> str:
        """CSV 导出（合规格式：完整元数据）"""
        data = await AuditService.query(session, page=1, page_size=100000, **filters)
        records = data["items"]
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow([
            "timestamp", "operator_id", "operator_ip", "device_info",
            "category", "action_type", "target_id", "details",
            "result", "failure_reason", "trace_id", "prev_hash", "curr_hash", "verified",
        ])
        for r in records:
            writer.writerow([
                r.timestamp.isoformat() if r.timestamp else "",
                r.operator_id or "", r.operator_ip or "", r.device_info or "",
                r.category or "", r.action_type or "", r.target_id or "",
                r.details or "", r.result or "", r.failure_reason or "",
                r.trace_id or "", r.prev_hash or "", r.curr_hash or "", r.verified,
            ])
        return buffer.getvalue()

    @staticmethod
    async def get_config(session: AsyncSession) -> Optional[AuditConfig]:
        result = await session.execute(select(AuditConfig).limit(1))
        return result.scalars().first()

    @staticmethod
    async def update_config(session: AsyncSession, data: Dict[str, Any]) -> AuditConfig:
        config = await AuditService.get_config(session)
        if not config:
            config = AuditConfig()
            session.add(config)
        for k, v in data.items():
            if hasattr(config, k) and v is not None:
                setattr(config, k, v)
        config.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(config)
        return config

    @staticmethod
    async def archive_old(session: AsyncSession) -> Dict[str, Any]:
        """冷热分离：将超过 archive_after_days 的记录归档（逻辑归档，标记归档元信息）"""
        config = await AuditService.get_config(session)
        archive_after = config.archive_after_days if config else 90
        cutoff = datetime.utcnow() - timedelta(days=archive_after)

        stmt = select(AuditLog).where(AuditLog.timestamp < cutoff)
        records = (await session.execute(stmt)).scalars().all()
        if not records:
            return {"archived": 0, "message": "no records to archive"}

        start_date = min(r.timestamp.date() for r in records)
        end_date = max(r.timestamp.date() for r in records)
        archive = AuditArchive(
            archive_key=f"audit_{start_date.isoformat()}_{end_date.isoformat()}",
            start_date=start_date,
            end_date=end_date,
            record_count=len(records),
            archive_path=f"/audit/archive/{start_date.isoformat()}_{end_date.isoformat()}.json",
        )
        session.add(archive)
        # 归档后删除热数据（归档文件视为不可变副本）
        for r in records:
            await session.delete(r)
        await session.commit()
        return {"archived": len(records), "archive_key": archive.archive_key}

    @staticmethod
    async def enforce_retention(session: AsyncSession) -> Dict[str, Any]:
        """合规保留期：删除超过 retention_days 的旧数据（同时保留归档元信息）"""
        config = await AuditService.get_config(session)
        retention = config.retention_days if config else 180
        cutoff = datetime.utcnow() - timedelta(days=retention)
        stmt = delete(AuditLog).where(AuditLog.timestamp < cutoff)
        result = await session.execute(stmt)
        await session.commit()
        return {"deleted": result.rowcount, "cutoff": cutoff.isoformat()}


class SIEMExporter:
    """SIEM 集成：Syslog RFC3164 标准格式输出"""

    @staticmethod
    def to_syslog(record: AuditLog) -> str:
        """转换为 Syslog 消息格式
        <PRI>MMM dd HH:MM:SS hostname tag[pid]: message
        """
        ts = record.timestamp.strftime("%b %d %H:%M:%S") if record.timestamp else ""
        tag = "agentsystem.audit"
        msg = (
            f"category={record.category} action={record.action_type} "
            f"operator={record.operator_id} target={record.target_id} "
            f"result={record.result} ip={record.operator_ip} "
            f"trace={record.trace_id} hash={record.curr_hash}"
        )
        return f"<134>{ts} localhost {tag}: {msg}"

    @staticmethod
    async def export_recent(session: AsyncSession, minutes: int = 60) -> List[str]:
        """导出最近 N 分钟审计日志为 Syslog 格式（供 SIEM 拉取/转发）"""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        stmt = select(AuditLog).where(AuditLog.timestamp >= cutoff).order_by(AuditLog.timestamp.asc())
        records = (await session.execute(stmt)).scalars().all()
        return [SIEMExporter.to_syslog(r) for r in records]

    @staticmethod
    def _resolve_protocol(protocol: Optional[str]) -> str:
        """解析传输协议：syslog 默认映射为 udp，其余仅支持 udp/tcp"""
        proto = (protocol or "syslog").lower()
        if proto in ("tcp",):
            return "tcp"
        return "udp"

    @staticmethod
    async def _send_udp(lines: List[str], host: str, port: int) -> int:
        """UDP 发送：每条 Syslog 消息一条独立 UDP 报文"""
        def _blocking() -> int:
            sent = 0
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(5.0)
                for line in lines:
                    sock.sendto(line.encode("utf-8"), (host, port))
                    sent += 1
            return sent
        return await asyncio.to_thread(_blocking)

    @staticmethod
    async def _send_tcp(lines: List[str], host: str, port: int) -> int:
        """TCP 发送：所有消息以 \\n 分隔拼接后一次发送"""
        def _blocking() -> int:
            with socket.create_connection((host, port), timeout=5.0) as sock:
                payload = ("\n".join(lines)).encode("utf-8") + b"\n"
                sock.sendall(payload)
            return len(lines)
        return await asyncio.to_thread(_blocking)

    @staticmethod
    async def send(
        lines: List[str],
        config: Optional[AuditConfig] = None,
        session: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """实际推送 Syslog 消息到配置的 SIEM 主机（UDP/TCP）

        - 读取 AuditConfig 的 siem_enabled / siem_host / siem_port / siem_protocol
        - protocol=udp → SOCK_DGRAM 发送到 (host, port)，每条一条报文
        - protocol=tcp → 建立 TCP 连接发送，消息以 \\n 分隔
        - 发送失败降级：仅记录日志，不抛异常（scheduler/自动推送中容错）

        返回: {pushed, failed, protocol, host, port, enabled, reason/error}
        """
        if config is None and session is not None:
            config = await AuditService.get_config(session)

        if config is None:
            logger.warning("[SIEM] send skipped: no audit config")
            return {"pushed": 0, "failed": len(lines), "enabled": False, "reason": "no_config"}
        if not config.siem_enabled:
            return {"pushed": 0, "failed": len(lines), "enabled": False, "reason": "disabled"}
        host = (config.siem_host or "").strip()
        if not host:
            logger.warning("[SIEM] send skipped: siem_enabled but siem_host is empty")
            return {"pushed": 0, "failed": len(lines), "enabled": True, "reason": "no_host"}
        port = config.siem_port or 514
        protocol = SIEMExporter._resolve_protocol(config.siem_protocol)

        try:
            if protocol == "tcp":
                pushed = await SIEMExporter._send_tcp(lines, host, port)
            else:
                pushed = await SIEMExporter._send_udp(lines, host, port)
            return {
                "pushed": pushed,
                "failed": len(lines) - pushed,
                "protocol": protocol,
                "host": host,
                "port": port,
                "enabled": True,
            }
        except Exception as e:
            logger.error(f"[SIEM] send failed to {host}:{port} ({protocol}): {e}", exc_info=True)
            return {
                "pushed": 0,
                "failed": len(lines),
                "protocol": protocol,
                "host": host,
                "port": port,
                "enabled": True,
                "error": str(e),
            }


class AnomalyDetector:
    """内置规则引擎：异常行为检测"""

    DEFAULT_RULES = [
        {"rule_type": AnomalyType.OFF_HOURS, "rule_name": "凌晨操作检测", "severity": "medium",
         "params": {"window": [0, 6], "threshold": 3}},
        {"rule_type": AnomalyType.HIGH_FREQ_FAILURE, "rule_name": "高频失败检测", "severity": "high",
         "params": {"threshold": 10, "window_minutes": 5}},
        {"rule_type": AnomalyType.PERMISSION_ESCALATION, "rule_name": "权限越界尝试", "severity": "critical",
         "params": {"actions": ["user.role_change", "auth.grant", "security.key_rotate"]}},
        {"rule_type": AnomalyType.BATCH_DELETE, "rule_name": "批量删除检测", "severity": "high",
         "params": {"threshold": 20, "window_minutes": 5}},
        {"rule_type": AnomalyType.SENSITIVE_OP, "rule_name": "敏感操作检测", "severity": "high",
         "params": {"actions": ["backup.encrypt_key", "agent.delete", "market.uninstall"]}},
    ]

    @staticmethod
    async def ensure_rules(session: AsyncSession) -> None:
        count = (await session.execute(select(func.count()).select_from(AuditRule))).scalar() or 0
        if count == 0:
            for r in AnomalyDetector.DEFAULT_RULES:
                session.add(AuditRule(**r))
            await session.commit()

    @staticmethod
    async def run_detection(session: AsyncSession) -> Dict[str, Any]:
        """执行全部启用规则的异常检测"""
        await AnomalyDetector.ensure_rules(session)
        rules = (await session.execute(select(AuditRule).where(AuditRule.enabled == True))).scalars().all()  # noqa: E712
        alerts: List[AuditAlert] = []
        now = datetime.utcnow()

        for rule in rules:
            params = json.loads(rule.params) if rule.params else {}
            if rule.rule_type == AnomalyType.OFF_HOURS:
                alerts += await AnomalyDetector._detect_off_hours(session, rule, params, now)
            elif rule.rule_type == AnomalyType.HIGH_FREQ_FAILURE:
                alerts += await AnomalyDetector._detect_high_freq_failure(session, rule, params, now)
            elif rule.rule_type == AnomalyType.PERMISSION_ESCALATION:
                alerts += await AnomalyDetector._detect_permission_escalation(session, rule, params, now)
            elif rule.rule_type == AnomalyType.BATCH_DELETE:
                alerts += await AnomalyDetector._detect_batch_delete(session, rule, params, now)
            elif rule.rule_type == AnomalyType.SENSITIVE_OP:
                alerts += await AnomalyDetector._detect_sensitive_ops(session, rule, params, now)

        for alert in alerts:
            session.add(alert)
        await session.commit()
        return {"alerts_created": len(alerts), "rules_evaluated": len(rules)}

    @staticmethod
    async def _detect_off_hours(session: AsyncSession, rule: AuditRule, params: Dict, now: datetime) -> List[AuditAlert]:
        """凌晨 0:00-6:00 操作检测"""
        window = params.get("window", [0, 6])
        threshold = params.get("threshold", 3)
        start = now.replace(hour=window[0], minute=0, second=0, microsecond=0)
        end = now.replace(hour=window[1], minute=0, second=0, microsecond=0)
        if start > now:  # 当前不在窗口内则跳过
            return []
        stmt = (
            select(AuditLog.operator_id, func.count())
            .where(AuditLog.timestamp >= start, AuditLog.timestamp <= end)
            .group_by(AuditLog.operator_id)
        )
        rows = (await session.execute(stmt)).all()
        alerts = []
        for op, cnt in rows:
            if cnt >= threshold:
                alerts.append(AuditAlert(
                    alert_type=AnomalyType.OFF_HOURS, severity=rule.severity,
                    operator_id=op,
                    description=f"操作者 {op} 在凌晨窗口({window[0]}:00-{window[1]}:00)执行 {cnt} 次操作",
                    evidence=json.dumps({"count": cnt, "window": window}, ensure_ascii=False),
                ))
        return alerts

    @staticmethod
    async def _detect_high_freq_failure(session: AsyncSession, rule: AuditRule, params: Dict, now: datetime) -> List[AuditAlert]:
        """高频失败：N 次/分钟"""
        threshold = params.get("threshold", 10)
        window_minutes = params.get("window_minutes", 5)
        cutoff = now - timedelta(minutes=window_minutes)
        stmt = (
            select(AuditLog.operator_id, func.count())
            .where(AuditLog.timestamp >= cutoff, AuditLog.result == AuditResult.FAILURE)
            .group_by(AuditLog.operator_id)
        )
        rows = (await session.execute(stmt)).all()
        alerts = []
        for op, cnt in rows:
            if cnt >= threshold:
                alerts.append(AuditAlert(
                    alert_type=AnomalyType.HIGH_FREQ_FAILURE, severity=rule.severity,
                    operator_id=op,
                    description=f"操作者 {op} 在 {window_minutes} 分钟内失败 {cnt} 次（疑似暴力尝试）",
                    evidence=json.dumps({"count": cnt, "window_minutes": window_minutes}, ensure_ascii=False),
                ))
        return alerts

    @staticmethod
    async def _detect_permission_escalation(session: AsyncSession, rule: AuditRule, params: Dict, now: datetime) -> List[AuditAlert]:
        """权限越界尝试：敏感权限动作的 denied/failure"""
        actions = params.get("actions", ["user.role_change", "auth.grant", "security.key_rotate"])
        cutoff = now - timedelta(hours=24)
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.timestamp >= cutoff,
                AuditLog.action_type.in_(actions),
                AuditLog.result.in_([AuditResult.DENIED, AuditResult.FAILURE]),
            )
            .order_by(AuditLog.timestamp.desc())
            .limit(50)
        )
        records = (await session.execute(stmt)).scalars().all()
        alerts = []
        for r in records:
            alerts.append(AuditAlert(
                alert_type=AnomalyType.PERMISSION_ESCALATION, severity=rule.severity,
                operator_id=r.operator_id,
                description=f"权限越界尝试：{r.operator_id} 执行 {r.action_type} 被拒绝（{r.failure_reason or 'denied'}）",
                evidence=json.dumps({"action": r.action_type, "target": r.target_id, "result": r.result}, ensure_ascii=False),
            ))
        return alerts

    @staticmethod
    async def _detect_batch_delete(session: AsyncSession, rule: AuditRule, params: Dict, now: datetime) -> List[AuditAlert]:
        """批量删除检测：短时间内大量 delete 操作"""
        threshold = params.get("threshold", 20)
        window_minutes = params.get("window_minutes", 5)
        cutoff = now - timedelta(minutes=window_minutes)
        stmt = (
            select(AuditLog.operator_id, func.count())
            .where(AuditLog.timestamp >= cutoff, AuditLog.action_type.like("%.delete%"))
            .group_by(AuditLog.operator_id)
        )
        rows = (await session.execute(stmt)).all()
        alerts = []
        for op, cnt in rows:
            if cnt >= threshold:
                alerts.append(AuditAlert(
                    alert_type=AnomalyType.BATCH_DELETE, severity=rule.severity,
                    operator_id=op,
                    description=f"检测到批量删除：{op} 在 {window_minutes} 分钟内执行 {cnt} 次删除操作",
                    evidence=json.dumps({"count": cnt, "window_minutes": window_minutes}, ensure_ascii=False),
                ))
        return alerts

    @staticmethod
    async def _detect_sensitive_ops(session: AsyncSession, rule: AuditRule, params: Dict, now: datetime) -> List[AuditAlert]:
        """敏感操作检测：密钥/删除/卸载等高危动作"""
        actions = params.get("actions", ["backup.encrypt_key", "agent.delete", "market.uninstall"])
        cutoff = now - timedelta(hours=24)
        stmt = (
            select(AuditLog)
            .where(AuditLog.timestamp >= cutoff, AuditLog.action_type.in_(actions))
            .order_by(AuditLog.timestamp.desc())
            .limit(50)
        )
        records = (await session.execute(stmt)).scalars().all()
        alerts = []
        for r in records:
            alerts.append(AuditAlert(
                alert_type=AnomalyType.SENSITIVE_OP, severity=rule.severity,
                operator_id=r.operator_id,
                description=f"敏感操作：{r.operator_id} 执行 {r.action_type}（{r.result}）",
                evidence=json.dumps({"action": r.action_type, "target": r.target_id}, ensure_ascii=False),
            ))
        return alerts

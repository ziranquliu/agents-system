"""
本地组件扫描器服务 - 扫描 Agent/Skill/MCP 健康状态
"""
import asyncio
import json
import uuid
from datetime import datetime
from typing import Optional

import aiohttp
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.scanner import ComponentScan, ComponentScanItem, ScannerAlert


async def _detect_changes_and_alert(db: AsyncSession, scan: ComponentScan) -> list[ScannerAlert]:
    """变化检测：对比本次扫描与上一次扫描，对状态变化生成告警

    规则：
    - healthy -> warning: 降级告警（warning）
    - healthy/warning -> error: 严重告警（critical）
    - error -> healthy: 恢复通知（info）
    """
    # 获取本次扫描的所有条目
    stmt = select(ComponentScanItem).where(ComponentScanItem.scan_id == scan.id)
    current_items = (await db.execute(stmt)).scalars().all()

    # 获取上一次扫描（排除本次）
    prev_scan = (await db.execute(
        select(ComponentScan)
        .where(ComponentScan.id != scan.id, ComponentScan.status == "completed")
        .order_by(ComponentScan.completed_at.desc())
        .limit(1)
    )).scalars().first()

    if not prev_scan:
        return []

    prev_stmt = select(ComponentScanItem).where(ComponentScanItem.scan_id == prev_scan.id)
    prev_items = (await db.execute(prev_stmt)).scalars().all()
    prev_map = {(p.component_type, p.component_id): p for p in prev_items}

    alerts: list[ScannerAlert] = []
    for item in current_items:
        prev = prev_map.get((item.component_type, item.component_id))
        if not prev or prev.status == item.status:
            continue  # 新增组件或状态未变化

        changed_from = prev.status
        changed_to = item.status

        if changed_to == "error" and changed_from != "error":
            severity = "critical"
            message = f"[组件扫描] {item.component_name or item.component_id} ({item.component_type}) 状态异常: {changed_from} → {changed_to}"
        elif changed_to == "warning" and changed_from == "healthy":
            severity = "warning"
            message = f"[组件扫描] {item.component_name or item.component_id} ({item.component_type}) 状态降级: {changed_from} → {changed_to}"
        elif changed_to == "healthy" and changed_from in ("error", "warning"):
            severity = "info"
            message = f"[组件扫描] {item.component_name or item.component_id} ({item.component_type}) 已恢复: {changed_from} → {changed_to}"
        else:
            severity = "warning"
            message = f"[组件扫描] {item.component_name or item.component_id} ({item.component_type}) 状态变化: {changed_from} → {changed_to}"

        alert = ScannerAlert(
            component_type=item.component_type,
            component_id=item.component_id,
            component_name=item.component_name,
            previous_status=changed_from,
            current_status=changed_to,
            severity=severity,
            message=message,
            scan_id=scan.id,
        )
        db.add(alert)
        alerts.append(alert)

    return alerts


async def trigger_scan(user_id: str = "system") -> ComponentScan:
    """触发一次全面扫描

    扫描范围：
    1. Agent: 检查 status 是否为正常状态
    2. Skill: 检查是否有绑定关系异常
    3. MCP Server: 检查是否能建立连接（健康检测）
    """
    scan = ComponentScan(
        id=str(uuid.uuid4()),
        status="running",
        started_at=datetime.utcnow(),
        triggered_by=user_id,
    )

    async with async_session_factory() as db:
        db.add(scan)
        await db.flush()

        totals = {"checked": 0, "healthy": 0, "warning": 0, "error": 0}

        # 1. 扫描 Agent
        agent_results = await _scan_agents(db, scan.id)
        for r in agent_results:
            db.add(r)
            totals["checked"] += 1
            totals[r.status] = totals.get(r.status, 0) + 1

        # 2. 扫描 Skill
        skill_results = await _scan_skills(db, scan.id)
        for r in skill_results:
            db.add(r)
            totals["checked"] += 1
            totals[r.status] = totals.get(r.status, 0) + 1

        # 3. 扫描 MCP Server
        mcp_results = await _scan_mcp_servers(db, scan.id)
        for r in mcp_results:
            db.add(r)
            totals["checked"] += 1
            totals[r.status] = totals.get(r.status, 0) + 1

        # 更新扫描会话
        scan.status = "completed"
        scan.completed_at = datetime.utcnow()
        scan.summary = json.dumps(totals, ensure_ascii=False)
        await db.flush()

        # 变化检测与告警（对比上一次扫描）
        try:
            alerts = await _detect_changes_and_alert(db, scan)
            if alerts:
                scan.summary = json.dumps({**totals, "alerts": len(alerts)}, ensure_ascii=False)
            await db.commit()
        except Exception:
            await db.rollback()

    return scan


async def _scan_agents(db: AsyncSession, scan_id: str) -> list[ComponentScanItem]:
    """扫描 Agent 状态"""
    from app.models.agent import Agent

    result = await db.execute(select(Agent))
    agents = result.scalars().all()
    items = []

    for agent in agents:
        status = "healthy"
        error_msg = None
        details = {}

        if agent.status == "draft":
            status = "warning"
            error_msg = "Agent 处于草稿状态，未激活"
        elif agent.status == "inactive":
            status = "error"
            error_msg = "Agent 已被停用"
        elif agent.status == "error":
            status = "error"
            error_msg = "Agent 报告错误状态"

        details["model_provider"] = agent.model_provider
        details["model_name"] = agent.model_name

        items.append(ComponentScanItem(
            id=str(uuid.uuid4()),
            scan_id=scan_id,
            component_type="agent",
            component_id=agent.id,
            component_name=agent.name,
            status=status,
            error_message=error_msg,
            details=json.dumps(details, ensure_ascii=False) if details else None,
        ))

    return items


async def _scan_skills(db: AsyncSession, scan_id: str) -> list[ComponentScanItem]:
    """扫描 Skill 状态"""
    from app.models.skill import Skill

    result = await db.execute(select(Skill))
    skills = result.scalars().all()
    items = []

    for skill in skills:
        status = "healthy"
        error_msg = None
        details = {}

        if skill.type not in ("builtin", "custom", "market"):
            status = "warning"
            error_msg = f"未知的 Skill 类型: {skill.type}"

        # 获取绑定计数
        from app.services.skill_service import get_skill_bindings_count
        try:
            bind_count = await get_skill_bindings_count(db, skill.id)
            details["bindings_count"] = bind_count
        except Exception:
            details["bindings_count"] = 0

        details["skill_type"] = skill.type

        items.append(ComponentScanItem(
            id=str(uuid.uuid4()),
            scan_id=scan_id,
            component_type="skill",
            component_id=skill.id,
            component_name=skill.name,
            status=status,
            error_message=error_msg,
            details=json.dumps(details, ensure_ascii=False) if details else None,
        ))

    return items


async def _scan_mcp_servers(db: AsyncSession, scan_id: str) -> list[ComponentScanItem]:
    """扫描 MCP Server 状态（含健康检测）"""
    from app.models.mcp import MCPServer

    result = await db.execute(select(MCPServer))
    servers = result.scalars().all()
    items = []

    for server in servers:
        status = "healthy"
        error_msg = None
        details = {"protocol": server.protocol or "unknown", "url": server.url or ""}

        # 健康检测 - 尝试连接
        if server.url:
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                    async with session.get(server.url) as resp:
                        if resp.status >= 400:
                            status = "error"
                            error_msg = f"HTTP {resp.status}: 连接失败"
                        elif resp.status >= 300:
                            status = "warning"
                            error_msg = f"HTTP {resp.status}: 可能需要重定向"
            except (TimeoutError, asyncio.TimeoutError):
                status = "error"
                error_msg = "连接超时（5秒）"
            except aiohttp.ClientConnectorError as e:
                status = "error"
                error_msg = f"连接失败: {e}"
            except Exception as e:
                status = "error"
                error_msg = f"异常: {e}"
        else:
            status = "warning"
            error_msg = "未配置 URL"

        items.append(ComponentScanItem(
            id=str(uuid.uuid4()),
            scan_id=scan_id,
            component_type="mcp",
            component_id=server.id,
            component_name=server.name,
            status=status,
            error_message=error_msg,
            details=json.dumps(details, ensure_ascii=False) if details else None,
        ))

    return items


async def get_latest_scan(db: AsyncSession) -> Optional[ComponentScan]:
    """获取最近一次扫描会话"""
    result = await db.execute(
        select(ComponentScan)
        .order_by(ComponentScan.started_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_scan_history(db: AsyncSession, page: int = 1, page_size: int = 10) -> tuple[list[ComponentScan], int]:
    """获取扫描历史"""
    # 总数
    count_result = await db.execute(select(func.count(ComponentScan.id)))
    total = count_result.scalar()

    # 分页
    offset = (page - 1) * page_size
    result = await db.execute(
        select(ComponentScan)
        .order_by(ComponentScan.started_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    scans = result.scalars().all()

    return scans, total


async def get_scan_items(db: AsyncSession, scan_id: str, component_type: Optional[str] = None,
                         status_filter: Optional[str] = None) -> list[ComponentScanItem]:
    """获取特定扫描的结果项"""
    query = select(ComponentScanItem).where(ComponentScanItem.scan_id == scan_id)

    if component_type:
        query = query.where(ComponentScanItem.component_type == component_type)
    if status_filter:
        query = query.where(ComponentScanItem.status == status_filter)

    query = query.order_by(ComponentScanItem.component_type, ComponentScanItem.component_name)
    result = await db.execute(query)
    return list(result.scalars().all())


async def clean_old_scans(db: AsyncSession, keep_count: int = 30) -> int:
    """清理旧的扫描记录，只保留最近 N 条"""
    # 获取要保留的最新记录的 ID
    result = await db.execute(
        select(ComponentScan.id)
        .order_by(ComponentScan.started_at.desc())
        .limit(keep_count)
    )
    keep_ids = set(row[0] for row in result.all())

    # 删除不在保留列表中的记录
    delete_result = await db.execute(
        delete(ComponentScan).where(ComponentScan.id.notin_(keep_ids))
    )
    return delete_result.rowcount

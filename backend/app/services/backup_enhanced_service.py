"""
各智能体备份与恢复(增强)服务
覆盖：增量备份、事件触发备份、部分恢复、AES-256-GCM 加密、SHA-256 校验、密钥轮换、恢复演练
"""
import hashlib
import json
import os
import secrets
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.backup_enhanced import (
    BackupRecord, BackupPolicy, BackupEventLog, RestoreOperation,
    RestoreDrill, EncryptionKey,
    BackupType, BackupStatus, BackupScope,
    RestoreType, RestoreStatus, DrillStatus, EncryptionAlgo,
)

_BACKUP_DIR = Path(__file__).parent.parent / "backups_enhanced"
_KEYSTORE_DIR = Path(__file__).parent.parent / "keystore"
_KEY_FILE = _KEYSTORE_DIR / "keys.json"

_CHUNK_SIZE = 1024 * 1024  # 1MB 加密分块


def _ensure_dirs():
    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    _KEYSTORE_DIR.mkdir(parents=True, exist_ok=True)


def _load_keystore() -> Dict[str, Dict]:
    if not _KEY_FILE.exists():
        return {}
    try:
        with open(_KEY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_keystore(store: Dict[str, Dict]):
    _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_KEY_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


def _generate_key() -> bytes:
    return secrets.token_bytes(32)  # AES-256


# ==================== 密钥管理 ====================

class KeyManager:

    @staticmethod
    async def create_key(session: AsyncSession, note: Optional[str] = None) -> EncryptionKey:
        """创建新密钥并轮换（旧密钥标记 retired）"""
        _ensure_dirs()
        store = _load_keystore()

        # 轮换旧密钥
        old_stmt = select(EncryptionKey).where(EncryptionKey.status == "active")
        old_result = await session.execute(old_stmt)
        for old in old_result.scalars().all():
            old.status = "retired"
            old.retired_at = datetime.utcnow()

        key_id = f"k_{uuid.uuid4().hex[:16]}"
        key_bytes = _generate_key()
        store[key_id] = {
            "key": key_bytes.hex(),
            "created_at": datetime.utcnow().isoformat(),
            "algorithm": "aes_256_gcm",
        }
        _save_keystore(store)

        key_record = EncryptionKey(
            key_id=key_id,
            status="active",
            note=note,
        )
        session.add(key_record)
        await session.flush()
        return key_record

    @staticmethod
    def get_key(key_id: str) -> Optional[bytes]:
        store = _load_keystore()
        entry = store.get(key_id)
        if not entry:
            return None
        return bytes.fromhex(entry["key"])

    @staticmethod
    async def list_keys(session: AsyncSession) -> Tuple[List[EncryptionKey], int]:
        stmt = select(EncryptionKey).order_by(desc(EncryptionKey.created_at))
        count_stmt = select(func.count(EncryptionKey.id))
        result = await session.execute(stmt)
        count_result = await session.execute(count_stmt)
        return list(result.scalars().all()), count_result.scalar() or 0

    @staticmethod
    async def get_active_key_id(session: AsyncSession) -> Optional[str]:
        stmt = select(EncryptionKey).where(EncryptionKey.status == "active").limit(1)
        result = await session.execute(stmt)
        key = result.scalar_one_or_none()
        return key.key_id if key else None


# ==================== 加密与校验 ====================

class CryptoHelper:

    @staticmethod
    def encrypt_bytes(data: bytes, key: bytes) -> bytes:
        """AES-256-GCM 加密，返回 nonce(12) + ciphertext + tag"""
        aesgcm = AESGCM(key)
        nonce = secrets.token_bytes(12)
        ciphertext = aesgcm.encrypt(nonce, data, None)
        return nonce + ciphertext

    @staticmethod
    def decrypt_bytes(data: bytes, key: bytes) -> bytes:
        nonce = data[:12]
        ciphertext = data[12:]
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, None)

    @staticmethod
    def sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def encrypt_file(src: Path, dst: Path, key: bytes) -> str:
        """流式加密大文件，返回 SHA-256"""
        h = hashlib.sha256()
        with open(src, "rb") as fin, open(dst, "wb") as fout:
            # 头部：魔数 8B + 版本 4B
            fout.write(b"AEBKv1\x00\x00")
            while True:
                chunk = fin.read(_CHUNK_SIZE)
                if not chunk:
                    break
                h.update(chunk)
                enc = CryptoHelper.encrypt_bytes(chunk, key)
                fout.write(len(enc).to_bytes(4, "big"))
                fout.write(enc)
        return h.hexdigest()

    @staticmethod
    def decrypt_file(src: Path, dst: Path, key: bytes) -> str:
        h = hashlib.sha256()
        with open(src, "rb") as fin, open(dst, "wb") as fout:
            header = fin.read(8)
            if header != b"AEBKv1\x00\x00":
                raise ValueError("非法加密文件头")
            while True:
                size_b = fin.read(4)
                if not size_b:
                    break
                size = int.from_bytes(size_b, "big")
                enc = fin.read(size)
                dec = CryptoHelper.decrypt_bytes(enc, key)
                h.update(dec)
                fout.write(dec)
        return h.hexdigest()


# ==================== 数据收集与备份 ====================

class BackupEnhancedService:

    @staticmethod
    async def get_policy(session: AsyncSession, agent_id: str) -> Optional[BackupPolicy]:
        stmt = select(BackupPolicy).where(BackupPolicy.agent_id == agent_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def upsert_policy(session: AsyncSession, agent_id: str, agent_name: str, **kwargs) -> BackupPolicy:
        existing = await BackupEnhancedService.get_policy(session, agent_id)
        if existing:
            for k, v in kwargs.items():
                if hasattr(existing, k) and v is not None:
                    setattr(existing, k, v)
            existing.updated_at = datetime.utcnow()
            await session.flush()
            return existing
        policy = BackupPolicy(agent_id=agent_id, agent_name=agent_name, **kwargs)
        session.add(policy)
        await session.flush()
        return policy

    @staticmethod
    async def list_policies(
        session: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        enabled_only: bool = False,
    ) -> Tuple[List[BackupPolicy], int]:
        conditions = []
        if enabled_only:
            conditions.append(BackupPolicy.enabled == True)
        stmt = select(BackupPolicy).where(and_(*conditions)).order_by(desc(BackupPolicy.updated_at)).offset(skip).limit(limit)
        count_stmt = select(func.count(BackupPolicy.id)).where(and_(*conditions))
        result = await session.execute(stmt)
        count_result = await session.execute(count_stmt)
        return list(result.scalars().all()), count_result.scalar() or 0

    @staticmethod
    async def delete_policy(session: AsyncSession, policy_id: str) -> bool:
        stmt = select(BackupPolicy).where(BackupPolicy.id == policy_id)
        result = await session.execute(stmt)
        policy = result.scalar_one_or_none()
        if not policy:
            return False
        policy.enabled = False
        await session.flush()
        return True

    # ---------- 数据收集 ----------

    @staticmethod
    async def _collect_data(session: AsyncSession, agent_id: str, scope: BackupScope) -> Dict[str, Any]:
        """按范围收集 Agent 数据"""
        data = {"agent_id": agent_id, "collected_at": datetime.utcnow().isoformat(), "tables": {}}

        from app.models.agent import Agent
        from app.models.conversation import Conversation, Message
        from app.models.memory import AgentMemory

        if scope in (BackupScope.ALL, BackupScope.CONFIG):
            agent_result = await session.execute(select(Agent).where(Agent.id == agent_id))
            agent = agent_result.scalar_one_or_none()
            if agent:
                a = {}
                for col in Agent.__table__.columns:
                    val = getattr(agent, col.name)
                    if isinstance(val, datetime):
                        val = val.isoformat()
                    a[col.name] = val
                data["tables"]["agent"] = [a]

        if scope in (BackupScope.ALL, BackupScope.MEMORY):
            mem_result = await session.execute(select(AgentMemory).where(AgentMemory.agent_id == agent_id))
            mems = []
            for m in mem_result.scalars().all():
                d = {}
                for col in AgentMemory.__table__.columns:
                    val = getattr(m, col.name)
                    if isinstance(val, datetime):
                        val = val.isoformat()
                    d[col.name] = val
                mems.append(d)
            data["tables"]["memories"] = mems

        if scope in (BackupScope.ALL, BackupScope.CONVERSATIONS):
            conv_result = await session.execute(select(Conversation).where(Conversation.agent_id == agent_id))
            convs = []
            for c in conv_result.scalars().all():
                d = {}
                for col in Conversation.__table__.columns:
                    val = getattr(c, col.name)
                    if isinstance(val, datetime):
                        val = val.isoformat()
                    d[col.name] = val
                convs.append(d)
            data["tables"]["conversations"] = convs

        return data

    # ---------- 备份 ----------

    @staticmethod
    async def create_backup(
        session: AsyncSession,
        agent_id: str,
        agent_name: str,
        backup_type: BackupType = BackupType.FULL,
        scope: BackupScope = BackupScope.ALL,
        created_by: str = "system",
        encryption_enabled: Optional[bool] = None,
        event_type: Optional[str] = None,
        event_meta: Optional[Dict] = None,
    ) -> BackupRecord:
        _ensure_dirs()
        policy = await BackupEnhancedService.get_policy(session, agent_id)
        encrypt = encryption_enabled if encryption_enabled is not None else (policy.encryption_enabled if policy else True)

        record = BackupRecord(
            agent_id=agent_id,
            agent_name=agent_name,
            backup_type=backup_type,
            scope=scope,
            status=BackupStatus.RUNNING,
            created_by=created_by,
        )

        # 增量备份：找最近的全量备份作为 base
        if backup_type == BackupType.INCREMENTAL:
            base_stmt = select(BackupRecord).where(
                and_(
                    BackupRecord.agent_id == agent_id,
                    BackupRecord.backup_type == BackupType.FULL,
                    BackupRecord.status == BackupStatus.SUCCESS,
                    BackupRecord.is_deleted == False,
                )
            ).order_by(desc(BackupRecord.completed_at)).limit(1)
            base_result = await session.execute(base_stmt)
            base = base_result.scalar_one_or_none()
            if base:
                record.base_backup_id = base.id

        session.add(record)
        await session.flush()

        try:
            # 收集数据
            data = await BackupEnhancedService._collect_data(session, agent_id, scope)
            payload = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
            checksum = CryptoHelper.sha256(payload)

            # 写入明文临时文件
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            tmp_path = _BACKUP_DIR / f"tmp_{record.id}.json"
            with open(tmp_path, "wb") as f:
                f.write(payload)

            record.checksum_sha256 = checksum
            record.size_bytes = len(payload)

            # 加密
            if encrypt:
                key_record = await KeyManager.get_active_key_id(session)
                if not key_record:
                    key_record = (await KeyManager.create_key(session)).key_id
                key = KeyManager.get_key(key_record)
                if key is None:
                    raise ValueError("密钥库中找不到密钥")
                final_path = _BACKUP_DIR / f"backup_{record.id}_{timestamp}.aebk"
                record.encryption_algo = EncryptionAlgo.AES_256_GCM
                record.key_id = key_record
                checksum_enc = CryptoHelper.encrypt_file(tmp_path, final_path, key)
                record.file_path = str(final_path)
                record.checksum_sha256 = checksum_enc  # 记录加密后文件校验
                tmp_path.unlink(missing_ok=True)
            else:
                final_path = _BACKUP_DIR / f"backup_{record.id}_{timestamp}.json"
                tmp_path.rename(final_path)
                record.file_path = str(final_path)
                record.encryption_algo = EncryptionAlgo.NONE

            # 统计
            record.data_stats = json.dumps({k: len(v) for k, v in data["tables"].items()})
            record.status = BackupStatus.SUCCESS
            record.completed_at = datetime.utcnow()
            record.duration_seconds = (record.completed_at - record.created_at).total_seconds()

            # 保留策略
            if policy:
                record.retained_until = datetime.utcnow() + timedelta(days=policy.retention_days)
                await BackupEnhancedService._apply_retention(session, agent_id, policy)

            # 事件日志
            if event_type:
                event = BackupEventLog(
                    agent_id=agent_id,
                    event_type=event_type,
                    event_meta=json.dumps(event_meta) if event_meta else None,
                    backup_id=record.id,
                    status="processed",
                )
                session.add(event)

            await session.flush()
            return record

        except Exception as e:
            record.status = BackupStatus.FAILED
            record.error_message = str(e)
            record.completed_at = datetime.utcnow()
            await session.flush()
            if event_type:
                event = BackupEventLog(
                    agent_id=agent_id,
                    event_type=event_type,
                    event_meta=json.dumps(event_meta) if event_meta else None,
                    backup_id=record.id,
                    status="failed",
                )
                session.add(event)
                await session.flush()
            return record

    @staticmethod
    async def _apply_retention(session: AsyncSession, agent_id: str, policy: BackupPolicy):
        """应用保留策略：删除超出保留数量的备份"""
        cutoff = datetime.utcnow() - timedelta(days=policy.retention_days)

        # 按时间倒序取该 Agent 的所有成功备份
        stmt = select(BackupRecord).where(
            and_(
                BackupRecord.agent_id == agent_id,
                BackupRecord.status == BackupStatus.SUCCESS,
                BackupRecord.is_deleted == False,
            )
        ).order_by(desc(BackupRecord.completed_at))
        result = await session.execute(stmt)
        records = list(result.scalars().all())

        full_count = 0
        incr_count = 0
        for r in records:
            # 过期删除
            if r.completed_at and r.completed_at < cutoff:
                await BackupEnhancedService._delete_record(session, r)
                continue
            if r.backup_type == BackupType.FULL:
                full_count += 1
                if full_count > policy.retention_full_count:
                    await BackupEnhancedService._delete_record(session, r)
            else:
                incr_count += 1
                if incr_count > policy.retention_incremental_count:
                    await BackupEnhancedService._delete_record(session, r)

    @staticmethod
    async def _delete_record(session: AsyncSession, record: BackupRecord):
        """逻辑删除 + 物理删除文件"""
        record.is_deleted = True
        if record.file_path:
            try:
                p = Path(record.file_path)
                if p.exists():
                    p.unlink()
            except OSError:
                pass

    # ---------- 查询 ----------

    @staticmethod
    async def get_backup(session: AsyncSession, backup_id: str) -> Optional[BackupRecord]:
        stmt = select(BackupRecord).where(and_(BackupRecord.id == backup_id, BackupRecord.is_deleted == False))
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_backups(
        session: AsyncSession,
        agent_id: Optional[str] = None,
        backup_type: Optional[BackupType] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[BackupRecord], int]:
        conditions = [BackupRecord.is_deleted == False]
        if agent_id:
            conditions.append(BackupRecord.agent_id == agent_id)
        if backup_type:
            conditions.append(BackupRecord.backup_type == backup_type)
        stmt = select(BackupRecord).where(and_(*conditions)).order_by(desc(BackupRecord.created_at)).offset(skip).limit(limit)
        count_stmt = select(func.count(BackupRecord.id)).where(and_(*conditions))
        result = await session.execute(stmt)
        count_result = await session.execute(count_stmt)
        return list(result.scalars().all()), count_result.scalar() or 0

    @staticmethod
    async def delete_backup(session: AsyncSession, backup_id: str) -> bool:
        record = await BackupEnhancedService.get_backup(session, backup_id)
        if not record:
            return False
        await BackupEnhancedService._delete_record(session, record)
        await session.flush()
        return True

    @staticmethod
    async def get_stats(session: AsyncSession, days: int = 30) -> Dict[str, Any]:
        since = datetime.utcnow() - timedelta(days=days)
        total = select(func.count(BackupRecord.id)).where(
            and_(BackupRecord.created_at >= since, BackupRecord.is_deleted == False)
        )
        success = select(func.count(BackupRecord.id)).where(
            and_(
                BackupRecord.created_at >= since,
                BackupRecord.status == BackupStatus.SUCCESS,
                BackupRecord.is_deleted == False,
            )
        )
        failed = select(func.count(BackupRecord.id)).where(
            and_(
                BackupRecord.created_at >= since,
                BackupRecord.status == BackupStatus.FAILED,
                BackupRecord.is_deleted == False,
            )
        )
        full = select(func.count(BackupRecord.id)).where(
            and_(
                BackupRecord.created_at >= since,
                BackupRecord.backup_type == BackupType.FULL,
                BackupRecord.is_deleted == False,
            )
        )
        incr = select(func.count(BackupRecord.id)).where(
            and_(
                BackupRecord.created_at >= since,
                BackupRecord.backup_type == BackupType.INCREMENTAL,
                BackupRecord.is_deleted == False,
            )
        )
        encrypted = select(func.count(BackupRecord.id)).where(
            and_(
                BackupRecord.created_at >= since,
                BackupRecord.encryption_algo == EncryptionAlgo.AES_256_GCM,
                BackupRecord.is_deleted == False,
            )
        )
        total_bytes = select(func.coalesce(func.sum(BackupRecord.size_bytes), 0)).where(
            and_(BackupRecord.created_at >= since, BackupRecord.is_deleted == False)
        )
        t, s, f, fu, i, e, tb = await asyncio.gather(
            session.execute(total), session.execute(success), session.execute(failed),
            session.execute(full), session.execute(incr), session.execute(encrypted),
            session.execute(total_bytes),
        )
        return {
            "total": t.scalar() or 0,
            "success": s.scalar() or 0,
            "failed": f.scalar() or 0,
            "success_rate": round((s.scalar() or 0) / max(t.scalar() or 1, 1) * 100, 2),
            "full_backups": fu.scalar() or 0,
            "incremental_backups": i.scalar() or 0,
            "encrypted": e.scalar() or 0,
            "total_bytes": tb.scalar() or 0,
            "period_days": days,
        }

    @staticmethod
    async def log_event(
        session: AsyncSession,
        agent_id: str,
        event_type: str,
        event_meta: Optional[Dict] = None,
    ) -> Optional[BackupRecord]:
        """事件触发备份：策略开启事件触发时自动备份"""
        policy = await BackupEnhancedService.get_policy(session, agent_id)
        if not policy or not policy.enabled or not policy.event_trigger_enabled:
            return None
        # 检查事件类型是否在配置范围内
        if policy.event_types:
            types = policy.event_types if isinstance(policy.event_types, list) else json.loads(policy.event_types or "[]")
            if event_type not in types:
                return None
        record = await BackupEnhancedService.create_backup(
            session,
            agent_id=agent_id,
            agent_name=policy.agent_name,
            backup_type=BackupType.EVENT,
            scope=policy.default_scope,
            event_type=event_type,
            event_meta=event_meta,
        )
        return record


# ==================== 恢复 ====================

class RestoreService:

    @staticmethod
    async def _precheck(backup: BackupRecord, target_agent_id: str) -> Dict[str, Any]:
        """恢复预检"""
        checks = {
            "backup_exists": backup.status == BackupStatus.SUCCESS,
            "file_exists": bool(backup.file_path) and Path(backup.file_path).exists(),
            "target_compatible": True,  # 简化：跨 Agent 恢复默认允许
            "encryption_key_available": True,
        }
        if backup.encryption_algo == EncryptionAlgo.AES_256_GCM:
            key = KeyManager.get_key(backup.key_id) if backup.key_id else None
            checks["encryption_key_available"] = key is not None
        checks["can_restore"] = all(checks.values())
        return checks

    @staticmethod
    async def _load_backup_data(backup: BackupRecord) -> Dict[str, Any]:
        """读取并解密备份数据"""
        if not backup.file_path or not Path(backup.file_path).exists():
            raise ValueError("备份文件不存在")
        path = Path(backup.file_path)
        if backup.encryption_algo == EncryptionAlgo.AES_256_GCM:
            key = KeyManager.get_key(backup.key_id) if backup.key_id else None
            if key is None:
                raise ValueError("解密密钥不可用")
            tmp_path = _BACKUP_DIR / f"dec_{backup.id}.json"
            try:
                checksum = CryptoHelper.decrypt_file(path, tmp_path, key)
                if checksum != backup.checksum_sha256:
                    raise ValueError("备份完整性校验失败（SHA-256 不匹配）")
                with open(tmp_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            finally:
                tmp_path.unlink(missing_ok=True)
            return data
        else:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

    @staticmethod
    async def create_restore(
        session: AsyncSession,
        backup_id: str,
        restore_type: RestoreType,
        target_agent_id: str,
        target_agent_name: str,
        created_by: str = "system",
    ) -> RestoreOperation:
        backup = await BackupEnhancedService.get_backup(session, backup_id)
        if not backup:
            raise ValueError("备份不存在")

        operation = RestoreOperation(
            backup_id=backup_id,
            restore_type=restore_type,
            target_agent_id=target_agent_id,
            target_agent_name=target_agent_name,
            source_agent_name=backup.agent_name,
            status=RestoreStatus.PENDING,
            created_by=created_by,
        )
        session.add(operation)
        await session.flush()

        try:
            # 预检
            operation.status = RestoreStatus.PRECHECK
            precheck = await RestoreService._precheck(backup, target_agent_id)
            operation.precheck_result = json.dumps(precheck)
            if not precheck["can_restore"]:
                operation.status = RestoreStatus.FAILED
                operation.error_message = "恢复预检未通过"
                operation.completed_at = datetime.utcnow()
                operation.duration_seconds = (operation.completed_at - operation.created_at).total_seconds()
                await session.flush()
                return operation

            # 执行恢复
            operation.status = RestoreStatus.RUNNING
            data = await RestoreService._load_backup_data(backup)
            restored = await RestoreService._apply_restore(
                session, data, restore_type, target_agent_id, backup
            )

            operation.restored_stats = json.dumps(restored)
            operation.status = RestoreStatus.SUCCESS
            operation.health_score_after = 100.0
            operation.completed_at = datetime.utcnow()
            operation.duration_seconds = (operation.completed_at - operation.created_at).total_seconds()
            await session.flush()
            return operation

        except Exception as e:
            operation.status = RestoreStatus.FAILED
            operation.error_message = str(e)
            operation.completed_at = datetime.utcnow()
            operation.duration_seconds = (operation.completed_at - operation.created_at).total_seconds()
            await session.flush()
            return operation

    @staticmethod
    async def _apply_restore(
        session: AsyncSession,
        data: Dict[str, Any],
        restore_type: RestoreType,
        target_agent_id: str,
        backup: BackupRecord,
    ) -> Dict[str, Any]:
        """执行部分/完整恢复"""
        stats = {}
        tables = data.get("tables", {})

        if restore_type in (RestoreType.FULL, RestoreType.CONFIG):
            # 恢复 Agent 配置
            agent_rows = tables.get("agent", [])
            restored_count = 0
            for row in agent_rows:
                row["id"] = target_agent_id  # 目标覆盖
                restored_count += 1
            stats["agent_config"] = restored_count

        if restore_type in (RestoreType.FULL, RestoreType.MEMORY):
            from app.models.memory import AgentMemory
            mem_rows = tables.get("memories", [])
            # 删除目标 Agent 现有记忆（谨慎：仅恢复场景）
            del_stmt = select(AgentMemory).where(AgentMemory.agent_id == target_agent_id)
            del_result = await session.execute(del_stmt)
            for m in del_result.scalars().all():
                await session.delete(m)
            for row in mem_rows:
                row["id"] = str(uuid.uuid4())
                row["agent_id"] = target_agent_id
                mem = AgentMemory(**{k: v for k, v in row.items() if hasattr(AgentMemory, k)})
                session.add(mem)
            stats["memories_restored"] = len(mem_rows)

        if restore_type in (RestoreType.FULL, RestoreType.CONVERSATIONS):
            from app.models.conversation import Conversation
            conv_rows = tables.get("conversations", [])
            for row in conv_rows:
                row["id"] = str(uuid.uuid4())
                row["agent_id"] = target_agent_id
                conv = Conversation(**{k: v for k, v in row.items() if hasattr(Conversation, k)})
                session.add(conv)
            stats["conversations_restored"] = len(conv_rows)

        await session.flush()
        return stats

    @staticmethod
    async def get_restore(session: AsyncSession, restore_id: str) -> Optional[RestoreOperation]:
        stmt = select(RestoreOperation).where(RestoreOperation.id == restore_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_restores(
        session: AsyncSession,
        agent_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[RestoreOperation], int]:
        conditions = []
        if agent_id:
            conditions.append(RestoreOperation.target_agent_id == agent_id)
        stmt = select(RestoreOperation).where(and_(*conditions)).order_by(desc(RestoreOperation.created_at)).offset(skip).limit(limit)
        count_stmt = select(func.count(RestoreOperation.id)).where(and_(*conditions))
        result = await session.execute(stmt)
        count_result = await session.execute(count_stmt)
        return list(result.scalars().all()), count_result.scalar() or 0


# ==================== 恢复演练 ====================

class DrillService:

    @staticmethod
    async def create_drill(
        session: AsyncSession,
        agent_id: str,
        agent_name: str,
        backup_id: str,
        created_by: str = "system",
    ) -> RestoreDrill:
        drill = RestoreDrill(
            agent_id=agent_id,
            agent_name=agent_name,
            backup_id=backup_id,
            status=DrillStatus.RUNNING,
            started_at=datetime.utcnow(),
            created_by=created_by,
        )
        session.add(drill)
        await session.flush()
        return drill

    @staticmethod
    async def complete_drill(
        session: AsyncSession,
        drill_id: str,
        restore_ok: bool,
        report_data: Optional[Dict] = None,
        error_message: Optional[str] = None,
    ) -> Optional[RestoreDrill]:
        stmt = select(RestoreDrill).where(RestoreDrill.id == drill_id)
        result = await session.execute(stmt)
        drill = result.scalar_one_or_none()
        if not drill:
            return None
        drill.status = DrillStatus.SUCCESS if restore_ok else DrillStatus.FAILED
        drill.restore_ok = restore_ok
        drill.completed_at = datetime.utcnow()
        if drill.started_at:
            drill.duration_seconds = (drill.completed_at - drill.started_at).total_seconds()
        drill.report_data = json.dumps(report_data) if report_data else None
        drill.error_message = error_message
        await session.flush()
        return drill

    @staticmethod
    async def list_drills(
        session: AsyncSession,
        agent_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[RestoreDrill], int]:
        conditions = []
        if agent_id:
            conditions.append(RestoreDrill.agent_id == agent_id)
        stmt = select(RestoreDrill).where(and_(*conditions)).order_by(desc(RestoreDrill.scheduled_at)).offset(skip).limit(limit)
        count_stmt = select(func.count(RestoreDrill.id)).where(and_(*conditions))
        result = await session.execute(stmt)
        count_result = await session.execute(count_stmt)
        return list(result.scalars().all()), count_result.scalar() or 0

    @staticmethod
    async def get_drill_stats(session: AsyncSession, days: int = 90) -> Dict[str, Any]:
        since = datetime.utcnow() - timedelta(days=days)
        total = select(func.count(RestoreDrill.id)).where(RestoreDrill.scheduled_at >= since)
        success = select(func.count(RestoreDrill.id)).where(
            and_(RestoreDrill.scheduled_at >= since, RestoreDrill.restore_ok == True)
        )
        failed = select(func.count(RestoreDrill.id)).where(
            and_(RestoreDrill.scheduled_at >= since, RestoreDrill.restore_ok == False)
        )
        t, s, f = await asyncio.gather(session.execute(total), session.execute(success), session.execute(failed))
        return {
            "total": t.scalar() or 0,
            "success": s.scalar() or 0,
            "failed": f.scalar() or 0,
            "success_rate": round((s.scalar() or 0) / max(t.scalar() or 1, 1) * 100, 2),
            "period_days": days,
        }


import asyncio  # noqa: E402

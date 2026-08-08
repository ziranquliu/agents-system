"""
统一更新检测服务 - 检测可更新的组件版本
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scanner import ComponentScan

_DATA_DIR = Path(__file__).parent.parent / "data"


# 简单的版本比较（支持 "1.0.0" / "1.2.3-beta" 格式）
def _compare_versions(v1: str, v2: str) -> int:
    """比较两个版本号，返回 -1/0/1"""
    def parse_version(v: str) -> tuple:
        # 移除前缀如 "v" 或 "V"
        v = v.lstrip("vV")
        parts = v.split("-")[0].split(".")
        result = []
        for p in parts:
            try:
                result.append(int(p))
            except ValueError:
                result.append(0)
        while len(result) < 3:
            result.append(0)
        return tuple(result)
    
    v1_parts = parse_version(v1)
    v2_parts = parse_version(v2)
    
    if v1_parts < v2_parts:
        return -1
    elif v1_parts > v2_parts:
        return 1
    return 0


async def get_latest_version(component: str) -> Optional[str]:
    """获取组件最新可用版本"""
    version_file = _DATA_DIR / "versions" / f"{component}.json"
    if not version_file.exists():
        return None
    
    try:
        data = json.loads(version_file.read_text(encoding="utf-8"))
        return data.get("version")
    except Exception:
        return None


async def check_update(
    db: AsyncSession,
    component: str,
    current_version: str,
    created_by: str = "system",
) -> dict:
    """检查组件是否有可用更新"""
    latest_version = await get_latest_version(component)
    
    if latest_version is None:
        return {"has_update": False, "current": current_version, "latest": None}
    
    cmp = _compare_versions(current_version, latest_version)
    has_update = cmp < 0
    
    # 记录扫描结果
    scan = ComponentScan(
        id=str(uuid.uuid4()),
        component=component,
        current_version=current_version,
        latest_version=latest_version,
        has_update=has_update,
        checked_at=datetime.utcnow(),
        created_by=created_by,
    )
    db.add(scan)
    await db.commit()
    
    return {
        "has_update": has_update,
        "current": current_version,
        "latest": latest_version,
        "scan_id": scan.id,
    }


async def list_updates(
    db: AsyncSession,
    component: Optional[str] = None,
    limit: int = 50,
) -> list:
    """列出更新检测结果"""
    query = select(ComponentScan).order_by(ComponentScan.created_at.desc())
    
    if component:
        query = query.where(ComponentScan.component == component)
    
    query = query.limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def apply_update(
    db: AsyncSession,
    component: str,
    target_version: str,
    created_by: str = "manual",
) -> dict:
    """应用更新（标记为已应用）"""
    # 查找最新的扫描记录
    scan_result = await db.execute(
        select(ComponentScan)
        .where(ComponentScan.component == component)
        .order_by(ComponentScan.created_at.desc())
        .limit(1)
    )
    scan = scan_result.scalar_one_or_none()
    
    if not scan:
        return {"success": False, "error": "未找到扫描记录"}
    
    if scan.latest_version != target_version:
        return {"success": False, "error": "目标版本不匹配"}
    
    # 创建快照
    from app.models.update_enhanced import UpdateSnapshot, UpdateLog
    snapshot = UpdateSnapshot(
        id=str(uuid.uuid4()),
        component=component,
        version=target_version,
        state="applying",
        created_by=created_by,
    )
    db.add(snapshot)
    await db.flush()
    
    # 记录更新日志
    log = UpdateLog(
        id=str(uuid.uuid4()),
        snapshot_id=snapshot.id,
        component_id=component,
        component_name=str(component),
        action="update",
        old_version=scan.current_version,
        new_version=target_version,
        compatibility="pass",
        status="success",
        created_by=created_by,
    )
    db.add(log)
    
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return {
        "success": True,
        "snapshot_id": snapshot.id,
        "component": component,
        "target_version": target_version,
    }


async def rollback_component(
    db: AsyncSession,
    snapshot_id: str,
    created_by: str = "manual",
) -> dict:
    """回滚组件到快照状态（保留前一版本快照）"""
    from app.models.update_enhanced import UpdateSnapshot, UpdateLog
    snapshot = await db.get(UpdateSnapshot, snapshot_id)
    if not snapshot:
        return {"success": False, "error": "快照不存在"}
    
    if snapshot.state == "rolled_back":
        return {"success": False, "error": "该快照已回滚过"}
    
    # 创建新快照（当前状态）
    new_snapshot = UpdateSnapshot(
        id=str(uuid.uuid4()),
        component=snapshot.component,
        version=snapshot.version,
        state="before_rollback",
        config_snapshot=snapshot.config_snapshot,
        created_by=created_by,
    )
    db.add(new_snapshot)
    
    # 更新原快照状态
    snapshot.state = "rolled_back"
    snapshot.rolled_back_at = datetime.utcnow()
    
    # 记录日志
    log = UpdateLog(
        id=str(uuid.uuid4()),
        snapshot_id=new_snapshot.id,
        component_id=snapshot.component,
        component_name=snapshot.component,
        action="rollback",
        old_version=snapshot.version,
        new_version=snapshot.version,
        compatibility="pass",
        status="success",
        created_by=created_by,
    )
    db.add(log)
    
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return {
        "success": True,
        "new_snapshot_id": new_snapshot.id,
        "rolled_back_snapshot_id": snapshot_id,
    }


async def get_snapshot(db: AsyncSession, snapshot_id: str) -> Optional[dict]:
    """获取快照详情"""
    from app.models.update_enhanced import UpdateSnapshot
    snapshot = await db.get(UpdateSnapshot, snapshot_id)
    if not snapshot:
        return None
    return {
        "id": snapshot.id,
        "component": snapshot.component,
        "version": snapshot.version,
        "state": snapshot.state,
        "config_snapshot": snapshot.config_snapshot,
        "created_at": snapshot.created_at,
        "rolled_back_at": snapshot.rolled_back_at,
    }


async def list_snapshots(
    db: AsyncSession,
    component: Optional[str] = None,
    limit: int = 50,
) -> list:
    """列出快照历史"""
    from app.models.update_enhanced import UpdateSnapshot
    query = select(UpdateSnapshot).order_by(UpdateSnapshot.created_at.desc())
    
    if component:
        query = query.where(UpdateSnapshot.component == component)
    
    query = query.limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

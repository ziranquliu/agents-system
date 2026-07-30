"""
备份与恢复服务 - 数据库导出/配置备份
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_BACKUP_DIR = Path(__file__).parent.parent / "backups"


def ensure_backup_dir():
    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)


async def create_backup(db: AsyncSession, created_by: str = "system", notes: Optional[str] = None) -> dict:
    """创建完整备份"""
    ensure_backup_dir()
    backup_id = str(uuid.uuid4())[:8]
    timestamp = datetime.utcnow()
    data = {
        "backup_id": backup_id,
        "created_at": timestamp.isoformat(),
        "created_by": created_by,
        "notes": notes or "",
        "version": "1.0",
        "data": {},
    }

    # 导出各表数据
    from app.models.agent import Agent, ModelConfigTemplate
    from app.models.conversation import Conversation
    from app.models.skill import Skill, MCPServer
    from app.models.workspace import Workspace
    from app.models.task import Task
    from app.models.knowledge import KnowledgeBase, KnowledgeDocument

    tables = {
        "agents": Agent,
        "model_configs": ModelConfigTemplate,
        "conversations": Conversation,
        "skills": Skill,
        "mcp_servers": MCPServer,
        "workspaces": Workspace,
        "tasks": Task,
        "knowledge_bases": KnowledgeBase,
    }

    for name, model in tables.items():
        result = await db.execute(select(model))
        records = result.scalars().all()
        serialized = []
        for r in records:
            d = {}
            for col in model.__table__.columns:
                val = getattr(r, col.name)
                if isinstance(val, datetime):
                    val = val.isoformat()
                d[col.name] = val
            serialized.append(d)
        data["data"][name] = serialized

    # 同时备份市场 JSON 文件
    market_files = ["skill_market.json", "mcp_market.json", "agent_market.json", "model_market.json"]
    market_data_dir = Path(__file__).parent.parent / "data"
    data["market_data"] = {}
    for fname in market_files:
        fpath = market_data_dir / fname
        if fpath.exists():
            with open(fpath, "r", encoding="utf-8") as f:
                data["market_data"][fname] = json.load(f)

    # 写入文件
    filename = f"backup_{backup_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
    filepath = _BACKUP_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return {
        "backup_id": backup_id,
        "filename": filename,
        "filepath": str(filepath),
        "size_bytes": filepath.stat().st_size,
        "tables": {k: len(v) for k, v in data["data"].items()},
        "created_at": timestamp.isoformat(),
    }


async def list_backups() -> list[dict]:
    """列出所有备份"""
    ensure_backup_dir()
    backups = []
    for fpath in sorted(_BACKUP_DIR.glob("backup_*.json"), reverse=True):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                meta = json.load(f)
                backups.append({
                    "backup_id": meta.get("backup_id", "unknown"),
                    "filename": fpath.name,
                    "size_bytes": fpath.stat().st_size,
                    "created_at": meta.get("created_at", ""),
                    "created_by": meta.get("created_by", ""),
                    "notes": meta.get("notes", ""),
                    "tables": {k: len(v) for k, v in meta.get("data", {}).items()},
                    "version": meta.get("version", ""),
                })
        except (json.JSONDecodeError, KeyError):
            backups.append({
                "backup_id": "corrupted",
                "filename": fpath.name,
                "size_bytes": fpath.stat().st_size,
                "created_at": "",
                "error": "无法读取备份文件",
            })
    return backups


async def delete_backup(backup_id: str) -> bool:
    """删除备份"""
    ensure_backup_dir()
    for fpath in _BACKUP_DIR.glob(f"backup_{backup_id}_*.json"):
        fpath.unlink()
        return True
    return False

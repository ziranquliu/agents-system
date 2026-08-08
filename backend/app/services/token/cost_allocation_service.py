"""
Token 成本分摊服务 — 按项目 / 部门 / 标签维度聚合成本

功能:
1. 按项目(project_id)聚合成本
2. 按部门(department)聚合成本
3. 按标签(tags)聚合成本
4. 成本趋势分析
5. 成本占比分析
"""
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.token import TokenUsage

logger = logging.getLogger(__name__)


def _safe_json(s, default=None):
    if not s:
        return default
    try:
        return json.loads(s) if isinstance(s, str) else s
    except (json.JSONDecodeError, TypeError):
        return default


class CostAllocationService:
    """Token 成本分摊服务"""

    @staticmethod
    async def record_usage_with_allocation(
        db: AsyncSession,
        user_id: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        project_id: Optional[str] = None,
        department: Optional[str] = None,
        tags: Optional[dict] = None,
        agent_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> dict:
        """记录用量并附加成本分摊标签"""
        from app.services.token_service import TokenService

        cost = TokenService.calc_cost(model_name, input_tokens, output_tokens)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        usage = TokenUsage(
            user_id=user_id,
            agent_id=agent_id,
            conversation_id=conversation_id,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            usage_date=today,
            project_id=project_id,
            department=department,
            tags=json.dumps(tags, ensure_ascii=False) if tags else None,
        )
        db.add(usage)
        await db.flush()

        return {
            "id": usage.id,
            "cost": cost,
            "project_id": project_id,
            "department": department,
        }

    @staticmethod
    async def get_cost_by_project(
        db: AsyncSession,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """按项目聚合成本"""
        filters = [TokenUsage.project_id.isnot(None)]
        if start_date:
            filters.append(TokenUsage.usage_date >= start_date)
        if end_date:
            filters.append(TokenUsage.usage_date <= end_date)

        result = await db.execute(
            select(
                TokenUsage.project_id,
                func.sum(TokenUsage.cost).label("total_cost"),
                func.sum(TokenUsage.input_tokens).label("total_input"),
                func.sum(TokenUsage.output_tokens).label("total_output"),
                func.count(TokenUsage.id).label("request_count"),
            )
            .where(and_(*filters))
            .group_by(TokenUsage.project_id)
            .order_by(func.sum(TokenUsage.cost).desc())
        )

        items = []
        for row in result.all():
            items.append({
                "project_id": row.project_id,
                "total_cost": round(float(row.total_cost or 0), 4),
                "total_input_tokens": int(row.total_input or 0),
                "total_output_tokens": int(row.total_output or 0),
                "request_count": row.request_count,
            })

        return items

    @staticmethod
    async def get_cost_by_department(
        db: AsyncSession,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """按部门聚合成本"""
        filters = [TokenUsage.department.isnot(None)]
        if start_date:
            filters.append(TokenUsage.usage_date >= start_date)
        if end_date:
            filters.append(TokenUsage.usage_date <= end_date)

        result = await db.execute(
            select(
                TokenUsage.department,
                func.sum(TokenUsage.cost).label("total_cost"),
                func.sum(TokenUsage.input_tokens).label("total_input"),
                func.sum(TokenUsage.output_tokens).label("total_output"),
                func.count(TokenUsage.id).label("request_count"),
            )
            .where(and_(*filters))
            .group_by(TokenUsage.department)
            .order_by(func.sum(TokenUsage.cost).desc())
        )

        items = []
        for row in result.all():
            items.append({
                "department": row.department,
                "total_cost": round(float(row.total_cost or 0), 4),
                "total_input_tokens": int(row.total_input or 0),
                "total_output_tokens": int(row.total_output or 0),
                "request_count": row.request_count,
            })

        return items

    @staticmethod
    async def get_cost_by_model(
        db: AsyncSession,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """按模型聚合成本（按项目分组）"""
        filters = []
        if start_date:
            filters.append(TokenUsage.usage_date >= start_date)
        if end_date:
            filters.append(TokenUsage.usage_date <= end_date)

        result = await db.execute(
            select(
                TokenUsage.model_name,
                TokenUsage.project_id,
                func.sum(TokenUsage.cost).label("total_cost"),
                func.sum(TokenUsage.input_tokens).label("total_input"),
                func.sum(TokenUsage.output_tokens).label("total_output"),
                func.count(TokenUsage.id).label("request_count"),
            )
            .where(and_(*filters) if filters else True)
            .group_by(TokenUsage.model_name, TokenUsage.project_id)
            .order_by(func.sum(TokenUsage.cost).desc())
        )

        items = []
        for row in result.all():
            items.append({
                "model_name": row.model_name,
                "project_id": row.project_id or "(未分配)",
                "total_cost": round(float(row.total_cost or 0), 4),
                "total_input_tokens": int(row.total_input or 0),
                "total_output_tokens": int(row.total_output or 0),
                "request_count": row.request_count,
            })

        return items

    @staticmethod
    async def get_daily_cost_trend(
        db: AsyncSession,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        project_id: Optional[str] = None,
        department: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """获取每日成本趋势（支持项目/部门筛选）"""
        filters = []
        if start_date:
            filters.append(TokenUsage.usage_date >= start_date)
        if end_date:
            filters.append(TokenUsage.usage_date <= end_date)
        if project_id:
            filters.append(TokenUsage.project_id == project_id)
        if department:
            filters.append(TokenUsage.department == department)

        where = and_(*filters) if filters else True

        result = await db.execute(
            select(
                TokenUsage.usage_date,
                func.sum(TokenUsage.cost).label("total_cost"),
                func.sum(TokenUsage.input_tokens).label("total_input"),
                func.sum(TokenUsage.output_tokens).label("total_output"),
                func.count(TokenUsage.id).label("request_count"),
            )
            .where(where)
            .group_by(TokenUsage.usage_date)
            .order_by(TokenUsage.usage_date)
        )

        return [
            {
                "date": row.usage_date,
                "cost": round(float(row.total_cost or 0), 4),
                "input_tokens": int(row.total_input or 0),
                "output_tokens": int(row.total_output or 0),
                "request_count": row.request_count,
            }
            for row in result.all()
        ]

    @staticmethod
    async def get_cost_summary(
        db: AsyncSession,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取成本分摊综合报告"""
        by_project = await CostAllocationService.get_cost_by_project(db, start_date, end_date)
        by_dept = await CostAllocationService.get_cost_by_department(db, start_date, end_date)
        by_model = await CostAllocationService.get_cost_by_model(db, start_date, end_date)

        # 总成本
        total_cost = sum(p["total_cost"] for p in by_project)
        total_requests = sum(p["request_count"] for p in by_project)

        # 未分配成本
        filters = [TokenUsage.project_id.is_(None)]
        if start_date:
            filters.append(TokenUsage.usage_date >= start_date)
        if end_date:
            filters.append(TokenUsage.usage_date <= end_date)

        unallocated_result = await db.execute(
            select(func.sum(TokenUsage.cost)).where(and_(*filters))
        )
        unallocated_cost = round(float(unallocated_result.scalar() or 0), 4)

        return {
            "total_cost": round(total_cost + unallocated_cost, 4),
            "total_requests": total_requests,
            "unallocated_cost": unallocated_cost,
            "by_project": by_project,
            "by_department": by_dept,
            "by_model": by_model,
        }

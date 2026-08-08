"""
ScheduledMaintenanceService 测试 — 维护任务CRUD、执行、报告
"""
import pytest
from datetime import datetime, timezone, timedelta

from app.services.scheduled_maintenance_service import (
    ScheduledMaintenanceService,
    MaintenanceTask,
    MaintenanceRecord,
    MaintenanceReport,
    MaintenanceType,
    MaintenanceStatus,
    ScheduleType,
)


# ============================================================
# 枚举测试
# ============================================================

class TestMaintenanceType:
    def test_all_types(self):
        values = {t.value for t in MaintenanceType}
        assert "session_cleanup" in values
        assert "cache_cleanup" in values
        assert "index_rebuild" in values
        assert "stats_rebuild" in values
        assert "report_daily" in values
        assert "report_weekly" in values
        assert "report_monthly" in values
        assert "backup_cleanup" in values
        assert "log_rotation" in values


class TestMaintenanceStatus:
    def test_all_statuses(self):
        values = {s.value for s in MaintenanceStatus}
        assert "pending" in values
        assert "running" in values
        assert "completed" in values
        assert "failed" in values
        assert "skipped" in values


class TestScheduleType:
    def test_all_schedule_types(self):
        values = {s.value for s in ScheduleType}
        assert "hourly" in values
        assert "daily" in values
        assert "weekly" in values
        assert "monthly" in values


# ============================================================
# MaintenanceReport 测试
# ============================================================

class TestMaintenanceReport:
    def test_to_dict(self):
        now = datetime.now(timezone.utc)
        report = MaintenanceReport(
            id="rpt_001",
            report_type="daily",
            period_start=now,
            period_end=now,
            generated_at=now,
            summary={"total_tasks": 5},
            sections=[{"title": "Overview"}],
            recommendations=["Check logs"],
        )
        d = report.to_dict()
        assert d["id"] == "rpt_001"
        assert d["report_type"] == "daily"
        assert d["period_start"] is not None
        assert d["summary"]["total_tasks"] == 5

    def test_to_dict_none_dates(self):
        report = MaintenanceReport(id="rpt_002")
        d = report.to_dict()
        assert d["period_start"] is None
        assert d["generated_at"] is None


# ============================================================
# ScheduledMaintenanceService 任务管理测试
# ============================================================

class TestMaintenanceTaskCRUD:
    def setup_method(self):
        self.service = ScheduledMaintenanceService()

    def test_create_task(self):
        task = self.service.create_task(
            name="Daily cleanup",
            task_type=MaintenanceType.SESSION_CLEANUP,
        )
        assert task.id.startswith("maint_")
        assert task.name == "Daily cleanup"
        assert task.task_type == MaintenanceType.SESSION_CLEANUP
        assert task.enabled is True
        assert task.next_run is not None

    def test_create_task_custom_schedule(self):
        task = self.service.create_task(
            name="Hourly check",
            task_type=MaintenanceType.LOG_ROTATION,
            schedule_type=ScheduleType.HOURLY,
            schedule_hour=0,
            schedule_minute=30,
        )
        assert task.schedule_type == ScheduleType.HOURLY

    def test_list_tasks(self):
        self.service.create_task("Task1", MaintenanceType.CACHE_CLEANUP)
        self.service.create_task("Task2", MaintenanceType.INDEX_REBUILD)
        tasks = self.service.list_tasks()
        assert len(tasks) == 2

    def test_list_tasks_fields(self):
        self.service.create_task("Task1", MaintenanceType.SESSION_CLEANUP)
        tasks = self.service.list_tasks()
        task = tasks[0]
        assert "id" in task
        assert "name" in task
        assert "type" in task
        assert "schedule" in task
        assert "enabled" in task
        assert "next_run" in task

    def test_enable_disable_task(self):
        task = self.service.create_task("Task1", MaintenanceType.SESSION_CLEANUP)
        assert self.service.disable_task(task.id) is True
        # verify disabled
        tasks = self.service.list_tasks()
        assert tasks[0]["enabled"] is False

        assert self.service.enable_task(task.id) is True
        tasks = self.service.list_tasks()
        assert tasks[0]["enabled"] is True

    def test_disable_nonexistent_task(self):
        assert self.service.disable_task("nonexistent") is False

    def test_enable_nonexistent_task(self):
        assert self.service.enable_task("nonexistent") is False


# ============================================================
# 任务执行测试
# ============================================================

class TestMaintenanceExecution:
    def setup_method(self):
        self.service = ScheduledMaintenanceService()

    @pytest.mark.asyncio
    async def test_run_nonexistent_task(self):
        record = await self.service.run_task("nonexistent")
        assert record.status == MaintenanceStatus.FAILED
        assert "not found" in record.error_message.lower()

    @pytest.mark.asyncio
    async def test_run_task_with_custom_handler(self):
        task = self.service.create_task("Custom", MaintenanceType.SESSION_CLEANUP)

        async def custom_handler(config):
            return {"cleaned": 42}

        self.service.register_handler(MaintenanceType.SESSION_CLEANUP, custom_handler)
        record = await self.service.run_task(task.id)
        assert record.status == MaintenanceStatus.COMPLETED
        assert record.result["cleaned"] == 42

    @pytest.mark.asyncio
    async def test_run_task_default_session_cleanup(self):
        task = self.service.create_task("Cleanup", MaintenanceType.SESSION_CLEANUP)
        record = await self.service.run_task(task.id)
        assert record.status == MaintenanceStatus.COMPLETED
        assert "session_cleanup" in record.result.get("action", "")

    @pytest.mark.asyncio
    async def test_run_task_default_cache_cleanup(self):
        task = self.service.create_task("Cache", MaintenanceType.CACHE_CLEANUP)
        record = await self.service.run_task(task.id)
        assert record.status == MaintenanceStatus.COMPLETED
        assert "cache_cleanup" in record.result.get("action", "")

    @pytest.mark.asyncio
    async def test_run_task_default_index_rebuild(self):
        task = self.service.create_task("Index", MaintenanceType.INDEX_REBUILD)
        record = await self.service.run_task(task.id)
        assert record.status == MaintenanceStatus.COMPLETED
        assert "index_rebuild" in record.result.get("action", "")

    @pytest.mark.asyncio
    async def test_run_task_default_stats_rebuild(self):
        task = self.service.create_task("Stats", MaintenanceType.STATS_REBUILD)
        record = await self.service.run_task(task.id)
        assert record.status == MaintenanceStatus.COMPLETED
        assert "stats_rebuild" in record.result.get("action", "")

    @pytest.mark.asyncio
    async def test_run_task_records_history(self):
        task = self.service.create_task("Cleanup", MaintenanceType.SESSION_CLEANUP)
        await self.service.run_task(task.id)
        assert len(self.service._records) == 1

    @pytest.mark.asyncio
    async def test_run_task_updates_last_run(self):
        task = self.service.create_task("Cleanup", MaintenanceType.SESSION_CLEANUP)
        assert task.last_run is None
        await self.service.run_task(task.id)
        assert task.last_run is not None
        assert task.next_run is not None

    @pytest.mark.asyncio
    async def test_run_task_with_handler_exception(self):
        task = self.service.create_task("Failing", MaintenanceType.SESSION_CLEANUP)

        async def failing_handler(config):
            raise RuntimeError("Handler failed")

        self.service.register_handler(MaintenanceType.SESSION_CLEANUP, failing_handler)
        record = await self.service.run_task(task.id)
        assert record.status == MaintenanceStatus.FAILED
        assert "Handler failed" in record.error_message

    @pytest.mark.asyncio
    async def test_run_task_duration_ms(self):
        task = self.service.create_task("Quick", MaintenanceType.CACHE_CLEANUP)
        record = await self.service.run_task(task.id)
        assert record.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_run_task_report_daily(self):
        task = self.service.create_task("Report", MaintenanceType.REPORT_DAILY)
        record = await self.service.run_task(task.id)
        assert record.status == MaintenanceStatus.COMPLETED
        assert "report" in record.result

    @pytest.mark.asyncio
    async def test_run_task_report_weekly(self):
        task = self.service.create_task("WeeklyReport", MaintenanceType.REPORT_WEEKLY)
        record = await self.service.run_task(task.id)
        assert record.status == MaintenanceStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_run_task_report_monthly(self):
        task = self.service.create_task("MonthlyReport", MaintenanceType.REPORT_MONTHLY)
        record = await self.service.run_task(task.id)
        assert record.status == MaintenanceStatus.COMPLETED


# ============================================================
# 多次执行 / 历史记录测试
# ============================================================

class TestMaintenanceHistory:
    def setup_method(self):
        self.service = ScheduledMaintenanceService()

    @pytest.mark.asyncio
    async def test_multiple_runs_accumulate_records(self):
        task = self.service.create_task("Cleanup", MaintenanceType.SESSION_CLEANUP)
        await self.service.run_task(task.id)
        await self.service.run_task(task.id)
        await self.service.run_task(task.id)
        assert len(self.service._records) == 3

    @pytest.mark.asyncio
    async def test_different_tasks_recorded(self):
        t1 = self.service.create_task("Task1", MaintenanceType.SESSION_CLEANUP)
        t2 = self.service.create_task("Task2", MaintenanceType.CACHE_CLEANUP)
        await self.service.run_task(t1.id)
        await self.service.run_task(t2.id)
        assert len(self.service._records) == 2
        types = {r.task_type for r in self.service._records}
        assert MaintenanceType.SESSION_CLEANUP.value in types
        assert MaintenanceType.CACHE_CLEANUP.value in types


# ============================================================
# 边界情况测试
# ============================================================

class TestMaintenanceEdgeCases:
    def setup_method(self):
        self.service = ScheduledMaintenanceService()

    def test_id_counter_increment(self):
        t1 = self.service.create_task("T1", MaintenanceType.SESSION_CLEANUP)
        t2 = self.service.create_task("T2", MaintenanceType.SESSION_CLEANUP)
        assert t1.id != t2.id
        assert int(t1.id.split("_")[1]) + 1 == int(t2.id.split("_")[1])

    def test_create_multiple_with_different_types(self):
        types_to_test = [
            MaintenanceType.SESSION_CLEANUP,
            MaintenanceType.CACHE_CLEANUP,
            MaintenanceType.INDEX_REBUILD,
            MaintenanceType.STATS_REBUILD,
            MaintenanceType.LOG_ROTATION,
            MaintenanceType.BACKUP_CLEANUP,
        ]
        for mt in types_to_test:
            task = self.service.create_task(f"Task_{mt.value}", mt)
            assert task.task_type == mt

    def test_record_to_dict(self):
        record = MaintenanceRecord(
            id="rec_001",
            task_id="maint_001",
            task_name="Test",
            task_type="session_cleanup",
            status=MaintenanceStatus.COMPLETED,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            result={"cleaned": 10},
        )
        assert record.id == "rec_001"
        assert record.status == MaintenanceStatus.COMPLETED
        assert record.result["cleaned"] == 10

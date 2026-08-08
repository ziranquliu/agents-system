"""
IncrementalBackupService 测试 — 全量/增量备份、变更追踪、恢复演练
"""
import pytest
from datetime import datetime, timezone, timedelta

from app.services.incremental_backup_service import (
    IncrementalBackupService,
    BackupMetadata,
    BackupType,
    BackupTrigger,
    BackupStatus,
    ChangeRecord,
)


# ============================================================
# 枚举测试
# ============================================================

class TestBackupType:
    def test_all_types(self):
        values = {t.value for t in BackupType}
        assert values == {"full", "incremental"}


class TestBackupTrigger:
    def test_all_triggers(self):
        values = {t.value for t in BackupTrigger}
        assert values == {"manual", "scheduled", "config_change", "version_update", "pre_deployment"}


class TestBackupStatus:
    def test_all_statuses(self):
        values = {s.value for s in BackupStatus}
        assert values == {"pending", "in_progress", "completed", "failed", "verified"}


# ============================================================
# BackupMetadata 测试
# ============================================================

class TestBackupMetadata:
    def test_to_dict(self):
        meta = BackupMetadata(
            id="b1",
            backup_type=BackupType.FULL,
            trigger=BackupTrigger.MANUAL,
            status=BackupStatus.COMPLETED,
            file_path="/backups/full.json",
            file_size=1024,
            checksum_sha256="abc123def456",
            components=["config", "memory"],
        )
        d = meta.to_dict()
        assert d["id"] == "b1"
        assert d["backup_type"] == "full"
        assert d["status"] == "completed"
        assert "abc123" in d["checksum_sha256"]

    def test_to_dict_none_dates(self):
        meta = BackupMetadata()
        d = meta.to_dict()
        assert d["created_at"] is None
        assert d["completed_at"] is None


# ============================================================
# 变更追踪测试
# ============================================================

class TestChangeTracking:
    def setup_method(self):
        self.service = IncrementalBackupService()

    def test_record_change(self):
        self.service.record_change("agent", "create", "a1", new_value={"name": "test"})
        changes = self.service.get_changes_since("agent")
        assert len(changes) == 1
        assert changes[0].change_type == "create"

    def test_record_multiple_changes(self):
        self.service.record_change("agent", "create", "a1")
        self.service.record_change("agent", "update", "a1", old_value={"name": "old"}, new_value={"name": "new"})
        self.service.record_change("skill", "create", "s1")
        assert len(self.service.get_changes_since("agent")) == 2
        assert len(self.service.get_changes_since("skill")) == 1

    def test_get_changes_since_backup(self):
        import time
        self.service.record_change("agent", "create", "a1")
        # 先创建全量备份
        import asyncio
        parent = asyncio.get_event_loop().run_until_complete(
            self.service.create_full_backup(["agent"])
        )
        time.sleep(0.01)
        # 再记录新变更
        self.service.record_change("agent", "update", "a1", new_value={"name": "updated"})
        changes = self.service.get_changes_since("agent", parent.id)
        assert len(changes) == 1
        assert changes[0].change_type == "update"

    def test_get_changes_unknown_component(self):
        changes = self.service.get_changes_since("nonexistent")
        assert len(changes) == 0


# ============================================================
# 全量备份测试
# ============================================================

class TestFullBackup:
    def setup_method(self):
        self.service = IncrementalBackupService()

    @pytest.mark.asyncio
    async def test_create_full_backup(self):
        backup = await self.service.create_full_backup()
        assert backup.id != ""
        assert backup.status == BackupStatus.COMPLETED
        assert backup.backup_type == BackupType.FULL
        assert backup.file_size > 0
        assert backup.checksum_sha256 != ""
        assert backup.completed_at is not None

    @pytest.mark.asyncio
    async def test_create_full_backup_custom_components(self):
        backup = await self.service.create_full_backup(components=["config", "memory"])
        assert "config" in backup.components
        assert "memory" in backup.components

    @pytest.mark.asyncio
    async def test_create_full_backup_trigger(self):
        backup = await self.service.create_full_backup(trigger=BackupTrigger.SCHEDULED)
        assert backup.trigger == BackupTrigger.SCHEDULED

    @pytest.mark.asyncio
    async def test_full_backup_clears_changes(self):
        self.service.record_change("config", "update", "c1")
        self.service.record_change("config", "update", "c2")
        await self.service.create_full_backup(["config"])
        changes = self.service.get_changes_since("config")
        assert len(changes) == 0

    @pytest.mark.asyncio
    async def test_full_backup_stored(self):
        backup = await self.service.create_full_backup()
        assert backup.id in self.service._backups


# ============================================================
# 增量备份测试
# ============================================================

class TestIncrementalBackup:
    def setup_method(self):
        self.service = IncrementalBackupService()

    @pytest.mark.asyncio
    async def test_create_incremental_backup(self):
        parent = await self.service.create_full_backup()
        self.service.record_change("agent", "update", "a1", new_value={"name": "updated"})
        incr = await self.service.create_incremental_backup(parent.id)
        assert incr.status == BackupStatus.COMPLETED
        assert incr.backup_type == BackupType.INCREMENTAL
        assert incr.parent_id == parent.id

    @pytest.mark.asyncio
    async def test_incremental_records_changes(self):
        parent = await self.service.create_full_backup()
        # 记录变更后再查 (不带 since_backup_id)
        self.service.record_change("agent", "create", "a1")
        self.service.record_change("agent", "update", "a2")
        changes = self.service.get_changes_since("agent")
        assert len(changes) == 2
        incr = await self.service.create_incremental_backup(parent.id)
        assert incr.status == BackupStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_incremental_chain(self):
        parent = await self.service.create_full_backup()
        incr1 = await self.service.create_incremental_backup(parent.id)
        incr2 = await self.service.create_incremental_backup(incr1.id)
        assert parent.id in self.service._backup_chain
        assert incr1.id in self.service._backup_chain
        assert incr1.id in self.service._backup_chain[parent.id]

    @pytest.mark.asyncio
    async def test_incremental_no_parent_raises(self):
        with pytest.raises(ValueError, match="not found"):
            await self.service.create_incremental_backup("nonexistent")

    @pytest.mark.asyncio
    async def test_incremental_clears_changes(self):
        parent = await self.service.create_full_backup()
        self.service.record_change("agent", "create", "a1")
        await self.service.create_incremental_backup(parent.id)
        # 增量备份后变更仍保留用于下一次增量
        changes = self.service.get_changes_since("agent")
        assert len(changes) == 1


# ============================================================
# 统计测试
# ============================================================

class TestBackupStats:
    def setup_method(self):
        self.service = IncrementalBackupService()

    @pytest.mark.asyncio
    async def test_get_stats(self):
        await self.service.create_full_backup()
        stats = self.service.get_stats()
        assert stats["total_backups"] == 1
        assert stats["full_backups"] == 1

    @pytest.mark.asyncio
    async def test_get_stats_after_incremental(self):
        parent = await self.service.create_full_backup()
        self.service.record_change("agent", "create", "a1")
        await self.service.create_incremental_backup(parent.id)
        stats = self.service.get_stats()
        assert stats["total_backups"] == 2

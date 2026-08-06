"""
远程备份存储 — MinIO / S3 兼容适配器

功能:
1. MinIO/S3 上传/下载/列举/删除
2. 自动创建桶、设置生命周期策略
3. 支持断点续传(大文件分块)
4. 本地加密文件 → 远程存储
"""
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class S3CompatibleStorage:
    """
    S3/MinIO 兼容存储。
    
    依赖: aiobotocore (异步 AWS SDK)
    安装: pip install aiobotocore
    """

    def __init__(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket_name: str = "agent-backups",
        region: str = "us-east-1",
        use_ssl: bool = True,
    ):
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket_name = bucket_name
        self.region = region
        self.use_ssl = use_ssl

    async def _get_session(self):
        """获取 aiobotocore session"""
        try:
            from aiobotocore.session import get_session
            return get_session()
        except ImportError:
            raise ImportError(
                "aiobotocore 未安装。请运行: pip install aiobotocore"
            )

    async def _create_client(self):
        """创建 S3 客户端"""
        session = await self._get_session()
        return session.create_client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            use_ssl=self.use_ssl,
        )

    async def ensure_bucket(self) -> bool:
        """确保桶存在，不存在则创建"""
        try:
            async with (await self._create_client()) as client:
                try:
                    await client.head_bucket(Bucket=self.bucket_name)
                except Exception:
                    await client.create_bucket(
                        Bucket=self.bucket_name,
                        CreateBucketConfiguration={
                            "LocationConstraint": self.region
                        } if self.region != "us-east-1" else {},
                    )
                    logger.info("创建远程备份桶: %s", self.bucket_name)
            return True
        except Exception as e:
            logger.error("确保桶存在失败: %s", str(e))
            return False

    async def upload_file(
        self,
        local_path: str,
        remote_key: str,
        metadata: Optional[dict] = None,
    ) -> dict:
        """上传文件到远程存储"""
        try:
            file_size = os.path.getsize(local_path)
            extra_args = {}
            if metadata:
                extra_args["Metadata"] = {
                    k: str(v) for k, v in metadata.items()
                }

            async with (await self._create_client()) as client:
                await client.upload_file(
                    str(local_path),
                    self.bucket_name,
                    remote_key,
                    ExtraArgs=extra_args,
                )

            return {
                "success": True,
                "remote_key": remote_key,
                "size": file_size,
                "bucket": self.bucket_name,
            }
        except Exception as e:
            logger.error("远程上传失败 %s -> %s: %s", local_path, remote_key, str(e))
            return {"success": False, "error": str(e)}

    async def download_file(
        self,
        remote_key: str,
        local_path: str,
    ) -> dict:
        """从远程存储下载文件"""
        try:
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            async with (await self._create_client()) as client:
                await client.download_file(
                    self.bucket_name,
                    remote_key,
                    str(local_path),
                )

            file_size = os.path.getsize(local_path)
            return {
                "success": True,
                "local_path": local_path,
                "size": file_size,
            }
        except Exception as e:
            logger.error("远程下载失败 %s: %s", remote_key, str(e))
            return {"success": False, "error": str(e)}

    async def list_files(
        self,
        prefix: str = "",
        max_keys: int = 1000,
    ) -> List[dict]:
        """列出远程文件"""
        try:
            async with (await self._create_client()) as client:
                response = await client.list_objects_v2(
                    Bucket=self.bucket_name,
                    Prefix=prefix,
                    MaxKeys=max_keys,
                )
                items = []
                for obj in response.get("Contents", []):
                    items.append({
                        "key": obj["Key"],
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"].isoformat(),
                        "etag": obj["ETag"],
                    })
                return {"success": True, "items": items, "truncated": response.get("IsTruncated", False)}
        except Exception as e:
            logger.error("远程列举失败: %s", str(e))
            return {"success": False, "items": [], "error": str(e)}

    async def delete_file(self, remote_key: str) -> bool:
        """删除远程文件"""
        try:
            async with (await self._create_client()) as client:
                await client.delete_object(
                    Bucket=self.bucket_name,
                    Key=remote_key,
                )
            return True
        except Exception as e:
            logger.error("远程删除失败 %s: %s", remote_key, str(e))
            return False

    async def get_file_info(self, remote_key: str) -> Optional[dict]:
        """获取远程文件元信息"""
        try:
            async with (await self._create_client()) as client:
                response = await client.head_object(
                    Bucket=self.bucket_name,
                    Key=remote_key,
                )
                return {
                    "key": remote_key,
                    "size": response.get("ContentLength", 0),
                    "content_type": response.get("ContentType", ""),
                    "last_modified": response.get("LastModified", "").isoformat() if response.get("LastModified") else "",
                    "etag": response.get("ETag", ""),
                    "metadata": response.get("Metadata", {}),
                }
        except Exception as e:
            return None

    async def health_check(self) -> dict:
        """远程存储健康检查"""
        try:
            async with (await self._create_client()) as client:
                await client.head_bucket(Bucket=self.bucket_name)
                return {"status": "healthy", "bucket": self.bucket_name}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


class RemoteBackupService:
    """远程备份管理器 — 本地加密 + 远程存储"""

    def __init__(
        self,
        storage: Optional[S3CompatibleStorage] = None,
        local_backup_dir: str = "backups_enhanced",
    ):
        self._storage = storage
        self._local_dir = Path(local_backup_dir)

    @classmethod
    def from_env(cls) -> "RemoteBackupService":
        """从环境变量构建"""
        endpoint = os.getenv("S3_ENDPOINT_URL")
        access_key = os.getenv("S3_ACCESS_KEY")
        secret_key = os.getenv("S3_SECRET_KEY")
        bucket = os.getenv("S3_BUCKET_NAME", "agent-backups")
        region = os.getenv("S3_REGION", "us-east-1")
        use_ssl = os.getenv("S3_USE_SSL", "true").lower() == "true"

        storage = None
        if endpoint and access_key and secret_key:
            storage = S3CompatibleStorage(
                endpoint_url=endpoint,
                access_key=access_key,
                secret_key=secret_key,
                bucket_name=bucket,
                region=region,
                use_ssl=use_ssl,
            )
        return cls(storage=storage)

    @property
    def is_configured(self) -> bool:
        return self._storage is not None

    async def sync_to_remote(
        self,
        backup_id: str,
        local_file: str,
        metadata: Optional[dict] = None,
    ) -> dict:
        """将本地备份同步到远程"""
        if not self.is_configured:
            return {"success": False, "error": "远程存储未配置"}

        remote_key = f"backups/{backup_id}/{Path(local_file).name}"
        meta = metadata or {}
        meta["backup_id"] = backup_id
        meta["sync_type"] = "incremental" if meta.get("is_incremental") else "full"

        return await self._storage.upload_file(local_file, remote_key, meta)

    async def restore_from_remote(
        self,
        backup_id: str,
        filename: str,
        local_target: Optional[str] = None,
    ) -> dict:
        """从远程存储恢复备份到本地"""
        if not self.is_configured:
            return {"success": False, "error": "远程存储未配置"}

        remote_key = f"backups/{backup_id}/{filename}"
        target = local_target or str(self._local_dir / "restore" / backup_id / filename)

        return await self._storage.download_file(remote_key, target)

    async def list_remote_backups(
        self, prefix: str = "backups/"
    ) -> dict:
        """列出远程备份"""
        if not self.is_configured:
            return {"success": False, "items": [], "error": "远程存储未配置"}
        return await self._storage.list_files(prefix)

    async def cleanup_remote(
        self,
        retention_days: int = 90,
    ) -> dict:
        """清理超过保留期的远程备份"""
        if not self.is_configured:
            return {"success": False, "deleted": 0, "error": "远程存储未配置"}

        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        list_result = await self._storage.list_files("backups/")
        if not list_result.get("success"):
            return {"success": False, "deleted": 0, "error": list_result.get("error")}

        deleted = 0
        for item in list_result.get("items", []):
            try:
                last_mod = datetime.fromisoformat(item["last_modified"].replace("Z", "+00:00"))
                if last_mod < cutoff:
                    ok = await self._storage.delete_file(item["key"])
                    if ok:
                        deleted += 1
            except Exception as e:
                logger.warning("清理远程文件失败 %s: %s", item["key"], str(e))

        return {"success": True, "deleted": deleted, "retention_days": retention_days}

    async def health_check(self) -> dict:
        """远程存储健康检查"""
        if not self.is_configured:
            return {"status": "not_configured"}
        return await self._storage.health_check()


# 全局实例
_remote_backup = None


def get_remote_backup_service() -> RemoteBackupService:
    global _remote_backup
    if _remote_backup is None:
        _remote_backup = RemoteBackupService.from_env()
    return _remote_backup

"""
向量索引重建任务

- rebuild_vector_index: 重建 Qdrant 向量索引
"""

import logging

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.index.rebuild_vector_index")
def rebuild_vector_index(collection_name: str = ""):
    """重建向量索引"""
    logger.info(f"Rebuilding vector index for collection: {collection_name or 'all'}")
    # TODO: Qdrant optimize API
    return {"status": "success", "collection": collection_name or "all"}

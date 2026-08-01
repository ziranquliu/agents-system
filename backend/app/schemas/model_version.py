"""
模型版本管理相关Schema
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class ModelVersionBase(BaseModel):
    """版本基础信息"""
    id: str
    template_id: str
    version: int
    name: str
    provider: str
    model: str
    config: Optional[str] = None
    description: Optional[str] = None
    change_log: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class ModelVersionResponse(ModelVersionBase):
    """版本响应"""
    
    @classmethod
    def from_orm(cls, obj):
        return cls(
            id=obj.id,
            template_id=obj.template_id,
            version=obj.version,
            name=obj.name,
            provider=obj.provider,
            model=obj.model,
            config=obj.config,
            description=obj.description,
            change_log=obj.change_log,
            created_by=obj.created_by,
            created_at=obj.created_at,
        )


class RollbackRequest(BaseModel):
    """回滚请求"""
    target_version: int = Field(..., ge=1, description="目标版本号")
    change_log: Optional[str] = Field(None, description="变更说明")
    
    model_config = {"protected_namespaces": ()}


class SyncResultItem(BaseModel):
    """同步结果项"""
    agent_id: str
    status: str  # synced | failed
    error: Optional[str] = None


class SyncResult(BaseModel):
    """同步结果"""
    template_id: str
    total: int
    synced: int
    failed: int
    results: List[SyncResultItem]
    
    model_config = {"protected_namespaces": ()}


class ModelBindingBase(BaseModel):
    """绑定基础信息"""
    id: str
    template_id: str
    agent_id: str
    sync_mode: str = "auto"  # auto | manual | gray
    override_config: Optional[str] = None
    override_model: Optional[str] = None
    override_provider: Optional[str] = None
    gray_percentage: int = 100
    gray_status: str = "synced"
    last_synced_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ModelBindingResponse(ModelBindingBase):
    """绑定响应（含Agent信息）"""
    agent_name: Optional[str] = None
    agent_status: Optional[str] = None
    binding_status: str = "synced"
    
    class Config:
        from_attributes = True
    
    @classmethod
    def from_orm(cls, obj):
        data = super().from_orm(obj)
        if hasattr(obj, 'agent') and obj.agent:
            data['agent_name'] = obj.agent.name
            data['agent_status'] = obj.agent.status
        return data

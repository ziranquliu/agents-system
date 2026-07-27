"""
认证管理 API
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

router = APIRouter()


@router.post("/login")
async def login():
    """用户登录 (占位)"""
    return {"message": "待实现"}


@router.post("/register")
async def register():
    """用户注册 (占位)"""
    return {"message": "待实现"}

"""
认证管理 API - 注册、登录、获取当前用户
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.config import settings
from app.models.user import User, OperationLog
from app.schemas.auth import UserCreate, UserLogin, UserResponse, TokenResponse
from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    authenticate_user,
)
from app.core.security import validate_password, PasswordPolicyError

from sqlalchemy.orm import selectinload, joinedload

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    """用户注册"""
    # 校验密码强度
    try:
        validate_password(data.password)
    except PasswordPolicyError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # 检查用户名是否已存在
    result = await db.execute(select(User).where(User.username == data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")

    # 检查邮箱是否已存在
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    # 创建用户
    user = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
        display_name=data.display_name or data.username,
        role="user",
    )
    db.add(user)
    await db.flush()

    # 记录操作日志
    log = OperationLog(
        user_id=user.id,
        action="register",
        resource_type="user",
        resource_id=user.id,
        detail=f"User {user.username} registered",
    )
    db.add(log)
    await db.flush()

    # 生成令牌
    token, expires_in = create_access_token(user.id, user.username, user.role)
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    """用户登录"""
    user = await authenticate_user(db, data.username, data.password)
    if not user:
        # 记录失败登录
        log = OperationLog(
            user_id="unknown",
            action="login_failed",
            resource_type="user",
            detail=f"Failed login attempt for: {data.username}",
        )
        db.add(log)
        await db.flush()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # 更新最后登录时间
    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()

    # 记录登录日志
    log = OperationLog(
        user_id=user.id,
        action="login",
        resource_type="user",
        resource_id=user.id,
    )
    db.add(log)
    await db.flush()

    # 生成令牌
    token, expires_in = create_access_token(user.id, user.username, user.role)
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return UserResponse.model_validate(current_user)


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """登出记录"""
    log = OperationLog(
        user_id=current_user.id,
        action="logout",
        resource_type="user",
        resource_id=current_user.id,
    )
    db.add(log)
    return {"message": "Logged out"}

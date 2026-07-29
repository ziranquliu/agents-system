@echo off
chcp 65001 >nul
title Agents System - 启动器
echo ============================================
echo   智能体管理系统 - 服务启动器
echo ============================================
echo.

:: 检测 Docker 是否运行
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [!!] Docker Desktop 未运行，请先启动 Docker Desktop
    pause
    exit /b
)
echo [OK] Docker 运行中

:: 启动 Docker 服务
echo [..] 启动 PostgreSQL / Redis / Qdrant ...
cd /d "%~dp0"
docker compose -f docker/docker-compose.dev.yml up -d agent-postgres agent-redis agent-qdrant
echo [OK] 基础服务已启动

:: 启动后端 (新窗口)
echo [..] 启动后端服务 (端口 8000) ...
start "Backend" cmd /c "chcp 65001 >nul && cd /d "%~dp0backend" && set PYTHONIOENCODING=utf-8 && "C:\Users\changruifeng\AppData\Local\hermes\hermes-agent\venv\Scripts\uvicorn.exe" app.main:app --reload --host 0.0.0.0 --port 8000"
timeout /t 5 /nobreak >nul

:: 启动前端 (新窗口)
echo [..] 启动前端服务 (端口 5173) ...
start "Frontend" cmd /c "chcp 65001 >nul && cd /d "%~dp0frontend" && npm run dev"

echo.
echo ============================================
echo   所有服务已启动！
echo   后端: http://localhost:8000/docs
echo   前端: http://localhost:5173
echo ============================================
echo.
echo 按任意键关闭本窗口...
pause >nul

@echo off
chcp 65001 >nul
title Agents System - 关闭器
echo ============================================
echo   智能体管理系统 - 服务关闭器
echo ============================================
echo.

:: 关闭后端进程
echo [..] 关闭后端服务 ...
taskkill /f /fi "WINDOWTITLE eq Backend*" >nul 2>&1
taskkill /f /im uvicorn.exe >nul 2>&1
echo [OK] 后端已关闭

:: 关闭前端进程
echo [..] 关闭前端服务 ...
taskkill /f /fi "WINDOWTITLE eq Frontend*" >nul 2>&1
taskkill /f /im node.exe >nul 2>&1
echo [OK] 前端已关闭

:: 关闭 Docker 服务
echo [..] 关闭 Docker 容器 ...
cd /d "%~dp0"
docker compose -f docker/docker-compose.dev.yml down
echo [OK] Docker 容器已关闭

echo.
echo ============================================
echo   所有服务已关闭！
echo ============================================
echo.
timeout /t 3 /nobreak >nul

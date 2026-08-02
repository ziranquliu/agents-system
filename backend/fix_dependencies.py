#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查并修复后端依赖问题"""
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent

def check_dependencies():
    """检查依赖"""
    print("=" * 70)
    print("Checking Dependencies")
    print("=" * 70)
    
    required = [
        "fastapi",
        "sqlalchemy",
        "sqlalchemy-utils",
        "asyncpg",
        "uvicorn",
        "pydantic",
        "redis",
        "qdrant-client",
        "cryptography",
        "pyjwt",
        "aiohttp",
        "httpx",
    ]
    
    missing = []
    for pkg in required:
        try:
            __import__(pkg.replace("-", "_"))
            print(f"  [OK] {pkg}")
        except ImportError:
            missing.append(pkg)
            print(f"  [MISS] {pkg}")
    
    return missing

def install_dependencies(missing):
    """安装缺失的依赖"""
    if not missing:
        print("\n[OK] All dependencies installed!")
        return True
    
    print(f"\n[INFO] Installing {len(missing)} missing dependencies...")
    
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install"] + missing,
            cwd=BASE_DIR
        )
        print("\n[OK] Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Failed to install dependencies: {e}")
        return False

def verify_import():
    """验证导入"""
    print("\n" + "=" * 70)
    print("Verifying Import")
    print("=" * 70)
    
    try:
        import sys
        sys.path.insert(0, str(BASE_DIR))
        from app.main import app
        print("\n[OK] Backend import successful!")
        return True
    except Exception as e:
        print(f"\n[ERROR] Import failed: {e}")
        return False

def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("Backend Dependency Fix")
    print("=" * 70)
    
    # 检查依赖
    missing = check_dependencies()
    
    # 安装依赖
    if missing:
        install_dependencies(missing)
    
    # 验证导入
    success = verify_import()
    
    if success:
        print("\n" + "=" * 70)
        print("Backend is ready to start!")
        print("=" * 70)
        print("\nStart command:")
        print("  cd backend")
        print("  python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
    
    return success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

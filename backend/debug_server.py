#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""启动调试服务器"""
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent

def check_dependencies():
    """检查依赖"""
    print("=" * 70)
    print("Checking Dependencies")
    print("=" * 70)
    
    dependencies = [
        ("fastapi", "FastAPI"),
        ("sqlalchemy", "SQLAlchemy"),
        ("uvicorn", "Uvicorn"),
        ("pydantic", "Pydantic"),
        ("redis", "Redis"),
        ("qdrant_client", "Qdrant"),
        ("cryptography", "Cryptography"),
        ("pyjwt", "PyJWT"),
    ]
    
    missing = []
    for package, name in dependencies:
        try:
            __import__(package.replace("-", "_"))
            print(f"  [OK] {name}")
        except ImportError:
            missing.append(name)
            print(f"  [MISS] {name}")
    
    return len(missing) == 0

def check_syntax():
    """检查语法"""
    print("\n" + "=" * 70)
    print("Checking Syntax")
    print("=" * 70)
    
    import ast
    errors = []
    
    for filepath in BASE_DIR.rglob("app/**/*.py"):
        if "__pycache__" in str(filepath):
            continue
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                ast.parse(f.read())
        except SyntaxError as e:
            errors.append((str(filepath.relative_to(BASE_DIR)), str(e)))
    
    if errors:
        print(f"\n[ERROR] Found {len(errors)} syntax errors:")
        for filepath, error in errors[:5]:
            print(f"  {filepath}: {error}")
        return False
    else:
        print("\n[OK] No syntax errors found!")
        return True

def start_server():
    """启动服务器"""
    print("\n" + "=" * 70)
    print("Starting Debug Server")
    print("=" * 70)
    
    cmd = [
        sys.executable, "-m", "uvicorn", "app.main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload",
        "--log-level", "debug"
    ]
    
    print(f"\nStarting server: {' '.join(cmd)}")
    print("\nPress Ctrl+C to stop")
    print("=" * 70)
    
    try:
        process = subprocess.Popen(
            cmd,
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            encoding='utf-8'
        )
        
        # 读取输出
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                print(line.rstrip())
            
            # 检查服务器是否启动成功
            if "Uvicorn running on" in line or "Application startup complete" in line:
                print("\n[OK] Server started successfully!")
                print(f"  URL: http://localhost:8000")
                print(f"  Docs: http://localhost:8000/docs")
                print(f"  API: http://localhost:8000/api/v1")
                break
            
            # 检查启动失败
            if "Error" in line or "Traceback" in line:
                print(f"\n[ERROR] Failed to start server: {line.strip()}")
                break
        
        process.wait()
        
    except KeyboardInterrupt:
        print("\n[INFO] Server stopped by user")
        process.terminate()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        process.terminate()

def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("Project Startup Debugger")
    print("=" * 70)
    
    # 检查依赖
    deps_ok = check_dependencies()
    if not deps_ok:
        print("\n[WARN] Some dependencies are missing. Install them first.")
        print("  Run: pip install -r requirements.txt")
        return 1
    
    # 检查语法
    syntax_ok = check_syntax()
    if not syntax_ok:
        print("\n[ERROR] Fix syntax errors before starting.")
        return 1
    
    # 启动服务器
    start_server()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

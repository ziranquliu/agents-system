#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断 app.db.session 模块"""
import sys
import os

# 设置 UTF-8 输出
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

BASE_DIR = r"D:\智能体管理\agents-system\backend"
sys.path.insert(0, BASE_DIR)

def main():
    print("=" * 70)
    print("Diagnosing app.db.session")
    print("=" * 70)
    
    try:
        print("\n[1] Reading session.py...")
        with open(os.path.join(BASE_DIR, "app", "db", "session.py"), 'r', encoding='utf-8') as f:
            content = f.read()
        print(f"  [OK] File read successfully ({len(content)} bytes)")
        
        print("\n[2] Checking syntax...")
        import ast
        ast.parse(content)
        print("  [OK] Syntax is valid")
        
        print("\n[3] Attempting to import...")
        from app.db import session
        print("  [OK] Import successful")
        
        print("\n[4] Checking session module attributes...")
        print(f"  get_db: {hasattr(session, 'get_db')}")
        print(f"  async_session_factory: {hasattr(session, 'async_session_factory')}")
        
        print("\n" + "=" * 70)
        print("SUCCESS: app.db.session is working correctly!")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

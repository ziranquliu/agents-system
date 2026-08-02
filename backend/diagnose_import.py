#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""详细诊断后端导入错误"""
import sys
import os
import traceback

# 设置 UTF-8 输出
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

BASE_DIR = r"D:\智能体管理\agents-system\backend"
sys.path.insert(0, BASE_DIR)

def main():
    print("=" * 70)
    print("Detailed Backend Import Diagnosis")
    print("=" * 70)
    
    try:
        print("\n[1] Checking Python version...")
        print(f"  Python: {sys.version}")
        
        print("\n[2] Checking working directory...")
        print(f"  CWD: {os.getcwd()}")
        
        print("\n[3] Attempting to import app.main...")
        from app.main import app
        print("  [OK] Import successful!")
        
        print("\n[4] Checking app configuration...")
        print(f"  App title: {app.title}")
        print(f"  App version: {app.version}")
        
        print("\n" + "=" * 70)
        print("SUCCESS: Backend is ready to start!")
        print("=" * 70)
        return 0
        
    except ImportError as e:
        print(f"\n[ERROR] Import error: {e}")
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

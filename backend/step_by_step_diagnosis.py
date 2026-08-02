#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分步诊断导入错误"""
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
    print("Step-by-step Import Diagnosis")
    print("=" * 70)
    
    steps = [
        ("app", "基础模块"),
        ("app.db", "数据库模块"),
        ("app.db.session", "数据库会话"),
        ("app.core.config", "配置模块"),
        ("app.core.security", "安全模块"),
        ("app.api", "API模块"),
        ("app.api.v1", "API v1"),
        ("app.api.v1.router", "API路由"),
        ("app.main", "主模块"),
    ]
    
    for module, desc in steps:
        try:
            print(f"\n[{desc}] 导入 {module}...")
            __import__(module)
            print(f"  [OK] {module} 导入成功")
        except Exception as e:
            print(f"  [ERROR] {module} 导入失败: {e}")
            import traceback
            traceback.print_exc()
            return 1
    
    print("\n" + "=" * 70)
    print("SUCCESS: All modules imported successfully!")
    print("=" * 70)
    return 0

if __name__ == "__main__":
    sys.exit(main())

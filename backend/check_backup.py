#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查备份目录结构"""
from pathlib import Path

BASE_DIR = Path(__file__).parent
BACKUP_DIR = BASE_DIR / "backup"

def check_backup():
    """检查备份目录"""
    print("=" * 70)
    print("Backup Directory Structure")
    print("=" * 70)
    
    if not BACKUP_DIR.exists():
        print("[ERROR] Backup directory not found!")
        return
    
    for backup_type in BACKUP_DIR.iterdir():
        if backup_type.is_dir():
            print(f"\n{backup_type.name}/")
            count = 0
            for root, dirs, files in backup_type.walk():
                for file in files:
                    if file.endswith('.py'):
                        count += 1
            print(f"  Total .py files: {count}")
            
            # 显示前10个文件
            print("  Sample files:")
            for i, file in enumerate(backup_type.rglob("*.py")):
                if i >= 10:
                    break
                print(f"    - {file.relative_to(backup_type)}")

def main():
    check_backup()

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从备份恢复文件并重新检查"""
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).parent
APP_DIR = BASE_DIR / "app"
BACKUP_DIR = BASE_DIR / "backup"

def restore_files():
    """从备份恢复文件"""
    print("=" * 70)
    print("Restoring Files from Backup")
    print("=" * 70)
    
    restored = 0
    
    # 恢复 API 文件
    api_backup = BACKUP_DIR / "api_v1"
    if api_backup.exists():
        for filepath in APP_DIR.rglob("api/v1/*.py"):
            if "__pycache__" in str(filepath):
                continue
            backup_file = api_backup / filepath.name
            if backup_file.exists():
                shutil.copy2(backup_file, filepath)
                restored += 1
                print(f"[OK] Restored: {filepath.name}")
    
    # 恢复服务文件
    service_backup = BACKUP_DIR / "service_restructure" / "services"
    if service_backup.exists():
        for filepath in APP_DIR.rglob("services/**/*.py"):
            if "__pycache__" in str(filepath):
                continue
            rel_path = filepath.relative_to(APP_DIR / "services")
            backup_file = service_backup / rel_path
            if backup_file.exists():
                shutil.copy2(backup_file, filepath)
                restored += 1
                print(f"[OK] Restored: {filepath.relative_to(BASE_DIR)}")
    
    return restored

def check_syntax():
    """检查语法"""
    print("\n" + "=" * 70)
    print("Checking Syntax")
    print("=" * 70)
    
    import ast
    errors = []
    
    for filepath in APP_DIR.rglob("*.py"):
        if "__pycache__" in str(filepath):
            continue
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                ast.parse(f.read())
        except SyntaxError as e:
            errors.append((str(filepath.relative_to(BASE_DIR)), str(e)))
    
    if errors:
        print(f"\n[ERROR] Found {len(errors)} syntax errors:")
        for filepath, error in errors[:10]:
            print(f"  {filepath}: {error}")
        return False
    else:
        print("\n[OK] No syntax errors found!")
        return True

def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("Project Structure Fix - Restore and Verify")
    print("=" * 70)
    
    # 恢复文件
    restored = restore_files()
    print(f"\n[OK] Restored {restored} files from backup")
    
    # 检查语法
    syntax_ok = check_syntax()
    
    if syntax_ok:
        print("\n" + "=" * 70)
        print("All files restored and syntax verified!")
        print("=" * 70)
        return True
    else:
        print("\n" + "=" * 70)
        print("Syntax errors remain. Manual fix required.")
        print("=" * 70)
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

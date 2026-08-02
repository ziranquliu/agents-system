#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""最终修复方案 - 从备份完整恢复"""
import shutil
from pathlib import Path
import os

BASE_DIR = Path(__file__).parent
APP_DIR = BASE_DIR / "app"
BACKUP_DIR = BASE_DIR / "backup"

def restore_complete():
    """完整恢复"""
    print("=" * 70)
    print("COMPLETE RESTORATION - Final Fix")
    print("=" * 70)
    
    restored = 0
    
    # 1. 恢复所有 API 文件
    api_backup = BACKUP_DIR / "api_v1"
    if api_backup.exists():
        for backup_file in api_backup.glob("*.py"):
            target = APP_DIR / "api" / "v1" / backup_file.name
            if target.exists():
                shutil.copy2(backup_file, target)
                restored += 1
                print(f"[OK] Restored: {backup_file.name}")
    
    # 2. 恢复服务目录
    service_backup = BACKUP_DIR / "service_restructure" / "services"
    if service_backup.exists():
        for backup_file in service_backup.rglob("*.py"):
            rel_path = backup_file.relative_to(service_backup)
            target = APP_DIR / "services" / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                shutil.copy2(backup_file, target)
                restored += 1
                print(f"[OK] Restored: {target.relative_to(BASE_DIR)}")
    
    # 3. 恢复结构优化备份的文件
    struct_backup = BACKUP_DIR / "structure_optimization"
    if struct_backup.exists():
        for backup_file in struct_backup.rglob("*.py"):
            rel_path = backup_file.relative_to(struct_backup)
            # 尝试在多个位置恢复
            for search_path in [APP_DIR, BASE_DIR]:
                target = search_path / rel_path
                if target.exists():
                    shutil.copy2(backup_file, target)
                    restored += 1
                    print(f"[OK] Restored: {target.relative_to(BASE_DIR)}")
                    break
    
    return restored

def check_remaining_errors():
    """检查剩余错误"""
    print("\n" + "=" * 70)
    print("Checking Remaining Errors")
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
            errors.append((str(filepath.relative_to(BASE_DIR)), e.lineno, e.msg))
    
    return errors

def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("Final Fix - Complete Restoration")
    print("=" * 70)
    
    # 恢复
    restored = restore_complete()
    print(f"\n[OK] Restored {restored} files")
    
    # 检查
    errors = check_remaining_errors()
    
    if errors:
        print(f"\n[WARN] Found {len(errors)} remaining errors:")
        for filepath, line, msg in errors[:10]:
            print(f"  {filepath}:{line} - {msg}")
        
        print("\n[SUGGESTION] Manual fix required:")
        print("  1. Check Git history: git log --oneline -10")
        print("  2. Restore from git: git checkout HEAD -- backend/app/")
        print("  3. Or delete corrupted files and recreate")
        
        return False
    else:
        print("\n[SUCCESS] All files restored successfully!")
        return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

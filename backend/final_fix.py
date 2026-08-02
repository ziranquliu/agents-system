#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""最终修复 - 从备份完整恢复并修复所有问题"""
import shutil
from pathlib import Path
import os

BASE_DIR = Path(__file__).parent
APP_DIR = BASE_DIR / "app"
BACKUP_DIR = BASE_DIR / "backup"

def restore_all_files():
    """完整恢复所有文件"""
    print("=" * 70)
    print("Final Restoration - Restoring All Files from Backup")
    print("=" * 70)
    
    restored = 0
    
    # 1. 恢复 API 文件
    api_backup = BACKUP_DIR / "api_v1"
    if api_backup.exists():
        for backup_file in api_backup.glob("*.py"):
            target = APP_DIR / "api" / "v1" / backup_file.name
            if target.exists():
                shutil.copy2(backup_file, target)
                restored += 1
                print(f"[OK] Restored API: {backup_file.name}")
    
    # 2. 恢复服务文件
    service_backup = BACKUP_DIR / "service_restructure" / "services"
    if service_backup.exists():
        for backup_file in service_backup.rglob("*.py"):
            rel_path = backup_file.relative_to(service_backup)
            target = APP_DIR / "services" / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                shutil.copy2(backup_file, target)
                restored += 1
                print(f"[OK] Restored Service: {target.relative_to(BASE_DIR)}")
    
    # 3. 恢复核心文件
    core_files = ["main.py", "__init__.py", "core/base.py", "core/csrf.py", 
                  "core/error_handler.py", "core/scheduler.py", "models/__init__.py",
                  "services/auth/token_service.py"]
    
    for core_file in core_files:
        target = APP_DIR / core_file
        if target.exists():
            # 尝试从多个备份位置恢复
            for backup_name in ["api_v1", "service_restructure", "structure_optimization"]:
                backup_file = BACKUP_DIR / backup_name / core_file
                if backup_file.exists():
                    shutil.copy2(backup_file, target)
                    restored += 1
                    print(f"[OK] Restored Core: {core_file}")
                    break
    
    # 4. 恢复 models 文件
    models_backup = BACKUP_DIR / "api_v1"
    if models_backup.exists():
        for backup_file in models_backup.glob("*.py"):
            if backup_file.name not in ["__init__.py", "router.py"]:
                # 尝试找到对应的 models 文件
                model_name = backup_file.name.replace('.py', '')
                target = APP_DIR / "models" / backup_file.name
                if target.exists():
                    # 检查是否有备份
                    alt_backup = BACKUP_DIR / "structure_optimization" / "app" / "models" / backup_file.name
                    if alt_backup.exists():
                        shutil.copy2(alt_backup, target)
                        restored += 1
                        print(f"[OK] Restored Model: {backup_file.name}")
    
    return restored

def verify_all():
    """验证所有文件"""
    print("\n" + "=" * 70)
    print("Verifying All Files")
    print("=" * 70)
    
    import ast
    errors = []
    
    # 检查 app 目录
    for filepath in APP_DIR.rglob("*.py"):
        if "__pycache__" in str(filepath):
            continue
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                ast.parse(f.read())
        except SyntaxError as e:
            errors.append((str(filepath.relative_to(BASE_DIR)), str(e)))
    
    return errors

def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("Final Fix - Complete Restoration")
    print("=" * 70)
    
    # 恢复文件
    restored = restore_all_files()
    print(f"\n[OK] Restored {restored} files from backup")
    
    # 验证
    errors = verify_all()
    
    if errors:
        print(f"\n[ERROR] Found {len(errors)} syntax errors:")
        for filepath, error in errors[:15]:
            print(f"  {filepath}: {error}")
        
        print("\n[INFO] Suggested manual fixes:")
        for filepath, _ in errors[:5]:
            print(f"  1. Delete: {filepath}")
            print(f"  2. Recreate with correct syntax")
        
        return False
    else:
        print("\n[OK] All syntax errors fixed!")
        return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

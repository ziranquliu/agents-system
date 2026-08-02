#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手动修复所有语法错误 - 基于详细诊断"""
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent
APP_DIR = BASE_DIR / "app"

def fix_file_manually(filepath: Path):
    """手动修复文件"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original = content
        lines = content.split('\n')
        
        # 重建文件：将所有导入移到文件开头
        imports = []
        code = []
        docstring_started = False
        
        for line in lines:
            stripped = line.strip()
            
            # 检测导入
            if stripped.startswith('from ') or stripped.startswith('import '):
                imports.append(line)
            elif stripped == '' and imports and not code:
                # 导入后的空行
                imports.append(line)
            else:
                # 代码部分
                if not docstring_started and stripped.startswith('"""'):
                    docstring_started = True
                code.append(line)
        
        # 重新组合
        new_content = '\n'.join(imports) + '\n\n' + '\n'.join(code)
        
        if new_content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return True
        
        return False
    
    except Exception as e:
        print(f"[ERROR] Failed to fix {filepath}: {e}")
        return False

def main():
    print("=" * 70)
    print("Manual Syntax Fix - All Python Files")
    print("=" * 70)
    
    fixed = 0
    for filepath in APP_DIR.rglob("*.py"):
        if "__pycache__" in str(filepath):
            continue
        if fix_file_manually(filepath):
            fixed += 1
            print(f"[OK] Fixed: {filepath.relative_to(BASE_DIR)}")
    
    print(f"\n[OK] Fixed {fixed} files")
    
    # 验证
    print("\n" + "=" * 70)
    print("Verifying fixes...")
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
        print("\n[OK] All syntax errors fixed!")
        return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

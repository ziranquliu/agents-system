#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复导入块被错误拆分的文件"""
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent
APP_DIR = BASE_DIR / "app"

def fix_broken_imports():
    """修复被错误拆分的导入块"""
    fixed = 0
    
    for filepath in APP_DIR.rglob("*.py"):
        if "__pycache__" in str(filepath):
            continue
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original = content
            
            # 修复模式：导入块被拆分，docstring 插在中间
            # 模式1: from ... import (...) 后面紧跟其他 import 或代码
            pattern1 = r'(from \S+ import \([^)]+\))\n(from \S+|import \S+|"""|""")'
            replacement1 = r'\1\n\n\2'
            content = re.sub(pattern1, replacement1, content)
            
            # 模式2: 多行导入被拆分
            lines = content.split('\n')
            new_lines = []
            i = 0
            
            while i < len(lines):
                line = lines[i]
                
                # 检测多行导入开始
                if line.strip().startswith('from ') and '(' in line and ')' not in line:
                    # 收集所有行直到找到 closing )
                    import_block = [line]
                    i += 1
                    while i < len(lines):
                        current = lines[i]
                        import_block.append(current)
                        if ')' in current:
                            break
                        i += 1
                    # 输出完整的导入块
                    new_lines.append('\n'.join(import_block))
                else:
                    new_lines.append(line)
                i += 1
            
            content = '\n'.join(new_lines)
            
            if content != original:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                fixed += 1
                print(f"[OK] Fixed: {filepath.relative_to(BASE_DIR)}")
        
        except Exception as e:
            print(f"[ERROR] Failed to fix {filepath}: {e}")
    
    return fixed

def main():
    print("=" * 70)
    print("Fixing Broken Import Blocks")
    print("=" * 70)
    
    fixed = fix_broken_imports()
    
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

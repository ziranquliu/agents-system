#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复所有 Python 文件的导入顺序问题"""
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent
APP_DIR = BASE_DIR / "app"

def fix_file(filepath: Path) -> bool:
    """修复单个文件的导入顺序"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original = content
        lines = content.split('\n')
        
        # 分离导入和代码
        imports = []
        code = []
        in_imports = False
        i = 0
        
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # 检测导入开始
            if stripped.startswith('from ') or stripped.startswith('import '):
                in_imports = True
                imports.append(line)
                i += 1
                continue
            
            # 如果是导入的延续（以括号、逗号或缩进开头）
            if in_imports and (stripped.startswith('(') or 
                               stripped.startswith(')') or
                               stripped.startswith(',') or
                               (line.startswith('    ') and stripped)):
                imports.append(line)
                i += 1
                continue
            
            # 导入块结束
            if in_imports and stripped == '':
                # 空行可能是导入块的延续
                if i + 1 < len(lines) and lines[i+1].strip().startswith(('from', 'import', '(', ')', ',')):
                    imports.append(line)
                    i += 1
                    continue
                else:
                    in_imports = False
            
            # 代码部分
            if not in_imports:
                code.append(line)
            else:
                # 导入块中的代码行，先输出导入
                imports.append(line)
            i += 1
        
        # 重新组合
        new_content = '\n'.join(imports) + '\n' + '\n'.join(code)
        
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
    print("Fixing Import Order in All Python Files")
    print("=" * 70)
    
    fixed = 0
    for filepath in APP_DIR.rglob("*.py"):
        if "__pycache__" in str(filepath):
            continue
        if fix_file(filepath):
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

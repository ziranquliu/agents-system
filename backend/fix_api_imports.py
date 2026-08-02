#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复所有 API 文件的导入问题"""
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent
APP_DIR = BASE_DIR / "app" / "api" / "v1"

def fix_imports_in_api_files():
    """修复 API 目录下的导入问题"""
    fixed = 0
    
    for filepath in APP_DIR.glob("*.py"):
        if filepath.name in ["router.py", "__init__.py"]:
            continue
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original = content
            
            # 修复多行导入：将导入块合并到正确位置
            lines = content.split('\n')
            new_lines = []
            i = 0
            
            while i < len(lines):
                line = lines[i]
                
                # 检测导入语句
                if line.strip().startswith('from ') or line.strip().startswith('import '):
                    # 收集所有连续的导入行
                    import_block = [line]
                    i += 1
                    
                    while i < len(lines):
                        next_line = lines[i]
                        # 如果下一行是导入的延续（以逗号、括号或缩进开头）
                        if (next_line.strip().startswith(',') or 
                            next_line.strip().startswith('(') or
                            next_line.strip().startswith(')') or
                            (next_line.startswith('    ') and next_line.strip())):
                            import_block.append(next_line)
                            i += 1
                        else:
                            break
                    
                    # 输出导入块
                    new_lines.extend(import_block)
                else:
                    new_lines.append(line)
                    i += 1
            
            content = '\n'.join(new_lines)
            
            if content != original:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                fixed += 1
                print(f"[OK] Fixed: {filepath.name}")
        
        except Exception as e:
            print(f"[ERROR] Failed to fix {filepath.name}: {e}")
    
    return fixed

def main():
    print("=" * 70)
    print("Fixing Import Issues in API Files")
    print("=" * 70)
    
    fixed = fix_imports_in_api_files()
    
    print(f"\n[OK] Fixed {fixed} files")
    
    # 验证
    print("\n" + "=" * 70)
    print("Verifying fixes...")
    print("=" * 70)
    
    import ast
    errors = []
    
    for filepath in APP_DIR.glob("*.py"):
        if filepath.name in ["router.py", "__init__.py"]:
            continue
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                ast.parse(f.read())
        except SyntaxError as e:
            errors.append((filepath.name, str(e)))
    
    if errors:
        print(f"\n[ERROR] Found {len(errors)} syntax errors:")
        for filename, error in errors[:10]:
            print(f"  {filename}: {error}")
        return False
    else:
        print("\n[OK] All syntax errors fixed!")
        return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

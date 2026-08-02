#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复所有 Python 文件的导入问题"""
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent
APP_DIR = BASE_DIR / "app"

def fix_all_imports():
    """修复所有导入问题"""
    fixed = 0
    
    for filepath in APP_DIR.rglob("*.py"):
        if "__pycache__" in str(filepath):
            continue
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original = content
            
            # 修复问题：导入语句后面紧跟 docstring 或其他内容
            # 模式：from ... import (...) followed by """
            pattern = r'(from \S+ import \([^)]+\))\n("""[^"]*""")'
            replacement = r'\1\n\n\2'
            content = re.sub(pattern, replacement, content, flags=re.DOTALL)
            
            # 修复问题：导入语句被拆分到多行但格式错误
            lines = content.split('\n')
            new_lines = []
            i = 0
            
            while i < len(lines):
                line = lines[i]
                
                # 检测导入语句开始
                if line.strip().startswith('from ') or line.strip().startswith('import '):
                    # 收集所有导入行
                    import_lines = [line]
                    i += 1
                    
                    # 继续收集导入行，直到遇到非导入行
                    while i < len(lines):
                        next_line = lines[i]
                        # 如果下一行以缩进开头且不是空行，可能是导入的延续
                        if next_line.startswith('    ') and next_line.strip():
                            import_lines.append(next_line)
                            i += 1
                        else:
                            break
                    
                    # 输出导入块
                    new_lines.extend(import_lines)
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
    print("Fixing All Import Issues")
    print("=" * 70)
    
    fixed = fix_all_imports()
    
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

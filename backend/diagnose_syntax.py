#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""详细诊断 Python 文件语法问题"""
import ast
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent
APP_DIR = BASE_DIR / "app"

def diagnose_file(filepath: Path):
    """诊断单个文件的语法问题"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        ast.parse(content)
        return None  # 无错误
    except SyntaxError as e:
        return {
            'file': str(filepath.relative_to(BASE_DIR)),
            'line': e.lineno,
            'offset': e.offset,
            'text': e.text,
            'msg': e.msg,
            'content_lines': content.split('\n')[:max(1, e.lineno + 5)]
        }

def main():
    print("=" * 70)
    print("Syntax Diagnostic Report")
    print("=" * 70)
    
    errors = []
    
    for filepath in APP_DIR.rglob("*.py"):
        if "__pycache__" in str(filepath):
            continue
        error = diagnose_file(filepath)
        if error:
            errors.append(error)
    
    if not errors:
        print("\n[OK] No syntax errors found in any Python file!")
        return
    
    print(f"\nFound {len(errors)} files with syntax errors:\n")
    
    for i, error in enumerate(errors[:15], 1):
        print(f"{i}. {error['file']}")
        print(f"   Line {error['line']}, Column {error['offset']}")
        print(f"   Message: {error['msg']}")
        if error['text']:
            print(f"   Text: {error['text'].strip()}")
        
        # 显示上下文
        if error['content_lines']:
            start_line = max(0, error['line'] - 3)
            end_line = min(len(error['content_lines']), error['line'] + 2)
            print("   Context:")
            for j in range(start_line, end_line):
                marker = ">>>" if j == error['line'] - 1 else "   "
                print(f"   {marker} {j+1}: {error['content_lines'][j]}")
        print()

if __name__ == "__main__":
    main()

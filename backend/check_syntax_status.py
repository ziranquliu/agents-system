#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查当前语法错误状态"""
import ast
from pathlib import Path

BASE_DIR = Path(__file__).parent
APP_DIR = BASE_DIR / "app"

def check_syntax():
    """检查语法错误"""
    errors = []
    
    for filepath in APP_DIR.rglob("*.py"):
        if "__pycache__" in str(filepath):
            continue
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                ast.parse(f.read())
        except SyntaxError as e:
            errors.append({
                'file': str(filepath.relative_to(BASE_DIR)),
                'line': e.lineno,
                'msg': e.msg,
                'text': e.text
            })
    
    return errors

def main():
    print("=" * 70)
    print("Current Syntax Error Status")
    print("=" * 70)
    
    errors = check_syntax()
    
    if errors:
        print(f"\nFound {len(errors)} syntax errors:\n")
        for i, error in enumerate(errors[:20], 1):
            print(f"{i}. {error['file']}")
            print(f"   Line {error['line']}: {error['msg']}")
            if error['text']:
                print(f"   Text: {error['text'].strip()}")
            print()
    else:
        print("\n[OK] No syntax errors found!")
    
    return len(errors) == 0

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

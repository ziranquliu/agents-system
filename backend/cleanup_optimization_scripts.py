#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清理临时优化脚本"""
from pathlib import Path

BASE_DIR = Path(__file__).parent

def cleanup():
    """清理临时文件"""
    temp_files = [
        "optimize_structure.py",
        "optimize_structure_v2.py",
        "rename_files.py",
        "restructure_services.py",
        "run_all_optimizations.py",
        "generate_optimization_report.py",
        "generate_optimization_report_v2.py",
        "generate_final_summary.py",
        "generate_final_summary_v2.py",
        "generate_final_summary_v3.py",
    ]
    
    cleaned = 0
    for filename in temp_files:
        filepath = BASE_DIR / filename
        if filepath.exists():
            filepath.unlink()
            cleaned += 1
            print(f"[OK] Deleted: {filename}")
    
    return cleaned

if __name__ == "__main__":
    print("=" * 70)
    print("Cleaning up temporary optimization scripts")
    print("=" * 70)
    
    cleaned = cleanup()
    
    print("\n" + "=" * 70)
    print(f"Cleaned {cleaned} temporary files")
    print("=" * 70)

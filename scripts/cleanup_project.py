#!/usr/bin/env python3
import os
import shutil
import time
import argparse
from datetime import datetime, timedelta

# --- 設定 (Settings) ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_BACKUP_DIR = os.path.join(PROJECT_ROOT, "models", "backup")
MLRUNS_DIR = os.path.join(PROJECT_ROOT, "mlruns", "118294905034743333") 
KEEP_MODELS_COUNT = 7  # 保留最近 7 個備份
KEEP_MLRUNS_DAYS = 30  # 保留最近 30 天的實驗

# 安全白名單 (禁止刪除的關鍵字或檔名)
SAFE_LIST = [
    "latest_lgbm.pkl",
    "baseline_stats.json",
    "meta.yaml",  # MLflow 基礎設定檔案
]

def format_size(size_bytes):
    """將位元組轉換為可讀格式"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

def get_dir_size(path):
    """計算目錄總大小"""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)
    return total_size

def cleanup_models(dry_run=True):
    print(f"\n--- 正在檢查模型備份 ({MODELS_BACKUP_DIR}) ---")
    if not os.path.exists(MODELS_BACKUP_DIR):
        print("目錄不存在，跳過。")
        return 0

    files = [os.path.join(MODELS_BACKUP_DIR, f) for f in os.listdir(MODELS_BACKUP_DIR) 
             if f.endswith('.pkl') and f not in SAFE_LIST]
    
    # 按修改時間排序 (從舊到新)
    files.sort(key=os.path.getmtime)
    
    if len(files) <= KEEP_MODELS_COUNT:
        print(f"目前備份數量 ({len(files)}) 未超過保留上限 ({KEEP_MODELS_COUNT})，無需清理。")
        return 0

    to_delete = files[:-KEEP_MODELS_COUNT]
    saved_space = 0
    
    print(f"預計清理 {len(to_delete)} 個舊模型備份：")
    for f in to_delete:
        size = os.path.getsize(f)
        saved_space += size
        print(f"  [ {'模擬刪除' if dry_run else '刪除'} ] {os.path.basename(f)} ({format_size(size)})")
        if not dry_run:
            os.remove(f)
            
    return saved_space

def cleanup_mlruns(dry_run=True):
    print(f"\n--- 正在檢查 MLflow 運行紀錄 ({MLRUNS_DIR}) ---")
    if not os.path.exists(MLRUNS_DIR):
        print("目錄不存在，跳過。")
        return 0

    now = time.time()
    cutoff_sec = now - (KEEP_MLRUNS_DAYS * 24 * 60 * 60)
    
    runs = [os.path.join(MLRUNS_DIR, d) for d in os.listdir(MLRUNS_DIR) 
            if os.path.isdir(os.path.join(MLRUNS_DIR, d)) and d != "meta.yaml"]
    
    to_delete = []
    saved_space = 0
    
    for run_path in runs:
        mtime = os.path.getmtime(run_path)
        if mtime < cutoff_sec:
            # 這裡可以再加入邏輯：檢查 tags 是否包含 "best" 或 "keep"
            to_delete.append(run_path)

    if not to_delete:
        print(f"沒有超過 {KEEP_MLRUNS_DAYS} 天的舊運行紀錄。")
        return 0

    print(f"預計清理 {len(to_delete)} 個超過 30 天的運行紀錄：")
    for run in to_delete:
        size = get_dir_size(run)
        saved_space += size
        print(f"  [ {'模擬清理' if dry_run else '清理'} ] {os.path.basename(run)} ({format_size(size)})")
        if not dry_run:
            shutil.rmtree(run)

    return saved_space

def main():
    parser = argparse.ArgumentParser(description="tw-top10 專案瘦身工具")
    parser.add_argument("--execute", action="store_true", help="正式執行清理 (不帶此參數則為模擬執行)")
    args = parser.parse_args()

    is_dry_run = not args.execute
    
    if is_dry_run:
        print("="*60)
        print("運行模式：模擬執行 (Dry-run Mode)")
        print("提示：本運行不會實際刪除任何檔案，僅列出清單供審閱。")
        print("要執行正式清理，請使用: python3 scripts/cleanup_project.py --execute")
        print("="*60)
    else:
        print("!"*60)
        print("運行模式：正式執行 (EXECTUE MODE)")
        print("!"*60)

    total_saved = 0
    total_saved += cleanup_models(dry_run=is_dry_run)
    total_saved += cleanup_mlruns(dry_run=is_dry_run)

    print("\n" + "="*60)
    status = "預估可節省" if is_dry_run else "已節省"
    print(f"清理總結：{status} {format_size(total_saved)} 空間。")
    print("="*60)

if __name__ == "__main__":
    main()

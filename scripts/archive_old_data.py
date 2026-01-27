#!/usr/bin/env python3
import os
import pandas as pd
from datetime import datetime

# --- 設定 (Settings) ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_CLEAN_DIR = os.path.join(PROJECT_ROOT, "data", "clean")
DATA_ARCHIVE_DIR = os.path.join(PROJECT_ROOT, "data", "archive")
CUTOFF_DATE = "2024-01-01"

def archive_file(filename):
    file_path = os.path.join(DATA_CLEAN_DIR, filename)
    if not os.path.exists(file_path):
        print(f"檔案 {filename} 不存在，跳過。")
        return

    print(f"\n--- 正在處理 {filename} ---")
    df = pd.read_parquet(file_path)
    
    # 確保 date 欄位是 datetime 格式
    if 'date' not in df.columns:
        print(f"警告: {filename} 找不到 'date' 欄位，無法按日期封存。")
        return
    
    df['date'] = pd.to_datetime(df['date'])
    
    # 切分資料
    archive_mask = df['date'] < CUTOFF_DATE
    df_archive = df[archive_mask]
    df_active = df[~archive_mask]
    
    if len(df_archive) == 0:
        print(f"沒有早於 {CUTOFF_DATE} 的資料，不需封存。")
        return

    print(f"封存項數: {len(df_archive)}")
    print(f"保留項數: {len(df_active)}")
    
    # 儲存封存檔 (使用壓縮)
    archive_filename = f"{os.path.splitext(filename)[0]}_pre_2024.parquet"
    archive_path = os.path.join(DATA_ARCHIVE_DIR, archive_filename)
    
    # 如果封存檔已存在，則合併
    if os.path.exists(archive_path):
        print(f"合併至現有封存檔: {archive_filename}")
        df_old_archive = pd.read_parquet(archive_path)
        df_archive = pd.concat([df_old_archive, df_archive]).drop_duplicates(subset=['date', 'stock_id'])
    
    df_archive.to_parquet(archive_path, compression='snappy')
    print(f"已儲存封存檔至: {archive_path}")
    
    # 更新原始檔 (僅保留 active)
    df_active.to_parquet(file_path, compression='snappy')
    print(f"已更新原始檔案，目前剩餘 {len(df_active)} 筆紀錄。")

def main():
    if not os.path.exists(DATA_ARCHIVE_DIR):
        os.makedirs(DATA_ARCHIVE_DIR)
        
    targets = ["universe.parquet", "features.parquet", "events.parquet"]
    
    for t in targets:
        try:
            archive_file(t)
        except Exception as e:
            print(f"處理 {t} 時發生錯誤: {e}")

    print("\n" + "="*60)
    print("資料封存作業完成。")
    print(f"歷史資料已移至: {DATA_ARCHIVE_DIR}")
    print("="*60)

if __name__ == "__main__":
    main()

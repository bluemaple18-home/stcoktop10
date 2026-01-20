#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日發布腳本
負責：
1. 讀取今日 top10_YYYYMMDD.csv
2. 載入歷史資料並生成技術圖表
3. 生成推薦理由
4. 渲染面板截圖
5. 寫入發布日誌
"""

import os
import sys
from datetime import datetime
from pathlib import Path
import pandas as pd

# 加入模組路徑
sys.path.append(str(Path(__file__).parent))

from chart_generator import generate_all_charts
from reason_generator import generate_reasons_batch
from dashboard_renderer import render_dashboard_to_image, render_simple_summary


def get_project_root() -> Path:
    """取得專案根目錄"""
    return Path(__file__).parent.parent


def log_skip(date: str, log_path: Path):
    """
    記錄跳過
    
    Args:
        date: 日期字串 YYYYMMDD
        log_path: 日誌檔路徑
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(log_path, 'a', encoding='utf-8') as f:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{timestamp}] SKIP: {date} - CSV 檔案不存在\n")
    
    print(f"⚠️  今日選股檔案不存在，已記錄跳過: {date}")


def write_publish_log(date: str, df: pd.DataFrame, log_path: Path, charts_dir: Path, dashboard_path: Path):
    """
    寫入發布日誌
    
    Args:
        date: 日期字串 YYYYMMDD
        df: Top10 DataFrame
        log_path: 日誌檔路徑
        charts_dir: 圖表目錄
        dashboard_path: 面板截圖路徑
    """
    with open(log_path, 'a', encoding='utf-8') as f:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"\n{'='*60}\n")
        f.write(f"[{timestamp}] SUCCESS: {date}\n")
        f.write(f"{'='*60}\n")
        f.write(f"  📊 面板截圖: {dashboard_path}\n")
        f.write(f"  📈 技術圖表目錄: {charts_dir}/ ({len(df)} 張)\n")
        f.write(f"  🎯 Top10 數量: {len(df)}\n")
        f.write(f"\n  【推薦清單】\n")
        for idx, row in df.iterrows():
            rank = idx + 1
            f.write(f"    {rank}. {row['stock_id']} {row['stock_name']} ")
            f.write(f"(期望報酬: {row['expected_return_5d']:.2f}%, 勝率: {row['win_rate']:.1f}%)\n")
        f.write(f"\n")
    
    print(f"✅ 發布日誌已更新: {log_path}")


def load_stock_history_dummy(stock_id: str) -> pd.DataFrame:
    """
    載入個股歷史資料（模擬版本）
    
    TODO: 實際實作應從 DuckDB 或 parquet 檔案讀取
    
    Args:
        stock_id: 股票代號
    
    Returns:
        DataFrame 包含 date, open, high, low, close, volume
    """
    import numpy as np
    
    # 模擬 60 天資料
    dates = pd.date_range(end=datetime.now(), periods=60, freq='D')
    
    # 模擬股價資料（隨機遊走）
    base_price = 100 if stock_id == '2330' else 50
    returns = np.random.randn(60) * 0.02  # 每日報酬率 ±2%
    close_prices = base_price * (1 + returns).cumprod()
    
    # 模擬 OHLC
    df = pd.DataFrame({
        'date': dates,
        'open': close_prices * (1 + np.random.randn(60) * 0.005),
        'high': close_prices * (1 + abs(np.random.randn(60)) * 0.01),
        'low': close_prices * (1 - abs(np.random.randn(60)) * 0.01),
        'close': close_prices,
        'volume': np.random.randint(10000, 100000, 60)
    })
    
    # 確保 high >= close, low <= close
    df['high'] = df[['high', 'close']].max(axis=1)
    df['low'] = df[['low', 'close']].min(axis=1)
    
    print(f"  ⚠️  使用模擬資料（請替換為實際 DuckDB 資料）: {stock_id}")
    
    return df


def main():
    """主程式流程"""
    print("=" * 60)
    print("🚀 TW Top10 每日發布腳本啟動")
    print("=" * 60)
    
    # 取得路徑
    root = get_project_root()
    artifacts_dir = root / "artifacts"
    charts_dir = artifacts_dir / "charts"
    log_path = artifacts_dir / "publish_log.txt"
    
    # 1. 檢查今日 CSV 是否存在
    today = datetime.now().strftime("%Y%m%d")
    csv_path = artifacts_dir / f"top10_{today}.csv"
    
    print(f"\n📅 今日日期: {today}")
    print(f"📂 檢查檔案: {csv_path}")
    
    if not csv_path.exists():
        log_skip(today, log_path)
        return
    
    print(f"✅ 找到選股檔案")
    
    # 2. 載入 CSV
    print(f"\n📊 載入選股資料...")
    try:
        df = pd.read_csv(csv_path, dtype={'stock_id': str})
        print(f"✅ 成功載入 {len(df)} 筆資料")
        print(f"   欄位: {list(df.columns)}")
    except Exception as e:
        print(f"❌ 載入 CSV 失敗: {e}")
        return
    
    # 驗證必要欄位
    required_cols = ['stock_id', 'stock_name', 'expected_return_5d', 'win_rate']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"❌ CSV 缺少必要欄位: {missing_cols}")
        return
    
    # 3. 生成推薦理由
    print(f"\n💡 生成推薦理由...")
    df = generate_reasons_batch(df)
    print(f"✅ 完成推薦理由生成")
    
    # 4. 為每檔股票生成圖表
    print(f"\n📈 生成技術圖表...")
    charts_dir.mkdir(parents=True, exist_ok=True)
    
    chart_results = generate_all_charts(
        top10_df=df,
        data_loader_func=load_stock_history_dummy,  # TODO: 替換為實際資料載入函式
        output_dir=charts_dir
    )
    
    # 5. 渲染面板截圖
    print(f"\n🎨 渲染面板截圖...")
    dashboard_path = artifacts_dir / "top10_dashboard.png"
    
    try:
        render_dashboard_to_image(df, dashboard_path, datetime.now().strftime("%Y-%m-%d"))
        print(f"✅ 面板截圖完成")
    except Exception as e:
        print(f"❌ 渲染面板失敗: {e}")
        return
    
    # 6. 同時產生文字摘要（備用）
    summary_path = artifacts_dir / "top10_summary.txt"
    render_simple_summary(df, summary_path)
    
    # 7. 寫入發布日誌
    print(f"\n📝 寫入發布日誌...")
    write_publish_log(today, df, log_path, charts_dir, dashboard_path)
    
    # 完成
    print("\n" + "=" * 60)
    print("✅ 每日發布完成！")
    print("=" * 60)
    print(f"📊 面板截圖: {dashboard_path}")
    print(f"📈 技術圖表: {charts_dir}/")
    print(f"📝 發布日誌: {log_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()

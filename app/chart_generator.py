#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
技術圖表生成模組
為每檔股票生成 K線圖 + MA + 布林通道 + 量能
"""

import mplfinance as mpf
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    計算技術指標
    
    Args:
        df: 包含 OHLCV 資料的 DataFrame
    
    Returns:
        加入技術指標的 DataFrame
    """
    df = df.copy()
    
    # 計算移動平均線
    df['MA5'] = df['close'].rolling(window=5).mean()
    df['MA20'] = df['close'].rolling(window=20).mean()
    df['MA60'] = df['close'].rolling(window=60).mean()
    
    # 計算布林通道
    df['BB_middle'] = df['close'].rolling(window=20).mean()
    bb_std = df['close'].rolling(window=20).std()
    df['BB_upper'] = df['BB_middle'] + (bb_std * 2)
    df['BB_lower'] = df['BB_middle'] - (bb_std * 2)
    
    return df


def generate_stock_chart(
    stock_id: str, 
    stock_name: str, 
    df: pd.DataFrame, 
    output_path: Path,
    days: int = 250
) -> bool:
    """
    生成個股技術圖表
    
    Args:
        stock_id: 股票代號
        stock_name: 股票名稱
        df: 包含 OHLCV 資料的 DataFrame（需有 date, open, high, low, close, volume 欄位）
        output_path: 圖表輸出路徑
        days: 顯示的天數（預設 60 天）
    
    Returns:
        bool: 成功回傳 True，失敗回傳 False
    """
    try:
        # 確保 date 是 datetime 格式並設為 index
        if 'date' in df.columns:
            df = df.copy()
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
        
        # 確保必要欄位存在
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_cols):
            print(f"❌ 缺少必要欄位: {required_cols}")
            return False
        
        # 取最近 N 天資料
        df = df.tail(days)
        
        # 計算技術指標
        df = calculate_indicators(df)
        
        # 準備附加線圖（MA、布林通道）
        apds = [
            # 移動平均線
            mpf.make_addplot(df['MA5'], color='orange', width=1.2, label='MA5'),
            mpf.make_addplot(df['MA20'], color='blue', width=1.2, label='MA20'),
            
            # 布林通道
            mpf.make_addplot(df['BB_upper'], color='gray', linestyle='--', width=0.8),
            mpf.make_addplot(df['BB_lower'], color='gray', linestyle='--', width=0.8),
        ]
        
        # 自訂樣式
        mc = mpf.make_marketcolors(
            up='red',      # 台股紅漲
            down='green',  # 台股綠跌
            edge='inherit',
            wick='inherit',
            volume='in',
            alpha=0.9
        )
        
        s = mpf.make_mpf_style(
            marketcolors=mc,
            gridstyle='-',
            gridcolor='lightgray',
            facecolor='white',
            figcolor='white',
            y_on_right=False
        )
        
        # 確保輸出目錄存在
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 繪製圖表
        mpf.plot(
            df,
            type='candle',
            style=s,
            addplot=apds,
            volume=True,
            title=f'{stock_id} {stock_name} - 技術分析圖',
            ylabel='價格 (TWD)',
            ylabel_lower='成交量',
            figsize=(12, 8),
            savefig=output_path,
            tight_layout=True
        )
        
        print(f"✅ 已生成圖表: {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ 生成圖表失敗 ({stock_id}): {e}")
        return False


def generate_all_charts(
    top10_df: pd.DataFrame,
    data_loader_func,
    output_dir: Path
) -> dict:
    """
    批次生成所有股票的技術圖表
    
    Args:
        top10_df: Top10 清單（需包含 stock_id, stock_name 欄位）
        data_loader_func: 載入歷史資料的函式，簽章為 func(stock_id) -> DataFrame
        output_dir: 圖表輸出目錄
    
    Returns:
        dict: {stock_id: 圖表路徑或 None}
    """
    results = {}
    
    for idx, row in top10_df.iterrows():
        stock_id = str(row['stock_id'])
        stock_name = row['stock_name']
        
        print(f"\n📊 正在生成圖表: {stock_id} {stock_name}")
        
        # 載入歷史資料
        try:
            hist_df = data_loader_func(stock_id)
            if hist_df is None or len(hist_df) < 20:
                print(f"⚠️  資料不足，跳過 {stock_id}")
                results[stock_id] = None
                continue
        except Exception as e:
            print(f"❌ 載入資料失敗 ({stock_id}): {e}")
            results[stock_id] = None
            continue
        
        # 生成圖表
        chart_path = output_dir / f"{stock_id}.png"
        success = generate_stock_chart(stock_id, stock_name, hist_df, chart_path)
        
        results[stock_id] = chart_path if success else None
    
    # 統計
    success_count = sum(1 for v in results.values() if v is not None)
    print(f"\n📈 圖表生成完成: {success_count}/{len(top10_df)}")
    
    return results

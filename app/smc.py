import pandas as pd
import numpy as np
from typing import Dict, List, Tuple

def detect_swing_points(df: pd.DataFrame, left_bars: int = 5, right_bars: int = 5) -> pd.DataFrame:
    """
    檢測 Swing Highs 和 Swing Lows
    """
    df = df.copy()
    
    # 使用 rolling 找出局部最值
    df['is_high'] = (df['high'] == df['high'].rolling(window=left_bars + right_bars + 1, center=True).max())
    df['is_low'] = (df['low'] == df['low'].rolling(window=left_bars + right_bars + 1, center=True).min())
    
    # 標記 Swing Point 價格
    df['sh_price'] = np.where(df['is_high'], df['high'], np.nan)
    df['sl_price'] = np.where(df['is_low'], df['low'], np.nan)
    
    return df

def calculate_fvg(df: pd.DataFrame) -> pd.DataFrame:
    """
    實作 Fair Value Gaps (FVG)
    """
    df = df.copy()
    
    # Bullish FVG: K1 High < K3 Low
    df['fvg_bulk'] = np.where((df['high'].shift(2) < df['low']), 1, 0)
    df['fvg_uptop'] = np.where(df['fvg_bulk'] == 1, df['low'], np.nan)
    df['fvg_upbot'] = np.where(df['fvg_bulk'] == 1, df['high'].shift(2), np.nan)
    
    # Bearish FVG: K1 Low > K3 High
    df['fvg_bear'] = np.where((df['low'].shift(2) > df['high']), -1, 0)
    df['fvg_dntop'] = np.where(df['fvg_bear'] == -1, df['low'].shift(2), np.nan)
    df['fvg_dnbot'] = np.where(df['fvg_bear'] == -1, df['high'], np.nan)
    
    return df

def calculate_smc(df: pd.DataFrame) -> pd.DataFrame:
    """
    實作 SMC 核心邏輯: BOS, CHOCH, Order Blocks
    """
    df = detect_swing_points(df)
    df = calculate_fvg(df)
    
    # 用於追蹤最近的結構點
    last_sh = np.nan
    last_sl = np.nan
    trend = 0 # 1: Bullish, -1: Bearish
    
    bos = []
    choch = []
    ob_top = []
    ob_bot = []
    
    # 追蹤最後一根反向 K 線 (Order Block 候選人)
    last_red_candle = None # (high, low)
    last_green_candle = None # (high, low)
    
    for i in range(len(df)):
        row = df.iloc[i]
        close = row['close']
        open_p = row['open']
        high = row['high']
        low = row['low']
        
        # 紀錄反向 K 線
        if close < open_p: last_red_candle = (high, low)
        if close > open_p: last_green_candle = (high, low)
        
        # 更新 Swing Points
        if not np.isnan(row['sh_price']): last_sh = row['sh_price']
        if not np.isnan(row['sl_price']): last_sl = row['sl_price']
        
        current_bos = 0
        current_choch = 0
        current_ob_top = np.nan
        current_ob_bot = np.nan
        
        # 檢測結構破壞
        if trend >= 0 and not np.isnan(last_sh) and close > last_sh:
            current_bos = 1 if trend == 1 else 0
            current_choch = 1 if trend == -1 else 0
            trend = 1
            last_sh = np.nan 
            # 標記 Bullish Order Block (破壞前的最後一根紅棒)
            if last_red_candle:
                current_ob_top, current_ob_bot = last_red_candle
                
        elif trend <= 0 and not np.isnan(last_sl) and close < last_sl:
            current_bos = -1 if trend == -1 else 0
            current_choch = -1 if trend == 1 else 0
            trend = -1
            last_sl = np.nan
            # 標記 Bearish Order Block (破壞前的最後一根綠棒)
            if last_green_candle:
                current_ob_top, current_ob_bot = last_green_candle
            
        bos.append(current_bos)
        choch.append(current_choch)
        ob_top.append(current_ob_top)
        ob_bot.append(current_ob_bot)
    
    df['bos'] = bos
    df['choch'] = choch
    df['ob_top'] = ob_top
    df['ob_bot'] = ob_bot
    
    return df

if __name__ == "__main__":
    # 簡單測試
    data = {
        'open':  [100, 102, 101, 105, 104, 110, 108, 115],
        'high':  [105, 106, 104, 110, 109, 115, 114, 120],
        'low':   [98,  100, 99,  103, 102, 108, 107, 113],
        'close': [102, 104, 102, 108, 106, 113, 111, 118]
    }
    test_df = pd.DataFrame(data)
    result = calculate_smc(test_df)
    print("SMC 計算測試結果:")
    print(result[['close', 'bos', 'choch', 'ob_top', 'fvg_bulk']])

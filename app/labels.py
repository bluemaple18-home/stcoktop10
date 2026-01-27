
import pandas as pd
import numpy as np

class LabelGenerator:
    """
    負責生成模型訓練用的標籤 (Labels)
    核心邏輯：
    1. Signal Day: D
    2. Entry: D+1 開盤價 (Open)
    3. Exit: D+N 收盤價 (Close) (N=horizon)
    4. Return: (Exit - Entry) / Entry
    5. Target: 1 if Return > threshold else 0 (Binary Classification)
    """
    
    def __init__(self, horizon: int = 10, threshold: float = 0.05):
        self.horizon = horizon
        self.threshold = threshold
        
    def generate_labels(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        生成標籤
        
        Args:
            df: 包含 OHLC 資料的 DataFrame (必須包含 stock_id, date, open, close)
            
        Returns:
            df: 包含 entry_price, exit_price, return_5d, target 的 DataFrame
        """
        # 避免修改原始 Frame
        df = df.copy()
        
        # 檢查欄位
        required = {'stock_id', 'date', 'open', 'close'}
        if not required.issubset(df.columns):
            raise ValueError(f"缺少必要欄位，需求: {required}, 實際: {df.columns.tolist()}")
            
        # 排序確保 shift 邏輯正確
        df = df.sort_values(['stock_id', 'date'])
        
        # 1. Entry Price: D+1 Open
        df['entry_price'] = df.groupby('stock_id')['open'].shift(-1)
        
        # New Logic: Rolling Windows
        # Target: 
        #   (1) Max High in next 20 days >= Entry * 1.05 (Profit 5%)
        #   (2) Min Low in next 5 days > Entry * 0.95 (Survival > 5 days, Stop Loss 5%)
        
        indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=20)
        df['future_max_20d'] = df.groupby('stock_id')['high'].rolling(window=indexer).max().reset_index(0, drop=True)
        # Shift back 1 to align with Signal Date (since window includes current row, we want window starting next day?)
        # Actually rolling forward on sorted date includes 'current' row. 
        # We need "Next 20 days from Entry Day". Entry is D+1.
        # So we want window(20) starting at D+1.
        # Which is shift(-1).rolling.
        
        # Let's simple logical equivalent:
        # Shift -1 to align to D+1
        # Then rolling max forward.
        
        # Max Price in [D+1, D+20]
        # Rolling(20) on D+1 (features at D+1) gives max in [D+1...D+20]
        # So we simply need to shift the rolling result? 
        # No, forward rolling at T includes T...T+W.
        # So forward_rolling(20) at T+1 covers T+1...T+20.
        
        # Implementation:
        # 1. Align valid High/Low series
        highs = df.groupby('stock_id')['high']
        lows = df.groupby('stock_id')['low']
        
        # 2. Compute Forward Rolling
        idx_20 = pd.api.indexers.FixedForwardWindowIndexer(window_size=20)
        idx_5 = pd.api.indexers.FixedForwardWindowIndexer(window_size=5)
        
        # Max High next 20 days (from tomorrow's perspective)
        # We shift results by -1 to put (Max of D+1...D+20) onto D
        # Wait, Entry is at D+1.
        # We want to know if trade taken at D+1 (Open) succeeds.
        # So we look at Highs from D+1 to D+20.
        
        # Step A: Get Highs shifted by -1 (starts at D+1)
        # Step B: Rolling Max (20) on that.
        # But rolling works on index.
        
        # Easier way:
        # Compute Rolling Max on whole series first (forward).
        # max_high_forward_20[t] = max(high[t]...high[t+19])
        # We want max(high[t+1]...high[t+20])
        # So we just taking max_high_forward_20 shifted by -1.
        
        df['high_roll_20'] = df.groupby('stock_id')['high'].transform(
            lambda x: x.rolling(window=idx_20).max().shift(-1)
        )
        
        df['low_roll_5'] = df.groupby('stock_id')['low'].transform(
            lambda x: x.rolling(window=idx_5).min().shift(-1)
        )
        
        # Generate Target
        # Profit Target: 5% (1.05)
        # Stop Loss: 5% (0.95)
        
        cond_profit = df['high_roll_20'] >= (df['entry_price'] * (1 + self.threshold))
        cond_survive = df['low_roll_5'] > (df['entry_price'] * (1 - self.threshold))
        
        df['target'] = (cond_profit & cond_survive).astype(int)
        
        # Fill helper cols for debug
        df['future_return'] = (df['high_roll_20'] / df['entry_price']) - 1
        df['return_5d'] = df['future_return']
        df['exit_price'] = df['high_roll_20']
        
        # 統計
        valid_count = df['future_return'].notna().sum()
        positive_count = df['target'].sum()
        ratio = positive_count / valid_count if valid_count > 0 else 0
        print(f"✓ 已生成標籤: {valid_count} 筆有效樣本 (Horizon={self.horizon}d, Threshold={self.threshold:.1%})")
        print(f"  - 正樣本數: {positive_count} ({ratio:.1%})")
        
        return df

"""
技術指標計算模組 (向量化優化版)
使用 Pandas 向量化運算取代迴圈，大幅提升計算效能
"""

import pandas as pd
import numpy as np
import logging
from typing import Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """技術指標計算器 (向量化版本)"""
    
    def __init__(self, df: pd.DataFrame):
        """
        初始化技術指標計算器
        
        Args:
            df: 必須包含 date, stock_id, open, high, low, close, volume 欄位
        """
        self.df = df.copy()
        # 確保資料型態正確
        self.df['date'] = pd.to_datetime(self.df['date'])
        self.df = self.df.sort_values(['date', 'stock_id'])
        
        # 準備寬表格 (Wide Format) 用於向量化計算
        # Index: Date, Columns: StockID
        logger.info("準備向量化資料結構...")
        self.pivots = {}
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in self.df.columns:
                self.pivots[col] = self.df.pivot(index='date', columns='stock_id', values=col)

    def _merge_indicator(self, indicator_df: pd.DataFrame, name: str):
        """
        將計算好的寬表格指標合併回原始長表格
        
        Args:
            indicator_df: 寬表格指標 (Index: Date, Columns: StockID)
            name: 指標名稱
        """
        # Melt 回長表格
        melted = indicator_df.melt(ignore_index=False, var_name='stock_id', value_name=name).reset_index()
        
        # 合併回 self.df
        # 注意: 這裡假設 self.df 與 melted 的 keys (date, stock_id) 是完全對齊的
        # 為了效能，我們使用 set_index 後的賦值，避免昂貴的 merge
        if 'date' in self.df.columns and 'stock_id' in self.df.columns:
            self.df = self.df.set_index(['date', 'stock_id'])
            melted = melted.set_index(['date', 'stock_id'])
            self.df[name] = melted[name]
            self.df = self.df.reset_index()
        else:
            # Fallback
            self.df = self.df.merge(melted, on=['date', 'stock_id'], how='left')

    def calculate_ma(self, periods: list = [5, 10, 20, 60]) -> pd.DataFrame:
        """計算移動平均線 (MA) - 向量化"""
        logger.info(f"計算移動平均線 (Vectorized): {periods}")
        
        close = self.pivots['close']
        
        for period in periods:
            # 直接對整個寬表格做 rolling mean
            ma = close.rolling(window=period).mean()
            self._merge_indicator(ma, f'ma{period}')
            
        return self.df
    
    def calculate_ema(self, periods: list = [12, 26]) -> pd.DataFrame:
        """計算指數移動平均線 (EMA) - 向量化"""
        logger.info(f"計算指數移動平均線 (Vectorized): {periods}")
        
        close = self.pivots['close']
        
        for period in periods:
            ema = close.ewm(span=period, adjust=False).mean()
            self._merge_indicator(ema, f'ema{period}')
            
        return self.df
    
    def calculate_macd(self, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        """計算 MACD 指標 - 向量化"""
        logger.info("計算 MACD 指標 (Vectorized)")
        
        close = self.pivots['close']
        
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        
        dif = ema_fast - ema_slow
        dem = dif.ewm(span=signal, adjust=False).mean()
        osc = dif - dem
        
        self._merge_indicator(dif, 'macd')
        self._merge_indicator(dem, 'macd_signal')
        self._merge_indicator(osc, 'macd_hist')
        
        return self.df
    
    def calculate_rsi(self, period: int = 14) -> pd.DataFrame:
        """計算 RSI 指標 (Wilder's Smoothing) - 向量化"""
        logger.info(f"計算 RSI 指標 (Vectorized, 週期={period})")
        
        close = self.pivots['close']
        delta = close.diff()
        
        # 分離漲跌
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        
        # Wilder's Smoothing
        # First value is SMA, subsequent are (prev * (n-1) + curr) / n
        # This is equivalent to ewm(alpha=1/n, adjust=False)
        avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        self._merge_indicator(rsi, 'rsi')
        
        return self.df
    
    def calculate_kd(self, k_period: int = 9, d_period: int = 3, smooth_k: int = 3) -> pd.DataFrame:
        """計算 KD 指標 - 向量化"""
        logger.info("計算 KD 指標 (Vectorized)")
        
        close = self.pivots['close']
        high = self.pivots['high']
        low = self.pivots['low']
        
        # RSV
        low_min = low.rolling(window=k_period).min()
        high_max = high.rolling(window=k_period).max()
        rsv = 100 * (close - low_min) / (high_max - low_min)
        
        # K = 2/3 * Prev_K + 1/3 * RSV
        # This is equivalent to EMA with alpha=1/3 (or span=5) if we enable adjust=False
        # However, standard KD uses SMA for initial or specific recursive formula
        # Pandas ewm is close enough. Standard definition:
        # K = RSV.ewm(com=2).mean() # com=2 means alpha=1/(2+1)=1/3
        k = rsv.ewm(alpha=1/3, adjust=False).mean()
        d = k.ewm(alpha=1/3, adjust=False).mean()
        
        self._merge_indicator(k, 'k')
        self._merge_indicator(d, 'd')
        
        return self.df
    
    def calculate_bollinger_bands(self, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
        """計算布林通道 - 向量化"""
        logger.info(f"計算布林通道 (Vectorized, 週期={period})")
        
        close = self.pivots['close']
        
        ma = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()
        
        upper = ma + (std * std_dev)
        lower = ma - (std * std_dev)
        width = (upper - lower) / ma
        
        self._merge_indicator(upper, 'bb_upper')
        self._merge_indicator(ma, 'bb_middle')
        self._merge_indicator(lower, 'bb_lower')
        self._merge_indicator(width, 'bb_width')
        
        return self.df
    
    def calculate_breakout_flag(self, lookback_period: int = 60) -> pd.DataFrame:
        """計算前高突破旗標 - 向量化"""
        logger.info(f"計算前高突破旗標 (Vectorized, 回溯={lookback_period})")
        
        close = self.pivots['close']
        high = self.pivots['high']
        
        # 過去 N 日最高價 (不含今日) -> shift(1)
        rolling_max = high.shift(1).rolling(window=lookback_period).max()
        
        breakout = (close > rolling_max).astype(int)
        
        self._merge_indicator(breakout, 'breakout_flag')
        
        return self.df
        
    def calculate_volume_spike(self, ma_period: int = 20, multiplier: float = 2.0) -> pd.DataFrame:
        """計算量能突增 - 向量化"""
        logger.info("計算量能突增 (Vectorized)")
        
        volume = self.pivots['volume']
        vol_ma = volume.rolling(window=ma_period).mean()
        
        spike = (volume > (vol_ma * multiplier)).astype(int)
        
        self._merge_indicator(spike, 'volume_spike')
        return self.df
    
    def calculate_position_indicators(self, periods: list = [60, 250]) -> pd.DataFrame:
        """
        計算相對位階指標 (受 StockSniper 啟發)
        
        這些指標能讓 AI 學會「位置判斷」：
        - 在低檔買進通常勝率較高
        - 在高檔追買風險較大
        
        Args:
            periods: 回溯期間 (預設 60天=季線, 250天=年線)
        """
        logger.info(f"計算位階指標 (Vectorized): {periods}天回溯")
        
        close = self.pivots['close']
        high = self.pivots['high']
        low = self.pivots['low']
        
        for period in periods:
            # 計算滾動高低點
            rolling_high = high.rolling(window=period).max()
            rolling_low = low.rolling(window=period).min()
            
            # 距高點百分比 (負數代表低於高點)
            pct_from_high = ((close - rolling_high) / rolling_high) * 100
            self._merge_indicator(pct_from_high, f'pct_from_high_{period}d')
            
            # 距低點百分比 (正數代表高於低點)
            pct_from_low = ((close - rolling_low) / rolling_low) * 100
            self._merge_indicator(pct_from_low, f'pct_from_low_{period}d')
            
            # 相對位置 (0-1之間，0=低點，1=高點)
            range_val = rolling_high - rolling_low
            relative_position = (close - rolling_low) / range_val
            relative_position = relative_position.clip(0, 1)  # 防止除0或異常值
            self._merge_indicator(relative_position, f'relative_position_{period}d')
        
        return self.df

    def calculate_revenue_factors(self) -> pd.DataFrame:
        """
        計算基礎基本面因子 (需有 'close' 與 'revenue' 資料)
        暫時使用 'close' 模擬展示 (因目前資料源尚未整合營收至此 DataFrame)
        
        TODO: 當資料源整合後，此處應使用 self.pivots['revenue']
        目前僅實作架構供未來擴充
        """
        # 檢查是否有營收資料
        if 'revenue' not in self.pivots:
            # 嘗試從 columns 找
            if 'revenue' in self.df.columns:
                 self.pivots['revenue'] = self.df.pivot(index='date', columns='stock_id', values='revenue')
            else:
                logger.warning("無營收資料，跳過基本面因子計算")
                return self.df
                
        logger.info("計算基本面因子 (Vectorized)")
        revenue = self.pivots['revenue']
        
        # 營收動能: 近 3 月平均營收 / 近 12 月最大營收
        rev_ma3 = revenue.rolling(window=3).mean()
        rev_max12 = revenue.rolling(window=12).max()
        
        rev_momentum = rev_ma3 / rev_max12
        
        self._merge_indicator(rev_momentum, 'revenue_momentum')
        return self.df

    def calculate_ma_squeeze(self, periods: list = [5, 10, 20, 60]) -> pd.DataFrame:
        """計算均線糾結指標 (各均線間的最大差距)"""
        logger.info(f"計算均線糾結指標 (Vectorized): {periods}")
        
        ma_cols = [f'ma{p}' for p in periods]
        # 確保這些 MA 已經計算過
        for col in ma_cols:
            if col not in self.df.columns:
                self.calculate_ma([int(col[2:])])
        
        # 提取這些 MA 欄位並轉為寬表格
        ma_pivots = [self.df.pivot(index='date', columns='stock_id', values=col) for col in ma_cols]
        
        # 計算最大值與最小值之差 / 平均值
        ma_stack = np.stack(ma_pivots)
        ma_max = np.max(ma_stack, axis=0)
        ma_min = np.min(ma_stack, axis=0)
        ma_avg = np.mean(ma_stack, axis=0)
        
        squeeze = (ma_max - ma_min) / ma_avg
        self._merge_indicator(pd.DataFrame(squeeze, index=ma_pivots[0].index, columns=ma_pivots[0].columns), 'ma_squeeze')
        
        return self.df

    def calculate_bias_ratio(self, periods: list = [5, 10, 20, 60]) -> pd.DataFrame:
        """計算乖離率 (Bias Ratio)"""
        logger.info(f"計算乖離率 (Vectorized): {periods}")
        
        close = self.pivots['close']
        for period in periods:
            ma_col = f'ma{period}'
            if ma_col not in self.df.columns:
                self.calculate_ma([period])
            
            ma = self.df.pivot(index='date', columns='stock_id', values=ma_col)
            bias = (close - ma) / ma
            self._merge_indicator(bias, f'bias_{period}')
            
        return self.df

    def calculate_binary_events(self) -> pd.DataFrame:
        """計算二元事件特徵 (Binary Events) 供模型與解釋使用"""
        logger.info("計算二元事件特徵 (Vectorized)")
        
        # 基本欄位引用
        close = self.pivots['close']
        open_ = self.pivots['open']
        high = self.pivots['high']
        low = self.pivots['low']
        volume = self.pivots['volume']
        
        # 1. 突破近 20 日新高 (break_20d_high)
        # shift(1) 確保不包含今日，嚴格突破
        rolling_max_20 = high.shift(1).rolling(window=20).max()
        self._merge_indicator((close > rolling_max_20).astype(int), 'break_20d_high')

        # 2. MA5 上穿 MA20 (ma5_cross_ma20_up)
        # 需確保 MA 已計算
        if 'ma5' not in self.pivots or 'ma20' not in self.pivots:
            self.calculate_ma([5, 20])
        ma5 = self.df.pivot(index='date', columns='stock_id', values='ma5')
        ma20 = self.df.pivot(index='date', columns='stock_id', values='ma20')
        
        # 黃金交叉: 今天 MA5 > MA20 且 昨天 MA5 <= MA20
        cross_up = (ma5 > ma20) & (ma5.shift(1) <= ma20.shift(1))
        self._merge_indicator(cross_up.astype(int), 'ma5_cross_ma20_up')
        
        # 死亡交叉: 今天 MA5 < MA20 且 昨天 MA5 >= MA20
        cross_down = (ma5 < ma20) & (ma5.shift(1) >= ma20.shift(1))
        self._merge_indicator(cross_down.astype(int), 'ma5_cross_ma20_down')

        # 3. 收盤站上布林中軌 (close_above_bb_mid)
        # 中軌通常是 MA20
        mid = ma20
        above_mid = (close > mid) & (close.shift(1) <= mid.shift(1))
        self._merge_indicator(above_mid.astype(int), 'close_above_bb_mid')
        
        # 收盤跌破布林中軌
        below_mid = (close < mid) & (close.shift(1) >= mid.shift(1))
        self._merge_indicator(below_mid.astype(int), 'close_below_bb_mid')

        # 4. MACD 金叉/死叉
        if 'macd' not in self.pivots or 'macd_signal' not in self.pivots:
            self.calculate_macd()
        dif = self.df.pivot(index='date', columns='stock_id', values='macd')
        dem = self.df.pivot(index='date', columns='stock_id', values='macd_signal')
        
        macd_bull = (dif > dem) & (dif.shift(1) <= dem.shift(1))
        macd_bear = (dif < dem) & (dif.shift(1) >= dem.shift(1))
        self._merge_indicator(macd_bull.astype(int), 'macd_bullish_cross')
        self._merge_indicator(macd_bear.astype(int), 'macd_bearish_cross')

        # 5. RSI 反彈 (rsi_rebound_from_40)
        # 假設: RSI 昨天 < 40 且 今天 > 40 (或今天回升勾頭?)
        # 用戶定義: "rsi_rebound_from_40" -> 簡單定義為從下往上穿過 40
        if 'rsi' not in self.pivots:
            self.calculate_rsi()
        rsi = self.df.pivot(index='date', columns='stock_id', values='rsi')
        
        rsi_rebound = (rsi > 40) & (rsi.shift(1) <= 40)
        self._merge_indicator(rsi_rebound.astype(int), 'rsi_rebound_from_40')
        
        # RSI 轉弱 (跌破 50)
        rsi_weak = (rsi < 50) & (rsi.shift(1) >= 50)
        self._merge_indicator(rsi_weak.astype(int), 'rsi_break_below_50')

        # 6. 量能突增 (volume_spike) > 20日均量 1.5倍
        vol_ma20 = volume.rolling(window=20).mean()
        vol_spike = (volume > (vol_ma20 * 1.5)).astype(int)
        self._merge_indicator(vol_spike, 'volume_spike_1.5x') # 區分原版

        # 7. 跳空強勢 (gap_up_close_strong)
        # 定義: 今天開盤 > 昨天最高 (跳空) 且 收盤 > 開盤 (紅K)
        gap_up = (open_ > high.shift(1)) & (close > open_)
        self._merge_indicator(gap_up.astype(int), 'gap_up_close_strong')

        # 8. 長上影線 (long_upper_shadow)
        # 定義: (High - Max(Open, Close)) > Body * 2 (Bar body)
        body = (close - open_).abs()
        upper_shadow = high - np.maximum(close, open_)
        # 避免除以 0: Body 極小時，影線長度 > 股價 0.5%? (簡單版: 影線 > 实体 * 2 且 影線長度 > 收盤價 * 0.01)
        long_shadow = (upper_shadow > body * 2) & (upper_shadow > close * 0.005)
        self._merge_indicator(long_shadow.astype(int), 'long_upper_shadow')
        
        return self.df

    def calculate_all_indicators(self) -> pd.DataFrame:
        """一次計算所有技術指標"""
        logger.info("開始計算所有技術指標 (Vectorized)...")
        
        self.calculate_ma()
        self.calculate_ema()
        self.calculate_macd()
        self.calculate_rsi()
        self.calculate_kd()
        self.calculate_bollinger_bands()
        self.calculate_breakout_flag()
        self.calculate_volume_spike()
        self.calculate_position_indicators()
        self.calculate_ma_squeeze()
        self.calculate_bias_ratio()
        self.calculate_revenue_factors()
        
        # 計算二元事件
        self.calculate_binary_events()
        
        logger.info("所有技術指標計算完成！")
        return self.df

    def get_missing_rate(self) -> pd.Series:
        """計算各欄位缺值率"""
        missing_rate = (self.df.isnull().sum() / len(self.df) * 100).round(2)
        return missing_rate.sort_values(ascending=False)


if __name__ == "__main__":
    # 測試程式碼
    import time
    from pathlib import Path
    
    print("生成測試資料...")
    # 建立一個假的測試資料集: 100 檔股票, 500 天
    dates = pd.date_range(end=pd.Timestamp.now(), periods=500, freq='B')
    stock_ids = [f"{i:04d}" for i in range(1101, 1201)] # 100 檔
    
    data = []
    for sid in stock_ids:
        # Random walk prices
        base_price = 100
        closes = base_price * (1 + np.random.randn(500) * 0.02).cumprod()
        opens = closes * (1 + np.random.randn(500) * 0.01)
        highs = np.maximum(opens, closes) * (1 + abs(np.random.randn(500) * 0.01))
        lows = np.minimum(opens, closes) * (1 - abs(np.random.randn(500) * 0.01))
        volumes = np.random.randint(100, 5000, 500) * 1000
        
        df_stock = pd.DataFrame({
            'date': dates,
            'stock_id': sid,
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'volume': volumes
        })
        data.append(df_stock)
        
    full_df = pd.concat(data)
    print(f"測試資料規模: {len(full_df)} 筆 (100 檔 x 500 天)")
    
    start_time = time.time()
    ti = TechnicalIndicators(full_df)
    result = ti.calculate_all_indicators()
    end_time = time.time()
    
    print(f"\n計算耗時: {end_time - start_time:.4f} 秒")
    print(f"結果欄位: {list(result.columns)}")
    print(result.tail())

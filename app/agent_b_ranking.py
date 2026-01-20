#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent B - 每日排名模組 (增強版)
負責預測、規則評分、融合與輸出 Top10/Watchlist
"""

import pandas as pd
import numpy as np
import pickle
import yaml
from pathlib import Path
from datetime import datetime
from sklearn.preprocessing import MinMaxScaler
import warnings

warnings.filterwarnings('ignore')

class StockRanker:
    """股票排名器，支援 LightGBM 預測與規則分數卡融合"""
    
    def __init__(self, data_dir: str = "data/clean", model_dir: str = "models",
                 artifact_dir: str = "artifacts", config_path: str = "config/signals.yaml"):
        """
        初始化排名器
        """
        self.data_dir = Path(data_dir)
        self.model_dir = Path(model_dir)
        self.artifact_dir = Path(artifact_dir)
        self.config_path = Path(config_path)
        self.model = None
        
        # 載入設定
        self.config = self._load_config()
        self.weights = self.config['scoring']['weights']
        self.buy_threshold = self.config['scoring'].get('buy_threshold', 3)
        self.max_bearish = self.config['scoring'].get('max_bearish', -2)
        self.alpha = self.config['scoring'].get('alpha', 0.5)
        self.top_reasons_count = self.config['scoring'].get('top_reasons', 3)
        
        # 建立必要目錄
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> dict:
        """載入 signals.yaml 設定"""
        if not self.config_path.exists():
            print(f"⚠ 找不到設定檔 {self.config_path}，使用預設值")
            return {
                'scoring': {
                    'weights': {},
                    'buy_threshold': 3,
                    'max_bearish': -2,
                    'alpha': 0.5,
                    'top_reasons': 3
                }
            }
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def load_model(self, filename: str = "latest_lgbm.pkl"):
        """載入 LightGBM 模型"""
        model_path = self.model_dir / filename
        if not model_path.exists():
            raise FileNotFoundError(f"模型檔案不存在: {model_path}")
        
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)
        print(f"✓ 載入模型: {model_path}")
        return self.model

    def load_daily_data(self, target_date: str = None) -> tuple:
        """
        載入今日 Universe, Features 與 Events
        """
        # 載入 parquet 檔案
        try:
            features = pd.read_parquet(self.data_dir / "features.parquet")
            universe = pd.read_parquet(self.data_dir / "universe.parquet")
            events = pd.read_parquet(self.data_dir / "events.parquet")
        except FileNotFoundError as e:
            raise FileNotFoundError(f"必要的資料檔案缺失: {e}")

        # 決定日期
        if target_date is None:
            target_date = features['date'].max()
            if isinstance(target_date, str):
                pass # already string
            else:
                 # Check if date is datetime object
                target_date = target_date.strftime("%Y-%m-%d")

        print(f"📅 處理日期: {target_date}")

        # 篩選當日資料
        def filter_date(df, date_col='date'):
            if df[date_col].dtype == 'object':
                return df[df[date_col] == target_date]
            else:
                # 假設是 datetime
                return df[df[date_col].astype(str) == target_date]

        daily_features = filter_date(features)
        daily_universe = filter_date(universe)
        daily_events = filter_date(events)

        # 合併 Universe 與 Features (Inner Join)
        # 確保 Universe 有 'name' 欄位，若無則嘗試從其他來源補或留空
        if 'name' not in daily_universe.columns:
            daily_universe['name'] = daily_universe['symbol'] # Fallback
            
        merged_df = daily_universe.merge(
            daily_features, on=['symbol', 'date'], how='inner'
        )
        
        # 合併 Events (Left Join)
        merged_df = merged_df.merge(
            daily_events, on=['symbol', 'date'], how='left'
        )
        
        # 填充 Events 的 NaN 為 0 (假設無紀錄即無事件)
        event_cols = [col for col in self.weights.keys() if col in events.columns]
        merged_df[event_cols] = merged_df[event_cols].fillna(0)

        print(f"✓ 資料載入完成: {len(merged_df)} 筆 (Universe + Features + Events)")
        return merged_df

    def calculate_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        計算規則分數與融合分數
        """
        df = df.copy()
        
        # 1. 模型分數 (Model Score)
        if self.model:
            # 排除非特徵欄位
            exclude_cols = ['symbol', 'date', 'target', 'name', 'industry', 'market', 'status'] + \
                           list(self.weights.keys()) # 排除事件欄位
            feature_cols = [c for c in df.columns if c not in exclude_cols and c in self.model.feature_name()]
            
            # 確保特徵存在
            X = df[feature_cols]
            df['expected_return_5d'] = self.model.predict(X)
        else:
            df['expected_return_5d'] = 0.0

        # 2. 規則分數 (Rule Score)
        pos_score = pd.Series(0.0, index=df.index)
        neg_score = pd.Series(0.0, index=df.index)
        
        for event, weight in self.weights.items():
            if event in df.columns:
                # 確保是數值 (0/1)
                triggered = df[event].astype(float) > 0
                score_contrib = triggered * abs(weight)
                
                if weight > 0:
                    pos_score += score_contrib
                else:
                    neg_score -= score_contrib # 負分累積
        
        df['pos_score'] = pos_score
        df['neg_score'] = neg_score
        df['rule_score'] = pos_score + neg_score
        
        # 3. 分數融合 (Fusion)
        # Normalize rule score to be comparable to returns (e.g. divide by 100 or minmax)
        # 使用簡單縮放：rule_score / 20 (假設滿分約 20) 大約對應 0~1 之間，再乘上類似 return 的 scale?
        # 或是依照指示: normalize(rule_score)
        # 這裡採用 MinMax Scaling (當日) 映射到 [0, 1] 區間，再平移至 [-0.5, 0.5] 以符合 alpha 混合?
        # 為了穩健，我們將 rule_score 除以 100，使其落在 [-0.15, 0.15] 區間，與 return 類似
        # 或者使用 Rank Percentile (0~1)
        
        df['rule_score_norm'] = df['rule_score'] / 100.0 
        
        # 融合: final = alpha * model + (1-alpha) * rule_norm
        df['final_score'] = self.alpha * df['expected_return_5d'] + (1 - self.alpha) * df['rule_score_norm']
        
        # 4. 估算 Winrate (Sigmoid of final score scaled)
        # 簡單 heuristic: 0.5 + tanh(score * k) / 2
        df['winrate'] = (1 / (1 + np.exp(-df['final_score'] * 20))).clip(0, 0.99)

        return df

    def generate_reasons_string(self, row) -> str:
        """
        生成理由字串
        """
        reasons = []
        
        # 收集觸發的事件
        triggered_events = []
        for event, weight in self.weights.items():
            if event in row and row[event] > 0:
                triggered_events.append((event, weight))
        
        # 依權重絕對值排序 (大到小)
        triggered_events.sort(key=lambda x: abs(x[1]), reverse=True)
        
        # 取 Top N
        top_events = triggered_events[:self.top_reasons_count]
        
        # 轉換為文字
        # 模板映射 (Hardcoded for now based on instructions, can be moved to config)
        templates = {
            'break_20d_high': "突破20日高",
            'ma5_cross_ma20_up': "MA5上穿MA20",
            'close_above_bb_mid': "站上布林中軌",
            'macd_bullish_cross': "MACD金叉",
            'rsi_rebound_from_40': "RSI回升",
            'gap_up_close_strong': "跳空強勢",
            'volume_spike': "量能突增",
            'revenue_momentum': "營收動能",
            'rev_yoy_positive': "營收成長",
            'eps_accel': "EPS加速",
            'lose_20d_low': "⚠破20日低",
            'ma5_cross_ma20_down': "⚠MA死叉",
            'close_below_bb_mid': "⚠破布林中軌",
            'macd_bearish_cross': "⚠MACD死叉",
            'rsi_break_below_50': "⚠RSI轉弱",
            'long_upper_shadow': "⚠長上影線"
        }
        
        for event, weight in top_events:
            name = templates.get(event, event)
            if weight < 0 and "⚠" not in name:
                name = f"⚠{name}"
            reasons.append(name)
            
        return " | ".join(reasons)

    def filter_and_label(self, df: pd.DataFrame) -> tuple:
        """
        篩選清單並標記 Buy Flag
        """
        # 生成理由
        df['reasons'] = df.apply(self.generate_reasons_string, axis=1)
        
        # 標記 Buy Flag
        # 條件: rule_score >= threshold AND rule_score > max_bearish
        # 注意: max_bearish 通常是負值 (例如 -2)。若是 neg_score <= -2 則為太差?
        # 需求: "rule_score > max_bearish" 可能是指 neg_score 不會太低? 
        # 原文: "rule_score >= buy_threshold 且 rule_score > max_bearish" -> 
        # 這裡假設 rule_score 本身就是總分。如果 max_bearish 是個底線 (e.g. -2)
        # 那麼 rule_score 必須 > -2。但通常 buy_threshold (e.g. 3) 已經大於 -2。
        # 也許是指 "neg_score > max_bearish" (負分不要扣太多)?
        # 依據 prompt: "rule_score >= buy_threshold 且 rule_score > max_bearish"
        # 照字面實作。
        
        def check_buy(row):
            is_score_high = row['rule_score'] >= self.buy_threshold
            is_bearish_ok = row['rule_score'] > self.max_bearish # 似乎有點多餘，除非 buy_threshold < max_bearish
            # 也許 user 意思是: pos_sum >= threshold AND neg_sum > max_bearish ?
            # "若負向總分 ≤ -2，直接排除" -> neg_score > -2
            
            # 修正邏輯：依據 "若負向總分 ≤ -2，直接排除"
            is_neg_ok = row['neg_score'] > self.max_bearish
            
            return is_score_high and is_neg_ok

        df['buy_flag'] = df.apply(check_buy, axis=1)
        
        # 排序: 依 final_score 高到低
        df_sorted = df.sort_values('final_score', ascending=False)
        
        # 輸出欄位
        out_cols = ['symbol', 'name', 'expected_return_5d', 'winrate', 
                    'final_score', 'rule_score', 'buy_flag', 'reasons']
        
        # Top 10: 必須是 Buy Flag = True 的前 10
        top10 = df_sorted[df_sorted['buy_flag'] == True].head(10)[out_cols].copy()
        
        # Watchlist: Buy Flag = False 但 rule_score >= 0 或 final_score 高的
        # 這裡取: 沒有進入 Top 10，但 final_score 前 50 名
        watchlist = df_sorted[~df_sorted.index.isin(top10.index)].head(50)[out_cols].copy()
        
        return top10, watchlist

    def save_results(self, top10: pd.DataFrame, watchlist: pd.DataFrame, target_date: str = None):
        """輸出 CSV"""
        if target_date is None:
            target_date = datetime.now().strftime("%Y%m%d")
        else:
            target_date = target_date.replace('-', '')
            
        top10_path = self.artifact_dir / f"top10_{target_date}.csv"
        watch_path = self.artifact_dir / f"watchlist_{target_date}.csv"
        
        top10.rename(columns={'symbol': 'code'}, inplace=True)
        watchlist.rename(columns={'symbol': 'code'}, inplace=True)
        
        top10.to_csv(top10_path, index=False, encoding='utf-8-sig')
        watchlist.to_csv(watch_path, index=False, encoding='utf-8-sig')
        
        print(f"✓ 輸出 Top10: {top10_path} ({len(top10)} 筆)")
        print(f"✓ 輸出 Watchlist: {watch_path} ({len(watchlist)} 筆)")

def main():
    print("=" * 60)
    print("Agent B - 每日股票排名 (融合版)")
    print("=" * 60)
    
    ranker = StockRanker()
    
    try:
        # Load Model
        try:
            ranker.load_model()
        except FileNotFoundError:
            print("⚠ 使用無模型模式 (僅規則評分)")
            
        # Load Data
        df = ranker.load_daily_data()
        
        # Calculate Scores
        scored_df = ranker.calculate_scores(df)
        
        # Filter & Rank
        top10, watchlist = ranker.filter_and_label(scored_df)
        
        # Save
        target_date = df['date'].iloc[0]
        ranker.save_results(top10, watchlist, str(target_date))
        
        print("\n✅ 執行完成")
        
    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

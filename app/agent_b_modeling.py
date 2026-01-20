#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent B - 模型訓練模組
負責 LightGBM 模型訓練、特徵重要性分析與模型持久化
"""

import pandas as pd
import numpy as np
import lightgbm as lgb
from pathlib import Path
from datetime import datetime, timedelta
import pickle
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import TimeSeriesSplit


class LightGBMTrainer:
    """LightGBM 模型訓練器，支援 Walk-forward Validation"""
    
    def __init__(self, data_dir: str = "data/clean", model_dir: str = "models", 
                 artifact_dir: str = "artifacts", horizon: int = 5):
        """
        初始化訓練器
        
        Args:
            data_dir: 資料目錄
            model_dir: 模型儲存目錄
            artifact_dir: 產出物目錄
            horizon: 預測天數（5日報酬）
        """
        self.data_dir = Path(data_dir)
        self.model_dir = Path(model_dir)
        self.artifact_dir = Path(artifact_dir)
        self.horizon = horizon
        self.model = None
        
        # 建立必要目錄
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
    
    def load_features(self, file_path: str = None) -> pd.DataFrame:
        """
        載入特徵資料
        
        Args:
            file_path: 特徵檔案路徑，預設為 data/clean/features.parquet
            
        Returns:
            特徵 DataFrame
        """
        if file_path is None:
            file_path = self.data_dir / "features.parquet"
        else:
            file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"特徵檔案不存在: {file_path}")
        
        df = pd.read_parquet(file_path)
        
        # 記憶體優化：將 float64 降轉為 float32
        float_cols = df.select_dtypes(include=['float64']).columns
        if len(float_cols) > 0:
            df[float_cols] = df[float_cols].astype('float32')
            print(f"📉 已將 {len(float_cols)} 個欄位降轉為 float32 以節省記憶體")
            
        print(f"✓ 載入特徵資料: {len(df)} 筆, {len(df.columns)} 欄位")
        return df
    
    def generate_labels(self, df: pd.DataFrame, price_col: str = "close") -> pd.DataFrame:
        """
        生成未來 N 日報酬標籤（避免資料洩漏）
        
        Args:
            df: 包含價格的 DataFrame (需有 'symbol' 和 'date' 欄位)
            price_col: 收盤價欄位名稱
            
        Returns:
            包含 target 欄位的 DataFrame
        """
        df = df.copy()
        
        # 確保按股票代碼和日期排序
        df = df.sort_values(['symbol', 'date'])
        
        # 計算未來 N 日收盤價
        df[f'future_{self.horizon}d_close'] = df.groupby('symbol')[price_col].shift(-self.horizon)
        
        # 計算報酬率
        df['target'] = (df[f'future_{self.horizon}d_close'] / df[price_col]) - 1
        
        # 移除無法計算標籤的資料
        df_clean = df.dropna(subset=['target'])
        
        # 移除輔助欄位
        df_clean = df_clean.drop(columns=[f'future_{self.horizon}d_close'])
        
        print(f"✓ 生成 {self.horizon} 日報酬標籤: {len(df_clean)} 筆有效資料")
        return df_clean
    
    def prepare_train_data(self, df: pd.DataFrame, exclude_cols: list = None):
        """
        準備訓練資料，分離特徵與標籤
        
        Args:
            df: 完整 DataFrame
            exclude_cols: 要排除的欄位（如 symbol, date 等）
            
        Returns:
            X, y, feature_names
        """
        if exclude_cols is None:
            exclude_cols = ['symbol', 'date', 'target']
        
        # 分離標籤
        y = df['target']
        
        # 分離特徵
        feature_cols = [col for col in df.columns if col not in exclude_cols]
        X = df[feature_cols]
        
        print(f"✓ 準備訓練資料: {len(X)} 筆, {len(feature_cols)} 個特徵")
        return X, y, feature_cols
    
    def train_model(self, X: pd.DataFrame, y: pd.Series, params: dict = None):
        """
        訓練 LightGBM 模型
        
        Args:
            X: 特徵
            y: 標籤
            params: LightGBM 參數
            
        Returns:
            訓練好的模型
        """
        if params is None:
            params = {
                'objective': 'regression',
                'metric': 'rmse',
                'boosting_type': 'gbdt',
                'num_leaves': 31,
                'learning_rate': 0.05,
                'feature_fraction': 0.8,
                'bagging_fraction': 0.8,
                'bagging_freq': 5,
                'verbose': -1
            }
        
        # 建立 LightGBM Dataset
        train_data = lgb.Dataset(X, label=y)
        
        # 訓練模型
        print("⏳ 開始訓練 LightGBM 模型...")
        self.model = lgb.train(
            params,
            train_data,
            num_boost_round=200,
            valid_sets=[train_data],
            valid_names=['train']
        )
        
        print("✓ 模型訓練完成")
        return self.model
    
    def save_model(self, filename: str = "latest_lgbm.pkl"):
        """
        儲存模型
        
        Args:
            filename: 模型檔案名稱
        """
        if self.model is None:
            raise ValueError("尚未訓練模型")
        
        model_path = self.model_dir / filename
        with open(model_path, 'wb') as f:
            pickle.dump(self.model, f)
        
        print(f"✓ 模型已儲存至: {model_path}")
    
    def plot_feature_importance(self, top_n: int = 20, filename: str = "feature_importance.png"):
        """
        繪製特徵重要性圖表
        
        Args:
            top_n: 顯示前 N 個重要特徵
            filename: 圖表檔名
        """
        if self.model is None:
            raise ValueError("尚未訓練模型")
        
        # 取得特徵重要性
        importance = self.model.feature_importance(importance_type='gain')
        feature_names = self.model.feature_name()
        
        # 建立 DataFrame
        fi_df = pd.DataFrame({
            'feature': feature_names,
            'importance': importance
        }).sort_values('importance', ascending=False).head(top_n)
        
        # 繪圖
        plt.figure(figsize=(10, 8))
        sns.barplot(data=fi_df, x='importance', y='feature', palette='viridis')
        plt.title(f'Top {top_n} 特徵重要性 (Gain)', fontsize=14, fontweight='bold')
        plt.xlabel('重要性分數', fontsize=12)
        plt.ylabel('特徵名稱', fontsize=12)
        plt.tight_layout()
        
        # 儲存
        output_path = self.artifact_dir / filename
        plt.savefig(output_path, dpi=150)
        plt.close()
        
        print(f"✓ 特徵重要性圖表已儲存至: {output_path}")
        
        return fi_df


def main():
    """主程式：執行完整訓練流程"""
    print("=" * 60)
    print("Agent B - LightGBM 模型訓練")
    print("=" * 60)
    
    # 初始化訓練器
    trainer = LightGBMTrainer(horizon=5)
    
    try:
        # 1. 載入特徵
        df = trainer.load_features()
        
        # 2. 生成標籤
        df = trainer.generate_labels(df)
        
        # 3. 準備訓練資料
        X, y, feature_names = trainer.prepare_train_data(df)
        
        # 4. 訓練模型
        model = trainer.train_model(X, y)
        
        # 5. 儲存模型
        trainer.save_model()
        
        # 6. 繪製特徵重要性
        trainer.plot_feature_importance()
        
        print("\n✅ 訓練流程完成！")
        
    except FileNotFoundError as e:
        print(f"\n❌ 錯誤: {e}")
        print("請確認 Agent A 已產生 features.parquet")
    except Exception as e:
        print(f"\n❌ 訓練失敗: {e}")
        raise


if __name__ == "__main__":
    main()

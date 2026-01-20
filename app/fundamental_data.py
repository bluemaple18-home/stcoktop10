"""
基本面資料整合模組
整合月營收、EPS、ROE 等基本面資料
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FundamentalData:
    """基本面資料整合器"""
    
    def __init__(self, df: pd.DataFrame):
        """
        初始化基本面資料整合器
        
        Args:
            df: 技術指標資料 DataFrame
        """
        self.df = df.copy()
    
    def merge_revenue_data(self, revenue_df: pd.DataFrame) -> pd.DataFrame:
        """
        合併月營收資料
        
        Args:
            revenue_df: 月營收 DataFrame，包含 stock_id, year, month, revenue_yoy, revenue_mom
            
        Returns:
            合併後的 DataFrame
        """
        logger.info("合併月營收資料")
        
        if revenue_df is None or revenue_df.empty:
            logger.warning("月營收資料為空，跳過合併")
            self.df['revenue_yoy'] = np.nan
            self.df['revenue_mom'] = np.nan
            return self.df
        
        # 從 date 欄位提取年月
        self.df['year'] = self.df['date'].dt.year
        self.df['month'] = self.df['date'].dt.month
        
        # 合併
        self.df = self.df.merge(
            revenue_df[['stock_id', 'year', 'month', 'revenue_yoy', 'revenue_mom']],
            on=['stock_id', 'year', 'month'],
            how='left'
        )
        
        logger.info("月營收資料合併完成")
        return self.df
    
    def merge_financial_ratios(self, financial_df: pd.DataFrame) -> pd.DataFrame:
        """
        合併財務比率資料（EPS、ROE、毛利率、殖利率）
        
        Args:
            financial_df: 財務比率 DataFrame，包含 stock_id, year, quarter, eps_4q, roe, gross_margin, dividend_yield
            
        Returns:
            合併後的 DataFrame
        """
        logger.info("合併財務比率資料")
        
        if financial_df is None or financial_df.empty:
            logger.warning("財務比率資料為空，跳過合併")
            self.df['eps_4q'] = np.nan
            self.df['roe'] = np.nan
            self.df['gross_margin'] = np.nan
            self.df['dividend_yield'] = np.nan
            return self.df
        
        # 從 date 欄位提取年季
        self.df['year'] = self.df['date'].dt.year
        self.df['quarter'] = self.df['date'].dt.quarter
        
        # 合併
        self.df = self.df.merge(
            financial_df[['stock_id', 'year', 'quarter', 'eps_4q', 'roe', 'gross_margin', 'dividend_yield']],
            on=['stock_id', 'year', 'quarter'],
            how='left'
        )
        
        # 移除暫存欄位
        self.df = self.df.drop(columns=['quarter'], errors='ignore')
        
        logger.info("財務比率資料合併完成")
        return self.df
    
    def create_dummy_fundamental_data(self) -> pd.DataFrame:
        """
        建立虛擬基本面資料（用於測試或當無真實資料時）
        
        Returns:
            包含虛擬基本面資料的 DataFrame
        """
        logger.warning("使用虛擬基本面資料（僅供測試）")
        
        # 產生隨機但合理的虛擬資料
        np.random.seed(42)
        
        self.df['revenue_yoy'] = np.random.uniform(-20, 50, len(self.df))  # -20% ~ 50%
        self.df['revenue_mom'] = np.random.uniform(-30, 30, len(self.df))  # -30% ~ 30%
        self.df['eps_4q'] = np.random.uniform(0, 10, len(self.df))         # 0 ~ 10 元
        self.df['roe'] = np.random.uniform(0, 30, len(self.df))            # 0% ~ 30%
        self.df['gross_margin'] = np.random.uniform(5, 60, len(self.df))   # 5% ~ 60%
        self.df['dividend_yield'] = np.random.uniform(0, 8, len(self.df))  # 0% ~ 8%
        
        # 部分資料設為缺值（模擬真實情況）
        for col in ['revenue_yoy', 'revenue_mom', 'eps_4q', 'roe', 'gross_margin', 'dividend_yield']:
            mask = np.random.random(len(self.df)) < 0.1  # 10% 缺值率
            self.df.loc[mask, col] = np.nan
        
        logger.info("虛擬基本面資料建立完成")
        return self.df
    
    def get_data(self) -> pd.DataFrame:
        """取得處理後的資料"""
        return self.df


if __name__ == "__main__":
    # 測試範例
    test_file = Path("data/clean/features_with_all_indicators.parquet")
    
    if test_file.exists():
        print(f"載入測試資料: {test_file}")
        df = pd.read_parquet(test_file)
        
        # 使用虛擬基本面資料測試
        fundamental = FundamentalData(df)
        result = fundamental.create_dummy_fundamental_data()
        
        print(f"\n新增基本面欄位:")
        fundamental_cols = ['revenue_yoy', 'revenue_mom', 'eps_4q', 'roe', 'gross_margin', 'dividend_yield']
        print(fundamental_cols)
        
        print(f"\n基本面資料統計:")
        print(result[fundamental_cols].describe())
        
        # 儲存
        output_path = Path("data/clean") / "features_with_fundamental.parquet"
        result.to_parquet(output_path, index=False)
        print(f"\n結果已儲存至: {output_path}")
    else:
        print(f"請先執行 volume_indicators.py 產生 {test_file}")

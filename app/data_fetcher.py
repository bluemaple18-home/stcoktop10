"""
資料擷取模組
提供從 TWSE、TPEX、Yahoo Finance 擷取台股資料的功能
"""

import pandas as pd
import requests
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import time
from tqdm import tqdm
import logging

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TWSEFetcher:
    """台灣證券交易所（上市）資料擷取器"""
    
    BASE_URL = "https://www.twse.com.tw"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self.data_source_log = []
    
    def fetch_daily_quotes(self, date: str) -> Optional[pd.DataFrame]:
        """
        擷取指定日期的上市股票日行情
        
        Args:
            date: 日期字串，格式 'YYYYMMDD'
            
        Returns:
            DataFrame 或 None（若失敗）
        """
        try:
            # TWSE API 格式：https://www.twse.com.tw/exchangeReport/MI_INDEX?date=20231220&type=ALL
            url = f"{self.BASE_URL}/exchangeReport/MI_INDEX"
            params = {
                'date': date,
                'type': 'ALL',
                'response': 'json'
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('stat') != 'OK':
                logger.warning(f"TWSE API 回傳非 OK 狀態: {date}")
                return None
            
            # 解析資料
            if 'data9' not in data:
                logger.warning(f"TWSE 資料中無 data9 欄位: {date}")
                return None
            
            df = pd.DataFrame(data['data9'])
            
            if df.empty:
                return None
            
            # 欄位對應：[證券代號, 證券名稱, 成交股數, 成交筆數, 成交金額, 開盤價, 最高價, 最低價, 收盤價, 漲跌, ...]
            df = df.iloc[:, :9]
            df.columns = ['stock_id', 'stock_name', 'volume', 'transactions', 'value', 'open', 'high', 'low', 'close']
            
            # 清理資料
            df['date'] = pd.to_datetime(date, format='%Y%m%d')
            df['stock_id'] = df['stock_id'].str.strip()
            df['stock_name'] = df['stock_name'].str.strip()
            
            # 移除非股票資料（如統計資料）
            df = df[df['stock_id'].str.match(r'^\d{4}$|^\d{4}[A-Z]$', na=False)]
            
            # 轉換數值欄位
            numeric_cols = ['volume', 'transactions', 'value', 'open', 'high', 'low', 'close']
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col].str.replace(',', ''), errors='coerce')
            
            # 記錄資料來源
            self.data_source_log.append({
                'date': date,
                'source': 'TWSE',
                'records': len(df),
                'status': 'success'
            })
            
            logger.info(f"成功擷取 TWSE {date} 資料，共 {len(df)} 筆")
            return df
            
        except Exception as e:
            logger.error(f"擷取 TWSE {date} 資料失敗: {e}")
            self.data_source_log.append({
                'date': date,
                'source': 'TWSE',
                'records': 0,
                'status': f'failed: {str(e)}'
            })
            return None
    
    def fetch_suspended_stocks(self) -> List[str]:
        """
        擷取處置股與全額交割股清單
        
        Returns:
            股票代碼清單
        """
        try:
            # 處置股票
            url = f"{self.BASE_URL}/announcement/publicForm"
            params = {'response': 'json'}
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            suspended = []
            
            if 'data' in data:
                for item in data['data']:
                    if len(item) > 0:
                        stock_id = item[0].strip()
                        if stock_id and stock_id.isdigit():
                            suspended.append(stock_id)
            
            logger.info(f"擷取到 {len(suspended)} 檔處置/全額交割股")
            return list(set(suspended))
            
        except Exception as e:
            logger.error(f"擷取處置股清單失敗: {e}")
            return []
    
    def fetch_revenue_data(self, year: int, month: int) -> Optional[pd.DataFrame]:
        """
        擷取月營收資料
        
        Args:
            year: 西元年
            month: 月份
            
        Returns:
            DataFrame 或 None
        """
        try:
            # 轉換為民國年
            roc_year = year - 1911
            
            url = f"{self.BASE_URL}/rwd/zh/fund/T21sc03"
            params = {
                'year': roc_year,
                'month': f"{month:02d}",
                'response': 'json'
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('stat') != 'OK' or 'data' not in data:
                return None
            
            df = pd.DataFrame(data['data'])
            
            if df.empty:
                return None
            
            # 基本欄位處理
            df = df.iloc[:, :5]
            df.columns = ['stock_id', 'stock_name', 'current_revenue', 'last_revenue', 'last_year_revenue']
            
            df['year'] = year
            df['month'] = month
            df['stock_id'] = df['stock_id'].str.strip()
            
            # 轉換數值
            for col in ['current_revenue', 'last_revenue', 'last_year_revenue']:
                df[col] = pd.to_numeric(df[col].str.replace(',', ''), errors='coerce')
            
            # 計算 YoY 和 MoM
            df['revenue_yoy'] = ((df['current_revenue'] - df['last_year_revenue']) / df['last_year_revenue'] * 100)
            df['revenue_mom'] = ((df['current_revenue'] - df['last_revenue']) / df['last_revenue'] * 100)
            
            logger.info(f"成功擷取 {year}/{month} 月營收資料，共 {len(df)} 筆")
            return df
            
        except Exception as e:
            logger.error(f"擷取月營收資料失敗 ({year}/{month}): {e}")
            return None

    def fetch_revenue_batch(self, start_date: str, end_date: str, save_to_disk: bool = True) -> pd.DataFrame:
        """
        批次擷取月營收資料
        
        Args:
            start_date: 起始日期 (YYYY-MM-DD)
            end_date: 結束日期 (YYYY-MM-DD)
            save_to_disk: 是否儲存至 data/raw/revenue_*.parquet
            
        Returns:
            合併後的 DataFrame
        """
        from datetime import datetime
        from dateutil.relativedelta import relativedelta
        
        logger.info(f"開始批次擷取營收資料: {start_date} ~ {end_date}")
        
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        all_data = []
        current = start
        
        while current <= end:
            year = current.year
            month = current.month
            
            # 營收通常在次月 10 日前公告，避免抓取未來月份
            if current > datetime.now():
                logger.warning(f"跳過未來月份: {year}/{month}")
                current += relativedelta(months=1)
                continue
                
            df = self.fetch_revenue_data(year, month)
            
            if df is not None and not df.empty:
                # 異常值偵測
                df = self._detect_revenue_outliers(df, year, month)
                
                all_data.append(df)
                
                # 儲存單月資料
                if save_to_disk:
                    self._save_revenue_data(df, year, month)
                    
            # API 限速：間隔 3 秒
            import time
            time.sleep(3)
            
            current += relativedelta(months=1)
        
        if not all_data:
            logger.warning("未抓取到任何營收資料")
            return pd.DataFrame()
            
        result = pd.concat(all_data, ignore_index=True)
        logger.info(f"批次擷取完成，共 {len(result)} 筆資料")
        return result

    def _detect_revenue_outliers(self, df: pd.DataFrame, year: int, month: int) -> pd.DataFrame:
        """
        偵測營收異常值並標記
        
        Args:
            df: 營收資料
            year, month: 年月（用於 log）
            
        Returns:
            標記後的 DataFrame
        """
        df['revenue_outlier'] = False
        
        # 異常值條件：YoY > 500% 或 < -90%
        outlier_mask = (df['revenue_yoy'] > 500) | (df['revenue_yoy'] < -90)
        
        if outlier_mask.any():
            outlier_count = outlier_mask.sum()
            logger.warning(f"{year}/{month} 發現 {outlier_count} 筆營收異常值")
            df.loc[outlier_mask, 'revenue_outlier'] = True
            
            # 列出異常股票代號（用於檢查）
            outlier_stocks = df.loc[outlier_mask, ['stock_id', 'stock_name', 'revenue_yoy']].to_dict('records')
            for stock in outlier_stocks[:5]:  # 最多顯示 5 筆
                logger.warning(f"  異常: {stock['stock_id']} {stock['stock_name']} YoY={stock['revenue_yoy']:.1f}%")
        
        return df

    def _save_revenue_data(self, df: pd.DataFrame, year: int, month: int):
        """
        儲存營收資料至 data/raw/revenue_*.parquet
        
        Args:
            df: 營收資料
            year, month: 年月
        """
        from pathlib import Path
        
        output_dir = Path("data/raw")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"revenue_{year}_{month:02d}.parquet"
        output_path = output_dir / filename
        
        df.to_parquet(output_path, index=False)
        logger.info(f"營收資料已儲存: {output_path}")


class TPEXFetcher:
    """櫃買中心（上櫃）資料擷取器"""
    
    BASE_URL = "https://www.tpex.org.tw"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self.data_source_log = []
    
    def fetch_daily_quotes(self, date: str) -> Optional[pd.DataFrame]:
        """
        擷取指定日期的上櫃股票日行情
        
        Args:
            date: 日期字串，格式 'YYYYMMDD'
            
        Returns:
            DataFrame 或 None
        """
        try:
            # 轉換日期格式為 ROC year
            dt = datetime.strptime(date, '%Y%m%d')
            roc_date = f"{dt.year - 1911}/{dt.month:02d}/{dt.day:02d}"
            
            url = f"{self.BASE_URL}/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php"
            params = {
                'l': 'zh-tw',
                'd': roc_date,
                'se': 'AL'
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if 'aaData' not in data or not data['aaData']:
                logger.warning(f"TPEX 無資料: {date}")
                return None
            
            df = pd.DataFrame(data['aaData'])
            
            # 欄位對應
            df = df.iloc[:, :9]
            df.columns = ['stock_id', 'stock_name', 'close', 'change', 'open', 'high', 'low', 'volume', 'value']
            
            df['date'] = pd.to_datetime(date, format='%Y%m%d')
            df['stock_id'] = df['stock_id'].str.strip()
            df['stock_name'] = df['stock_name'].str.strip()
            
            # 移除非股票
            df = df[df['stock_id'].str.match(r'^\d{4}$', na=False)]
            
            # 轉換數值
            numeric_cols = ['close', 'open', 'high', 'low', 'volume', 'value']
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col].str.replace(',', ''), errors='coerce')
            
            # 欄位順序與 TWSE 一致
            df = df[['date', 'stock_id', 'stock_name', 'open', 'high', 'low', 'close', 'volume', 'value']]
            
            self.data_source_log.append({
                'date': date,
                'source': 'TPEX',
                'records': len(df),
                'status': 'success'
            })
            
            logger.info(f"成功擷取 TPEX {date} 資料，共 {len(df)} 筆")
            return df
            
        except Exception as e:
            logger.error(f"擷取 TPEX {date} 資料失敗: {e}")
            self.data_source_log.append({
                'date': date,
                'source': 'TPEX',
                'records': 0,
                'status': f'failed: {str(e)}'
            })
            return None
    
    def fetch_suspended_stocks(self) -> List[str]:
        """擷取櫃買處置股清單"""
        try:
            url = f"{self.BASE_URL}/web/stock/aftertrading/attention_stock/attention_stock_result.php"
            params = {'l': 'zh-tw'}
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            suspended = []
            
            if 'aaData' in data:
                for item in data['aaData']:
                    if len(item) > 0:
                        stock_id = item[0].strip()
                        if stock_id and stock_id.isdigit():
                            suspended.append(stock_id)
            
            logger.info(f"擷取到 {len(suspended)} 檔櫃買處置股")
            return list(set(suspended))
            
        except Exception as e:
            logger.error(f"擷取櫃買處置股清單失敗: {e}")
            return []


class YahooFetcher:
    """Yahoo Finance 備援資料擷取器"""
    
    def __init__(self):
        self.data_source_log = []
    
    def fetch_daily_quotes(self, stock_id: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """
        擷取單一股票的歷史資料
        
        Args:
            stock_id: 股票代碼
            start_date: 開始日期 'YYYY-MM-DD'
            end_date: 結束日期 'YYYY-MM-DD'
            
        Returns:
            DataFrame 或 None
        """
        try:
            # Yahoo Finance 台股代碼格式：2330.TW (上市) 或 6111.TWO (上櫃)
            ticker = f"{stock_id}.TW"
            
            stock = yf.Ticker(ticker)
            df = stock.history(start=start_date, end=end_date)
            
            if df.empty:
                # 嘗試上櫃
                ticker = f"{stock_id}.TWO"
                stock = yf.Ticker(ticker)
                df = stock.history(start=start_date, end=end_date)
            
            if df.empty:
                return None
            
            df = df.reset_index()
            df = df.rename(columns={
                'Date': 'date',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            
            df['stock_id'] = stock_id
            df = df[['date', 'stock_id', 'open', 'high', 'low', 'close', 'volume']]
            
            self.data_source_log.append({
                'stock_id': stock_id,
                'source': 'Yahoo',
                'records': len(df),
                'status': 'success'
            })
            
            return df
            
        except Exception as e:
            logger.error(f"Yahoo Finance 擷取 {stock_id} 失敗: {e}")
            self.data_source_log.append({
                'stock_id': stock_id,
                'source': 'Yahoo',
                'records': 0,
                'status': f'failed: {str(e)}'
            })
            return None


class DataFetcherOrchestrator:
    """資料擷取協調器，整合多個資料來源並實作容錯機制"""
    
    def __init__(self, data_dir: str = "data/raw"):
        self.twse = TWSEFetcher()
        self.tpex = TPEXFetcher()
        self.yahoo = YahooFetcher()
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.all_source_logs = []
    
    def fetch_historical_data(self, start_date: str, end_date: str, delay: float = 3.0) -> pd.DataFrame:
        """
        擷取歷史資料（近 3 年）
        
        Args:
            start_date: 開始日期 'YYYY-MM-DD'
            end_date: 結束日期 'YYYY-MM-DD'
            delay: 每次請求間隔秒數（避免被封鎖）
            
        Returns:
            合併後的 DataFrame
        """
        all_data = []
        
        # 產生日期範圍（僅工作日）
        date_range = pd.date_range(start=start_date, end=end_date, freq='B')  # B = business days
        
        logger.info(f"開始擷取 {len(date_range)} 個交易日的資料...")
        
        for date in tqdm(date_range, desc="擷取日行情"):
            date_str = date.strftime('%Y%m%d')
            
            # 1. 嘗試 TWSE
            twse_data = self.twse.fetch_daily_quotes(date_str)
            if twse_data is not None:
                twse_data['market'] = 'TWSE'
                all_data.append(twse_data)
            
            time.sleep(delay)
            
            # 2. 嘗試 TPEX
            tpex_data = self.tpex.fetch_daily_quotes(date_str)
            if tpex_data is not None:
                tpex_data['market'] = 'TPEX'
                all_data.append(tpex_data)
            
            time.sleep(delay)
        
        # 合併所有資料
        if not all_data:
            logger.error("無法擷取任何資料！")
            return pd.DataFrame()
        
        df = pd.concat(all_data, ignore_index=True)
        
        # 彙整資料來源記錄
        self.all_source_logs.extend(self.twse.data_source_log)
        self.all_source_logs.extend(self.tpex.data_source_log)
        
        logger.info(f"成功擷取 {len(df)} 筆歷史資料")
        
        # 儲存原始資料
        output_path = self.data_dir / f"daily_quotes_{start_date}_to_{end_date}.parquet"
        df.to_parquet(output_path, index=False)
        logger.info(f"原始資料已儲存至 {output_path}")
        
        return df
    
    def fetch_suspended_stocks_list(self) -> List[str]:
        """取得所有處置股與全額交割股"""
        twse_suspended = self.twse.fetch_suspended_stocks()
        tpex_suspended = self.tpex.fetch_suspended_stocks()
        
        all_suspended = list(set(twse_suspended + tpex_suspended))
        
        # 儲存清單
        output_path = self.data_dir / "suspended_stocks.txt"
        with open(output_path, 'w') as f:
            f.write('\n'.join(all_suspended))
        
        logger.info(f"處置股清單已儲存至 {output_path}")
        return all_suspended
    
    def get_data_quality_report(self) -> pd.DataFrame:
        """產生資料品質報告"""
        if not self.all_source_logs:
            return pd.DataFrame()
        
        df = pd.DataFrame(self.all_source_logs)
        return df


if __name__ == "__main__":
    # 測試：擷取近 7 天資料
    orchestrator = DataFetcherOrchestrator()
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    df = orchestrator.fetch_historical_data(
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        delay=3.0
    )
    
    print(f"\n擷取資料統計：")
    print(f"總筆數: {len(df)}")
    print(f"股票數: {df['stock_id'].nunique()}")
    print(f"日期範圍: {df['date'].min()} ~ {df['date'].max()}")
    
    # 取得處置股清單
    suspended = orchestrator.fetch_suspended_stocks_list()
    print(f"\n處置股數量: {len(suspended)}")
    
    # 資料品質報告
    quality_report = orchestrator.get_data_quality_report()
    print(f"\n資料來源統計:")
    print(quality_report.groupby('source')['status'].value_counts())

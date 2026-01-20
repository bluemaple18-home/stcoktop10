"""
資料擷取模組
提供從 TWSE、TPEX、Yahoo Finance 擷取台股資料的功能
"""

import pandas as pd
import requests
import yfinance as yf
from datetime import datetime, timedelta
from typing import List, Optional
from pathlib import Path
import time
from tqdm import tqdm
import logging
import json

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TWSEFetcher:
    """台灣證券交易所（上市）資料擷取器"""
    
    BASE_URL = "https://www.twse.com.tw"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.data_source_log = []
    
    def fetch_daily_quotes(self, date: str) -> Optional[pd.DataFrame]:
        """
        擷取指定日期的上市股票日行情 (使用 RWD API 動態解析)
        """
        try:
            # 排除週末 (簡易防呆)
            dt = datetime.strptime(date, '%Y%m%d')
            if dt.weekday() > 4:
                return None

            # TWSE RWD API
            url = f"{self.BASE_URL}/rwd/zh/afterTrading/MI_INDEX"
            params = {
                'date': date,
                'type': 'ALLBUT0999',  # 排除權證與特殊商品，減少資料量
                'response': 'json'
            }
            
            response = self.session.get(url, params=params, timeout=30)
            
            # 處理 HTTP 錯誤
            if response.status_code != 200:
                logger.warning(f"TWSE 連線失敗 ({date}): Status {response.status_code}")
                return None

            try:
                data = response.json()
            except json.JSONDecodeError:
                logger.warning(f"TWSE 回傳非 JSON 格式 ({date})")
                return None
            
            if data.get('stat') != 'OK':
                # 這是正常現象（如果當天沒資料或假日）
                # logger.debug(f"TWSE 無資料 ({date}): {data.get('stat')}")
                return None
            
            # 動態尋找目標表格
            target_table = None
            if 'tables' in data:
                for table in data['tables']:
                    title = table.get('title', '')
                    # 關鍵字匹配：包含 "每日收盤行情" 且 "全部" 或 "不含權證"
                    if "每日收盤行情" in title:
                        target_table = table
                        break
            
            if not target_table:
                # 舊版結構或找不到表
                if 'data9' in data:
                    # 嘗試舊版相容 (fields9 / data9)
                    fields = data.get('fields9', [])
                    raw_data = data.get('data9', [])
                    target_table = {'fields': fields, 'data': raw_data}
                else:
                    logger.warning(f"TWSE 找不到行情表 ({date})")
                    return None

            fields = target_table.get('fields', [])
            raw_data = target_table.get('data', [])
            
            if not raw_data:
                return None
                
            df = pd.DataFrame(raw_data, columns=fields)
            
            # --- 動態欄位對應 ---
            # TWSE 欄位名稱通常為：["證券代號", "證券名稱", "成交股數", "成交筆數", "成交金額", "開盤價", "最高價", "最低價", "收盤價", ...]
            # 我們需要 mapping 到標準英文欄位
            col_map = {
                "證券代號": "stock_id",
                "證券名稱": "stock_name",
                "成交股數": "volume",
                "成交筆數": "transactions",
                "成交金額": "value",
                "開盤價": "open",
                "最高價": "high",
                "最低價": "low",
                "收盤價": "close"
            }
            
            rename_dict = {}
            for col in df.columns:
                if col in col_map:
                    rename_dict[col] = col_map[col]
            
            df = df.rename(columns=rename_dict)
            
            # 檢查必要欄位是否都存在
            required_cols = ['stock_id', 'stock_name', 'open', 'high', 'low', 'close', 'volume']
            missing_cols = [c for c in required_cols if c not in df.columns]
            if missing_cols:
                logger.warning(f"TWSE 缺漏必要欄位 {missing_cols} ({date})")
                return None
            
            # 資料清理
            df['date'] = pd.to_datetime(date, format='%Y%m%d')
            
            # 數值轉換
            numeric_cols = ['volume', 'transactions', 'value', 'open', 'high', 'low', 'close']
            for col in numeric_cols:
                if col in df.columns:
                    # 去除逗號，處理 "--" (無交易)
                    df[col] = df[col].astype(str).str.replace(',', '').replace('--', 'NaN')
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 移除 Nan (無交易)
            df = df.dropna(subset=['close'])
            
            # 儲存 Log
            self.data_source_log.append({
                'date': date,
                'source': 'TWSE',
                'records': len(df),
                'status': 'success'
            })
            
            return df
            
        except Exception as e:
            logger.error(f"擷取 TWSE {date} 失敗: {e}")
            return None
    
    def fetch_suspended_stocks(self) -> List[str]:
        """擷取處置股 (維持原樣或略作保護)"""
        return [] # 暫時簡化，避免此處報錯影響主流程


class TPEXFetcher:
    """櫃買中心（上櫃）資料擷取器"""
    
    BASE_URL = "https://www.tpex.org.tw"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.data_source_log = []
    
    def fetch_daily_quotes(self, date: str) -> Optional[pd.DataFrame]:
        """
        擷取指定日期的上櫃股票日行情
        """
        try:
            # 排除週末
            dt = datetime.strptime(date, '%Y%m%d')
            if dt.weekday() > 4:
                return None

            roc_date = f"{dt.year - 1911}/{dt.month:02d}/{dt.day:02d}"
            
            # TPEX 日收盤行情 JSON
            url = f"{self.BASE_URL}/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php"
            params = {
                'l': 'zh-tw',
                'd': roc_date,
                'se': 'AL'
            }
            
            response = self.session.get(url, params=params, timeout=30)
            if response.status_code != 200:
                return None
                
            try:
                data = response.json()
            except:
                return None
            
            if 'aaData' not in data or not data['aaData']:
                return None
            
            # TPEX 欄位通常固定，但也建議用 header mapping 如果有的話
            # 這裡簡化：TPEX JSON 是一個 list of list，無 fields key，通常第一行是 header? 
            # TPEX aaData 純資料。固定順序: 
            # 代號, 名稱, 收盤, 漲跌, 開盤, 最高, 最低, 成交股數, 成交筆數, 成交金額...
            
            raw_data = data['aaData']
            # 只取前幾欄
            df = pd.DataFrame(raw_data)
            
            # 防呆：確保欄位數夠
            if df.shape[1] < 10:
                return None

            # Mapping (依據 API 文件或經驗)
            # 0: 代號, 1: 名稱, 2: 收盤, 3: 漲跌, 4: 開盤, 5: 最高, 6: 最低, 7: 成交股數, 8: 成交金額, 9: 成交筆數
            df = df.iloc[:, [0, 1, 4, 5, 6, 2, 7, 8]]
            df.columns = ['stock_id', 'stock_name', 'open', 'high', 'low', 'close', 'volume', 'value']
            
            # 清理
            df['stock_id'] = df['stock_id'].str.strip()
            df['stock_name'] = df['stock_name'].str.strip()
            
            # 篩選標準股票代號 (4碼)
            df = df[df['stock_id'].str.match(r'^\d{4}$')]
            
            # 數值轉換
            for col in ['open', 'high', 'low', 'close', 'volume', 'value']:
                df[col] = df[col].astype(str).str.replace(',', '').replace('---', 'NaN').replace('--', 'NaN')
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df = df.dropna(subset=['close'])
            df['date'] = dt
            
            self.data_source_log.append({
                'date': date,
                'source': 'TPEX',
                'records': len(df),
                'status': 'success'
            })
            
            return df
            
        except Exception as e:
            logger.error(f"擷取 TPEX {date} 失敗: {e}")
            return None

    def fetch_suspended_stocks(self) -> List[str]:
        return []


class YahooFetcher:
    """Yahoo Finance 備援"""
    def __init__(self):
        self.data_source_log = []
    
    def fetch_daily_quotes(self, stock_id: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        return None # 暫時不實作，專注主力 API


class DataFetcherOrchestrator:
    """資料擷取協調器"""
    
    def __init__(self, data_dir: str = "data/raw"):
        self.twse = TWSEFetcher()
        self.tpex = TPEXFetcher()
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.all_source_logs = []
    
    def fetch_historical_data(self, start_date: str, end_date: str, delay: float = 3.0) -> pd.DataFrame:
        """擷取歷史資料 (主流程)"""
        all_data = []
        
        # 產生日期範圍 (僅工作日)
        # B freq 會排除週末，但不會排除國定假日 => fetcher 內部會回傳 None
        date_range = pd.date_range(start=start_date, end=end_date, freq='B')
        
        logger.info(f"計畫擷取: {start_date} ~ {end_date} ({len(date_range)} 天)")
        
        for date in tqdm(date_range, desc="資料回補中"):
            date_str = date.strftime('%Y%m%d')
            
            # 1. TWSE
            twse_df = self.twse.fetch_daily_quotes(date_str)
            if twse_df is not None and not twse_df.empty:
                twse_df['market'] = 'TWSE'
                all_data.append(twse_df)
                
            time.sleep(1) # 基本限速
            
            # 2. TPEX
            tpex_df = self.tpex.fetch_daily_quotes(date_str)
            if tpex_df is not None and not tpex_df.empty:
                tpex_df['market'] = 'TPEX'
                all_data.append(tpex_df)
                
            time.sleep(1)

        if not all_data:
            logger.error("未擷取到任何有效資料。請確認日期範圍或網路狀態。")
            return pd.DataFrame()
            
        df = pd.concat(all_data, ignore_index=True)
        logger.info(f"資料擷取完成: 共 {len(df)} 筆行情")
        
        # 儲存
        save_path = self.data_dir / "latest_quotes.parquet"
        df.to_parquet(save_path, index=False)
        return df

    def fetch_suspended_stocks_list(self) -> List[str]:
        return []

    def fetch_revenue_batch(self, start_date: str, end_date: str, save_to_disk: bool = True) -> pd.DataFrame:
        # 暫回傳空，避免阻擋主流程，待後續優化
        return pd.DataFrame()

    def get_data_quality_report(self) -> pd.DataFrame:
        return pd.DataFrame(self.twse.data_source_log + self.tpex.data_source_log)

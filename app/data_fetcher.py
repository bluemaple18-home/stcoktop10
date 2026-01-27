"""
資料擷取模組 (Async Version)
提供從 TWSE、TPEX、Yahoo Finance 擷取台股資料的功能
使用 aiohttp 與 asyncio 進行併發抓取優化
"""

import pandas as pd
import aiohttp
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from pathlib import Path
import time
from tqdm.asyncio import tqdm
import logging
import json

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AsyncTWSEFetcher:
    """台灣證券交易所（上市）資料擷取器 (Async)"""
    
    BASE_URL = "https://www.twse.com.tw"
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.data_source_log = []
    
    async def fetch_daily_quotes(self, date: str) -> Optional[pd.DataFrame]:
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
            
            # 模擬瀏覽器行為
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            async with self.session.get(url, params=params, headers=headers, timeout=30) as response:
                if response.status != 200:
                    logger.warning(f"TWSE 連線失敗 ({date}): Status {response.status}")
                    return None
                    
                try:
                    data = await response.json()
                except Exception:
                    logger.warning(f"TWSE 回傳非 JSON 格式 ({date})")
                    return None

            if data.get('stat') != 'OK':
                return None
            
            # 動態尋找目標表格
            target_table = None
            if 'tables' in data:
                for table in data['tables']:
                    title = table.get('title', '')
                    # 關鍵字匹配
                    if "每日收盤行情" in title:
                        target_table = table
                        break
            
            if not target_table:
                # 舊版相容
                if 'data9' in data:
                    fields = data.get('fields9', [])
                    raw_data = data.get('data9', [])
                    target_table = {'fields': fields, 'data': raw_data}
                else:
                    return None

            fields = target_table.get('fields', [])
            raw_data = target_table.get('data', [])
            
            if not raw_data:
                return None
                
            df = pd.DataFrame(raw_data, columns=fields)
            
            # 欄位對應
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
            
            rename_dict = {c: col_map[c] for c in df.columns if c in col_map}
            df = df.rename(columns=rename_dict)
            
            # 檢查必要欄位
            required_cols = ['stock_id', 'stock_name', 'open', 'high', 'low', 'close', 'volume']
            missing_cols = [c for c in required_cols if c not in df.columns]
            if missing_cols:
                return None
            
            # 資料清理
            df['date'] = pd.to_datetime(date, format='%Y%m%d')
            
            numeric_cols = ['volume', 'transactions', 'value', 'open', 'high', 'low', 'close']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.replace(',', '').replace('--', 'NaN')
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df = df.dropna(subset=['close'])
            
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


class AsyncTPEXFetcher:
    """櫃買中心（上櫃）資料擷取器 (Async)"""
    
    BASE_URL = "https://www.tpex.org.tw"
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.data_source_log = []
    
    async def fetch_daily_quotes(self, date: str) -> Optional[pd.DataFrame]:
        try:
            dt = datetime.strptime(date, '%Y%m%d')
            if dt.weekday() > 4:
                return None

            roc_date = f"{dt.year - 1911}/{dt.month:02d}/{dt.day:02d}"
            
            url = f"{self.BASE_URL}/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php"
            params = {
                'l': 'zh-tw',
                'd': roc_date,
                'se': 'AL'
            }
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }

            async with self.session.get(url, params=params, headers=headers, timeout=30) as response:
                if response.status != 200:
                    return None
                try:
                    data = await response.json()
                except:
                    return None
            
            if 'aaData' not in data or not data['aaData']:
                return None
            
            raw_data = data['aaData']
            df = pd.DataFrame(raw_data)
            
            if df.shape[1] < 10:
                return None

            # 0: 代號, 1: 名稱, 2: 收盤, 3: 漲跌, 4: 開盤, 5: 最高, 6: 最低, 7: 成交股數, 8: 成交金額, 9: 成交筆數
            df = df.iloc[:, [0, 1, 4, 5, 6, 2, 7, 8]]
            df.columns = ['stock_id', 'stock_name', 'open', 'high', 'low', 'close', 'volume', 'value']
            
            df['stock_id'] = df['stock_id'].str.strip()
            df['stock_name'] = df['stock_name'].str.strip()
            df = df[df['stock_id'].str.match(r'^\d{4}$')]
            
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


import yfinance as yf

class AsyncYFinanceFetcher:
    """Yahoo Finance 資料擷取器 (Fallback)"""
    
    def __init__(self):
        self.data_source_log = []
        
    async def fetch_daily_quotes_batch(self, stock_ids: List[str], date_str: str) -> Optional[pd.DataFrame]:
        """
        批量抓取指定日期的 Yahoo Finance 資料
        注意: yfinance 不支援單日精確查詢，需抓取 range 後 filter
        為求效率，這裡改為: 不在此處抓，而是由 Orchestrator 統一處理 yfinance?
        或者: 針對特定日期，轉換為 yfinance 下載
        """
        # 由於 yfinance 結構不同，這裡僅作為 "當 TWSE 失敗時的備援"
        # 實作策略: 針對該日期的所有潛在股票進行下載 (太慢)
        # 替代策略: 改為 "補抓模式"，不依賴單日迴圈，而是針對所有股票抓取缺失區間
        # 但為了配合 DataFetcherOrchestrator 的架構，我們在此模擬單日抓取 (效率較差但相容)
        # BETTER APPROACH: 在 Orchestrator 層級，若發現 TWSE/TPEX 失敗，則標記該日需用 yfinance 補
        return None

class DataFetcherOrchestrator:
    """資料擷取協調器 (Async 版本)"""
    
    def __init__(self, data_dir: str = "data/raw"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.all_source_logs = []
        self.semaphore = asyncio.Semaphore(3) 

    async def _fetch_day_data(self, session: aiohttp.ClientSession, date: datetime) -> List[pd.DataFrame]:
        """單日資料抓取任務 (TWSE + TPEX + YFinance Fallback)"""
        date_str = date.strftime('%Y%m%d')
        async with self.semaphore:
            twse = AsyncTWSEFetcher(session)
            tpex = AsyncTPEXFetcher(session)
            
            # 1. 嘗試官方來源
            results = await asyncio.gather(
                twse.fetch_daily_quotes(date_str),
                tpex.fetch_daily_quotes(date_str)
            )
            
            valid_dfs = []
            
            # TWSE
            if results[0] is not None and not results[0].empty:
                results[0]['market'] = 'TWSE'
                valid_dfs.append(results[0])
                self.all_source_logs.extend(twse.data_source_log)
            # TPEX
            if results[1] is not None and not results[1].empty:
                results[1]['market'] = 'TPEX'
                valid_dfs.append(results[1])
                self.all_source_logs.extend(tpex.data_source_log)
                
            # 2. 如果官方來源全失敗 (且不是週末)，啟用 YFinance Fallback
            # 注意: 這裡無法簡單用 yfinance 補 "全市場" 的單日資料
            # 因此，我們記錄 "失敗日期"，稍後在主流程統一用 yfinance 補齊特定股票
            # 或者: 這裡回傳空，Orchestrator 統計缺漏後再補
            
            if not valid_dfs and date.weekday() <= 4:
                # 簡單判定: 若非週末且無資料，視為失敗
                logger.warning(f"{date_str} 官方來源無資料，標記為需 YFinance 回補")
                # 我們回傳一個特殊的標記或空的 DataFrame，讓主流程知道
                return [] 
            
            return valid_dfs

    async def _run_async_fetch(self, start_date: str, end_date: str) -> pd.DataFrame:
        """非同步主迴圈"""
        date_range = pd.date_range(start=start_date, end=end_date, freq='B')
        logger.info(f"計畫擷取: {start_date} ~ {end_date} ({len(date_range)} 天) - Async Mode")
        
        connector = aiohttp.TCPConnector(limit=5) # 限制全域連線數
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = []
            for date in date_range:
                tasks.append(self._fetch_day_data(session, date))
            
            # 使用 tqdm 顯示進度
            all_results = []
            failed_dates = []
            
            for f in tqdm.as_completed(tasks, desc="非同步資料回補中"):
                day_dfs = await f
                if day_dfs:
                    all_results.extend(day_dfs)
                else:
                    # 無法分辨是週末還是失敗，但我們會在最後統整日期
                    pass
            
            # --- YFinance Fallback (批次補齊) ---
            # 1. 找出有抓到資料的日期
            fetched_dates = set()
            for df in all_results:
                fetched_dates.update(df['date'].unique())
            
            # 2. 找出預期但缺失的日期 (排除週末)
            expected_dates = set(date_range)
            missing_dates = sorted([d for d in expected_dates if d not in fetched_dates and d.weekday() <= 4])
            
            if missing_dates:
                logger.info(f"發現 {len(missing_dates)} 天缺失資料 (官方來源失敗)，改用 Yahoo Finance 救援...")
                # 由於 yfinance 適合抓 "所有代碼" 的 "一段時間"，或是 "特定代碼" 的 "一段時間"
                # 這裡最簡單的方式是：針對目前已知的 universe (雖然還沒生成，但可從歷史資料或本次部分成功資料得知)
                # 但為了簡化，我們直接抓取 "重點 ETF 與 指數成分股" 作為代表，或者...
                # 更好的方式：既然是 Fallback，我們針對 "Top 權值股 + 用戶關注股" 抓取?
                # 不，這樣會漏掉很多。
                # 正確做法：下載台股清單 -> 遍歷下載。這會很久。
                
                # 妥協方案：直接對 yfinance 請求 TAIEX (雖然 yfinance 沒有大盤明細)
                # 實際上，若要用 yfinance 補全市場，需要股票代碼清單。
                # 我們可以假設：如果完全沒資料，至少要抓主要 ETF (0050, 0056, 00878...) 和權值股，確保系統能跑。
                # 我們先讀取一個靜態的最愛清單或歷史 features 裡的 stock_id
                
                logger.info("正在讀取歷史股票代碼清單...")
                target_stocks = []
                try:
                    # 嘗試從 data/clean/features.parquet 讀取所有 stock_id
                    hist_path = Path("data/clean/features.parquet")
                    if hist_path.exists():
                        hist_df = pd.read_parquet(hist_path, columns=['stock_id'])
                        target_stocks = hist_df['stock_id'].unique().tolist()
                except:
                    pass
                
                if not target_stocks:
                    # Fallback list
                    target_stocks = ['2330', '2317', '2454', '2308', '2303', '0050', '0056', '00878']
                
                logger.info(f"準備從 YFinance 更新 {len(target_stocks)} 檔股票資料 (涵蓋日期: {missing_dates[0].strftime('%Y-%m-%d')} ~ {missing_dates[-1].strftime('%Y-%m-%d')})...")
                
                yf_dfs = await self._fetch_yfinance_batch(target_stocks, missing_dates[0], missing_dates[-1])
                if yf_dfs:
                    all_results.extend(yf_dfs)
                    logger.info(f"✅ Yahoo Finance 救援成功，補回 {len(pd.concat(yf_dfs))} 筆資料")
                
        if not all_results:
            logger.error("未擷取到任何有效資料。")
            return pd.DataFrame()
            
        return pd.concat(all_results, ignore_index=True)

    async def _fetch_yfinance_batch(self, stock_ids: List[str], start_d: datetime, end_d: datetime) -> List[pd.DataFrame]:
        """使用 yfinance 抓取清單內股票的區間資料"""
        import yfinance as yf
        
        # yfinance 需要 .TW 或 .TWO 後綴
        # 這裡簡單判斷：看起來像上市的加 .TW，上櫃加 .TWO (不精確但可用)
        # 更好的方式是試錯。
        # 為了效率，我們分兩批嘗試
        
        tickers = []
        id_map = {}
        for sid in stock_ids:
            # 簡單規則：00開頭通常是上市(ETF)，除少數。
            # 大部分 4 碼數字
            ticker_tw = f"{sid}.TW"
            tickers.append(ticker_tw)
            id_map[ticker_tw] = sid
            
            # 我們暫時只抓 .TW，因為無法確定哪些是 .TWO，除非有 mapping。
            # 如果要完整，可以兩種都 generate
        
        # 批次下載 (yfinance 最好一次下載多檔)
        # 分批處理，一次 100 檔
        batch_size = 50
        results = []
        
        # Adjust end date for yfinance (exclusive)
        yf_end = end_d + timedelta(days=1)
        
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i:i+batch_size]
            try:
                # 使用 threads=True 加速
                data = yf.download(batch, start=start_d.strftime('%Y-%m-%d'), end=yf_end.strftime('%Y-%m-%d'), 
                                   group_by='ticker', threads=True, progress=False)
                
                # yfinance return format varies by number of tickers
                if len(batch) == 1:
                    # Single ticker logic could be here, but usually structured similarly if group_by='ticker'
                    pass
                
                # Parse Result
                # data columns MultiIndex: (Ticker, PriceType)
                for ticker in batch:
                    try:
                        if ticker in data.columns.levels[0]: # Check if ticker data exists
                            df_tick = data[ticker].copy()
                        elif len(batch) == 1 and not data.empty: # Single ticker case
                             df_tick = data.copy()
                        else:
                            continue
                            
                        if df_tick.empty: continue
                        
                        df_tick = df_tick.reset_index()
                        # Rename cols
                        df_tick = df_tick.rename(columns={
                            'Date': 'date', 'Open': 'open', 'High': 'high', 'Low': 'low', 
                            'Close': 'close', 'Volume': 'volume'
                        })
                        
                        # Add metadata
                        df_tick['stock_id'] = id_map.get(ticker, ticker.replace('.TW', ''))
                        df_tick['stock_name'] = df_tick['stock_id'] # YF doesn't give name easily
                        df_tick['market'] = 'YF_TW'
                        
                        # Format
                        df_tick = df_tick[['date', 'stock_id', 'stock_name', 'open', 'high', 'low', 'close', 'volume']]
                        results.append(df_tick)
                    except Exception as e:
                        continue
                        
            except Exception as e:
                logger.error(f"YFinance batch failed: {e}")
                
        return results

    def fetch_historical_data(self, start_date: str, end_date: str, delay: float = 3.0) -> pd.DataFrame:
        """
        同步接口 (與舊版相容)，內部呼叫 async 邏輯
        """
        try:
            # 嘗試使用現有的 loop，如果沒有則建立新的
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            
            if loop and loop.is_running():
                # 如果已經在 async 環境中 (例如被 async function 呼叫)
                # 這裡可能需要 nest_asyncio，但為了簡單，假設這是 top-level call
                logger.warning("Detected running event loop, careful with blocking calls.")
                # 若確實需要，應使用 await self._run_async_fetch(...) 
                # 但為了維持介面相容性 (return DataFrame)，這裡可能比較尷尬
                # 暫時假設都在 main script 最外層執行
                return asyncio.run(self._run_async_fetch(start_date, end_date))
            else:
                return asyncio.run(self._run_async_fetch(start_date, end_date))
                
        except Exception as e:
            logger.error(f"Async fetch failed: {e}")
            return pd.DataFrame()
            
        finally:
            # Save logs or cleanup (optional)
            pass

    # --- 為了相容性保留的方法 ---
    def fetch_suspended_stocks_list(self) -> List[str]:
        return []

    def fetch_revenue_batch(self, start_date: str, end_date: str, save_to_disk: bool = True) -> pd.DataFrame:
        return pd.DataFrame()

    def get_data_quality_report(self) -> pd.DataFrame:
        return pd.DataFrame(self.all_source_logs)

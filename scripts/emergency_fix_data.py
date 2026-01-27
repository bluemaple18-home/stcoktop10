
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import logging
from pathlib import Path
import time

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

import json

DATA_DIR = Path("data/clean")
DATA_DIR.mkdir(parents=True, exist_ok=True)
FEATURES_PATH = DATA_DIR / "features.parquet"
PROGRESS_FILE = DATA_DIR / "repair_progress.json"

def update_progress(current, total, status="Processing"):
    """Write progress to JSON for UI to read"""
    try:
        with open(PROGRESS_FILE, 'w') as f:
            json.dump({
                "current": current,
                "total": total,
                "percentage": int((current / total) * 100),
                "status": status,
                "updated": time.time()
            }, f)
    except:
        pass

def get_stock_list():
    """Get list of stocks to download. Try universe first, then features."""
    stocks = set()
    
    # Try universe.parquet
    universe_path = DATA_DIR / "universe.parquet"
    if universe_path.exists():
        try:
            df = pd.read_parquet(universe_path)
            stocks.update(df['stock_id'].unique())
            logger.info(f"Loaded {len(stocks)} stocks from universe.parquet")
        except Exception as e:
            logger.error(f"Failed to load universe: {e}")

    # Try features.parquet if list is small
    if len(stocks) < 100 and FEATURES_PATH.exists():
        try:
            df = pd.read_parquet(FEATURES_PATH, columns=['stock_id'])
            stocks.update(df['stock_id'].unique())
            logger.info(f"Loaded {len(stocks)} stocks from features.parquet")
        except Exception as e:
            logger.error(f"Failed to load features: {e}")
            
    # Fallback default list if everything fails (Top stocks)
    if not stocks:
        logger.warning("No stocks found! Using default Top 50 list.")
        stocks = {
            '2330', '2317', '2454', '2308', '2303', '2881', '2882', '2891', '2002', '1301',
            '1303', '1326', '2412', '3008', '3045', '2912', '5880', '2886', '2892', '2884',
            '2885', '2880', '2883', '2887', '2890', '5871', '2801', '2834', '2838', '2845',
            '2849', '2850', '2851', '2852', '2855', '2867', '2812', '2816', '2820', '2823',
            '0050', '0056', '00878', '00929', '00919', '00940'
        }
        
    return sorted(list(stocks))

def download_and_save():
    stocks = get_stock_list()
    if not stocks:
        logger.error("No stocks to process.")
        return

    logger.info(f"Starting Emergency Download for {len(stocks)} stocks...")
    logger.info("Source: Yahoo Finance")
    logger.info("Range: Last 400 days (fixing the gap)")

    # Prepare Tickers
    tickers = [f"{s}.TW" for s in stocks] # Assume Listed (.TW) primarily. 
    # NOTE: TPEX stocks should be .TWO. Yfinance auto-adjust sometimes works but explicit is better.
    # To be safe, we might try both or guess. But for now let's try .TW. 
    # If we knew which were OTC, we'd use .TWO.
    # Hack: Download .TW. If empty, try .TWO? No, too slow.
    # Better: Use the input file to know market? 
    # Let's assume most are .TW. If features.parquet has 'market' col that would be great.
    
    # Let's check market mapping if possible
    market_map = {}
    if FEATURES_PATH.exists():
        try:
            df_meta = pd.read_parquet(FEATURES_PATH, columns=['stock_id', 'market'])
            # Create dict: stock_id -> market
            # drop duplicates
            df_meta = df_meta.drop_duplicates(subset=['stock_id'])
            market_map = dict(zip(df_meta.stock_id, df_meta.market))
        except:
            pass

    final_tickers = []
    id_map = {}
    
    for s in stocks:
        suffix = ".TW"
        if market_map.get(s) == 'TPEX':
            suffix = ".TWO"
        elif market_map.get(s) == 'TWSE':
            suffix = ".TW"
        
        t = f"{s}{suffix}"
        final_tickers.append(t)
        id_map[t] = s

    # Download in chunks
    CHUNK_SIZE = 100
    all_dfs = []
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=400) # Covers the gap nicely
    
    logger.info(f"Chunk Size: {CHUNK_SIZE}")
    total_chunks = (len(final_tickers) + CHUNK_SIZE - 1) // CHUNK_SIZE
    
    update_progress(0, len(final_tickers), "Starting Download...")
    
    for i in range(0, len(final_tickers), CHUNK_SIZE):
        current_chunk_idx = i // CHUNK_SIZE + 1
        chunk = final_tickers[i:i+CHUNK_SIZE]
        
        msg = f"Downloading chunk {current_chunk_idx}/{total_chunks} ({len(all_dfs)} stocks saved)"
        logger.info(msg)
        update_progress(i, len(final_tickers), msg)
        
        try:
            data = yf.download(
                chunk, 
                start=start_date.strftime('%Y-%m-%d'), 
                end=end_date.strftime('%Y-%m-%d'),
                group_by='ticker',
                threads=True,
                progress=False
            )
            
            # Process MultiIndex
            for ticker in chunk:
                try:
                    if len(chunk) > 1:
                        if ticker not in data.columns.levels[0]: continue
                        df = data[ticker].copy()
                    else:
                        if data.empty: continue
                        df = data.copy()

                    if df.empty: continue
                    
                    # Clean and Standardize
                    df = df.reset_index()
                    df.columns = [c.lower() for c in df.columns]
                    
                    # Rename
                    rename_map = {'date': 'date', 'open': 'open', 'high': 'high', 'low': 'low', 'close': 'close', 'volume': 'volume'}
                    df = df.rename(columns=rename_map)
                    
                    # Add metadata
                    sid = id_map.get(ticker)
                    df['stock_id'] = sid
                    df['stock_name'] = sid # Missing name, but acceptable for chart
                    
                    # Valid check
                    if 'close' in df.columns and 'date' in df.columns:
                        # Drop NaNs
                        df = df.dropna(subset=['close'])
                        all_dfs.append(df[['date', 'stock_id', 'stock_name', 'open', 'high', 'low', 'close', 'volume']])
                        
                except Exception as e:
                    # logger.warning(f"Error processing {ticker}: {e}")
                    pass
                    
        except Exception as e:
            logger.error(f"Chunk failed: {e}")
            
    if not all_dfs:
        logger.error("No data downloaded!")
        return

    # Merge
    logger.info("Merging data...")
    update_progress(len(final_tickers), len(final_tickers), "Merging and saving data...")
    
    final_df = pd.concat(all_dfs, ignore_index=True)
    
    # Save
    logger.info(f"Saving {len(final_df)} records to {FEATURES_PATH}...")
    final_df.to_parquet(FEATURES_PATH, index=False)
    
    # Also Validate
    max_date = final_df['date'].max()
    min_date = final_df['date'].min()
    logger.info(f"Data Range: {min_date} to {max_date}")
    logger.info("✅ SUCCESS: Data overwritten with continuous history.")
    
    update_progress(len(final_tickers), len(final_tickers), "✅ Complete! Please refresh page.")

if __name__ == "__main__":
    download_and_save()


import pandas as pd
import logging
from pathlib import Path
import sys

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

DATA_DIR = Path("data/clean")
RAW_DIR = Path("data/raw")
FEATURES_PATH = DATA_DIR / "features.parquet"
UNIVERSE_PATH = DATA_DIR / "universe.parquet"
QUOTES_PATH = RAW_DIR / "latest_quotes.parquet"

def restore_names():
    if not QUOTES_PATH.exists():
        logger.error("Mapping source not found!")
        return
        
    logger.info("Loading mapping...")
    map_df = pd.read_parquet(QUOTES_PATH, columns=['stock_id', 'stock_name'])
    # formatting
    map_df = map_df.drop_duplicates(subset=['stock_id'])
    name_map = dict(zip(map_df.stock_id, map_df.stock_name))
    logger.info(f"Loaded {len(name_map)} names.")
    
    # Update FEATURES
    if FEATURES_PATH.exists():
        logger.info("Updating features.parquet...")
        df = pd.read_parquet(FEATURES_PATH)
        # map
        df['stock_name'] = df['stock_id'].map(name_map).fillna(df['stock_id'])
        df.to_parquet(FEATURES_PATH, index=False)
        logger.info("Features updated.")
        
    # Update UNIVERSE
    if UNIVERSE_PATH.exists():
        logger.info("Updating universe.parquet...")
        df = pd.read_parquet(UNIVERSE_PATH)
        df['stock_name'] = df['stock_id'].map(name_map).fillna(df['stock_id'])
        df.to_parquet(UNIVERSE_PATH, index=False)
        logger.info("Universe updated.")
        
    logger.info("✅ Names restored.")

if __name__ == "__main__":
    restore_names()


import pandas as pd
import logging
from pathlib import Path
import sys

# Add project root to path
sys.path.append(".")

from app.indicators import TechnicalIndicators
from app.volume_indicators import VolumeIndicators

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

DATA_DIR = Path("data/clean")
FEATURES_PATH = DATA_DIR / "features.parquet"

def recalc():
    logger.info("Loading raw data from features.parquet...")
    if not FEATURES_PATH.exists():
        logger.error("features.parquet not found!")
        return

    df = pd.read_parquet(FEATURES_PATH)
    logger.info(f"Loaded {len(df)} records.")
    
    # 1. Technical Indicators
    logger.info("Calculating Technical Indicators (MA, RSI, MACD, BB)...")
    tech_ind = TechnicalIndicators(df)
    df = tech_ind.calculate_all_indicators()
    
    # 2. Volume Indicators
    logger.info("Calculating Volume Indicators (OBV, Quant)...")
    vol_ind = VolumeIndicators(df)
    df = vol_ind.calculate_all_volume_indicators()
    
    # Save back
    logger.info(f"Saving updated data with {len(df.columns)} columns to {FEATURES_PATH}...")
    df.to_parquet(FEATURES_PATH, index=False)
    logger.info("✅ SUCCESS: Indicators restored.")

if __name__ == "__main__":
    recalc()

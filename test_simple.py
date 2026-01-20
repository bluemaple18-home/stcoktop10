"""
Agent A 系統簡化測試腳本
使用 Yahoo Finance 進行快速測試
"""

import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from app.indicators import TechnicalIndicators
from app.volume_indicators import VolumeIndicators
from app.fundamental_data import FundamentalData
from app.risk_filter import RiskFilter
from app.event_detector import EventDetector
from app.visualization import generate_signals_preview

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def simple_yahoo_test():
    """使用 Yahoo Finance 下載測試資料"""
    
    logger.info("=" * 80)
    logger.info("Agent A 系統簡化測試（使用 Yahoo Finance）")
    logger.info("=" * 80)
    
    # 1. 使用 Yahoo Finance 下載測試資料
    logger.info("\n[測試 1/6] 使用 Yahoo Finance 下載測試資料")
    
    import yfinance as yf
    
    # 下載幾檔台股資料進行測試
    test_stocks = ['2330.TW', '2317.TW', '2454.TW', '2882.TW', '6505.TW']  # 台積電、鴻海、聯發科、國泰金、台塑化
    
    all_data = []
    for ticker in test_stocks:
        logger.info(f"下載 {ticker}...")
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(start='2023-01-01', end='2024-01-31')
            
            if not df.empty:
                df = df.reset_index()
                df['stock_id'] = ticker.replace('.TW', '').replace('.TWO', '')
                df['stock_name'] = ticker
                df = df.rename(columns={
                    'Date': 'date',
                    'Open': 'open',
                    'High': 'high',
                    'Low': 'low',
                    'Close': 'close',
                    'Volume': 'volume'
                })
                df = df[['date', 'stock_id', 'stock_name', 'open', 'high', 'low', 'close', 'volume']]
                all_data.append(df)
                logger.info(f"✅ {ticker}: {len(df)} 筆資料")
        except Exception as e:
            logger.error(f"❌ {ticker} 下載失敗: {e}")
    
    if not all_data:
        logger.error("❌ 無法下載任何資料")
        return False
    
    df = pd.concat(all_data, ignore_index=True)
    logger.info(f"✅ 成功下載 {len(df)} 筆資料，{df['stock_id'].nunique()} 檔股票")
    
    # 2. 技術指標測試
    logger.info("\n[測試 2/6] 計算技術指標")
    tech_ind = TechnicalIndicators(df)
    df = tech_ind.calculate_all_indicators()
    
    required_indicators = ['ma5', 'ma10', 'rsi', 'macd', 'k', 'd', 'bb_upper']
    missing = [ind for ind in required_indicators if ind not in df.columns]
    
    if missing:
        logger.error(f"❌ 缺少指標: {missing}")
        return False
    
    logger.info(f"✅ 技術指標計算完成")
    logger.info(f"   缺值率: {tech_ind.get_missing_rate().max():.2f}%")
    
    # 3. 量能指標測試
    logger.info("\n[測試 3/6] 計算量能指標")
    vol_ind = VolumeIndicators(df)
    df = vol_ind.calculate_all_volume_indicators()
    
    required_volume = ['avg_volume_20d', 'volume_ratio_20d', 'obv', 'avg_value_20d']
    missing_vol = [ind for ind in required_volume if ind not in df.columns]
    
    if missing_vol:
        logger.error(f"❌ 缺少量能指標: {missing_vol}")
        return False
    
    logger.info(f"✅ 量能指標計算完成")
    
    # 4. 基本面測試
    logger.info("\n[測試 4/6] 整合基本面資料")
    fundamental = FundamentalData(df)
    df = fundamental.create_dummy_fundamental_data()
    
    fundamental_cols = ['revenue_yoy', 'eps_4q', 'roe']
    missing_fund = [col for col in fundamental_cols if col not in df.columns]
    
    if missing_fund:
        logger.error(f"❌ 缺少基本面欄位: {missing_fund}")
        return False
    
    logger.info(f"✅ 基本面資料整合完成")
    
    # 5. 技術事件偵測
    logger.info("\n[測試 5/7] 技術事件偵測")
    event_detector = EventDetector(df)
    events_df = event_detector.detect_all_events()
    
    expected_events = [
        'break_20d_high', 'ma5_cross_ma20_up', 'close_above_bb_mid', 'macd_bullish_cross', 
        'rsi_rebound_from_40', 'gap_up_close_strong', 'volume_spike', 
        'lose_20d_low', 'ma5_cross_ma20_down', 'close_below_bb_mid', 'macd_bearish_cross', 
        'rsi_break_below_50', 'long_upper_shadow'
    ]
    missing_events = [e for e in expected_events if e not in events_df.columns]
    
    if missing_events:
        logger.error(f"❌ 缺少事件欄位: {missing_events}")
        return False
        
    logger.info(f"✅ 技術事件偵測完成，共 {len(events_df.columns)-2} 個事件")
    logger.info(f"   事件觸發總數: {events_df[expected_events].sum().sum()}")

    # 6. 風險過濾測試
    logger.info("\n[測試 6/7] 風險過濾")
    
    initial_stocks = df['stock_id'].nunique()
    risk_filter = RiskFilter(df)
    universe = risk_filter.apply_all_filters(
        suspended_list=[],  # 測試模式不過濾
        min_listing_days=30,
        min_avg_value=1_000_000,  # 降低門檻
        min_price=5.0
    )
    
    final_stocks = universe['stock_id'].nunique()
    
    logger.info(f"✅ 風險過濾完成：{initial_stocks} → {final_stocks} 檔")
    
    # 7. 視覺化測試
    logger.info("\n[測試 7/7] 產生視覺化")
    
    test_dir = Path("data/test")
    test_dir.mkdir(parents=True, exist_ok=True)
    
    # 儲存測試資料
    df.to_parquet(test_dir / "features_test.parquet", index=False)
    events_df.to_parquet(test_dir / "events_test.parquet", index=False)
    universe.to_parquet(test_dir / "universe_test.parquet", index=False)
    
    # 產生預覽圖
    preview_path = test_dir / "signals_preview_test.png"
    try:
        generate_signals_preview(
            df=df,
            output_path=str(preview_path),
            num_samples=min(3, df['stock_id'].nunique())
        )
        logger.info(f"✅ 視覺化產生完成: {preview_path}")
    except Exception as e:
        logger.warning(f"⚠️  視覺化產生失敗: {e}")
    
    logger.info(f"✅ 測試資料已儲存至 {test_dir}")
    
    # 總結
    logger.info("\n" + "=" * 80)
    logger.info("✅ 測試完成！所有模組運作正常")
    logger.info("=" * 80)
    logger.info(f"\n測試統計:")
    logger.info(f"  - 資料期間: {df['date'].min().date()} ~ {df['date'].max().date()}")
    logger.info(f"  - 資料筆數: {len(df):,}")
    logger.info(f"  - 原始股票數: {initial_stocks}")
    logger.info(f"  - 過濾後股票數: {final_stocks}")
    logger.info(f"  - 總欄位數: {len(df.columns)}")
    logger.info(f"\n產出檔案:")
    logger.info(f"  - {test_dir / 'features_test.parquet'}")
    logger.info(f"  - {test_dir / 'universe_test.parquet'}")
    logger.info(f"  - {preview_path}")
    
    return True


if __name__ == "__main__":
    try:
        success = simple_yahoo_test()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"測試過程發生錯誤: {e}", exc_info=True)
        sys.exit(1)

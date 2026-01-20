"""
Agent A 系統快速測試腳本
測試資料擷取與指標計算（使用少量資料）
"""

import sys
from pathlib import Path

# 確保可以引入 app 模組
sys.path.insert(0, str(Path(__file__).parent))

from app.data_fetcher import DataFetcherOrchestrator
from app.indicators import TechnicalIndicators
from app.volume_indicators import VolumeIndicators
from app.fundamental_data import FundamentalData
from app.risk_filter import RiskFilter

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def quick_test():
    """快速測試（僅擷取近 7 天資料）"""
    
    logger.info("=" * 80)
    logger.info("Agent A 系統快速測試")
    logger.info("=" * 80)
    
    # 1. 資料擷取測試
    logger.info("\n[測試 1] 資料擷取")
    orchestrator = DataFetcherOrchestrator(data_dir="data/raw")
    
    # 使用已知有資料的日期範圍（2024年1月）
    start_date = "2024-01-08"  # 星期一
    end_date = "2024-01-15"    # 下星期一（約7個交易日）
    
    df = orchestrator.fetch_historical_data(
        start_date=start_date,
        end_date=end_date,
        delay=2.0  # 縮短延遲加快測試
    )
    
    if df.empty:
        logger.error("❌ 資料擷取失敗")
        return False
    
    logger.info(f"✅ 成功擷取 {len(df)} 筆資料，{df['stock_id'].nunique()} 檔股票")
    
    # 2. 技術指標測試
    logger.info("\n[測試 2] 技術指標計算")
    tech_ind = TechnicalIndicators(df)
    df = tech_ind.calculate_all_indicators()
    
    required_indicators = ['ma5', 'ma10', 'rsi', 'macd', 'k', 'd', 'bb_upper']
    missing = [ind for ind in required_indicators if ind not in df.columns]
    
    if missing:
        logger.error(f"❌ 缺少指標: {missing}")
        return False
    
    logger.info(f"✅ 技術指標計算完成，缺值率: {tech_ind.get_missing_rate().max():.2f}%")
    
    # 3. 量能指標測試
    logger.info("\n[測試 3] 量能指標計算")
    vol_ind = VolumeIndicators(df)
    df = vol_ind.calculate_all_volume_indicators()
    
    required_volume = ['avg_volume_20d', 'volume_ratio_20d', 'obv', 'avg_value_20d']
    missing_vol = [ind for ind in required_volume if ind not in df.columns]
    
    if missing_vol:
        logger.error(f"❌ 缺少量能指標: {missing_vol}")
        return False
    
    logger.info(f"✅ 量能指標計算完成")
    
    # 4. 基本面測試
    logger.info("\n[測試 4] 基本面資料整合")
    fundamental = FundamentalData(df)
    df = fundamental.create_dummy_fundamental_data()
    
    fundamental_cols = ['revenue_yoy', 'eps_4q', 'roe']
    missing_fund = [col for col in fundamental_cols if col not in df.columns]
    
    if missing_fund:
        logger.error(f"❌ 缺少基本面欄位: {missing_fund}")
        return False
    
    logger.info(f"✅ 基本面資料整合完成")
    
    # 5. 風險過濾測試
    logger.info("\n[測試 5] 風險過濾")
    suspended_list = orchestrator.fetch_suspended_stocks_list()
    
    initial_stocks = df['stock_id'].nunique()
    risk_filter = RiskFilter(df)
    universe = risk_filter.apply_all_filters(
        suspended_list=suspended_list,
        min_listing_days=30,  # 降低門檻以便測試
        min_avg_value=5_000_000,  # 降低門檻
        min_price=5.0  # 降低門檻
    )
    
    final_stocks = universe['stock_id'].nunique()
    
    logger.info(f"✅ 風險過濾完成：{initial_stocks} → {final_stocks} 檔")
    
    # 6. 儲存測試結果
    logger.info("\n[測試 6] 檔案儲存")
    test_dir = Path("data/test")
    test_dir.mkdir(parents=True, exist_ok=True)
    
    df.to_parquet(test_dir / "features_test.parquet", index=False)
    universe.to_parquet(test_dir / "universe_test.parquet", index=False)
    
    logger.info(f"✅ 測試資料已儲存至 {test_dir}")
    
    # 總結
    logger.info("\n" + "=" * 80)
    logger.info("測試完成！所有模組運作正常")
    logger.info("=" * 80)
    logger.info(f"\n測試統計:")
    logger.info(f"  - 資料筆數: {len(df):,}")
    logger.info(f"  - 原始股票數: {initial_stocks}")
    logger.info(f"  - 過濾後股票數: {final_stocks}")
    logger.info(f"  - 技術指標數: {len([c for c in df.columns if 'ma' in c or 'rsi' in c or 'macd' in c])}")
    logger.info(f"  - 量能指標數: {len([c for c in df.columns if 'volume' in c or 'obv' in c])}")
    
    return True


if __name__ == "__main__":
    try:
        success = quick_test()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"測試過程發生錯誤: {e}", exc_info=True)
        sys.exit(1)

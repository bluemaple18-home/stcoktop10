"""
ETL 主流程
整合所有模組的完整資料處理流程
"""

import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import logging

from data_fetcher import DataFetcherOrchestrator
from indicators import TechnicalIndicators
from volume_indicators import VolumeIndicators
from fundamental_data import FundamentalData
from risk_filter import RiskFilter
from event_detector import EventDetector
try:
    from finmind_integrator import FinMindIntegrator
except ImportError:
    from app.finmind_integrator import FinMindIntegrator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ETLPipeline:
    """完整的 ETL 流程"""
    
    def __init__(self, data_dir: str = "data", artifacts_dir: str = "artifacts"):
        self.data_dir = Path(data_dir)
        self.raw_dir = self.data_dir / "raw"
        self.clean_dir = self.data_dir / "clean"
        self.artifacts_dir = Path(artifacts_dir)
        
        # 建立目錄
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.clean_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        self.etl_stats = {}
    
    def run_full_pipeline(
        self,
        start_date: str = None,
        end_date: str = None,
        use_dummy_fundamental: bool = True,
        delay: float = 3.0
    ):
        """
        執行完整的 ETL 流程
        
        Args:
            start_date: 開始日期 'YYYY-MM-DD'（預設為 3 年前）
            end_date: 結束日期 'YYYY-MM-DD'（預設為今日）
            use_dummy_fundamental: 是否使用虛擬基本面資料
            delay: API 請求延遲秒數
        """
        logger.info("=" * 80)
        logger.info("開始執行 Agent A 盤後資料整備 ETL 流程")
        logger.info("=" * 80)
        
        # 設定日期範圍
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=3*365)).strftime('%Y-%m-%d')
        
        logger.info(f"資料區間: {start_date} ~ {end_date}")
        
        # 1. 資料擷取
        logger.info("\n[階段 1/7] 資料擷取")
        logger.info("-" * 80)
        orchestrator = DataFetcherOrchestrator(data_dir=str(self.raw_dir))
        
        # 擷取日行情
        df = orchestrator.fetch_historical_data(
            start_date=start_date,
            end_date=end_date,
            delay=delay
        )
        
        if df.empty:
            logger.error("資料擷取失敗，中止流程")
            return
        
        self.etl_stats['data_fetching'] = {
            'total_records': len(df),
            'unique_stocks': df['stock_id'].nunique(),
            'date_range': f"{df['date'].min()} ~ {df['date'].max()}",
            'markets': df['market'].value_counts().to_dict() if 'market' in df.columns else {}
        }
        
        # 擷取處置股清單
        suspended_list = orchestrator.fetch_suspended_stocks_list()
        
        # 1.1 整合 FinMind 籌碼面資料 (新增)
        logger.info("\n[階段 1.1] FinMind 籌碼面資料整合")
        logger.info("-" * 80)
        # 嘗試從環境變數或檔案讀取 token (此處暫留 null)
        finmind = FinMindIntegrator()
        df = finmind.integrate_chip_data(df)
        
        # 2. 技術指標計算
        logger.info("\n[階段 2/7] 技術指標計算")
        logger.info("-" * 80)
        tech_ind = TechnicalIndicators(df)
        df = tech_ind.calculate_all_indicators()
        
        self.etl_stats['technical_indicators'] = {
            'missing_rate': tech_ind.get_missing_rate().to_dict()
        }
        
        # 3. 量能指標計算
        logger.info("\n[階段 3/7] 量能指標計算")
        logger.info("-" * 80)
        vol_ind = VolumeIndicators(df)
        df = vol_ind.calculate_all_volume_indicators()
        
        self.etl_stats['volume_indicators'] = {
            'missing_rate': vol_ind.get_missing_rate().to_dict()
        }
        
        # 4. 基本面資料整合
        logger.info("\n[階段 4/7] 基本面資料整合")
        logger.info("-" * 80)
        fundamental = FundamentalData(df)
        
        # 抓取營收資料（使用批次抓取）
        logger.info("批次抓取月營收資料...")
        try:
            # 計算營收抓取的日期範圍（取主資料的日期範圍）
            rev_start = df['date'].min().strftime('%Y-%m-%d')
            rev_end = df['date'].max().strftime('%Y-%m-%d')
            
            revenue_df = orchestrator.twse.fetch_revenue_batch(
                start_date=rev_start,
                end_date=rev_end,
                save_to_disk=True
            )
            
            if not revenue_df.empty:
                # 合併營收資料
                df = fundamental.merge_revenue_data(revenue_df)
                logger.info(f"✅ 已整合真實營收資料，共 {len(revenue_df)} 筆")
                
                # 統計營收資料覆蓋率
                revenue_coverage = (df['revenue_yoy'].notna().sum() / len(df)) * 100
                self.etl_stats['revenue_data'] = {
                    'total_records': len(revenue_df),
                    'coverage_rate': f"{revenue_coverage:.2f}%",
                    'yoy_mean': df['revenue_yoy'].mean(),
                    'mom_mean': df['revenue_mom'].mean()
                }
            else:
                logger.warning("營收資料抓取失敗，使用虛擬資料")
                df = fundamental.create_dummy_fundamental_data()
                self.etl_stats['revenue_data'] = {'status': 'dummy_data_used'}
                
        except Exception as e:
            logger.error(f"營收資料處理失敗: {e}")
            logger.warning("改用虛擬基本面資料")
            df = fundamental.create_dummy_fundamental_data()
            self.etl_stats['revenue_data'] = {'status': f'error: {str(e)}'}
            
        # 5. 儲存完整特徵資料
        logger.info("\n[階段 5/7] 儲存完整特徵資料")
        logger.info("-" * 80)
        features_path = self.clean_dir / "features.parquet"
        df.to_parquet(features_path, index=False)
        logger.info(f"features.parquet 已儲存: {len(df)} 筆, {df['stock_id'].nunique()} 檔股票")
        
        self.etl_stats['features_file'] = {
            'path': str(features_path),
            'size_mb': features_path.stat().st_size / 1024 / 1024,
            'records': len(df),
            'stocks': df['stock_id'].nunique()
        }

        # 6. 技術事件偵測 (新增)
        logger.info("\n[階段 6/7] 技術事件偵測")
        logger.info("-" * 80)
        event_detector = EventDetector(df)
        events_df = event_detector.detect_all_events()
        
        events_path = self.clean_dir / "events.parquet"
        events_df.to_parquet(events_path, index=False)
        logger.info(f"events.parquet 已儲存: {len(events_df)} 筆, {len(events_df.columns)-2} 個事件")
        
        self.etl_stats['events_file'] = {
            'path': str(events_path),
            'size_mb': events_path.stat().st_size / 1024 / 1024,
            'records': len(events_df),
            'events_count': len(events_df.columns) - 2
        }
        
        # 7. 風險過濾
        logger.info("\n[階段 7/7] 風險過濾")
        logger.info("-" * 80)
        risk_filter = RiskFilter(df)
        universe = risk_filter.apply_all_filters(
            suspended_list=suspended_list,
            min_listing_days=60,
            min_avg_value=10_000_000,
            min_price=10.0
        )
        
        # 儲存股票池
        universe_path = self.clean_dir / "universe.parquet"
        universe.to_parquet(universe_path, index=False)
        logger.info(f"universe.parquet 已儲存: {len(universe)} 筆, {universe['stock_id'].nunique()} 檔股票")
        
        self.etl_stats['universe_file'] = {
            'path': str(universe_path),
            'size_mb': universe_path.stat().st_size / 1024 / 1024,
            'records': len(universe),
            'stocks': universe['stock_id'].nunique()
        }
        
        self.etl_stats['risk_filtering'] = risk_filter.get_filter_report().to_dict('records')
        
        # 8. 產生報告與視覺化
        logger.info("\n[階段 8/8] 產生報告與視覺化")
        logger.info("-" * 80)
        
        # 產生 ETL 報告
        self.generate_etl_report(df, universe, events_df, orchestrator, tech_ind, vol_ind)
        
        # 產生視覺化
        from visualization import generate_signals_preview
        preview_path = self.artifacts_dir / "signals_preview.png"
        generate_signals_preview(universe, output_path=str(preview_path), num_samples=5)
        
        logger.info("\n" + "=" * 80)
        logger.info("ETL 流程執行完成！")
        logger.info("=" * 80)
        logger.info(f"\n產出檔案:")
        logger.info(f"  - {features_path}")
        logger.info(f"  - {universe_path}")
        logger.info(f"  - {self.artifacts_dir / 'etl_report.md'}")
        logger.info(f"  - {preview_path}")
    
    def generate_etl_report(
        self,
        features_df: pd.DataFrame,
        universe_df: pd.DataFrame,
        events_df: pd.DataFrame,
        orchestrator: DataFetcherOrchestrator,
        tech_ind: TechnicalIndicators,
        vol_ind: VolumeIndicators
    ):
        """產生 ETL 報告"""
        
        report_path = self.artifacts_dir / "etl_report.md"
        
        # 計算整體缺值率
        all_missing = features_df.isnull().sum() / len(features_df) * 100
        main_indicators_missing = all_missing[all_missing.index.str.contains('ma|rsi|macd|obv|volume', case=False, na=False)]
        
        # 資料來源統計
        data_quality = orchestrator.get_data_quality_report()
        source_stats = data_quality['source'].value_counts().to_dict() if not data_quality.empty else {}
        
        # 產生報告
        report = f"""# Agent A 盤後資料整備 ETL 報告

**執行時間**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 📊 資料摘要

### 完整特徵資料 (features.parquet)

- **資料筆數**: {len(features_df):,} 筆
- **股票數量**: {features_df['stock_id'].nunique():,} 檔
- **涵蓋日期**: {features_df['date'].min().strftime('%Y-%m-%d')} ~ {features_df['date'].max().strftime('%Y-%m-%d')}
- **檔案大小**: {self.etl_stats['features_file']['size_mb']:.2f} MB

### 技術事件資料 (events.parquet)

- **資料筆數**: {len(events_df):,} 筆
- **事件數量**: {self.etl_stats['events_file']['events_count']} 種
- **檔案大小**: {self.etl_stats['events_file']['size_mb']:.2f} MB

### 股票池 (universe.parquet)

- **資料筆數**: {len(universe_df):,} 筆
- **股票數量**: {universe_df['stock_id'].nunique():,} 檔
- **檔案大小**: {self.etl_stats['universe_file']['size_mb']:.2f} MB

> [!{"IMPORTANT" if universe_df['stock_id'].nunique() >= 500 else "WARNING"}]
> 今日 universe 股票數: **{universe_df['stock_id'].nunique()} 檔**
> {"✅ 達到驗收標準 (≥ 500)" if universe_df['stock_id'].nunique() >= 500 else "⚠️ 未達驗收標準 (< 500)"}

---

## 📈 資料來源統計

| 來源 | 成功筆數 | 失敗筆數 |
|------|---------|---------|
"""
        
        if not data_quality.empty:
            success_stats = data_quality[data_quality['status'] == 'success'].groupby('source').size()
            failed_stats = data_quality[data_quality['status'] != 'success'].groupby('source').size()
            
            all_sources = set(success_stats.index.tolist() + failed_stats.index.tolist())
            for source in sorted(all_sources):
                success = success_stats.get(source, 0)
                failed = failed_stats.get(source, 0)
                report += f"| {source} | {success:,} | {failed:,} |\n"
        else:
            report += "| N/A | N/A | N/A |\n"
        
        report += f"""
---

## 🔍 缺值率分析

### 主要技術指標缺值率

| 指標 | 缺值率 (%) |
|------|-----------|
"""
        
        for indicator, missing_pct in main_indicators_missing.head(10).items():
            status = "✅" if missing_pct < 1.0 else "⚠️"
            report += f"| {indicator} | {missing_pct:.2f}% {status} |\n"
        
        max_missing = main_indicators_missing.max()
        report += f"""
> [!{"IMPORTANT" if max_missing < 1.0 else "WARNING"}]
> 主要指標最高缺值率: **{max_missing:.2f}%**
> {"✅ 達到驗收標準 (< 1%)" if max_missing < 1.0 else "⚠️ 未達驗收標準 (≥ 1%)"}

---

## 🛡️ 風險過濾統計

| 過濾階段 | 剩餘股票數 | 移除股票數 |
|---------|-----------|-----------|
"""
        
        for stage_info in self.etl_stats.get('risk_filtering', []):
            stage = stage_info.get('stage', 'N/A')
            remaining = stage_info.get('remaining_stocks', stage_info.get('unique_stocks', 'N/A'))
            removed = stage_info.get('removed_stocks', 0)
            
            if stage == 'initial':
                report += f"| 初始資料 | {remaining:,} | - |\n"
            else:
                report += f"| {stage} | {remaining:,} | {removed:,} |\n"
        
        report += f"""
---

## 📋 欄位清單

### 基本欄位
- `date`: 日期
- `stock_id`: 股票代碼
- `stock_name`: 股票名稱
- `open`, `high`, `low`, `close`: 開高低收
- `volume`: 成交量

### 技術指標
- MA: `ma5`, `ma10`, `ma20`, `ma60`
- EMA: `ema12`, `ema26`
- MACD: `macd`, `macd_signal`, `macd_hist`
- RSI: `rsi`
- KD: `k`, `d`
- 布林通道: `bb_upper`, `bb_middle`, `bb_lower`, `bb_width`
- 前高突破: `breakout_flag`

### 量能指標
- 平均量: `avg_volume_5d`, `avg_volume_10d`, `avg_volume_20d`
- 量比: `volume_ratio_5d`, `volume_ratio_10d`, `volume_ratio_20d`
- OBV: `obv`
- 日均成交值: `avg_value_20d`

### 基本面指標
- 營收: `revenue_yoy`, `revenue_mom`
- 獲利: `eps_4q`, `roe`, `gross_margin`
- 殖利率: `dividend_yield`

---

## ⚠️ 注意事項

> [!NOTE]
> 基本面資料目前使用虛擬資料（測試模式），實際應用時需整合真實資料來源。

> [!TIP]
> 建議每日執行此 ETL 流程，確保資料保持最新狀態。

---

**報告產生時間**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        # 寫入報告
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"ETL 報告已產生: {report_path}")
    
    def validate(self):
        """驗證產出是否符合驗收標準"""
        logger.info("執行驗收測試...")
        
        # 檢查檔案是否存在
        features_path = self.clean_dir / "features.parquet"
        universe_path = self.clean_dir / "universe.parquet"
        events_path = self.clean_dir / "events.parquet"
        
        if not features_path.exists() or not universe_path.exists() or not events_path.exists():
            logger.error("❌ 必要檔案不存在")
            return False
        
        # 載入檔案
        universe = pd.read_parquet(universe_path)
        features = pd.read_parquet(features_path)
        events = pd.read_parquet(events_path)
        
        # 檢查 events 與 features 用量是否一致 (簡單檢查行數)
        if len(events) != len(features):
             logger.warning(f"⚠️ events ({len(events)}) 與 features ({len(features)}) 筆數不一致")
        else:
             logger.info("✅ events 與 features 筆數一致")
             
        # 檢查事件欄位
        expected_events = [
            'break_20d_high', 'ma5_cross_ma20_up', 'close_above_bb_mid', 'macd_bullish_cross', 
            'rsi_rebound_from_40', 'gap_up_close_strong', 'volume_spike', 
            'lose_20d_low', 'ma5_cross_ma20_down', 'close_below_bb_mid', 'macd_bearish_cross', 
            'rsi_break_below_50', 'long_upper_shadow'
        ]
        
        missing_events = [e for e in expected_events if e not in events.columns]
        if missing_events:
            logger.warning(f"⚠️ events 缺少欄位: {missing_events}")
        else:
            logger.info("✅ events 包含所有預期事件欄位")
        
        # 檢查股票數
        stock_count = universe['stock_id'].nunique()
        if stock_count < 500:
            logger.warning(f"⚠️ universe 股票數 ({stock_count}) < 500")
        else:
            logger.info(f"✅ universe 股票數 ({stock_count}) ≥ 500")
        
        # 檢查缺值率
        main_indicators = universe.filter(regex='ma|rsi|macd|obv|volume', axis=1)
        missing_rate = (main_indicators.isnull().sum() / len(universe) * 100).max()
        
        if missing_rate >= 1.0:
            logger.warning(f"⚠️ 主要指標缺值率 ({missing_rate:.2f}%) ≥ 1%")
        else:
            logger.info(f"✅ 主要指標缺值率 ({missing_rate:.2f}%) < 1%")
        
        logger.info("驗收測試完成")
        
        return stock_count >= 500 and missing_rate < 1.0 and len(missing_events) == 0


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Agent A 盤後資料整備 ETL 流程')
    parser.add_argument('--start-date', type=str, help='開始日期 (YYYY-MM-DD)', default=None)
    parser.add_argument('--end-date', type=str, help='結束日期 (YYYY-MM-DD)', default=None)
    parser.add_argument('--delay', type=float, help='API 請求延遲秒數', default=3.0)
    parser.add_argument('--validate', action='store_true', help='僅執行驗收測試')
    
    args = parser.parse_args()
    
    pipeline = ETLPipeline()
    
    if args.validate:
        # 僅驗證
        pipeline.validate()
    else:
        # 執行完整流程
        pipeline.run_full_pipeline(
            start_date=args.start_date,
            end_date=args.end_date,
            delay=args.delay
        )
        
        # 執行驗收
        pipeline.validate()

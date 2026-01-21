
import pandas as pd
import numpy as np
import lightgbm as lgb
import yaml
from pathlib import Path
from datetime import datetime
import pickle
import logging
import shap

# 新增：報告生成器
try:
    from report_generator import StockReportGenerator
except ImportError:
    from app.report_generator import StockReportGenerator

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class StockRanker:
    """股票排名器 (Advanced版)：融合校準後的模型機率、規則分數與 SHAP 解釋"""
    
    # 技術指標中英對照表
    SIGNAL_TRANSLATIONS = {
        'break_20d_high': '突破20日新高',
        'rebound_ma20': '月線支撐反彈',
        'close_above_bb_mid': '站上布林中軌',
        'macd_bullish_cross': 'MACD黃金交叉',
        'gap_up_close_strong': '跳空強勢收紅',
        'volume_spike': '成交量暴增',
        'ma5_cross_ma20_up': '5日線突破月線',
        'rsi_oversold_bounce': 'RSI超賣反彈',
        'kd_golden_cross': 'KD黃金交叉',
        'break_60d_high': '突破60日新高',
        'volume_ma_breakout': '量能突破均量',
        'bullish_engulfing': '多頭吞噬K線',
        'hammer': '錘子線型態',
        'morning_star': '晨星反轉',
    }
    
    def __init__(self, data_dir: str = "data/clean", model_dir: str = "models",
                 artifact_dir: str = "artifacts", config_path: str = "config/signals.yaml"):
        """
        初始化排名器
        """
        self.data_dir = Path(data_dir)
        self.model_dir = Path(model_dir)
        self.artifact_dir = Path(artifact_dir)
        self.config_path = Path(config_path)
        self.model = None
        self.calibrator = None
        
        # 載入設定
        self.config = self._load_config()
        self.weights = self.config['scoring']['weights']
        # Alpha: 模型分數權重 (預設 0.5)
        self.alpha = self.config['scoring'].get('alpha', 0.5)
        self.top_n = 10
        
        # 建立必要目錄
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_config(self):
        """載入訊號設定"""
        if not self.config_path.exists():
            logger.warning(f"設定檔 {self.config_path} 不存在，使用預設值")
            return {
                'scoring': {
                    'weights': {
                         'rebound_ma20': 1.0,
                         'break_20d_high': 1.5
                    },
                    'alpha': 0.5
                }
            }
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def load_model(self, filename: str = "latest_lgbm.pkl"):
        """載入模型 (支援 Old Booster or New Dict)"""
        model_path = self.model_dir / filename
        if not model_path.exists():
            raise FileNotFoundError(f"找不到模型檔案: {model_path}")
            
        with open(model_path, 'rb') as f:
            obj = pickle.load(f)
            
        if isinstance(obj, dict):
            self.model = obj['model']
            self.calibrator = obj.get('calibrator')
            logger.info(f"✓ 已載入模型與校準器: {filename}")
        else:
            self.model = obj
            self.calibrator = None
            logger.info(f"✓ 已載入舊版模型 (無校準): {filename}")

    def load_daily_data(self, date: str = None) -> tuple:
        """載入當日資料"""
        features_path = self.data_dir / "features.parquet"
        universe_path = self.data_dir / "universe.parquet"
        
        if not features_path.exists():
             raise FileNotFoundError("找不到特徵檔案 (features.parquet)")
        
        features = pd.read_parquet(features_path)
        
        if universe_path.exists():
            universe = pd.read_parquet(universe_path)
            if universe.empty:
                logger.warning("universe.parquet 是空的，使用 features 所有股票")
                universe = pd.DataFrame({'stock_id': features['stock_id'].unique()})
        else:
            universe = pd.DataFrame({'stock_id': features['stock_id'].unique()})

        if date:
            target_date = pd.to_datetime(date)
        else:
            target_date = features['date'].max()
            
        logger.info(f"載入日期: {target_date}")
        
        # 優化：只保留最近 90 天以加速 Rolling 計算
        start_date = target_date - pd.Timedelta(days=90)
        features = features[features['date'] >= start_date].copy()
        
        # 預計算：壓力線 (近20日高點，不含今日)
        features['ref_high_20d'] = features.groupby('stock_id')['high'].transform(lambda x: x.shift(1).rolling(20).max())
        features['ref_high_60d'] = features.groupby('stock_id')['high'].transform(lambda x: x.shift(1).rolling(60).max())
        
        daily_features = features[features['date'] == target_date].copy()
        
        if 'date' in universe.columns:
            daily_universe = universe[universe['date'] == target_date].copy()
        else:
            daily_universe = universe

        valid_stocks = daily_universe['stock_id'].unique()
        df = daily_features[daily_features['stock_id'].isin(valid_stocks)].copy()
        
        # 確保 float32 (LightGBM 需求)
        float_cols = df.select_dtypes(include=['float64']).columns
        if len(float_cols) > 0:
            df[float_cols] = df[float_cols].astype('float32')
            
        return df, features # Return both daily and history

    def calculate_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """計算總分 (含校準機率)"""
        df = df.copy()
        
        # 1. 模型預測分數 (Win Prob)
        if self.model:
            model_features = self.model.feature_name()
            # 補缺值
            for f in model_features:
                if f not in df.columns:
                    df[f] = 0
            
            X = df[model_features]
            # Predict Raw
            raw_prob = self.model.predict(X)
            df['raw_prob'] = raw_prob
            
            # Calibrate if available
            if self.calibrator:
                # IsotonicRegression.predict expects 1D array
                df['model_prob'] = self.calibrator.predict(raw_prob)
            else:
                df['model_prob'] = raw_prob
        else:
            df['model_prob'] = 0.5 
            df['raw_prob'] = 0.5
            
        # 2. 規則分數 (Rule Score)
        df['rule_score'] = 0.0
        df['reasons'] = "" # Rule-based reasons
        
        for signal, weight in self.weights.items():
            if signal in df.columns:
                val = df[signal].fillna(0).astype(float)
                triggered = val > 0
                df.loc[triggered, 'rule_score'] += weight
                
                reason_mask = triggered
                # 使用中文翻譯（如有）
                display_name = self.SIGNAL_TRANSLATIONS.get(signal, signal)
                tag = f"{display_name}(+{weight}) " if weight > 0 else f"{display_name}({weight}) "
                
                if reason_mask.any():
                    # 暫存原始訊號，稍後統一組裝模板
                    # df.loc[reason_mask, 'reasons'] = df.loc[reason_mask, 'reasons'] + tag
                    # 這裡改為用一個 new column 存 raw signals
                    if 'raw_signals' not in df.columns:
                        df['raw_signals'] = ""
                    df.loc[reason_mask, 'raw_signals'] = df.loc[reason_mask, 'raw_signals'] + tag
        
        # 組裝完整模板
        # 需要計算：止損(MA20 or Low*0.95)、目標(Close*1.1)
        # 格式：
        # **🎯 操作策略**
        # • 進場：{Close}
        # • 止損：{Stop_Loss} ({Note})
        # • 目標：{Target} (+10%)
        #
        # **💡 關鍵理由**
        # • {Reason 1}
        # • {Reason 2}
        
        reasons_formatted = []
        for idx, row in df.iterrows():
            close = row.get('close', 0)
            ma20 = row.get('ma20', 0)
            
            # 策略計算
            if ma20 > 0 and close > ma20:
                stop_loss = ma20 * 0.98 # 月線下方一點點
                stop_note = "月線支撐"
            else:
                stop_loss = close * 0.95
                stop_note = "回檔5%"
                
            target_price = close * 1.1 # 預設 10% 獲利
            
            # 解析原始訊號
            raw_sigs = row.get('raw_signals', '').strip()
            # 移除分數括號，只留中文名稱
            import re
            clean_sigs = re.sub(r'\([+-]?\d+\.?\d*\)', '', raw_sigs).split()
            
            # 組合模板
            tpl = f"""**🎯 操作策略**  
• 進場：{close:.1f}  
• 止損：{stop_loss:.1f} ({stop_note})  
• 目標：{target_price:.1f} (+10%)  

**💡 關鍵理由**  
"""
            if clean_sigs:
                # 豐富化理由 (加入具體數值)
                enriched_sigs = []
                for s in clean_sigs[:3]:
                    if '突破20日' in s:
                        prior_high = row.get('ref_high_20d', 0)
                        if prior_high > 0:
                            s = f"{s} (壓力{prior_high:.1f})"
                    if '突破60日' in s:
                        prior_high = row.get('ref_high_60d', 0)
                        if prior_high > 0:
                            s = f"{s} (壓力{prior_high:.1f})"
                    if '月線支撐' in s:
                        s = f"{s} (MA20:{ma20:.1f})"
                    if '黃金交叉' in s:
                        # 標註日期 (當日)
                        date_str = row['date'].strftime('%m/%d') if 'date' in row else ""
                        s = f"{s} ({date_str})"
                    enriched_sigs.append(s)
                    
                tpl += "  \n".join([f"• {s}" for s in enriched_sigs])
            else:
                tpl += "• 綜合技術指標轉強"
                
            reasons_formatted.append(tpl)
            
        df['reasons'] = reasons_formatted
        
        # 3. 規則分數正規化
        max_score = df['rule_score'].max()
        min_score = df['rule_score'].min()
        if max_score > min_score:
            df['rule_score_norm'] = (df['rule_score'] - min_score) / (max_score - min_score)
        else:
            df['rule_score_norm'] = 0.5
            
        # 4. 融合 (改用 raw_prob 以保留 AI 排序能力)
        df['final_score'] = self.alpha * df['raw_prob'] + (1 - self.alpha) * df['rule_score_norm']
        df = df.sort_values('final_score', ascending=False)
        return df
        
    def _enrich_with_shap(self, df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
        """為 Top N 股票增加 SHAP AI 解釋"""
        if self.model is None: return df
        
        # 只取前 N 名做解釋 (加速)
        top_df = df.head(top_n).copy()
        
        try:
            model_features = self.model.feature_name()
            X_top = top_df[model_features]
            
            # 建立 Explainer (TreeExplainer)
            explainer = shap.TreeExplainer(self.model)
            shap_values = explainer.shap_values(X_top)
            
            # shap_values 可能是 list (Binary case sometimes returns [neg, pos])
            if isinstance(shap_values, list):
                shap_values = shap_values[1] # 取 Positive class contribution
                
            # 為每一列生成 "AI Reason"
            ai_reasons = []
            for i in range(len(top_df)):
                # 找出貢獻最大的前 3 個特徵
                vals = shap_values[i]
                # sort indices
                top_indices = np.argsort(np.abs(vals))[-3:][::-1] # absolute value biggest 3
                
                reason_parts = []
                for idx in top_indices:
                    feat_name = model_features[idx]
                    contrib = vals[idx]
                    # 只顯示有意義的貢獻 (> 0.01 或 < -0.01 margin)
                    if abs(contrib) > 0.01:
                        sign = "+" if contrib > 0 else ""
                        reason_parts.append(f"{feat_name}({sign}{contrib:.2f})")
                
                if reason_parts:
                    ai_reasons.append(" | AI: " + " ".join(reason_parts))
                else:
                    ai_reasons.append("")
            
            top_df['reasons'] = top_df['reasons'] + pd.Series(ai_reasons, index=top_df.index)
            
            # 更新回原始 DF
            df.loc[top_df.index, 'reasons'] = top_df['reasons']
            
        except Exception as e:
            logger.warning(f"SHAP 解釋生成失敗: {e}")
            
        return df

    def run_ranking(self, date: str = None):
        """執行排名主流程"""
        try:
            # Load Data
            df, history_df = self.load_daily_data(date)
            if df.empty:
                logger.warning("無資料可排名")
                return
            
            # Calc Scores
            rank_df = self.calculate_scores(df)
            
            # Enrich with SHAP (Before saving Top 10)
            rank_df = self._enrich_with_shap(rank_df, top_n=20)
            
            # Select Top 10
            top10 = rank_df.head(10).copy()
            
            # Enrich with Stock Names (using local mapping)
            if 'stock_name' not in top10.columns or top10['stock_name'].isnull().any():
                logger.info("正在添加股票名稱...")
                from stock_names import get_stock_name
                
                names = []
                for _, row in top10.iterrows():
                    sid = str(row['stock_id'])
                    names.append(get_stock_name(sid))
                
                top10['stock_name'] = names
                # Update rank_df as well for completeness if needed (optional)

            # Save
            today_str = date if date else datetime.now().strftime('%Y-%m-%d')
            path = self.artifact_dir / f"ranking_{today_str}.csv"
            
            out_cols = ['stock_id', 'stock_name', 'close', 'final_score', 'model_prob', 'rule_score', 'reasons']
            # Ensure cols exist
            out_cols = [c for c in out_cols if c in top10.columns]
            
            top10[out_cols].to_csv(path, index=False, encoding='utf-8-sig')
            
            print(f"\n🏆 Top 10 選股結果 (含 AI 解釋) ({today_str}):")
            print(top10[out_cols].to_string(index=False))
            print(f"\n檔案已儲存: {path}")
            
            # 新增：生成結構化分析報告
            try:
                print("\n📝 生成結構化分析報告...")
                report_gen = StockReportGenerator(artifacts_dir=str(self.artifact_dir))
                report_gen.generate_report(ranked_df=rank_df, features_df=history_df)
            except Exception as report_err:
                logger.warning(f"報告生成失敗（不影響主流程）: {report_err}")
            
        except Exception as e:
            logger.error(f"排名執行失敗: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    ranker = StockRanker()
    try:
        ranker.load_model()
    except Exception as e:
        print(f"注意: {e}")
        
    ranker.run_ranking()

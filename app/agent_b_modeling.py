
import pandas as pd
import numpy as np
import lightgbm as lgb
from pathlib import Path
from datetime import datetime, timedelta
import pickle
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import TimeSeriesSplit
import optuna
from sklearn.metrics import roc_auc_score, log_loss
from sklearn.isotonic import IsotonicRegression
import shap
import mlflow
import mlflow.lightgbm
import webbrowser
import os

# 引入新的標籤生成器
try:
    from labels import LabelGenerator
except ImportError:
    # 若相對路徑匯入失敗，嘗試從 app 匯入
    from app.labels import LabelGenerator


class LightGBMTrainer:
    """LightGBM 分類模型訓練器 (Advanced 版: Calibration + SHAP)"""
    
    def __init__(self, data_dir: str = "data/clean", model_dir: str = "models", 
                 artifact_dir: str = "artifacts", horizon: int = 10, threshold: float = 0.03):
        """
        初始化訓練器
        Args:
            horizon: 持有天數 (預設 10 天)
            threshold: 獲利門檻 (預設 5%)
        """
        self.data_dir = Path(data_dir)
        self.model_dir = Path(model_dir)
        self.artifact_dir = Path(artifact_dir)
        self.horizon = horizon
        self.threshold = threshold
        self.model = None
        self.calibrator = None  # 機率校準器
        self.best_params = None
        
        # 建立必要目錄
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
    
    def load_features(self, file_path: str = None) -> pd.DataFrame:
        """載入特徵資料"""
        if file_path is None:
            # 優先搜尋正式路徑
            file_path = self.data_dir / "features.parquet"
            if not file_path.exists():
                file_path = Path("data/test/features_test.parquet")
        else:
            file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"特徵檔案不存在: {file_path}")
        
        df = pd.read_parquet(file_path)
        
        # 記憶體優化
        float_cols = df.select_dtypes(include=['float64']).columns
        if len(float_cols) > 0:
            df[float_cols] = df[float_cols].astype('float32')
            
        print(f"✓ 載入特徵資料: {len(df)} 筆, {len(df.columns)} 欄位")
        return df
    
    def generate_labels(self, df: pd.DataFrame) -> pd.DataFrame:
        """使用 LabelGenerator 生成標籤"""
        generator = LabelGenerator(horizon=self.horizon, threshold=self.threshold)
        # 需確保 df 有 open/close 欄位，ETL 產出的 features.parquet 應該有
        if 'open' not in df.columns:
            print("⚠ 警告: 找不到 'open' 欄位，標籤生成可能失敗")
        
        df_labeled = generator.generate_labels(df)
        return df_labeled
    
    def prepare_train_data(self, df: pd.DataFrame, exclude_cols: list = None):
        """準備訓練資料"""
        if exclude_cols is None:
            exclude_cols = [
                'symbol', 'stock_id', 'date', 'target', 'stock_name', 
                'entry_price', 'exit_price', 'return_5d', 'future_close',
                'return_long', 'future_return',
                'high_roll_20', 'low_roll_5', 'future_max_20d' # 修正 leakage
            ]
        
        y = df['target'] # 0 or 1
        
        # 1. 先排除明確指定的欄位
        potential_features = [col for col in df.columns if col not in exclude_cols]
        X_raw = df[potential_features]
        
        # 2. 強制僅保留數值型別 (int, float, bool)
        # LightGBM 不接受 object / string
        X = X_raw.select_dtypes(include=[np.number, bool])
        
        # 記錄被排除的欄位 (Debug用)
        dropped = set(X_raw.columns) - set(X.columns)
        if dropped:
            print(f"⚠ 自動排除非數值欄位: {dropped}")
            
        feature_cols = X.columns.tolist()
        
        print(f"✓ 準備訓練資料: {len(X)} 筆, {len(feature_cols)} 個特徵")
        return X, y, feature_cols
    
    def walk_forward_train(self, df: pd.DataFrame, n_splits: int = 5):
        """
        時序滾動驗證
        依據用戶需求：訓練窗口 24-36 個月 (簡化版：使用 TimeSeriesSplit 自動切分)
        """
        print(f"⏳ 開始 Walk-forward Validation (n_splits={n_splits})...")
        
        df = df.sort_values('date')
        dates = df['date'].unique()
        
        tscv = TimeSeriesSplit(n_splits=n_splits)
        metrics = []
        
        # 準備資料
        X_all, y_all, feature_cols = self.prepare_train_data(df)
        
        for i, (train_idx, val_idx) in enumerate(tscv.split(dates)):
            train_dates = dates[train_idx]
            val_dates = dates[val_idx]
            
            d_train = df[df['date'].isin(train_dates)]
            d_val = df[df['date'].isin(val_dates)]
            
            # 使用 prepare_train_data 確保欄位一致
            X_train, y_train, _ = self.prepare_train_data(d_train)
            X_val, y_val, _ = self.prepare_train_data(d_val)
            
            params = self.best_params if self.best_params else self._get_default_params()
            
            lgb_train = lgb.Dataset(X_train, label=y_train)
            lgb_val = lgb.Dataset(X_val, label=y_val, reference=lgb_train)
            
            # 訓練分類模型
            model = lgb.train(
                params,
                lgb_train,
                num_boost_round=1000,
                valid_sets=[lgb_train, lgb_val],
                valid_names=['train', 'valid'],
                callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)]
            )
            
            # 預測機率
            preds_prob = model.predict(X_val)
            
            # 評估指標: AUC & LogLoss
            try:
                auc = roc_auc_score(y_val, preds_prob)
                loss = log_loss(y_val, preds_prob)
            except ValueError:
                auc = 0
                loss = 999
            
            metrics.append({'auc': auc, 'logloss': loss})
            print(f"  Fold {i+1} ({val_dates[0]}~{val_dates[-1]}): AUC={auc:.4f}, LogLoss={loss:.4f}")
            
        avg_auc = np.mean([m['auc'] for m in metrics])
        print(f"✅ 驗證完成. 平均 AUC: {avg_auc:.4f}")
        
        # 最終全量訓練 (含校準拆分)
        self.train_final_model(X_all, y_all, feature_cols)
        return metrics

    def optimize_params(self, X: pd.DataFrame, y: pd.Series, n_trials: int = 20):
        """Optuna 超參數調優"""
        print(f"⏳ 開始 Optuna 超參數調優 (trials={n_trials})...")
        
        # 啟動 MLflow 實驗
        mlflow.set_experiment("Agent_B_Stock_Prediction")
        
        def objective(trial):
            with mlflow.start_run(nested=True, run_name=f"Trial_{trial.number}"):
                param = {
                    'objective': 'binary',
                    'metric': 'auc',
                    'verbosity': -1,
                    'boosting_type': 'gbdt',
                    'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.1),
                    'num_leaves': trial.suggest_int('num_leaves', 20, 150),
                    'feature_fraction': trial.suggest_float('feature_fraction', 0.5, 1.0),
                    'bagging_fraction': trial.suggest_float('bagging_fraction', 0.5, 1.0),
                    'bagging_freq': trial.suggest_int('bagging_freq', 1, 10),
                    'min_child_samples': trial.suggest_int('min_child_samples', 5, 100),
                    'lambda_l1': trial.suggest_float('lambda_l1', 1e-8, 10.0, log=True),
                    'lambda_l2': trial.suggest_float('lambda_l2', 1e-8, 10.0, log=True),
                    'is_unbalance': True 
                }
                
                # 紀錄參數到 MLflow
                mlflow.log_params(param)
                
                train_size = int(len(X) * 0.8)
                X_t, y_t = X.iloc[:train_size], y.iloc[:train_size]
                X_v, y_v = X.iloc[train_size:], y.iloc[train_size:]
                
                dtrain = lgb.Dataset(X_t, label=y_t)
                dval = lgb.Dataset(X_v, label=y_v, reference=dtrain)
                
                model = lgb.train(param, dtrain, num_boost_round=500, 
                                  valid_sets=[dval], callbacks=[lgb.early_stopping(30), lgb.log_evaluation(0)])
                
                preds = model.predict(X_v)
                try:
                    score = roc_auc_score(y_v, preds)
                except:
                    score = 0
                
                # 紀錄結果指標到 MLflow
                mlflow.log_metric("auc", score)
                
                return score # Maximize AUC

        study = optuna.create_study(direction='maximize')
        study.optimize(objective, n_trials=n_trials)
        
        self.best_params = study.best_params
        self.best_params.update({'objective': 'binary', 'metric': 'auc', 'verbosity': -1, 'is_unbalance': True})
        
        print(f"✅ 最佳參數: {self.best_params}")
        return self.best_params

    def train_final_model(self, X: pd.DataFrame, y: pd.Series, feature_names: list):
        """訓練最終模型 + 機率校準 (Probability Calibration)"""
        params = self.best_params if self.best_params else self._get_default_params()
        
        # 拆分 10% 做校準 (依時間序列，取最後 10%)
        # 因為這是 Time Series，不能隨機拆
        calib_size = int(len(X) * 0.1)
        train_size = len(X) - calib_size
        
        X_train = X.iloc[:train_size]
        y_train = y.iloc[:train_size]
        X_calib = X.iloc[train_size:]
        y_calib = y.iloc[train_size:]
        
        print(f"⏳ 訓練最終模型 (Train: {len(X_train)}, Calibration: {len(X_calib)})...")
        
        # 啟動 MLflow 父運行
        with mlflow.start_run(run_name="Final_Model_Training"):
            mlflow.log_params(params)
            mlflow.lightgbm.autolog()
            
            lgb_train = lgb.Dataset(X_train, label=y_train, feature_name=feature_names)
            self.model = lgb.train(params, lgb_train, num_boost_round=500)
            
            # 進行機率校準 (Isotonic Regression)
            print("🔧 執行 Isotonic Probability Calibration...")
            raw_probs = self.model.predict(X_calib)
            self.calibrator = IsotonicRegression(out_of_bounds='clip')
            self.calibrator.fit(raw_probs, y_calib)
            
            # 記錄模型到 MLflow
            mlflow.lightgbm.log_model(self.model, "model")
            print(f"✅ 最終模型已紀錄至 MLflow")
            
        return self.model

    def _get_default_params(self):
        return {
            'objective': 'binary',
            'metric': 'auc',
            'is_unbalance': True,
            'verbose': -1
        }

    def save_model(self, filename: str = "latest_lgbm.pkl"):
        """儲存模型與校準器"""
        if self.model is None: raise ValueError("尚未訓練模型")
        model_path = self.model_dir / filename
        
        # 儲存字典包含模型與校準器
        save_obj = {
            'model': self.model,
            'calibrator': self.calibrator,
            'feature_names': self.model.feature_name()
        }
        
        with open(model_path, 'wb') as f:
            pickle.dump(save_obj, f)
        print(f"✓ 模型與校準器已儲存至: {model_path}")

    def plot_feature_importance(self, top_n: int = 30):
        """繪製特徵重要性 (Gain)"""
        importance = self.model.feature_importance(importance_type='gain')
        features = self.model.feature_name()
        fi_df = pd.DataFrame({'feature': features, 'importance': importance}).sort_values('importance', ascending=False)
        
        plt.figure(figsize=(12, 10))
        sns.barplot(data=fi_df.head(top_n), x='importance', y='feature', palette='magma')
        plt.title(f'Top {top_n} 模型特徵重要性 (Gain)')
        plt.tight_layout()
        plt.savefig(self.artifact_dir / "feature_importance.png", dpi=150)
        plt.close()
        print(f"✓ 已產出特徵重要性圖表")
        return fi_df
        
    def plot_shap_summary(self, X_sample: pd.DataFrame = None, sample_size: int = 1000):
        """繪製 SHAP Summary Plot (Scikit-Learn Skill Integration)"""
        if self.model is None:
            print("⚠ 模型尚未訓練，無法繪製 SHAP")
            return

        print("⏳ 計算 SHAP values...")
        try:
            # 使用 TreeExplainer (針對 LightGBM 優化)
            explainer = shap.TreeExplainer(self.model)
            
            if X_sample is None:
                # 若未提供，嘗試自動載入一部分資料
                try:
                    df = self.load_features()
                    X, _, _ = self.prepare_train_data(df)
                    # 隨機採樣以加速
                    if len(X) > sample_size:
                        X_sample = X.sample(n=sample_size, random_state=42)
                    else:
                        X_sample = X
                except Exception as e:
                    print(f"⚠ 無法自動載入資料供 SHAP 分析: {e}")
                    return

            shap_values = explainer.shap_values(X_sample)
            
            # LightGBM binary classification returns list of arrays [class0, class1] or just class1 depending on version
            # New LightGBM versions with SHAP might return array. Handle carefully.
            if isinstance(shap_values, list):
                # Binary classification: index 1 is positive class
                shap_vals_target = shap_values[1]
            else:
                shap_vals_target = shap_values

            plt.figure(figsize=(10, 8))
            shap.summary_plot(shap_vals_target, X_sample, show=False)
            plt.title("SHAP Summary Plot (Top Features)")
            plt.tight_layout()
            
            save_path = self.artifact_dir / "shap_summary.png"
            plt.savefig(save_path, dpi=150)
            plt.close()
            print(f"✓ 已產出 SHAP Summary Plot: {save_path}")
            
        except Exception as e:
            print(f"❌ SHAP 分析失敗: {e}")


def main():
    print("🚀 Agent B 模型優化訓練啟動 (Mini版 - Classification)...")
    trainer = LightGBMTrainer()
    
    try:
        # 1. 準備資料
        df = trainer.load_features()
        # 使用 LabelGenerator 生成 D+1 標籤
        df = trainer.generate_labels(df)
        
        # 2. 自動調優
        X, y, feature_cols = trainer.prepare_train_data(df)
        trainer.optimize_params(X, y, n_trials=100) # Weekend Mode: 100 trials
        
        # 3. 時序滾動驗證與最終訓練
        trainer.walk_forward_train(df)
        
        # 4. 儲存與產出分析
        trainer.save_model()
        trainer.plot_feature_importance()
        
        print("\n✨ 模型優化流程已圓滿完成！")
        
    except Exception as e:
        print(f"\n❌ 流程中斷: {e}")
        import traceback; traceback.print_exc()

if __name__ == "__main__":
    main()

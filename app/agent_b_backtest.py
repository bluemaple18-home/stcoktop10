#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent B - 回測摘要模組
負責計算本月迄今績效並產生 Markdown 報告
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')


class BacktestReporter:
    """回測報告產生器"""
    
    def __init__(self, data_dir: str = "data/clean", artifact_dir: str = "artifacts",
                 transaction_cost: float = 0.003):
        """
        初始化回測報告器
        
        Args:
            data_dir: 資料目錄
            artifact_dir: 產出物目錄
            transaction_cost: 交易成本（預設 0.3%）
        """
        self.data_dir = Path(data_dir)
        self.artifact_dir = Path(artifact_dir)
        self.transaction_cost = transaction_cost
    
    def load_historical_top10(self, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        載入歷史 Top10 資料
        
        Args:
            start_date: 起始日期 (YYYYMMDD)
            end_date: 結束日期 (YYYYMMDD)
            
        Returns:
            合併的 Top10 DataFrame
        """
        top10_files = sorted(self.artifact_dir.glob("top10_*.csv"))
        
        if len(top10_files) == 0:
            raise FileNotFoundError("找不到任何 Top10 檔案")
        
        # 篩選日期範圍
        filtered_files = []
        for file in top10_files:
            date_str = file.stem.replace("top10_", "")
            if start_date and date_str < start_date:
                continue
            if end_date and date_str > end_date:
                continue
            filtered_files.append(file)
        
        # 合併所有檔案
        dfs = []
        for file in filtered_files:
            df = pd.read_csv(file)
            # 相容性處理：若有 code 則轉為 symbol
            if 'code' in df.columns:
                df = df.rename(columns={'code': 'symbol'})
            
            date_str = file.stem.replace("top10_", "")
            if 'date' not in df.columns:
                df['date'] = date_str
            dfs.append(df)
        
        if len(dfs) == 0:
            raise ValueError(f"指定日期範圍無資料: {start_date} ~ {end_date}")
        
        result = pd.concat(dfs, ignore_index=True)
        print(f"✓ 載入歷史 Top10: {len(result)} 筆, {len(filtered_files)} 個交易日")
        
        return result
    
    def load_price_data(self) -> pd.DataFrame:
        """
        載入價格資料
        
        Returns:
            價格 DataFrame
        """
        features_path = self.data_dir / "features.parquet"
        
        if not features_path.exists():
            raise FileNotFoundError(f"特徵檔案不存在: {features_path}")
        
        df = pd.read_parquet(features_path)
        
        # 只保留必要欄位
        price_df = df[['symbol', 'date', 'close']].copy()
        
        print(f"✓ 載入價格資料: {len(price_df)} 筆")
        return price_df
    
    def calculate_returns(self, top10_df: pd.DataFrame, price_df: pd.DataFrame) -> pd.DataFrame:
        """
        計算每日報酬率
        
        Args:
            top10_df: Top10 DataFrame
            price_df: 價格 DataFrame
            
        Returns:
            包含報酬率的 DataFrame
        """
        # 確保日期格式一致
        price_df['date'] = price_df['date'].astype(str).str.replace('-', '')
        top10_df['date'] = top10_df['date'].astype(str).str.replace('-', '')
        
        # 合併價格
        merged = top10_df.merge(price_df, on=['symbol', 'date'], how='left')
        merged = merged.rename(columns={'close': 'entry_price'})
        
        # 計算下一交易日價格
        price_df_sorted = price_df.sort_values(['symbol', 'date'])
        price_df_sorted['next_close'] = price_df_sorted.groupby('symbol')['close'].shift(-1)
        price_df_sorted = price_df_sorted.rename(columns={'close': 'current_close'})
        
        merged = merged.merge(
            price_df_sorted[['symbol', 'date', 'next_close']], 
            on=['symbol', 'date'], 
            how='left'
        )
        
        # 計算報酬率（扣除交易成本）
        merged['daily_return'] = (merged['next_close'] / merged['entry_price']) - 1 - self.transaction_cost
        
        return merged
    
    def calculate_metrics(self, returns_df: pd.DataFrame) -> dict:
        """
        計算績效指標
        
        Args:
            returns_df: 包含報酬率的 DataFrame
            
        Returns:
            績效指標字典
        """
        # 移除 NaN
        valid_returns = returns_df['daily_return'].dropna()
        
        if len(valid_returns) == 0:
            return {
                'avg_daily_return': 0,
                'total_return': 0,
                'win_rate': 0,
                'max_drawdown': 0,
                'sharpe_ratio': 0,
                'num_trades': 0
            }
        
        # 平均日報酬
        avg_daily_return = valid_returns.mean()
        
        # 累積報酬
        total_return = (1 + valid_returns).prod() - 1
        
        # 勝率
        win_rate = (valid_returns > 0).sum() / len(valid_returns)
        
        # 最大回撤
        cumulative = (1 + valid_returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()
        
        # Sharpe Ratio (假設無風險利率 = 0)
        sharpe_ratio = avg_daily_return / valid_returns.std() * np.sqrt(252) if valid_returns.std() > 0 else 0
        
        return {
            'avg_daily_return': avg_daily_return,
            'total_return': total_return,
            'win_rate': win_rate,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'num_trades': len(valid_returns)
        }
    
    def generate_markdown_report(self, metrics: dict, start_date: str, end_date: str) -> str:
        """
        產生 Markdown 格式報告
        
        Args:
            metrics: 績效指標
            start_date: 起始日期
            end_date: 結束日期
            
        Returns:
            Markdown 字串
        """
        report = f"""# Agent B 回測摘要報告

**報告期間**: {start_date} ~ {end_date}  
**交易成本**: {self.transaction_cost * 100:.2f}%  
**更新時間**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

## 📊 績效指標

| 指標 | 數值 |
|------|------|
| 平均日報酬 | {metrics['avg_daily_return'] * 100:.3f}% |
| 累積報酬率 | {metrics['total_return'] * 100:.2f}% |
| 勝率 | {metrics['win_rate'] * 100:.1f}% |
| 最大回撤 | {metrics['max_drawdown'] * 100:.2f}% |
| Sharpe Ratio | {metrics['sharpe_ratio']:.2f} |
| 交易次數 | {metrics['num_trades']} |

---

## 📈 績效評估

"""
        
        # 評估績效
        if metrics['avg_daily_return'] > 0:
            report += "✅ **策略表現良好**，平均日報酬為正。\n"
        else:
            report += "⚠️ **策略表現不佳**，建議檢視模型或切換至規則分數卡。\n"
        
        if metrics['win_rate'] > 0.5:
            report += f"✅ 勝率達 {metrics['win_rate']*100:.1f}%，表現穩定。\n"
        else:
            report += f"⚠️ 勝率僅 {metrics['win_rate']*100:.1f}%，需要改進。\n"
        
        if metrics['max_drawdown'] > -0.1:
            report += f"✅ 最大回撤控制良好 ({metrics['max_drawdown']*100:.2f}%)。\n"
        else:
            report += f"⚠️ 最大回撤過大 ({metrics['max_drawdown']*100:.2f}%)，風險較高。\n"
        
        report += "\n---\n\n"
        report += "_本報告由 Agent B 自動產生_\n"
        
        return report
    
    def save_report(self, report: str, filename: str = "daily_backtest.md"):
        """
        儲存報告
        
        Args:
            report: 報告字串
            filename: 檔名
        """
        output_path = self.artifact_dir / filename
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"✓ 回測報告已儲存至: {output_path}")


def main():
    """主程式：產生本月迄今回測報告"""
    print("=" * 60)
    print("Agent B - 回測摘要報告")
    print("=" * 60)
    
    reporter = BacktestReporter()
    
    try:
        # 計算本月起始日期
        today = datetime.now()
        start_of_month = today.replace(day=1).strftime("%Y%m%d")
        end_date = today.strftime("%Y%m%d")
        
        print(f"📅 報告期間: {start_of_month} ~ {end_date}")
        
        # 1. 載入歷史 Top10
        top10_df = reporter.load_historical_top10(start_date=start_of_month, end_date=end_date)
        
        # 2. 載入價格資料
        price_df = reporter.load_price_data()
        
        # 3. 計算報酬率
        returns_df = reporter.calculate_returns(top10_df, price_df)
        
        # 4. 計算績效指標
        metrics = reporter.calculate_metrics(returns_df)
        
        # 5. 產生報告
        report = reporter.generate_markdown_report(metrics, start_of_month, end_date)
        
        # 6. 顯示報告
        print("\n" + "=" * 60)
        print(report)
        print("=" * 60)
        
        # 7. 儲存報告
        reporter.save_report(report)
        
        print("\n✅ 回測報告產生完成！")
        
    except FileNotFoundError as e:
        print(f"\n❌ 錯誤: {e}")
    except Exception as e:
        print(f"\n❌ 報告產生失敗: {e}")
        raise


if __name__ == "__main__":
    main()

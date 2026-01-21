"""
測試報告生成器（無需模型）
"""
import pandas as pd
import sys
sys.path.append('app')

from report_generator import StockReportGenerator

# 載入資料
features_df = pd.read_parquet('data/clean/features.parquet')

# 模擬排名結果（取最新日期的前10檔）
latest_date = features_df['date'].max()
latest_data = features_df[features_df['date'] == latest_date].copy()

# 簡單排序（以收盤價為準，模擬排名）
latest_data = latest_data.sort_values('close', ascending=False).head(10).copy()
latest_data['model_prob'] = 0.78  # 模擬 AI 勝率

# 重命名以符合 ranked_df 格式
ranked_df = latest_data[['stock_id', 'stock_name', 'close', 'model_prob']].copy()
ranked_df['final_score'] = ranked_df['model_prob']

# 生成報告
print("🚀 測試報告生成功能...")
report_gen = StockReportGenerator()
report_gen.generate_report(ranked_df=ranked_df, features_df=features_df)

print("\n✅ 報告生成完成！請查看 artifacts/ 資料夾")
print("   - ranked_stocks_detailed.csv (表格版)")
print("   - analysis_report.md (文章版)")
print("   - analysis_report.yaml (結構化版)")

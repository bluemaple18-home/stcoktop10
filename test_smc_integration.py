import pandas as pd
import numpy as np
from app.indicators import TechnicalIndicators
from app.report_generator import StockReportGenerator
from pathlib import Path

# 1. 生成測試資料 (10 檔股票)
dates = pd.date_range(end=pd.Timestamp.now(), periods=100, freq='B')
stock_ids = [f"{i:04d}.TW" for i in range(2330, 2340)]
data = []
for sid in stock_ids:
    base_price = 500 + np.random.randn() * 100
    closes = base_price * (1 + np.random.randn(100) * 0.01).cumprod()
    opens = closes * (1 + np.random.randn(100) * 0.005)
    highs = np.maximum(opens, closes) * (1 + abs(np.random.randn(100) * 0.005))
    lows = np.minimum(opens, closes) * (1 - abs(np.random.randn(100) * 0.005))
    volumes = np.random.randint(1000, 10000, 100)
    data.append(pd.DataFrame({
        'date': dates, 'stock_id': sid, 'stock_name': f'測試股_{sid}',
        'open': opens, 'high': highs, 'low': lows, 'close': closes, 'volume': volumes
    }))
full_df = pd.concat(data)

# 2. 計算指標
ti = TechnicalIndicators(full_df)
features_df = ti.calculate_all_indicators()

# 3. 模擬排名 (取前 5 檔)
ranked_df = pd.DataFrame({
    'stock_id': [s for s in stock_ids[:5]],
    'model_prob': [0.85, 0.78, 0.72, 0.65, 0.60]
})

# 4. 生成報告
generator = StockReportGenerator(artifacts_dir="test_artifacts")
generator.generate_report(ranked_df, features_df)

print("✅ 整合測試完成，請檢查 test_artifacts/analysis_report.md")

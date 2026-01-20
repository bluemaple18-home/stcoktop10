import pandas as pd
import numpy as np
from pathlib import Path
import os
import shutil

# Setup dummy data
data_dir = Path("data/clean")
data_dir.mkdir(parents=True, exist_ok=True)

dates = ['2023-01-01']
symbols = ['2330', '2317', '2454', '2308', '2603', '2881', '2882', '2303', '1101', '3008', '2886', '2002']

# Universe
universe = pd.DataFrame([{
    'symbol': s,
    'date': d,
    'name': f"Stock_{s}",
    'industry': 'Semi',
    'market': 'TSE',
    'status': 'Active'
} for s in symbols for d in dates])
universe.to_parquet(data_dir / "universe.parquet")

# Features
features = universe.copy()
# Add random features
np.random.seed(42)
for col in ['feature1', 'feature2', 'rsi', 'macd']:
    features[col] = np.random.randn(len(features))
features['close'] = 100 + np.random.randn(len(features)) * 10
features.to_parquet(data_dir / "features.parquet")

# Events
events = universe[['symbol', 'date']].copy()
# Randomly trigger events
events['break_20d_high'] = np.random.choice([0, 1], size=len(events), p=[0.8, 0.2])
events['ma5_cross_ma20_up'] = np.random.choice([0, 1], size=len(events), p=[0.9, 0.1])
events['lose_20d_low'] = np.random.choice([0, 1], size=len(events), p=[0.95, 0.05])
events.to_parquet(data_dir / "events.parquet")

print("Created dummy data in data/clean")

# Run ranking
from app.agent_b_ranking import main
main()

# Check outputs
artifact_dir = Path("artifacts")
top10 = list(artifact_dir.glob("top10_*.csv"))
watchlist = list(artifact_dir.glob("watchlist_*.csv"))

if top10:
    print(f"\nTop 10 generated: {top10[0]}")
    df = pd.read_csv(top10[0])
    print(df.head())
    print("\nColumns:", df.columns.tolist())
else:
    print("\nNo Top 10 generated")

if watchlist:
    print(f"\nWatchlist generated: {watchlist[0]}")
else:
    print("\nNo Watchlist generated")

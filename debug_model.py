
import pickle
import pandas as pd
import numpy as np

model_path = "models/latest_lgbm.pkl"
data_path = "data/clean/features.parquet"

print(f"Loading model from {model_path}...")
with open(model_path, 'rb') as f:
    obj = pickle.load(f)
    
if isinstance(obj, dict):
    model = obj['model']
    print("Loaded New Dict Model")
else:
    model = obj
    print("Loaded Old Booster Model")

print(f"Loading data from {data_path}...")
df = pd.read_parquet(data_path)
df = df.sort_values('date').tail(1000) # Test on recent data

print("Features expected by model:", model.feature_name())

# Check missing
missing = [f for f in model.feature_name() if f not in df.columns]
if missing:
    print("MISSING FEATURES:", missing)
else:
    print("All features present.")
    
# Predict
X = df[model.feature_name()]
# Fill NaNs
X = X.fillna(0)

preds = model.predict(X)
print("Raw Predictions stats:")
print(pd.Series(preds).describe())

if isinstance(obj, dict) and 'calibrator' in obj and obj['calibrator']:
    cal = obj['calibrator']
    cal_preds = cal.predict(preds)
    print("Calibrated stats:")
    print(pd.Series(cal_preds).describe())
else:
    print("No calibrator found.")

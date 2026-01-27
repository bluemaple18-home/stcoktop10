import yfinance as yf
from datetime import datetime, timedelta

start = "2025-06-12"
end = datetime.now().strftime("%Y-%m-%d")

print(f"Testing yfinance download for 2330.TW from {start} to {end}...")

data = yf.download(["2330.TW"], start=start, end=end, progress=True)

if not data.empty:
    print("Success!")
    print(data.tail())
    print(f"Max Date: {data.index.max()}")
else:
    print("Failed: No data returned.")

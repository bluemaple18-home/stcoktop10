
import requests
import json

url = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date=20240701&type=ALLBUT0999&response=json"
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

try:
    print(f"Fetching {url}...")
    res = requests.get(url, headers=headers, timeout=10)
    print(f"Status Code: {res.status_code}")
    
    if res.status_code == 200:
        data = res.json()
        print("Keys:", data.keys())
        
        if 'tables' in data:
            print(f"Tables count: {len(data['tables'])}")
            for i, table in enumerate(data['tables']):
                print(f"Table {i} Title: {table.get('title')}")
                if '每日收盤行情' in table.get('title', ''):
                    print(f"--> FOUND TARGET at index {i}")
                    print("First row data:", table.get('data', [])[0] if table.get('data') else 'Empty')
        elif 'data9' in data:
            print("Found data9 key!")
        else:
            print("Neither tables nor data9 found.")
    else:
        print("Request failed")
except Exception as e:
    print(f"Error: {e}")

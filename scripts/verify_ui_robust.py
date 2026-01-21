from playwright.sync_api import sync_playwright
import sys

def verify_ui():
    print("🚀 Starting robust UI verification (VISIBLE MODE)...")
    with sync_playwright() as p:
        # headless=False 讓瀏覽器視窗跳出來，slow_mo=1000 讓動作變慢以便觀察
        browser = p.chromium.launch(headless=False, slow_mo=1000)
        try:
            page = browser.new_page()
            
            # 1. 導航到首頁
            print("⏳ Navigating to localhost:8501...")
            page.goto("http://localhost:8501", timeout=30000)
            
            # Debug: Print title
            print(f"📄 Page Title: {page.title()}")
            
            # 2. 等待 Streamlit App Container (更穩定的檢查點)
            print("⏳ Waiting for Streamlit app to load...")
            page.wait_for_selector(".stApp", timeout=30000)
            print("✅ Streamlit container loaded.")

            # Take a screenshot of the main page
            page.screenshot(path="artifacts/verification_main_page.png")
            print("📸 Main page screenshot saved.")

            # 3. 檢查標題 (使用更寬鬆的選擇器)
            # 根據 app/ui.py 的實際內容調整檢查文字
            # 假設標題在 h1 中
            try:
                # 嘗試尋找主要標題
                heading = page.wait_for_selector("h1", timeout=10000)
                print(f"✅ Found H1: {heading.inner_text()}")
            except:
                print("⚠️ H1 not found within timeout.")

            # 4. 檢查是否有個股列表 (確保 features.parquet 讀取成功)
            # 找尋包含數字的元素，代表股票代碼
            print("⏳ Looking for stock list...")
            try:
                page.wait_for_selector("text=1141", timeout=10000)
                print("✅ Stock list loaded (Found stock 1141).")
            except:
                print("⚠️ Stock 1141 not found. Dumping page text...")
                print(page.inner_text("body")[:500])
                raise Exception("Stock list not loaded.")
            
            # 5. 點擊進入詳情頁
            print("⏳ Clicking stock detail...")
            # 嘗試點擊 "1141"
            page.click("text=1141", timeout=5000)
            
            # 6. 等待詳情頁內容
            print("⏳ Waiting for detail page content...")
            # 等待關鍵字 "推薦理由" 或 "個股分析"
            try:
                page.wait_for_selector("text=推薦理由", timeout=20000)
                print("✅ Found '推薦理由'.")
            except:
                 # Fallback check
                 page.wait_for_selector("text=個股分析", timeout=5000)
                 print("✅ Found '個股分析'.")

            page.screenshot(path="artifacts/verification_detail_page.png")
            print("📸 Detail page screenshot saved.")
            
            # 7. 驗證內容 (確保中文化生效)
            content = page.content()
            keyword_found = False
            keywords_cn = ["突破20日新高", "月線支撐", "布林中軌", "MACD", "KD"]
            
            for kw in keywords_cn:
                if kw in content:
                    print(f"✅ Found Chinese keyword: {kw}")
                    keyword_found = True
                    break
            
            if not keyword_found:
                 # Check for English leftovers
                 if "break_20d_high" in content:
                     print("❌ Found ENGLISH explanation keywords (Translation failed!).")
                     sys.exit(1)
                 else:
                     print("⚠️ No specific known explanation keywords found, but page seems valid.")

            # 8. 檢查錯誤訊息
            if "PyExtensionType" in content or "StreamlitAPIException" in content:
                print("❌ FAILURE: Critical Error Message found on page!")
                sys.exit(1)
            
            print("🎉 VERIFICATION SUCCESS: UI is stable and functioning correctly.")
            
        except Exception as e:
            print(f"❌ Verification Failed: {e}")
            # Try to screenshot on failure
            try:
                page.screenshot(path="artifacts/verification_failure.png")
                print("📸 Failure screenshot saved to artifacts/verification_failure.png")
            except:
                pass
            sys.exit(1)
        finally:
            browser.close()

if __name__ == "__main__":
    verify_ui()

from playwright.sync_api import sync_playwright, Page
import sys
import time

class UIVerifier:
    """
    Robust UI Verification using Playwright Best Practices
    """
    def __init__(self, page: Page):
        self.page = page

    def navigate_home(self):
        print("⏳ Navigating to localhost:8501...")
        self.page.goto("http://localhost:8501", timeout=30000)
        # Critical: Wait for network to be idle (Streamlit loads a lot of chunks)
        try:
            self.page.wait_for_load_state('networkidle', timeout=10000)
        except:
            print("⚠️ Network idle timed out, proceeding anyway...")
        
        # Wait for the main app container
        print("⏳ Waiting for Streamlit app container...")
        self.page.wait_for_selector(".stApp", state="visible", timeout=30000)
        print(f"✅ Page loaded: {self.page.title()}")

    def check_stock_list_and_click(self, stock_text: str = "1141"):
        print(f"⏳ Looking for stock {stock_text}...")
        # Use precise Selector
        selector = f"text={stock_text}"
        try:
            self.page.wait_for_selector(selector, state="visible", timeout=15000)
            print(f"✅ Found stock {stock_text}")
            
            # Click and wait for re-render
            print(f"⏳ Clicking {stock_text}...")
            self.page.click(selector)
            # Streamlit re-runs script on interaction, wait for network idle again if possible
            # or wait for a specific element that appears ONLY after click
            time.sleep(2) # Stability wait for Streamlit trigger
            
        except Exception as e:
            print(f"❌ Stock {stock_text} interaction failed.")
            raise e

    def verify_detail_page_report(self):
        print("⏳ Verifying Detail Page Content (Report)...")
        # Check for our new layout elements
        try:
            # Look for "Deep Dive" section or TL;DR
            # Using partial text match or CSS
            self.page.wait_for_selector("h4:has-text('TL;DR')", timeout=20000)
            print("✅ Found 'TL;DR' section (Markdown Report confirmed).")
        except:
            print("⚠️ 'TL;DR' header not found. Checking for fallback '詳細分析報告'...")
            self.page.wait_for_selector("text=詳細分析報告", timeout=20000)
            print("✅ Found '詳細分析報告'.")

        self.page.screenshot(path="artifacts/verification_detail_page.png")
        print("📸 Screenshot saved.")

    def check_no_errors(self):
        content = self.page.content()
        if "StreamlitAPIException" in content:
            raise Exception("❌ Streamlit API Exception detected!")
        if "Traceback" in content:
            raise Exception("❌ Key Error / Traceback detected!")
        print("✅ No obvious error stack traces found.")

def run_verification():
    print("🚀 Starting Refactored UI Verification...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        verifier = UIVerifier(page)
        
        try:
            verifier.navigate_home()
            verifier.check_stock_list_and_click("1141")
            verifier.verify_detail_page_report()
            verifier.check_no_errors()
            
            print("🎉 VERIFICATION SUCCESS!")
            
        except Exception as e:
            print(f"❌ Verification Failed: {e}")
            page.screenshot(path="artifacts/verification_failure.png")
            sys.exit(1)
        finally:
            browser.close()

if __name__ == "__main__":
    run_verification()

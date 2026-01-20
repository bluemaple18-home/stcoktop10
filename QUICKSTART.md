# Agent C 快速啟動指南

## 🚀 立即開始

### 方法一：查看已生成的結果

```bash
cd /Users/matt/tw-top10

# 查看面板截圖
open artifacts/top10_dashboard.png

# 查看技術圖表
open artifacts/charts/

# 查看文字摘要
cat artifacts/top10_summary.txt

# 查看發布日誌
cat artifacts/publish_log.txt
```

---

### 方法二：啟動 Streamlit Web UI

```bash
cd /Users/matt/tw-top10

# 啟動虛擬環境
source .venv/bin/activate

# 啟動 Streamlit
streamlit run app/ui.py
```

瀏覽器會自動開啟 `http://localhost:8501`

---

### 方法三：重新執行每日發布

```bash
cd /Users/matt/tw-top10

# 啟動虛擬環境
source .venv/bin/activate

# 執行發布腳本
python app/publish_daily.py
```

會重新生成所有圖表與面板截圖。

---

## 📂 重要檔案位置

| 檔案 | 路徑 |
|------|------|
| 面板截圖 | `artifacts/top10_dashboard.png` |
| 技術圖表 | `artifacts/charts/*.png` (10 張) |
| 文字摘要 | `artifacts/top10_summary.txt` |
| 發布日誌 | `artifacts/publish_log.txt` |

---

## 🔧 如何整合 Agent A & B

當 Agent A（資料擷取）與 Agent B（模型預測）完成後：

1. **修改 `app/publish_daily.py` 第 67-95 行**
   - 將 `load_stock_history_dummy` 替換為從 DuckDB 讀取實際資料

2. **確保 Agent B 輸出的 CSV 包含以下欄位**：
   ```
   stock_id, stock_name, expected_return_5d, win_rate, close, volume
   ```

3. **可選：新增更多欄位以豐富推薦理由**：
   ```
   rsi, macd, macd_signal, ma5, ma20, pe_ratio, dividend_yield, revenue_growth
   ```

就完成整合了！

---

## ❓ 常見問題

**Q: Emoji 顯示有警告訊息？**
A: 這是正常的字體警告，不影響圖片生成。圖片中 emoji 會以方框顯示，但中文正常。

**Q: 如何更改顯示的天數？**
A: 修改 `chart_generator.py` 第 50 行的 `days` 參數（預設 60 天）。

**Q: 如何客製化推薦理由？**
A: 編輯 `reason_generator.py` 的 `generate_reasons` 函式，新增自己的判斷邏輯。

---

💡 更多詳細說明請參考 [walkthrough.md](file:///Users/matt/.gemini/antigravity/brain/4db2162c-1333-42ad-8ec2-89a1f6e2b069/walkthrough.md)

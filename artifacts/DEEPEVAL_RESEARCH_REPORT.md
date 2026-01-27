# 研究報告：DeepEval 與 RAG

## 1. Threads 貼文分析

**來源**: `https://www.threads.com/@ainnoforge/post/DT-OayQinPv`
**主題**: RAG (檢索增強生成) 的自動化評估。
**核心問題**: 人工測試 AI 聊天機器人/RAG 系統既緩慢又不可靠（容易出現「幻覺」）。
**解決方案**: **DeepEval** (由 Confident AI 開發)。
**關鍵指標**:
-   **Faithfulness (忠實度)**: 回答是否忠於檢索到的事實？
-   **Contextual Precision (上下文精準度)**: 系統是否檢索到了*正確*的事實？
**概念**: 「AI 的單元測試 (Unit Testing)」— 每當程式碼或 Prompt 變更時，自動執行檢查。

## 2. 對 `tw-top10` 的適用性分析

我已分析目前的 `tw-top10` 程式碼庫 (`agent_b_ranking.py`, `report_generator.py`, `data_healer.py`)。

**狀態**: ❌ **目前不適用**

**理由**:
-   **無 GenAI 成分**: 專案主要使用 **LightGBM** (決策樹) 進行預測，並使用 **固定 Python 模板** (`f-strings`) 生成報告。
-   **無幻覺風險**: 由於報告內容是寫死的程式邏輯（例如 `f"MA5={ma5}"`），它不會像 LLM 那樣「產生幻覺」。它只會輸出既有的數據。
-   **DeepEval 的角色**: DeepEval 是設計來測試 *LLM 生成的文本*。如果沒有 LLM 組件，就沒有東西可以讓它評分。

## 3. 未來可能的路徑

如果您希望「研究並應用」這項技術，這意味著我們需要將專案升級以包含生成式 AI。

**建議提案：「Agent C - AI 分析師」**
1.  **升級報告系統**: 將目前固定的 `StockReportGenerator` 替換為基於 LLM 的生成器。
    -   *輸入*: 股票特徵、新聞摘要、技術數據。
    -   *輸出*: 自然語言分析報告（像真實分析師寫的筆記）。
2.  **應用 DeepEval**:
    -   完成第 1 步後，我們使用 **DeepEval** 來監控 AI 分析師，確保它不會引用錯誤的價格或編造假新聞。
    -   **指標**: Faithfulness (分析內容是否由 `features.parquet` 數據支持？)。

## 4. 結論

我們無法將 DeepEval 應用於目前的程式碼，因為沒有 AI 模型在生成文字。
**需要決策**: 您是否希望在此專案中**加入 LLM 功能**（例如 AI 市場評論）？如果是，我們就可以應用 DeepEval 來測試它。

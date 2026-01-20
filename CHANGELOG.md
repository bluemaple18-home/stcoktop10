# Changelog

## [v2.4.0-ui] - 2026-01-21 (UI/UX 大幅優化)

### 🎨 Web UI 改進

#### Added
- **股票名稱對照表**: 新增 `app/stock_names.py`，自動顯示股票中文名稱（瑞展、聲寶等）
- **個股分析頁面**: 全新設計，專注於 AI 推薦理由與投資決策支援
  - 🤖 AI 推薦理由區塊：白話解釋每個技術訊號
  - 📍 技術位置分析：自動判斷多空格局、RSI 超買超賣、KD 交叉
  - 📈 整合式 K 線圖：K 線 + 成交量雙子圖設計
  - 💡 投資建議：明確的進場/出場參考指標
- **側邊欄股票選擇器**: 新增「📈 個股分析」頁籤，可直接選股查看詳細資訊
- **工作流程定義**: 新增 `.agent/workflows/switch-to-stock.md` 用於專案切換

#### Changed
- **台股配色模式**: K 線圖改為台股習慣（紅漲綠跌）
- **成交量視覺化**: 根據漲跌上色（紅色=漲，綠色=跌）並整合到 K 線圖下方
- **推薦理由顯示**: 解析 AI 訊號並翻譯成易懂的中文說明
  - ✅ 綠色顯示正面訊號
  - ⚠️ 橙色顯示警示訊號
- **均線顏色優化**: 使用更明亮的顏色以便區分（MA5/MA20/MA60）

#### Fixed
- **股票名稱缺失**: 修正選股列表只顯示代號的問題
- **資料型態問題**: 修正 `stock_id` 字串/整數型態不匹配導致圖表無法顯示
- **推薦理由格式**: 修正原始 AI 輸出格式，改為結構化展示

#### Technical
- 整合 Plotly subplots 實現 K 線 + 成交量雙子圖
- 新增技術訊號解釋字典（volume_ratio_20d, bb_width, macd, kd 等）
- 優化頁面路由邏輯支援個股詳細頁

#### Philosophy
- **以使用者為中心**: 從「展示技術指標」轉向「幫助理解投資決策」
- **可解釋 AI**: 每個推薦都有清楚的理由和建議
- **降低進入門檻**: 適合股市小白理解 AI 選股邏輯

---

## [v2.2.0-ml] - 2026-01-20 (Mini 發布: Web UI 介面)

### 📱 Web Interface

#### Added
- **Streamlit Web UI**: 完整的視覺化介面 (`app/ui.py`)
  - 今日選股頁面（Top 10 + AI 推薦理由）
  - 歷史績效頁面（趨勢圖 + 回測報告）
  - PSI 監控頁面（漂移狀態視覺化）
  - 系統資訊頁面
- **ngrok 遠端存取**: 從任何地方連回 Mac Mini
- **啟動腳本**: `scripts/start_ui.sh` (整合 Streamlit + ngrok)
- **launchd 自動啟動**: 開機自動啟動 Web UI
- **使用手冊**: `docs/WEBUI.md` (詳細安裝與設定指南)

#### Features
- 響應式設計（支援手機、平板、電腦）
- 即時資料更新（快取 5 分鐘）
- 互動式圖表（Plotly）
- 自訂 CSS 樣式

---

## [v2.1.0-ml] - 2026-01-20 (Mini 發布: 自動化系統)

### 🤖 Automation System

#### Added
- **每日自動執行腳本**: `scripts/run_daily.sh` (22:00 ETL + 選股)
- **每日自動重訓腳本**: `scripts/daily_retrain.sh` (02:00 模型訓練)
- **PSI 漂移監控**: `app/model_monitor.py` (自動偵測特徵分佈變化)
- **macOS launchd 排程**: 完整的 plist 設定檔與安裝腳本
- **自動化設定檔**: `config/automation.yaml` (集中管理參數)
- **使用手冊**: `docs/AUTOMATION.md` (詳細安裝與管理指南)

#### Features
- 模型自動備份 (保留 30 天)
- 訓練失敗自動恢復備份
- PSI 監控報告 (`artifacts/psi_report.json`)
- 完整日誌記錄 (`logs/`)

---

## [v2.0.0-ml] - 2026-01-20 (Mini 發布: ML模型優化)

### 🎯 Advanced Modeling: 中長期波段策略

#### Added
- **標籤系統升級**: 實作 `LabelGenerator` (持有 10 天, 獲利門檻 5%)
- **機率校準**: 整合 Isotonic Calibration 提升模型可信度
- **AI 可解釋性**: 加入 SHAP TreeExplainer，提供每日選股推薦理由
- **二元事件特徵**: 突破、均線交叉、布林通道、MACD、RSI 等技術訊號

#### Changed
- **模型訓練目標**: 從「短期獲利 (>0%)」改為「中長期波段 (>5%, 10天)」
- **排名邏輯優化**: 使用原始機率 (raw_prob) 排序，避免校準平坦化影響
- **回測持有期**: 從 5 天調整為 10 天，符合中長期定位

#### Fixed
- **資料洩漏修復**: 排除 `return_long`, `future_return` 等未來資訊欄位
- **ETL 穩定性**: 更新 TWSE RWD API 動態解析邏輯，支援欄位變更

#### Performance
- **平均單次報酬**: +5.33% (10天持有)
- **正報酬勝率**: 67.0%
- **適用客群**: 股市小白、無時間盯盤的中長期投資者

---

## [1.0.0] - 2025-XX-XX (估)

### Initial Release
- ETL 資料擷取 (TWSE, TPEX)
- LightGBM 分類模型 (Optuna 調優)
- Walk-forward Validation
- 基礎回測系統

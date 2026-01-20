# tw-top10 Web UI 使用手冊

## 📱 功能概覽

Web UI 提供視覺化介面，讓您可以從任何裝置（電腦、手機、平板）查看選股結果。

### 核心功能
1. **今日選股** - 查看每日 Top 10 推薦股票與 AI 推薦理由
2. **歷史績效** - 追蹤選股趨勢與回測報告
3. **PSI 監控** - 即時查看模型漂移狀態
4. **系統資訊** - 了解系統版本與功能

---

## 🚀 快速開始

### 方法 A：本地存取（同網路）

```bash
cd /Users/mattkuo/Projects/tw-top10
bash scripts/start_ui.sh
```

啟動後，在瀏覽器開啟：
- **本地**: `http://localhost:8501`
- **同網路其他裝置**: `http://[Mac-Mini-IP]:8501`

### 方法 B：遠端存取（任何地方）

需要安裝 ngrok：

```bash
# 安裝 ngrok
/opt/homebrew/bin/brew install ngrok

# 或從官網下載
# https://ngrok.com/download

# 啟動 Web UI + ngrok
bash scripts/start_ui.sh
```

啟動後會顯示類似以下訊息：
```
✅ Web UI 已啟動！
📱 遠端存取: https://xxxx-xx-xx-xx-xx.ngrok-free.app
```

將這個網址傳到手機，就能從任何地方存取！

---

## 🔧 進階設定

### 1. 開機自動啟動 Web UI

```bash
# 設定 launchd (讓 Web UI 開機自動啟動)
WEBUI_PLIST="$HOME/Library/LaunchAgents/com.tw-top10.webui.plist"
sed "s|__PROJECT_DIR__|$(pwd)|g" scripts/com.tw-top10.webui.plist > "$WEBUI_PLIST"
launchctl load "$WEBUI_PLIST"
```

### 2. 固定 ngrok 網址（需付費版）

1. 註冊 ngrok 帳號: https://dashboard.ngrok.com/signup
2. 取得 authtoken
3. 執行: `ngrok authtoken YOUR_TOKEN`
4. 購買固定網域 (Reserved Domain)
5. 修改 `scripts/start_ui.sh`，將 `ngrok http 8501` 改為 `ngrok http --domain=your-domain.ngrok-free.app 8501`

### 3. 查看 Mac Mini 內網 IP

```bash
# 方法 1: ifconfig
ifconfig | grep "inet " | grep -v 127.0.0.1

# 方法 2: 系統偏好設定
# 系統偏好設定 → 網路 → Wi-Fi/乙太網路 → 查看 IP 位址
```

---

## 📊 頁面說明

### 🎯 今日選股
- 顯示最新的 Top 10 選股名單
- 包含股票代號、名稱、綜合分數、AI 勝率
- **推薦理由**: 顯示 SHAP 解釋（例如「突破20日高點」）

### 📊 歷史績效
- 回測報告摘要
- 最近 30 天選股趨勢圖
- 核心績效指標（勝率、平均報酬）

### 🔍 PSI 監控
- 模型漂移狀態 (OK / WARNING / CRITICAL)
- 整體 PSI 數值
- Top 5 漂移特徵視覺化

### ℹ️ 系統資訊
- 版本資訊
- 功能列表
- 使用說明

---

## 🔒 安全建議

### ngrok 免費版注意事項
- ⚠️ 每次重啟網址會變動
- ⚠️ 網址是公開的，任何人都能存取
- ⚠️ 建議不要分享網址給陌生人

### 建議做法
1. **僅在需要時啟動 ngrok**（平時用本地模式）
2. **使用密碼保護**（Streamlit 付費版功能）
3. **升級 ngrok 付費版** 取得固定網址與密碼保護

---

## 🛠️ 疑難排解

### Q: 啟動後無法存取？
檢查防火牆設定：
```bash
# macOS 防火牆可能阻擋連線
# 系統偏好設定 → 安全性與隱私 → 防火牆 → 防火牆選項
# 允許 Python 或 Streamlit 的連線
```

### Q: ngrok 網址無法開啟？
1. 確認 ngrok 已正確安裝: `ngrok version`
2. 檢查是否有其他程式佔用 4040 port
3. 重新啟動 `bash scripts/start_ui.sh`

### Q: 頁面顯示「無資料」？
1. 確認已執行過選股: `python app/agent_b_ranking.py`
2. 檢查 `artifacts/` 目錄是否有 `ranking_*.csv`

### Q: 如何停止 Web UI？
```bash
# 方法 1: 在終端機按 Ctrl+C

# 方法 2: 找到 PID 並 kill
ps aux | grep streamlit
kill [PID]

# 方法 3: 停用 launchd (若有設定開機啟動)
launchctl unload ~/Library/LaunchAgents/com.tw-top10.webui.plist
```

---

## 📱 手機存取範例

### iPhone / Android
1. 啟動 Web UI (含 ngrok)
2. 複製 ngrok 網址 (例如 `https://xxxx.ngrok-free.app`)
3. 在手機瀏覽器貼上網址
4. 加入書籤以便快速存取

### 建議瀏覽器
- **iOS**: Safari / Chrome
- **Android**: Chrome / Firefox
- **桌面**: Chrome / Edge / Safari

---

## 🎨 自訂樣式（進階）

若想修改 UI 外觀，編輯 `app/ui.py` 中的 CSS：

```python
st.markdown("""
<style>
    .main-header {
        color: #your-color;  # 修改標題顏色
    }
</style>
""", unsafe_allow_html=True)
```

---

## 📞 支援

若遇到問題，請檢查：
1. 日誌檔案: `logs/webui.log`
2. Streamlit 文件: https://docs.streamlit.io
3. ngrok 文件: https://ngrok.com/docs

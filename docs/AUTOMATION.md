# tw-top10 自動化系統使用手冊

## 📚 概覽

本系統提供完整的自動化功能，讓選股系統能夠無人值守運作：

- 📊 **每日自動執行** (22:00): ETL 資料更新 + Agent B 選股
- 🔧 **每日自動重訓** (02:00): 模型重新訓練與備份
- 📈 **PSI 漂移監控**: 自動偵測特徵分佈變化
- 🔔 **通知推播** (可選): Line Notify 整合

---

## 🚀 快速開始

### 1. 安裝自動排程 (macOS 推薦)

```bash
cd /Users/mattkuo/Projects/tw-top10
bash scripts/setup_launchd.sh
```

**說明**: macOS 上 launchd 比 cron 更可靠，開機後會自動載入。

### 2. 手動測試腳本

在安裝排程前，建議先手動測試：

```bash
# 測試每日執行流程
bash scripts/run_daily.sh

# 測試每日重訓流程
bash scripts/daily_retrain.sh
```

### 3. 檢查排程狀態

```bash
# 查看已載入的排程
launchctl list | grep tw-top10

# 查看日誌
tail -f logs/launchd_daily.log
tail -f logs/launchd_retrain.log
```

---

## 📋 腳本說明

### `scripts/run_daily.sh`
**功能**: 每日自動執行 (22:00)
**流程**:
1. 執行 ETL 更新當日資料
2. 呼叫 Agent B 選股
3. 產出 `artifacts/ranking_YYYY-MM-DD.csv`
4. 記錄日誌至 `logs/daily_YYYYMMDD.log`

### `scripts/daily_retrain.sh`
**功能**: 每日自動重訓 (02:00)
**流程**:
1. 備份現有模型至 `models/backup/`
2. 執行 LightGBM 訓練 (Optuna + Walk-forward)
3. 執行 PSI 漂移監控
4. 清理 30 天前的舊備份
5. 若訓練失敗，自動恢復備份

### `app/model_monitor.py`
**功能**: PSI 漂移監控
**用法**:
```bash
# 手動執行監控
python app/model_monitor.py

# 查看結果
cat artifacts/psi_report.json
```

**說明**: PSI (Population Stability Index) 用於偵測特徵分佈變化
- PSI < 0.1: 穩定
- 0.1 < PSI < 0.25: 輕微變化
- PSI > 0.25: 需注意 ⚠️
- PSI > 0.5: 嚴重漂移 🚨 (建議重訓)

---

## ⚙️ 設定檔

### `config/automation.yaml`

```yaml
daily:
  run_time: "22:00"
  
retrain:
  schedule: "daily"
  time: "02:00"
  backup_keep_days: 30
  
monitor:
  psi_warning: 0.25
  psi_critical: 0.5
```

**修改後需重新載入排程**:
```bash
bash scripts/setup_launchd.sh
```

---

## 🔧 管理指令

### 停用排程
```bash
launchctl unload ~/Library/LaunchAgents/com.tw-top10.daily.plist
launchctl unload ~/Library/LaunchAgents/com.tw-top10.retrain.plist
```

### 重新啟用排程
```bash
launchctl load ~/Library/LaunchAgents/com.tw-top10.daily.plist
launchctl load ~/Library/LaunchAgents/com.tw-top10.retrain.plist
```

### 查看排程狀態
```bash
launchctl list | grep tw-top10
```

### 手動觸發執行（測試用）
```bash
launchctl start com.tw-top10.daily
launchctl start com.tw-top10.retrain
```

---

## 📂 檔案結構

```
tw-top10/
├── scripts/
│   ├── run_daily.sh              # 每日執行腳本
│   ├── daily_retrain.sh          # 每日重訓腳本
│   ├── setup_launchd.sh          # launchd 安裝
│   ├── setup_cron.sh             # cron 安裝 (備選)
│   ├── com.tw-top10.daily.plist  # launchd 設定
│   └── com.tw-top10.retrain.plist
│
├── app/
│   └── model_monitor.py          # PSI 監控模組
│
├── config/
│   └── automation.yaml           # 自動化設定
│
├── logs/                         # 日誌目錄
│   ├── daily_20260120.log
│   ├── retrain_20260120.log
│   ├── launchd_daily.log
│   └── launchd_retrain.log
│
└── models/
    ├── latest_lgbm.pkl           # 最新模型
    └── backup/                   # 模型備份
        └── lgbm_20260120_020000.pkl
```

---

## ❓ 常見問題

### Q: 如何確認排程是否正常執行？
查看日誌檔案：
```bash
ls -lh logs/
tail -50 logs/daily_$(date +%Y%m%d).log
```

### Q: 如何停止自動化？
```bash
launchctl unload ~/Library/LaunchAgents/com.tw-top10.*.plist
```

### Q: 電腦關機後排程會失效嗎？
不會。launchd 會在開機後自動載入排程。

### Q: 如何改變執行時間？
1. 修改 `config/automation.yaml`
2. 重新執行 `bash scripts/setup_launchd.sh`

### Q: 模型備份存放在哪？
`models/backup/`，自動保留最近 30 天。

---

## 🔐 安全建議

1. **定期檢查日誌**: 確保執行正常
2. **備份重要檔案**: `models/`, `data/clean/`
3. **監控 PSI 報告**: 若持續漂移，需人工介入

---

## 📞 支援

若遇到問題，請檢查：
1. 日誌檔案 (`logs/`)
2. PSI 監控報告 (`artifacts/psi_report.json`)
3. 確認虛擬環境路徑正確 (`.venv/`)

# TW-Top10 選股系統

> AI 助手必讀：此專案為**雙機協作開發**，請務必遵守以下規則。

## 🚨 協作規則（AI 必讀）

本專案由兩台電腦共同開發，**你只能修改屬於你的檔案**：

### 如果你是在「主電腦」上
你**只能修改**這些檔案：
- `app/ui.py` - Streamlit 介面
- `app/reason_generator.py` - 理由生成
- `app/glossary.py` - 名詞解釋
- `app/dashboard_renderer.py` - 圖表渲染
- `app/etl_pipeline.py` - 資料管線
- `app/data_fetcher.py` - 資料抓取
- `app/publish_daily.py` - 每日發布
- `static/*`, `templates/*`

**禁止修改**：`indicators.py`, `agent_b_modeling.py`, `agent_b_ranking.py`, `fundamental_data.py`, `models/*`

### 如果你是在「Mini」上
你**只能修改**這些檔案：
- `app/indicators.py` - 技術指標計算
- `app/agent_b_modeling.py` - 模型訓練
- `app/agent_b_ranking.py` - 排名邏輯
- `app/fundamental_data.py` - 基本面資料
- `app/event_detector.py` - 事件偵測
- `app/risk_filter.py` - 風險過濾
- `app/volume_indicators.py` - 量能指標
- `models/*` - 訓練模型
- `run_agent_b.py` - 訓練腳本

**禁止修改**：`ui.py`, `reason_generator.py`, `glossary.py`, `dashboard_renderer.py`

---

## 版本同步

每次開始工作前：
```bash
./scripts/sync_from_remote.sh
```

完成工作後：
```bash
./scripts/push_changes.sh "修改說明"
```

---

## 版本號規則

採用 `主版本.功能版本.修復版本` 格式，例如 `v1.2.3`

### Commit 訊息格式
```
<類型>: <簡短描述>

類型：
- feat:     新功能
- fix:      修復錯誤
- docs:     文件更新
- refactor: 重構（不改變功能）
- perf:     效能優化
- test:     測試相關
```

### 標籤命名
- **主電腦發布**：`v*.*.* -ui` (例如 `v1.3.0-ui`)
- **Mini 發布**：`v*.*.* -ml` (例如 `v1.3.0-ml`)
- **正式版本**：`v*.*.*` (兩邊功能合併後)

### 範例
```bash
# Mini 完成新指標
git tag v1.3.0-ml
git push origin v1.3.0-ml

# 主電腦完成 UI 更新
git tag v1.3.0-ui
git push origin v1.3.0-ui

# 合併後發正式版
git tag v1.3.0
git push origin v1.3.0
```

---

## 專案簡介

台股 AI 選股系統，每日精選前 10 名潛力股票。

### 核心模組
- **Agent A**：資料整備 + 技術指標計算
- **Agent B**：LightGBM 模型訓練 + 排名預測
- **UI**：Streamlit 互動式儀表板

### 技術棧
- Python 3.9+
- Streamlit (UI)
- LightGBM (ML)
- Pandas (資料處理)

---
description: 切換到股票專案並檢查 mini 更新
---

# 切換到股票專案並檢查更新

這個工作流程用於切換到股票專案（tw-top10）並檢查是否有從 mini 端上傳的新版本。

## 步驟

### 1. 檢查遠端更新
// turbo
```bash
cd /Users/matt/tw-top10
git fetch origin
```

### 2. 查看本地與遠端狀態
// turbo
```bash
git status -uno
```

### 3. 查看遠端新提交
// turbo
```bash
git log HEAD..origin/main --oneline
```

### 4. 查看詳細歷史（可選）
```bash
git log --oneline --graph --all -10
```

## 預期結果

- 如果有新提交：會顯示從 mini 端上傳的新版本
- 如果沒有新提交：表示已經是最新狀態

## 後續動作

如果發現有新版本：
- 檢視新功能和變更內容
- 決定是否要執行 `git pull --rebase origin main` 來合併更新
- 或使用 `./scripts/sync_from_remote.sh` 進行安全同步

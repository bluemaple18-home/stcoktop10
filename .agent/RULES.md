# Agent 開發規則與慣例

本文件記錄所有 Agent 在開發此專案時應遵循的規則、慣例與工作流程。

---

## 📋 目錄


1. [Agent 溝通語言規範](#agent-溝通語言規範)
2. [全域技能中心 (Agent Skills Hub)](#全域技能中心-agent-skills-hub)
3. [版本命名規則](#版本命名規則)
4. [Git 工作流程](#git-工作流程)
5. [測試與驗證](#測試與驗證)
6. [程式碼風格](#程式碼風格)
7. [文件撰寫](#文件撰寫)

---

## Agent 溝通語言規範

### 互動原則
- **確認訊息**：所有需要用戶確認 (Confirm) 的訊息，一律使用**繁體中文**。
- **過程描述**：系統執行階段的描述 (What I am doing / TaskStatus)，若能顯示給用戶，一律使用**繁體中文**。
- **思考過程**：Agent 內部的思考過程 (Thinking Process) 預設使用繁體中文。

---

## 全域技能中心 (Agent Skills Hub)

本專案調用位於 `/Users/mattkuo/Projects/agent-skills-hub` 的全域技能中心。

### 使用規範
- **自發評估 (Self-Evaluation)**：開發時應根據 `/Users/mattkuo/Projects/agent-skills-hub/GLOBAL_RULES.md` 中的判定邏輯，自動選擇並套用對應技能。
- **優先調用**：開發新功能或需要特定工具（如 MCP, DeepEval）時，應先檢查技能中心是否已有對應技能。
- **技能同步**：若在專案中開發了具備通用價值的技能，應將其同步至技能中心，而非僅保留在專案內。
- **路徑參考**：`/Users/mattkuo/Projects/agent-skills-hub/skills/`

---

## 版本命名規則

### 格式
```
v{major}.{minor}.{patch}-{category}
```

### Category 後綴說明

- **`-ml`** (Machine Learning): 機器學習模型、訓練、預測相關
- **`-ui`** (User Interface): Web UI、視覺化、使用者體驗相關
- **`-verified`** (Verification): 測試系統、驗證機制、品質保證相關
- **`-data`** (Data Pipeline): 資料處理、ETL、資料源整合相關

### 版本號遞增規則

- **Major**: 重大架構變更、不向後相容
- **Minor**: 新功能新增、向後相容的改進
- **Patch**: Bug 修復、小幅優化

### 整合版本處理

當一個版本整合多個模組時，使用最能代表該版本**核心價值**的 category。

**範例**：
- `v2.5.0-verified` - 建立驗證系統（跨 ML + UI 的品質保證）
- `v2.4.0-ui` - UI 大幅改版

---

## Git 工作流程

### Commit Message 格式

使用**繁體中文**撰寫 commit message：

```
<type>: <subject>

<body>
```

**Type 類型**：
- `feat`: 新功能
- `fix`: Bug 修復
- `docs`: 文件更新
- `refactor`: 重構
- `test`: 測試相關
- `chore`: 雜項（依賴更新、設定調整等）

**範例**：
```
feat: Release v2.5.0-verified - 整合驗證系統

- 新增自動化驗證腳本 (scripts/verify_ui_robust.py)
- 修復 PyArrow 相容性問題
- 整合 Mini 環境的推薦理由中文化
```

### 發布流程

1. 更新 `VERSION` 檔案
2. 更新 `CHANGELOG.md`
3. 清理測試垃圾檔案
4. `git add -A`
5. `git commit -m "feat: Release v{version} - {description}"`
6. `git tag v{version}`
7. `git push origin main && git push origin v{version}`

---

## 測試與驗證

### 自動化測試腳本

**檔案位置**: `scripts/verify_ui_robust.py`

**執行方式**：
```bash
source .venv/bin/activate
python scripts/verify_ui_robust.py
```

**功能**：
- 自動檢測頁面載入
- 驗證關鍵元素存在
- 檢查中文化是否正確
- 偵測錯誤訊息
- 自動截圖存證

### 驗證時機

- 每次 UI 修改後
- 每次依賴套件更新後
- 發布新版本前
- 整合 Mini 環境更新後

### 雙重驗證機制

1. **原生瀏覽器工具** (Browser Subagent): 視覺化驗證，可觀察操作過程
2. **Python 腳本** (Playwright): 自動化驗證，適合 CI/CD 整合

---

## 程式碼風格

### Python

- 使用 **繁體中文** 撰寫註解與 docstring
- 函數名稱使用英文 snake_case
- 類別名稱使用英文 PascalCase
- 常數使用大寫 SNAKE_CASE

**範例**：
```python
class StockRanker:
    """股票排名器 (Advanced版)：融合校準後的模型機率、規則分數與 SHAP 解釋"""
    
    SIGNAL_TRANSLATIONS = {
        'break_20d_high': '突破20日新高',
        'rebound_ma20': '月線支撐反彈',
    }
    
    def calculate_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """計算總分 (含校準機率)"""
        pass
```

### 環境管理

- **必須使用** `uv` 與 `.venv` 建立虛擬環境
- **禁止** 使用 base 環境或單獨使用 pip
- 新增依賴後必須更新 `requirements.txt`

---

## 文件撰寫

### 語言規範

- **所有文件** (README、CHANGELOG、commit message) 使用**繁體中文台灣用語**
- **程式碼本體**保留原始語言（英文）
- **註解與說明**使用繁體中文

### CHANGELOG 格式

```markdown
## [v{version}] - {date} ({description})

### 🎨 分類標題

#### Added
- 新增功能說明

#### Changed
- 變更項目說明

#### Fixed
- 修復問題說明

#### Technical
- 技術細節說明
```

### Agent 產生的文件

- `implementation_plan.md`: 使用繁體中文
- `task.md`: 使用繁體中文
- `walkthrough.md`: 使用繁體中文

---

## 專案特定規則

### 股票資料處理

- 股票代碼 (`stock_id`) 統一使用**字串型態**
- 股票名稱優先使用 `app/stock_names.py` 的本地對照表
- 技術指標名稱使用 `SIGNAL_TRANSLATIONS` 進行中文化

### UI 設計慣例

- K 線圖使用**台股配色**（紅漲綠跌）
- 成交量根據漲跌上色（紅色=漲，綠色=跌）
- 推薦理由使用色塊 (chips) 顯示：
  - 綠色：正面訊號
  - 橙色：警示訊號

---

## 更新記錄

- 2026-01-21: 初版建立，整合版本命名、Git 流程、測試規則

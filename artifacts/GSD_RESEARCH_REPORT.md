# 研究報告：GSD 與 Agentskills

## 1. Threads 貼文分析 (GSD)

貼文探討了「Context Rot」（上下文腐爛）的問題 — 隨著對話變長，AI 的效能會逐漸下降。

**解決方案：GSD (Get Shit Done)**
- **核心哲學**：「將複雜度留在系統中，而非你的工作流裡。」
- **方法論**：
    - **全新 Context**：每個任務都分配一個全新的 AI Session。
    - **結構化流程**：討論 (Discuss) → 規劃 (Plan) → 執行 (Execute) → 驗證 (Verify)。
    - **原子化提交**：頻繁 Commit，保持 Git 歷史乾淨且可追溯。
    - **歸檔**：任務完成後即歸檔，清空 Context。

**應用建議**：
- 我們應採用「每個任務使用新 Session」的模式。
- 對於複雜需求，將其拆解為：
    1.  **規劃 Session**：產出嚴謹的計畫/規格書。
    2.  **執行 Session**：實作該計畫。
    3.  **驗證 Session**：驗證並修復。

## 2. Agentskills 分析

**Repo**: `https://github.com/agentskills/agentskills.git`
**性質**：這是 Agent Skills 的**規範 (Specification)** 與參考實作 (SDK)，而非單一的檢查工具。

**標準規範**：
- 一個 Skill 就是一個包含 `SKILL.md` 的目錄。
- `SKILL.md` 必須包含 YAML frontmatter (`name`, `description`)。
- `skills-ref` 工具 (Python) 可用來**驗證** Skill 是否符合規範。

**使用者規則解讀**：
規則「apply skill to check everything」應理解為：
**「使用 `skills-ref` 驗證工具來確保專案中所有的 Skills 都符合 Agentskills 規範。」**

## 3. Clawd 專案中的發現

- `clawd` 專案包含一個 `skills/` 目錄，內有 50 多個子目錄（如 `github`, `slack`）。
- 這些看起來就是 Agent Skills。
- **行動項目**：我們必須使用 `agentskills` validator 來驗證這些目錄。

## 4. 建議與後續步驟

1.  **採用 GSD**：持續使用「任務模式 (Task Mode)」和 Artifacts (`task.md`, `implementation_plan.md`) 來結構化工作，模擬 GSD 的規劃/執行分離。
2.  **落實 Agentskills 規則**：
    -   **立即行動**：嘗試對 `clawd/skills` 執行 `skills-ref validate`。
    -   **持續進行**：每當編輯或新增 Skill 時，都必須執行驗證器。

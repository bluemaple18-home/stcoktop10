# Changelog

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

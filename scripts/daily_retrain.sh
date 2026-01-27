#!/bin/bash
# tw-top10 每日自動重訓腳本
# 執行時間: 每日 02:00
# 功能: 重新訓練模型、備份舊模型、PSI 監控

set -e

# 切換到專案目錄
cd "$(dirname "$0")/.."
PROJECT_DIR=$(pwd)

# 日誌目錄
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/retrain_$(date +%Y%m%d).log"

echo "========================================" | tee -a "$LOG_FILE"
echo "🔧 開始每日模型重訓 - $(date)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# 啟動虛擬環境
source .venv/bin/activate
export PYTHONPATH=$PROJECT_DIR

# 備份舊模型
echo "" | tee -a "$LOG_FILE"
echo "💾 備份現有模型..." | tee -a "$LOG_FILE"
BACKUP_DIR="models/backup"
mkdir -p "$BACKUP_DIR"

if [ -f "models/latest_lgbm.pkl" ]; then
    BACKUP_NAME="lgbm_$(date +%Y%m%d_%H%M%S).pkl"
    cp models/latest_lgbm.pkl "$BACKUP_DIR/$BACKUP_NAME"
    echo "✅ 已備份至 $BACKUP_DIR/$BACKUP_NAME" | tee -a "$LOG_FILE"
else
    echo "⚠️ 未找到舊模型，跳過備份" | tee -a "$LOG_FILE"
fi

# 執行模型訓練
echo "" | tee -a "$LOG_FILE"
echo "🎓 執行 LightGBM 訓練 (Optuna + Walk-forward)..." | tee -a "$LOG_FILE"
python -m app.agent_b_modeling >> "$LOG_FILE" 2>&1
if [ $? -eq 0 ]; then
    echo "✅ 模型訓練完成" | tee -a "$LOG_FILE"
else
    echo "❌ 模型訓練失敗" | tee -a "$LOG_FILE"
    # 如果訓練失敗，恢復備份
    if [ -f "$BACKUP_DIR/$BACKUP_NAME" ]; then
        echo "🔄 恢復備份模型..." | tee -a "$LOG_FILE"
        cp "$BACKUP_DIR/$BACKUP_NAME" models/latest_lgbm.pkl
    fi
    exit 1
fi

# PSI 監控 (若已實作)
if [ -f "app/model_monitor.py" ]; then
    echo "" | tee -a "$LOG_FILE"
    echo "📊 執行 PSI 漂移監控..." | tee -a "$LOG_FILE"
    python app/model_monitor.py >> "$LOG_FILE" 2>&1
fi

# 清理舊備份 (保留最近 30 天)
echo "" | tee -a "$LOG_FILE"
echo "🧹 清理 30 天前的舊備份..." | tee -a "$LOG_FILE"
find "$BACKUP_DIR" -name "lgbm_*.pkl" -mtime +30 -delete 2>> "$LOG_FILE"

# 完成
echo "" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "✨ 重訓完成 - $(date)" | tee -a "$LOG_FILE"
echo "📄 新模型: models/latest_lgbm.pkl" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

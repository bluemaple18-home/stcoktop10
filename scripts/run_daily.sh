#!/bin/bash
# tw-top10 每日自動執行腳本
# 執行時間: 每日 22:00
# 功能: ETL 資料更新 + 選股推論

set -e  # 遇到錯誤立即停止

# 切換到專案目錄
cd "$(dirname "$0")/.."
PROJECT_DIR=$(pwd)

# 日誌目錄
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/daily_$(date +%Y%m%d).log"

echo "========================================" | tee -a "$LOG_FILE"
echo "🚀 開始每日自動執行 - $(date)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# 啟動虛擬環境
source .venv/bin/activate

# Step 1: ETL 資料更新
echo "" | tee -a "$LOG_FILE"
echo "📊 Step 1/2: 執行 ETL 資料更新..." | tee -a "$LOG_FILE"
python app/etl_pipeline.py --update-daily >> "$LOG_FILE" 2>&1
if [ $? -eq 0 ]; then
    echo "✅ ETL 完成" | tee -a "$LOG_FILE"
else
    echo "❌ ETL 失敗，中止流程" | tee -a "$LOG_FILE"
    exit 1
fi

# Step 2: 執行選股
echo "" | tee -a "$LOG_FILE"
echo "🎯 Step 2/2: 執行 Agent B 選股..." | tee -a "$LOG_FILE"
python app/agent_b_ranking.py >> "$LOG_FILE" 2>&1
if [ $? -eq 0 ]; then
    echo "✅ 選股完成" | tee -a "$LOG_FILE"
else
    echo "⚠️ 選股執行有誤" | tee -a "$LOG_FILE"
fi

# 完成
echo "" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "✨ 每日執行完成 - $(date)" | tee -a "$LOG_FILE"
echo "📄 選股結果: $PROJECT_DIR/artifacts/ranking_$(date +%Y-%m-%d).csv" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

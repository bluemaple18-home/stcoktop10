#!/bin/bash
# Agent A 系統執行腳本

set -e

echo "========================================="
echo "Agent A｜盤後資料整備系統"
echo "========================================="
echo ""

# 檢查虛擬環境
if [ ! -d ".venv" ]; then
    echo "❌ 找不到虛擬環境，請先執行: uv venv"
    exit 1
fi

# 啟動虛擬環境
source .venv/bin/activate

# 檢查套件
echo "[1/3] 檢查相依套件..."
python -c "import pandas, ta, yfinance, tqdm" 2>/dev/null || {
    echo "⚠️  缺少必要套件，開始安裝..."
    uv pip install -r requirements.txt
}

echo "✅ 套件檢查完成"
echo ""

# 執行 ETL
echo "[2/3] 執行 ETL 流程..."
python app/etl_pipeline.py "$@"

# 驗收測試
echo ""
echo "[3/3] 執行驗收測試..."
python app/etl_pipeline.py --validate

echo ""
echo "========================================="
echo "✅ Agent A 執行完成！"
echo "========================================="
echo ""
echo "產出檔案："
echo "  - data/clean/features.parquet"
echo "  - data/clean/universe.parquet"
echo "  - artifacts/etl_report.md"
echo "  - artifacts/signals_preview.png"

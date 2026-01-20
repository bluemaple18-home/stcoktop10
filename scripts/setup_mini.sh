#!/bin/bash
# ============================================================
# Mini 端初始化腳本
# 在 Mini 電腦上執行此腳本來設置開發環境
# ============================================================

set -e

echo "🖥️  Mini 開發環境初始化"
echo "========================"
echo ""

# 1. Clone 專案
echo "📥 克隆專案..."
git clone https://github.com/bluemaple18-home/stcoktop10.git tw-top10
cd tw-top10

# 2. 建立虛擬環境
echo ""
echo "🐍 建立 Python 虛擬環境..."
python3 -m venv .venv
source .venv/bin/activate

# 3. 安裝相依套件
echo ""
echo "📦 安裝相依套件..."
pip install --upgrade pip
pip install -r requirements.txt

# 4. 安裝 libomp (LightGBM 需要)
echo ""
echo "🔧 安裝 libomp (Mac M1/M2 需要)..."
if command -v brew &> /dev/null; then
    brew install libomp 2>/dev/null || echo "libomp 已安裝"
else
    echo "⚠️  請手動安裝 Homebrew 後執行: brew install libomp"
fi

# 5. 建立必要目錄
echo ""
echo "📁 建立目錄..."
mkdir -p data/clean data/raw models artifacts

# 6. 設定可執行權限
chmod +x scripts/*.sh

echo ""
echo "✅ 初始化完成！"
echo ""
echo "📋 接下來您可以："
echo "   1. cd tw-top10"
echo "   2. source .venv/bin/activate"
echo "   3. 開始開發 ML 相關檔案"
echo ""
echo "📖 請閱讀 DEVELOPMENT.md 了解協作規則"
echo ""
echo "🔄 每日工作前請執行: ./scripts/sync_from_remote.sh"

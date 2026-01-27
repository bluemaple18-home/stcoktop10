#!/bin/bash
# tw-top10 Web UI 啟動腳本
# 功能: 啟動 Streamlit 並透過 ngrok 提供外部存取

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

echo "========================================="
echo "🚀 啟動 tw-top10 Web UI"
echo "========================================="
echo ""

# 啟動虛擬環境
source .venv/bin/activate

# 檢查是否為非互動式模式 (例如 launchd)
if [ ! -t 0 ] || [ "$1" == "--no-interact" ]; then
    echo "🤖 偵測到非互動式模式，直接啟動 Streamlit (Local Only)..."
    # SECURITY FIX: Bind to localhost only
    exec streamlit run app/ui.py --server.port 8501 --server.address 127.0.0.1 --server.headless true
fi

# 檢查 ngrok 是否安裝
if ! command -v ngrok &> /dev/null; then
    echo "⚠️ ngrok 未安裝"
    echo ""
    echo "請執行以下指令安裝 ngrok:"
    echo "  brew install ngrok"
    echo ""
    echo "或從官網下載: https://ngrok.com/download"
    echo ""
    read -p "是否僅啟動本地模式 (localhost:8501)? (y/n): " local_only
    
    if [ "$local_only" != "y" ]; then
        echo "❌ 取消啟動"
        exit 1
    fi
    
    # 僅啟動 Streamlit (本地模式)
    echo ""
    echo "🌐 啟動 Streamlit (本地模式)..."
    echo "   存取網址: http://localhost:8501"
    echo ""
    # SECURITY FIX: Bind to localhost only
    streamlit run app/ui.py --server.port 8501 --server.address 127.0.0.1
    
else
    # 啟動 Streamlit (背景執行)
    echo "🌐 啟動 Streamlit..."
    # SECURITY FIX: Bind to localhost only
    streamlit run app/ui.py --server.port 8501 --server.address 127.0.0.1 &
    STREAMLIT_PID=$!
    
    # 等待 Streamlit 啟動
    sleep 3
    
    # 啟動 ngrok
    echo ""
    echo "🔗 啟動 ngrok 隧道..."
    ngrok http 8501 &
    NGROK_PID=$!
    
    # 等待 ngrok 啟動
    sleep 2
    
    # 取得 ngrok 公開網址
    echo ""
    echo "========================================="
    echo "✅ Web UI 已啟動！"
    echo "========================================="
    echo ""
    echo "📱 存取方式:"
    echo ""
    echo "  1. 本地存取 (同網路):"
    echo "     http://localhost:8501"
    echo ""
    echo "  2. 遠端存取 (任何地方):"
    
    # 嘗試從 ngrok API 取得網址
    sleep 1
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"https://[^"]*' | head -1 | cut -d'"' -f4)
    
    if [ -n "$NGROK_URL" ]; then
        echo "     $NGROK_URL"
    else
        echo "     請開啟 http://localhost:4040 查看 ngrok 網址"
    fi
    
    echo ""
    echo "========================================="
    echo ""
    echo "💡 提示:"
    echo "  - ngrok 免費版每次啟動網址會變動"
    echo "  - 若需固定網址，請升級 ngrok 付費版"
    echo "  - 按 Ctrl+C 停止服務"
    echo ""
    
    # 等待使用者中斷
    wait
fi

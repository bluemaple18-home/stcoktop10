#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TW Top10 選股系統 - Streamlit Web UI

此介面提供：
1. 顯示最新選股結果
2. 個股詳細分析與技術指標圖表
3. 歷史選股績效回測
4. 參數調整與自訂選股條件
"""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from pathlib import Path
import glob
import ast
from collections import Counter

# 匯入自訂模組
from reason_generator import format_reasons_text, generate_reasons_structured
from glossary import get_glossary, generate_dynamic_explanation

# 定義常數
TYPE_POSITIVE = "POSITIVE"
TYPE_CAUTION = "CAUTION"



# 頁面設定
st.set_page_config(
    page_title="TW Top10 選股系統",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)


def get_project_root() -> Path:
    """取得專案根目錄"""
    return Path(__file__).parent.parent


def parse_reasons(reasons_data):
    """
    解析理由資料，支援結構化 (List[Dict]) 或字串列表
    """
    if isinstance(reasons_data, list):
        if not reasons_data:
            return []
        # 檢查是否為結構化資料
        if isinstance(reasons_data[0], dict):
            return reasons_data
        # 舊版純字串列表，轉換為結構化
        return [{"type": TYPE_POSITIVE, "text": r} for r in reasons_data]
    
    if isinstance(reasons_data, str):
        try:
            # 嘗試解析字串表示的列表
            parsed = ast.literal_eval(reasons_data)
            return parse_reasons(parsed)
        except:
            pass
            
    # 處理 float 類型的 NaN
    if isinstance(reasons_data, float):
        return []

    # 字串 fallback (可能是單一字串或錯誤格式)
    if isinstance(reasons_data, str) and reasons_data:
        if reasons_data.startswith("⚠"):
            return [{"type": TYPE_CAUTION, "text": reasons_data}]
        return [{"type": TYPE_POSITIVE, "text": reasons_data}]
        
    return []


def get_chip_html(text, chip_type):
    """產生 Chip 的 HTML"""
    color_class = "chip-caution" if chip_type == TYPE_CAUTION else "chip-positive"
    icon = "⚠ " if chip_type == TYPE_CAUTION else ""
    return f'<span class="chip {color_class}">{icon}{text}</span>'


@st.cache_data(ttl=3600)
def load_latest_picks():
    """載入最新選股結果"""
    root = get_project_root()
    artifacts_dir = root / "artifacts"
    
    # 尋找最新的 top10_YYYYMMDD.csv
    csv_files = sorted(artifacts_dir.glob("top10_*.csv"), reverse=True)
    
    if not csv_files:
        return None, None
    
    latest_csv = csv_files[0]
    
    # 從檔名提取日期
    filename = latest_csv.stem  # top10_YYYYMMDD
    date_str = filename.replace("top10_", "")
    
    try:
        # 強制將 stock_id 讀取為字串，避免型態不一致（int vs str）
        df = pd.read_csv(latest_csv, dtype={'stock_id': str})
        return df, date_str
    except Exception as e:
        st.error(f"載入選股檔案失敗: {e}")
        return None, None


@st.cache_data(ttl=3600)
def load_all_historical_picks():
    """載入所有歷史選股結果"""
    root = get_project_root()
    artifacts_dir = root / "artifacts"
    
    csv_files = sorted(artifacts_dir.glob("top10_*.csv"))
    
    if not csv_files:
        return []
    
    history = []
    for csv_file in csv_files:
        date_str = csv_file.stem.replace("top10_", "")
        try:
            # 強制將 stock_id 讀取為字串
            df = pd.read_csv(csv_file, dtype={'stock_id': str})
            history.append({
                'date': date_str,
                'date_obj': datetime.strptime(date_str, "%Y%m%d"),
                'data': df
            })
        except:
            continue
    
    return sorted(history, key=lambda x: x['date_obj'], reverse=True)


import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import ta

# ... (other imports)

# ... (get_project_root, parse_reasons, get_chip_html, load_latest_picks, load_all_historical_picks unchanged) ...

@st.cache_data(ttl=900) # 15 min cache for real-time data
def fetch_stock_history(stock_id: str, days: int = 180) -> pd.DataFrame:
    """
    使用 yfinance 抓取個股歷史資料並計算指標
    """
    try:
        # 台股代號處理
        ticker = f"{stock_id}.TW"
        
        # 設定日期範圍 (拉長到 180 天以確保指標計算穩定)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # 下載資料
        df = yf.download(ticker, start=start_date, end=end_date, progress=False)
        
        if df.empty:
            # 嘗試 .TWO (上櫃)
             ticker = f"{stock_id}.TWO"
             df = yf.download(ticker, start=start_date, end=end_date, progress=False)
        
        if df.empty:
            return None
            
        # 整理欄位 (yfinance MultiIndex 處理)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # 確保有需要的欄位
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        if not all(col in df.columns for col in required_cols):
             return None
             
        # ===== 計算基礎指標 =====
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA60'] = df['Close'].rolling(window=60).mean()
        
        # ===== 計算進階指標 (使用 ta 套件) =====
        
        # 1. KD 指標 (Stochastic Oscillator)
        kd = ta.momentum.StochasticOscillator(high=df['High'], low=df['Low'], close=df['Close'], window=9, smooth_window=3)
        df['K'] = kd.stoch()
        df['D'] = kd.stoch_signal()
        
        # 2. MACD 指標
        macd = ta.trend.MACD(close=df['Close'], window_slow=26, window_fast=12, window_sign=9)
        df['MACD_DIF'] = macd.macd()
        df['MACD_Signal'] = macd.macd_signal()
        df['MACD_Hist'] = macd.macd_diff()
        
        # 3. 布林通道 (Bollinger Bands)
        bb = ta.volatility.BollingerBands(close=df['Close'], window=20, window_dev=2)
        df['BB_Upper'] = bb.bollinger_hband()
        df['BB_Lower'] = bb.bollinger_lband()
        df['BB_Middle'] = bb.bollinger_mavg()
        
        # 計算前一日特徵 (for reason generator)
        df['prev_close'] = df['Close'].shift(1)
        df['prev_volume'] = df['Volume'].shift(1)
        df['prev_ma5'] = df['MA5'].shift(1)
        df['prev_ma20'] = df['MA20'].shift(1)
        
        return df
        
    except Exception as e:
        print(f"Error fetching data for {stock_id}: {e}")
        return None

def plot_interactive_chart(df: pd.DataFrame, stock_id: str, stock_name: str):
    """
    繪製互動式 K 線圖 (包含 KD, MACD, 布林通道)
    """
    if df is None or df.empty:
        st.warning("無有效數據可繪製圖表")
        return

    # 建立子圖 (Main, Volume, KD, MACD)
    fig = make_subplots(
        rows=4, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.03, 
        row_heights=[0.5, 0.15, 0.15, 0.2],
        subplot_titles=(f'{stock_id} {stock_name}', '成交量', 'KD指標', 'MACD')
    )

    # --- Row 1: K線 + MA + 布林通道 ---
    
    # 布林通道 (區域填色)
    if 'BB_Upper' in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df['BB_Upper'],
            line=dict(width=0),
            showlegend=False, hoverinfo='skip'
        ), row=1, col=1)
        
        fig.add_trace(go.Scatter(
            x=df.index, y=df['BB_Lower'],
            fill='tonexty', # 填滿到上一個 trace (BB_Upper)
            fillcolor='rgba(0,0,255,0.05)',
            line=dict(width=0),
            name='布林通道',
            hoverinfo='skip'
        ), row=1, col=1)

    # K線
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['Open'], high=df['High'],
        low=df['Low'], close=df['Close'],
        name='K線'
    ), row=1, col=1)

    # 均線
    ma_colors = {'MA5': 'orange', 'MA20': 'blue', 'MA60': 'purple'}
    for ma, color in ma_colors.items():
        if ma in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df[ma],
                mode='lines', name=ma,
                line=dict(color=color, width=1.5)
            ), row=1, col=1)

    # --- Row 2: 成交量 ---
    colors_vol = ['red' if c >= o else 'green' for c, o in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(
        x=df.index, y=df['Volume'],
        name='成交量',
        marker_color=colors_vol
    ), row=2, col=1)

    # --- Row 3: KD 指標 ---
    if 'K' in df.columns and 'D' in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df['K'],
            mode='lines', name='K',
            line=dict(color='orange', width=1.5)
        ), row=3, col=1)
        
        fig.add_trace(go.Scatter(
            x=df.index, y=df['D'],
            mode='lines', name='D',
            line=dict(color='blue', width=1.5)
        ), row=3, col=1)
        
        # 參考線
        fig.add_hline(y=80, line_dash="dot", line_color="red", row=3, col=1)
        fig.add_hline(y=20, line_dash="dot", line_color="green", row=3, col=1)

    # --- Row 4: MACD ---
    if 'MACD_DIF' in df.columns:
        # 柱狀圖顏色
        colors_hist = ['red' if h >= 0 else 'green' for h in df['MACD_Hist']]
        
        fig.add_trace(go.Bar(
            x=df.index, y=df['MACD_Hist'],
            name='MACD Hist',
            marker_color=colors_hist
        ), row=4, col=1)
        
        fig.add_trace(go.Scatter(
            x=df.index, y=df['MACD_DIF'],
            mode='lines', name='DIF',
            line=dict(color='orange', width=1.5)
        ), row=4, col=1)
        
        fig.add_trace(go.Scatter(
            x=df.index, y=df['MACD_Signal'],
            mode='lines', name='Signal',
            line=dict(color='blue', width=1.5)
        ), row=4, col=1)

    # 布局設定
    fig.update_layout(
        xaxis_rangeslider_visible=False,
        height=800, # 增加高度以容納 4 層
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", y=1.01, x=0.5, xanchor="center"),
        # 移除部分子圖的 x 軸標籤以節省空間
        xaxis1_showticklabels=False,
        xaxis2_showticklabels=False,
        xaxis3_showticklabels=False
    )
    
    # y軸標題
    fig.update_yaxes(title_text="價格", row=1, col=1)
    fig.update_yaxes(title_text="成交量", row=2, col=1)
    
    # 顯示圖表
    st.plotly_chart(fig, use_container_width=True)




def render_sidebar():
    """渲染側邊欄"""
    st.sidebar.title("⚙️ 設定")
    
    st.sidebar.markdown("---")
    
    # 資訊區域
    st.sidebar.subheader("📊 系統資訊")
    
    # 檢查最新選股
    df, date_str = load_latest_picks()
    if df is not None:
        formatted_date = datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
        st.sidebar.success(f"✅ 最新選股: {formatted_date}")
        st.sidebar.info(f"📈 推薦數量: {len(df)} 檔")
    else:
        st.sidebar.warning("⚠️ 尚無選股資料")
    
    st.sidebar.markdown("---")
    
    # 歷史記錄數量
    history = load_all_historical_picks()
    st.sidebar.info(f"📚 歷史記錄: {len(history)} 次選股")
    
    st.sidebar.markdown("---")
    
    # 關於
    st.sidebar.subheader("ℹ️ 關於")
    st.sidebar.markdown("""
    **TW Top10 選股系統**
    
    透過 AI 模型與技術分析，每日精選台股前 10 名潛力股票。
    
    ⚠️ 本系統僅供參考，不構成投資建議。
    """)


def render_main_page():
    """渲染主頁面"""
    st.title("📈 TW Top10 選股系統")
    
    # Inject CSS
    st.markdown("""
    <style>
    table {
      width: 100%;
      border-collapse: collapse;
    }
    th {
      background-color: #f8f9fa;
      font-weight: bold;
      padding: 12px 8px;
      text-align: left;
      border-bottom: 2px solid #dee2e6;
    }
    td {
      padding: 10px 8px;
      border-bottom: 1px solid #dee2e6;
      vertical-align: middle;
    }
    tr:nth-child(even) {background-color: #f8f9fa;}
    .chip {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 12px;
      font-size: 0.85em;
      margin-right: 4px;
      margin-bottom: 4px;
      font-weight: 500;
    }
    .chip-positive {
      background-color: #e3f2fd;
      color: #0d47a1;
      border: 1px solid #bbdefb;
    }
    .chip-caution {
      background-color: #fff3e0;
      color: #e65100;
      border: 1px solid #ffe0b2;
    }
    .rank-cell {
      font-weight: bold;
      text-align: center;
    }
    .top-1 { color: #f1c40f; font-size: 1.2em; }
    .top-2 { color: #95a5a6; font-size: 1.2em; }
    .top-3 { color: #d35400; font-size: 1.2em; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("### 🏠 今日推薦")
    st.markdown("---")
    
    # 載入最新選股
    df, date_str = load_latest_picks()
    
    if df is None:
        st.warning("⚠️ 目前尚未有選股資料，請執行 `python app/publish_daily.py` 產生選股結果。")
        return
    
    formatted_date = datetime.strptime(date_str, "%Y%m%d").strftime("%Y年%m月%d日")
    st.success(f"📅 選股日期: {formatted_date}")
    
    # 預先處理理由與統計
    processed_rows = []
    all_reasons_text = []
    
    for _, row in df.iterrows():
        reasons = []
        # 優先使用 reasons_json
        if 'reasons_json' in row and pd.notna(row['reasons_json']):
            reasons = parse_reasons(row['reasons_json'])
        elif 'reasons' in row and pd.notna(row['reasons']):
            reasons = parse_reasons(row['reasons'])
        
        # 若無理由資料，根據數據自動生成 (使用專業理由生成器)
        if not reasons:
            reasons = generate_reasons_structured(row)

        # 收集統計
        for r in reasons:
            all_reasons_text.append(r['text'])
            
        processed_rows.append({
            'stock_id': row['stock_id'],
            'stock_name': row['stock_name'],
            'exp_ret': row['expected_return_5d'],
            'win_rate': row['win_rate'],
            'reasons': reasons
        })


    # 計算 Top3 觸發
    top_triggers = Counter(all_reasons_text).most_common(3)
    
    # 顯示關鍵指標摘要
    col1, col2, col3 = st.columns(3)
    
    with col1:
        avg_return = df['expected_return_5d'].mean()
        st.metric("📊 平均期望報酬", f"{avg_return:.2f}%")
    
    with col2:
        avg_winrate = df['win_rate'].mean()
        st.metric("🎯 平均勝率", f"{avg_winrate:.1f}%")
    
    with col3:
        st.metric("📈 推薦股票數", f"{len(df)} 檔")
        
    # 顯示熱門觸發
    if top_triggers:
        trigger_text = "  |  ".join([f"{t[0]} ({t[1]})" for t in top_triggers])
        st.info(f"🔥 **本日最常見觸發 (Top 3)**: {trigger_text}")
    
    st.markdown("---")
    
    # 顯示 Top10 表格 (使用 HTML 渲染 Chips)
    st.subheader("🏆 Top10 推薦清單")
    
    html_rows = ""
    for idx, row in enumerate(processed_rows):
        rank = idx + 1
        rank_class = f"top-{rank}" if rank <= 3 else ""
        
        # Format metrics
        ret_color = "red" if row['exp_ret'] >= 3 else "black"
        win_color = "green" if row['win_rate'] >= 70 else "black"
        
        # Chips
        chips_html = ""
        for r in row['reasons'][:5]: # 最多顯示 5 個
            chips_html += get_chip_html(r['text'], r['type'])
            
        html_rows += f"""<tr style="border-bottom: 1px solid #eee;">
<td class="rank-cell {rank_class}" style="text-align:center;font-weight:bold;">{rank}</td>
<td>
    <div style="font-weight:bold;">{row['stock_id']}</div>
    <div style="font-size:0.85em;color:#666;">{row['stock_name']}</div>
</td>
<td style="color:{ret_color};font-weight:bold;">{row['exp_ret']:.2f}%</td>
<td style="color:{win_color};">{row['win_rate']:.1f}%</td>
<td>{chips_html}</td>
</tr>"""
        
    table_html = f"""
<table style="width:100%; border-collapse:collapse;">
    <thead>
        <tr style="background-color:#f8f9fa; border-bottom:2px solid #dee2e6;">
            <th width="8%" style="padding:10px;text-align:center;">排名</th>
            <th width="15%" style="padding:10px;text-align:left;">股號/名稱</th>
            <th width="15%" style="padding:10px;text-align:left;">5日報酬</th>
            <th width="12%" style="padding:10px;text-align:left;">勝率</th>
            <th style="padding:10px;text-align:left;">推薦理由</th>
        </tr>
    </thead>
    <tbody>
        {html_rows}
    </tbody>
</table>
"""
    
    st.markdown(table_html.strip(), unsafe_allow_html=True)
    
    st.markdown("---")
    
    st.markdown("---")
    
    # Tips
    st.info("💡 提示：點擊左側選單的「個股分析」可查看詳細技術線圖與指標。")



def render_stock_detail_page():
    """渲染個股詳細分析頁面"""
    st.title("🔍 個股詳細分析")
    st.markdown("---")
    
    # 載入最新選股
    df, date_str = load_latest_picks()
    
    if df is None:
        st.warning("⚠️ 目前尚未有選股資料")
        return
    
    # 選擇股票
    stock_options = [f"{row['stock_id']} {row['stock_name']}" for _, row in df.iterrows()]
    selected_stock = st.selectbox("請選擇股票", stock_options)
    
    if not selected_stock:
        return
    
    # 解析選擇的股票
    stock_id = selected_stock.split()[0]
    
    # 增加安全檢查，確保不會因為找不到資料而崩潰
    stock_data = df[df['stock_id'] == stock_id]
    if stock_data.empty:
        st.error(f"❌ 找不到股票代號 {stock_id} 的資料，請確認資料是否正確。")
        return
        
    stock_row = stock_data.iloc[0]
    
    st.markdown(f"## {stock_row['stock_id']} {stock_row['stock_name']}")
    
    # 顯示基本資訊
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("5日期望報酬", f"{stock_row['expected_return_5d']:.2f}%")
    
    with col2:
        st.metric("勝率", f"{stock_row['win_rate']:.1f}%")
    
    with col3:
        if 'close' in stock_row:
            st.metric("收盤價", f"{stock_row['close']:.2f}")
    
    with col4:
        if 'volume' in stock_row:
            volume_k = stock_row['volume'] / 1000
            st.metric("成交量", f"{volume_k:.1f}K")
    
    st.markdown("---")
    
    st.markdown("---")
    
    # 獲取歷史數據 (for Chart & Real Analysis)
    hist_df = fetch_stock_history(stock_id)
    
    # 解析/生成推薦理由
    st.subheader("💡 推薦理由")
    
    reasons = []
    # 1. 優先使用 CSV 內的 reasons_json (若有)
    if 'reasons_json' in stock_row and pd.notna(stock_row['reasons_json']):
         reasons = parse_reasons(stock_row['reasons_json'])
    
    # 2. 若無，嘗試使用歷史數據進行「真實技術分析」
    if not reasons and hist_df is not None and not hist_df.empty:
        # 取最後一筆數據作為當前狀態
        latest_row = hist_df.iloc[-1].copy()
        # 補上選股時的預期報酬與勝率 (這些是模型預測值，歷史數據沒有)
        latest_row['expected_return_5d'] = stock_row['expected_return_5d']
        latest_row['win_rate'] = stock_row['win_rate']
        
        reasons = generate_reasons_structured(latest_row, hist_df=hist_df)
        
    # 3. 若還是無 (Failover)，使用 CSV 單行數據進行推斷
    # 3. 若還是無 (Failover)，使用 CSV 單行數據進行推斷
    if not reasons:
        reasons = generate_reasons_structured(stock_row)
        
    # 顯示理由
    if reasons:
        st.write("###### 點擊下方理由查看白話文解釋 👇")
        for i, reason in enumerate(reasons, 1):
            r_text = reason['text']
            r_type = reason['type']
            metadata = reason.get('metadata', {})
            
            icon = "⚠ " if r_type == TYPE_CAUTION else "✅ "
            
            # 使用 Expander 顯示教學 (動態生成)
            glossary_item = generate_dynamic_explanation(r_text, metadata)
            
            with st.expander(f"{i}. {icon}{r_text}"):
                st.markdown(f"**{glossary_item['simple']}**")
                
                # 若有元數據，顯示 "佐證數據" 標籤，增加專業感
                if metadata and 'note' not in metadata: 
                    st.caption("🕵️‍♂️ AI 偵探分析報告：")
                    
                st.info(glossary_item['detail'])
                
    else:
        st.info("暫無推薦理由")
            
    st.markdown("---")
    
    # 顯示技術圖表 (互動式)
    st.subheader("📊 技術分析圖表")
    
    # 新手教學區塊
    with st.expander("🔰 3分鐘看懂這張圖 (新手教學)"):
        st.markdown("""
        **1. 什麼是 K 線 (蠟燭圖)?**
        *   **紅K棒 (實心紅)**: 收盤價 > 開盤價，代表今天**漲**了。
        *   **黑K棒 (實心綠)**: 收盤價 < 開盤價，代表今天**跌**了。
        *   上下那兩根線叫做「影線」，代表今天曾經到過的最高價與最低價。
        
        **2. 那些彩色線條是什麼? (均線)**
        *   **橘線 (MA5)**: 最近 5 天大家的平均成本，代表**短線**趨勢。
        *   **藍線 (MA20)**: 最近一個月大家的平均成本，代表**中線**趨勢（生命線）。
        *   **紫線 (MA60)**: 最近一季大家的平均成本，代表**長線**趨勢。
        *   **用法**: 當橘線(短)由下往上穿過藍線(中)，叫做「黃金交叉」，通常是買點！
        
        **3. 下面的柱子是什麼? (成交量)**
        *   代表今天買賣的熱絡程度。柱子越高，代表參與的人越多。
        *   **紅柱**: 手氣旺，買盤強。
        *   **綠柱**: 賣壓重，大家在逃。
        *   **用法**: 股價漲的時候，最好柱子也要變高（量價齊揚），代表是玩真的。
        
        **4. 什麼是 KD 與 MACD?**
        *   **KD (第3層)**: 超過80代表太貴(過熱)，低於20代表太便宜(超賣)。
        *   **MACD (第4層)**: 紅柱變長代表漲勢變強，綠柱變長代表跌勢變重。
        """)
    
    if hist_df is not None and not hist_df.empty:
        plot_interactive_chart(hist_df, stock_id, stock_row['stock_name'])
        st.caption(f"資料來源: Yahoo Finance (延遲報價), 更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    else:
        st.warning("⚠️ 無法取得即時歷史數據，無法繪製互動圖表。")
        # Fallback to static image if available
        chart_path = load_stock_chart(stock_id)
        if chart_path:
            st.image(str(chart_path), caption="靜態備份圖表")


def render_backtest_page():
    """渲染回測績效頁面"""
    st.title("📊 歷史選股記錄")
    st.markdown("---")
    
    # 載入歷史資料
    history = load_all_historical_picks()
    
    if not history:
        st.warning("⚠️ 目前尚無歷史選股資料")
        return
    
    st.info(f"📚 共有 {len(history)} 次選股記錄")
    
    # 顯示每次選股的摘要
    for record in history:
        date_obj = record['date_obj']
        df = record['data']
        
        with st.expander(f"📅 {date_obj.strftime('%Y-%m-%d')} ({len(df)} 檔)", expanded=False):
            # 顯示摘要統計
            col1, col2 = st.columns(2)
            
            with col1:
                avg_return = df['expected_return_5d'].mean()
                st.metric("平均期望報酬", f"{avg_return:.2f}%")
            
            with col2:
                avg_winrate = df['win_rate'].mean()
                st.metric("平均勝率", f"{avg_winrate:.1f}%")
            
            # 顯示清單
            display_df = df[['stock_id', 'stock_name', 'expected_return_5d', 'win_rate']].copy()
            display_df.columns = ['股票代號', '股票名稱', '期望報酬 (%)', '勝率 (%)']
            st.dataframe(display_df, hide_index=True, use_container_width=True)


def main():
    """主程式"""
    # 渲染側邊欄
    render_sidebar()
    
    # 頁面導航
    page = st.sidebar.radio(
        "導航",
        ["🏠 首頁", "🔍 個股分析", "📊 歷史記錄"]
    )
    
    # 根據選擇的頁面渲染對應內容
    if page == "🏠 首頁":
        render_main_page()
    elif page == "🔍 個股分析":
        render_stock_detail_page()
    elif page == "📊 歷史記錄":
        render_backtest_page()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tw-top10 選股系統 Web UI
使用 Streamlit 建立互動式網頁介面
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
from datetime import datetime, timedelta
import json

# 頁面設定
st.set_page_config(
    page_title="TW Top10 選股系統",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自訂 CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .stock-card {
        border: 2px solid #e0e0e0;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        background: #f9f9f9;
    }
</style>
""", unsafe_allow_html=True)

# ========================================
# 資料載入函數
# ========================================

@st.cache_data(ttl=300)  # 快取 5 分鐘
def load_latest_ranking():
    """載入最新選股結果"""
    artifacts_dir = Path("artifacts")
    ranking_files = list(artifacts_dir.glob("ranking_*.csv"))
    
    if not ranking_files:
        return None, None
    
    # 找最新的檔案
    latest_file = max(ranking_files, key=lambda x: x.stat().st_mtime)
    date_str = latest_file.stem.replace("ranking_", "")
    
    df = pd.read_csv(latest_file)
    return df, date_str

@st.cache_data(ttl=600)
def load_backtest_report():
    """載入回測報告"""
    report_path = Path("artifacts/backtest_report.md")
    if report_path.exists():
        return report_path.read_text()
    return None

@st.cache_data(ttl=600)
def load_psi_report():
    """載入 PSI 監控報告"""
    psi_path = Path("artifacts/psi_report.json")
    if psi_path.exists():
        with open(psi_path, 'r') as f:
            return json.load(f)
    return None

@st.cache_data(ttl=3600)
def load_historical_rankings():
    """載入歷史選股記錄"""
    artifacts_dir = Path("artifacts")
    ranking_files = sorted(artifacts_dir.glob("ranking_*.csv"))
    
    history = []
    for file in ranking_files[-30:]:  # 最近 30 天
        date_str = file.stem.replace("ranking_", "")
        df = pd.read_csv(file)
        history.append({
            'date': date_str,
            'count': len(df),
            'avg_score': df['final_score'].mean() if 'final_score' in df.columns else 0
        })
    
    return pd.DataFrame(history) if history else None

# ========================================
# 主頁面
# ========================================

def main():
    # === Emergency Progress Bar ===
    import time
    from pathlib import Path
    try:
        progress_file = Path("data/clean/repair_progress.json")
        if progress_file.exists():
            import json
            with open(progress_file, 'r') as f:
                p_data = json.load(f)
            
            # Show if active (< 5 mins old)
            if time.time() - p_data.get("updated", 0) < 300:
                if p_data.get("percentage", 0) < 100:
                    st.warning(f"🚧 正在從 Yahoo Finance 下載修復資料... ({p_data.get('percentage')}%)")
                    st.progress(p_data.get("percentage", 0) / 100.0)
                    st.caption(f"狀態: {p_data.get('status')} ({p_data.get('current')}/{p_data.get('total')})")
                    if st.button("🔄 點擊刷新進度"):
                        st.rerun()
                elif p_data.get("percentage", 0) >= 100:
                    st.success("✅ 資料修復完成！請重新整理頁面。")
    except Exception as e:
        pass
    # ==============================

    # 標題
    st.markdown('<div class="main-header">📈 TW Top10 選股系統</div>', unsafe_allow_html=True)
    
    # 側邊欄
    with st.sidebar:
        st.image("https://via.placeholder.com/300x100/667eea/ffffff?text=TW+Top10", use_container_width=True)
        st.markdown("---")
        
        page = st.radio(
            "選擇頁面",
            ["🎯 今日選股", "📊 歷史績效", "🔍 PSI 監控", "📈 個股分析", "ℹ️ 系統資訊"],
            index=0
        )
        
        # If stock analysis selected, show stock selector in main area, not here
        # Removed sidebar selector logic to move to main page

        
        st.markdown("---")
        st.markdown("### 系統狀態")
        
        # 資料健康度檢查
        df_rank, date_str = load_latest_ranking()
        if date_str:
            last_dt = datetime.strptime(date_str, '%Y-%m-%d').date()
            if (datetime.now().date() - last_dt).days <= 2:
                st.success(f"✅ 資料更新中 (最後日期: {date_str})")
            else:
                st.error(f"🚨 資料停滯 (最後日期: {date_str})")
        else:
             st.warning("⚠️ 查無選股資料")
             
        st.info(f"🕐 介面更新: {datetime.now().strftime('%H:%M')}")
    
    # 根據選擇顯示不同頁面
    if st.session_state.get('page') == 'detail' or page == "📈 個股分析":
        show_stock_detail()
    elif page == "🎯 今日選股":
        show_daily_ranking()
    elif page == "📊 歷史績效":
        show_performance()
    elif page == "🔍 PSI 監控":
        show_psi_monitor()
    else:
        show_system_info()

# ========================================
# 頁面 1: 今日選股
# ========================================

def show_daily_ranking():
    st.header("🎯 今日 Top 10 選股")
    
    df, date_str = load_latest_ranking()
    
    if df is None:
        st.warning("⚠️ 尚無選股資料，請先執行 `python app/agent_b_ranking.py`")
        return
    
    # 顯示日期與摘要
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📅 選股日期", date_str)
    with col2:
        st.metric("📊 選股數量", len(df))
    with col3:
        avg_score = df['final_score'].mean() if 'final_score' in df.columns else 0
        st.metric("⭐ 平均分數", f"{avg_score:.3f}")
    with col4:
        # 顯示回測實證勝率 (比原始機率更有意義)
        st.metric("🏆 實證勝率", "63.5%", delta="+38.5% (vs 目標)")
    
    st.markdown("---")
    
    # 顯示 Top 10 列表
    st.subheader("📋 推薦清單")
    
    for idx, row in df.head(10).iterrows():
        with st.container():
            col1, col2, col3 = st.columns([2, 3, 5])
            
            with col1:
                stock_id = row.get('stock_id', 'N/A')
                stock_name = row.get('stock_name', '')
                
                # Make clickable
                if st.button(f"{idx+1}. {stock_id} {stock_name}", key=f"stock_{idx}"):
                    st.session_state['selected_stock'] = stock_id
                    st.session_state['selected_stock_name'] = stock_name
                    st.session_state['page'] = 'detail'
                    st.rerun()
            
            with col2:
                st.metric("綜合分數", f"{row.get('final_score', 0):.3f}")
                st.metric("AI 勝率", f"{row.get('model_prob', 0)*100:.1f}%")
            
            with col3:
                st.markdown("**推薦理由**")
                reasons = row.get('reasons', '無')
                
                # Parse AI reasons (format: "| AI: feature1(+0.12) feature2(-0.14)")
                if reasons and '| AI:' in reasons:
                    ai_part = reasons.split('| AI:')[1].strip()
                    # Split by space, parse each feature
                    features = ai_part.split()
                    chips = []
                    for feat in features:
                        if '(' in feat and ')' in feat:
                            # Extract feature name and value
                            name = feat[:feat.index('(')]
                            value = feat[feat.index('(')+1:feat.index(')')]
                            # Translate common features
                            translations = {
                                'volume_ratio_20d': '20日量能比',
                                'd': 'KD-D值',
                                'k': 'KD-K值',
                                'macd': 'MACD',
                                'macd_signal': 'MACD信號',
                                'bb_width': '布林寬度',
                                'pct_from_low_60d': '60日相對低點',
                                'pct_from_high_60d': '60日相對高點',
                                'ma20': 'MA20',
                                'rsi': 'RSI'
                            }
                            display_name = translations.get(name, name)
                            
                            # Color based on value
                            if value.startswith('+'):
                                st.markdown(f':green[✓ {display_name} {value}]', unsafe_allow_html=True)
                            else:
                                st.markdown(f':orange[⚠ {display_name} {value}]', unsafe_allow_html=True)
                else:
                    st.info(reasons if reasons else "無特定理由")
            
            st.markdown("---")

# ========================================
# 頁面 2: 歷史績效
# ========================================

def show_performance():
    st.header("📊 歷史績效分析")
    
    # 載入回測報告
    report = load_backtest_report()
    if report:
        st.markdown("### 📄 回測報告")
        st.markdown(report)
    
    # 載入歷史選股趨勢
    history_df = load_historical_rankings()
    
    if history_df is not None and not history_df.empty:
        st.markdown("---")
        st.subheader("📈 選股趨勢 (最近 30 天)")
        
        # 繪製趨勢圖
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=history_df['date'],
            y=history_df['avg_score'],
            mode='lines+markers',
            name='平均分數',
            line=dict(color='#667eea', width=3)
        ))
        
        fig.update_layout(
            title="每日平均選股分數趨勢",
            xaxis_title="日期",
            yaxis_title="平均分數",
            hovermode='x unified',
            template='plotly_white'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # 顯示績效指標
    st.markdown("---")
    st.subheader("🎯 核心績效指標")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown('<div class="metric-card"><h3>67.0%</h3><p>正報酬勝率</p></div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="metric-card"><h3>+5.33%</h3><p>平均報酬 (10天)</p></div>', unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="metric-card"><h3>10天</h3><p>建議持有期</p></div>', unsafe_allow_html=True)

# ========================================
# 頁面 3: PSI 監控
# ========================================

def show_psi_monitor():
    st.header("🔍 PSI 漂移監控")
    
    psi_data = load_psi_report()
    
    if psi_data is None:
        st.warning("⚠️ 尚無 PSI 監控資料，請執行 `python app/model_monitor.py`")
        return
    
    # 顯示狀態
    status = psi_data.get('status', 'UNKNOWN')
    avg_psi = psi_data.get('avg_psi', 0)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if status == 'OK':
            st.success(f"✅ 狀態: {status}")
        elif status == 'WARNING':
            st.warning(f"⚠️ 狀態: {status}")
        else:
            st.error(f"🚨 狀態: {status}")
    
    with col2:
        st.metric("整體 PSI", f"{avg_psi:.4f}")
    
    with col3:
        st.info(psi_data.get('action', '無建議'))
    
    # 顯示 Top 漂移特徵
    st.markdown("---")
    st.subheader("📊 Top 5 漂移特徵")
    
    top_features = psi_data.get('top_drift_features', [])
    
    if top_features:
        feature_df = pd.DataFrame(top_features, columns=['特徵', 'PSI 值'])
        
        fig = px.bar(
            feature_df,
            x='PSI 值',
            y='特徵',
            orientation='h',
            color='PSI 值',
            color_continuous_scale='Reds',
            title="特徵漂移程度"
        )
        
        fig.update_layout(template='plotly_white')
        st.plotly_chart(fig, use_container_width=True)

# ========================================
# 頁面: 分析報告
# ========================================



# ========================================
# 頁面: 個股詳細資訊
# ========================================

# Helper: Load analysis report
@st.cache_data(ttl=300)
def load_analysis_report():
    yaml_path = Path("artifacts/analysis_report.yaml")
    if yaml_path.exists():
        import yaml
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                # Use FullLoader or suppress constructor errors if possible
                # Simple fix: try safe_load, if fail return None
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading YAML report: {e}")
            return None
    return None

def show_stock_detail():
    st.markdown("""
    <style>
    .matrix-card {
        background-color: #262730;
        border: 1px solid #464b59;
        border-radius: 5px;
        padding: 15px;
        height: 100%;
    }
    .matrix-title {
        font-size: 0.9em;
        color: #aaa;
        margin-bottom: 5px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .matrix-value-good { color: #4CAF50; font-weight: bold; font-size: 1.1em; }
    .matrix-value-bad { color: #FF5252; font-weight: bold; font-size: 1.1em; }
    .matrix-value-neutral { color: #E0E0E0; font-weight: bold; font-size: 1.1em; }
    
    .deep-dive-header {
        border-left: 3px solid #4CAF50;
        padding-left: 10px;
        color: #4CAF50;
        margin-top: 30px;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

    # Move selector to main area
    df, _ = load_latest_ranking()
    stock_options = []
    if df is not None and not df.empty:
        # Get Top 10 options first
        stock_options = [f"{row['stock_id']} {row.get('stock_name', '')}" for _, row in df.head(10).iterrows()]
    
    col_header_1, col_header_2 = st.columns([3, 1])
    
    with col_header_2:
        # Get current selection from state
        current_stock_id = st.session_state.get('selected_stock', None)
        current_stock_name = st.session_state.get('selected_stock_name', '')
        
        # Ensure current selection is in options
        current_opt_str = f"{current_stock_id} {current_stock_name}"
        
        # Check if current stock is in the list based on stock_id
        found_in_list = False
        current_idx = 0
        
        if current_stock_id:
            for i, opt in enumerate(stock_options):
                if opt.startswith(str(current_stock_id)):
                    current_idx = i
                    found_in_list = True
                    break
            
            # If not in list (e.g. selected from sidebar but not in Top 10), add it
            if not found_in_list:
                stock_options.append(current_opt_str)
                current_idx = len(stock_options) - 1
        
        # Callback to update session state
        def on_ticker_change():
            sel = st.session_state['main_ticker_selector']
            if sel:
                parts = sel.split()
                st.session_state['selected_stock'] = parts[0]
                st.session_state['selected_stock_name'] = ' '.join(parts[1:]) if len(parts) > 1 else ''

        # Render Selectbox
        # Use key='main_ticker_selector' and on_change callback for stability
        st.selectbox(
            "Switch Ticker", 
            stock_options, 
            index=current_idx, 
            key='main_ticker_selector',
            label_visibility="collapsed",
            on_change=on_ticker_change
        )

    stock_id = st.session_state.get('selected_stock', None)
    stock_name = st.session_state.get('selected_stock_name', '')

    if not stock_id:
        st.warning("⚠️ 請選擇股票")
        return
    
    if not stock_id:
        st.warning("⚠️ 請選擇股票")
        return
    
    with col_header_1:
         # Simplified header or remove it if redundant. User complained about duplication.
         # The selector above shows the stock. The section below says "1141 瑞展 ...".
         # Let's keep a clean big title here and remove the stock name from the section header below.
         st.markdown(f"## {stock_id} {stock_name}")

    # Load data
    try:
        features_df = pd.read_parquet("data/clean/features.parquet")
        stock_data = features_df[features_df['stock_id'] == str(stock_id)].copy()
        
        if stock_data.empty:
            st.error(f"❌ 找不到 {stock_id} 的歷史資料")
            return
        
        stock_data = stock_data.sort_values('date')
        latest = stock_data.iloc[-1]
        
        # Load Ranking Data
        ranking_df, _ = load_latest_ranking()
        ranking_df['stock_id'] = ranking_df['stock_id'].astype(str).str.strip()
        target_id = str(stock_id).strip()
        stock_ranking = ranking_df[ranking_df['stock_id'] == target_id]
        
        score, prob, rank = 0, 0, "N/A"
        ai_features = []
        if not stock_ranking.empty:
            row = stock_ranking.iloc[0]
            score = row.get('final_score', 0)
            prob = row.get('model_prob', 0)
            rank = ranking_df[ranking_df['stock_id'] == target_id].index[0] + 1
            reasons = row.get('reasons', '')
            if reasons and '| AI:' in reasons:
                ai_part = reasons.split('| AI:')[1].strip()
                ai_features = ai_part.split()

        # Data preparation (Restore missing definitions)
        close = latest['close']
        ma20 = latest.get('ma20', close)
        ma5 = latest.get('ma5', close)
        volume = latest.get('volume', 0)
        rsi = latest.get('rsi', 50)
        k_val = latest.get('k', 50)
        d_val = latest.get('d', 50)

        # ===========================================
        # 1. 核心訊號總結 (Summary)
        # ===========================================
        # Removed redundant "{stock_id} {stock_name}" from title
        st.markdown(f"### 🛡️ 核心訊號總結") 
        
        # Top Metrics Row
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("目前股價", f"${close:.2f}")
        
        ma20_diff = (close - ma20) / ma20 * 100
        m2.metric("20日乖離", f"{ma20_diff:+.2f}%", delta_color="normal")
        
        m3.metric("AI 預測勝率", f"{prob*100:.1f}%", help="模型預測未來 5-10 日上漲機率")
        m4.metric("今日排名", f"#{rank}", help="綜合評分排名")
        
        # Reason Chips (Translated)
        # Feature Name Mapping
        feature_map = {
            'volume_ratio_20d': '20日量比',
            'bb_width': '布林寬度',
            'macd_signal': 'MACD訊號',
            'macd': 'MACD柱',
            'd': 'KD-D值',
            'k': 'KD-K值',
            'rsi': 'RSI',
            'pct_from_low_60d': '距60日低(%)',
            'pct_from_high_60d': '距60日高(%)',
            'ma5': '5日均線',
            'ma20': '20日均線',
            'close': '收盤價'
        }

        if ai_features:
            st.markdown("**AI 關注特徵：**")
            chip_cols = st.columns(len(ai_features) if len(ai_features) < 5 else 5)
            for i, feat in enumerate(ai_features[:5]): # Show max 5
                # Parse format: name(val)
                display_text = feat
                if '(' in feat:
                    fname = feat.split('(')[0]
                    fval = feat.split('(')[1].replace(')', '')
                    if fname in feature_map:
                        display_text = f"{feature_map[fname]} {fval}"
                
                with chip_cols[i % 5]:
                     st.caption(f"🏷️ {display_text}")
        
        st.markdown("---")

        # ===========================================
        # 2. 市場訊號矩陣 (Signal Matrix)
        # ===========================================
        st.subheader("📊 市場訊號矩陣")
        
        # Determine Matrix States (Chinese)
        # Trend
        trend_status = "多頭排列" if close > ma20 else "空頭排列"
        trend_color = "good" if trend_status == "多頭排列" else "bad"
        trend_desc = "股價 > 20日均線 (月線)"
        
        # Momentum
        rsi = latest.get('rsi', 50)
        mom_status = "中性整理"
        mom_color = "neutral"
        if rsi > 70: mom_status, mom_color = "短線過熱", "bad"
        elif rsi < 30: mom_status, mom_color = "短線超賣", "good"
        else:
             if latest.get('k',0) > latest.get('d',0): mom_status, mom_color = "黃金交叉", "good"
        
        mom_desc = f"RSI: {rsi:.1f}"
             
        # Volume
        vol = latest.get('volume', 0)
        vol_avg = stock_data.tail(20)['volume'].mean()
        vol_ratio = vol / vol_avg if vol_avg > 0 else 0
        vol_status = "放量攻擊" if vol_ratio > 1.2 else "量縮/正常"
        vol_color = "good" if vol_ratio > 1.2 else "neutral"
        vol_desc = f"量比: {vol_ratio:.1f}倍"
        
        # SMC (Smart Money Concepts)
        smc_val = latest.get('bos', 0)
        smc_status = "多頭結構 (BOS)" if smc_val == 1 else "空頭結構 (BOS)" if smc_val == -1 else "中性/整理"
        smc_color = "good" if smc_val == 1 else "bad" if smc_val == -1 else "neutral"
        
        choch_val = latest.get('choch', 0)
        smc_desc = f"CHoCH: {'翻多' if choch_val == 1 else '翻空' if choch_val == -1 else '無'}"
        
        # AI
        ai_status = "強力推薦" if prob > 0.7 else "中立偏多"
        ai_color = "good" if prob > 0.7 else "neutral"
        ai_desc = f"綜合分: {score:.2f}"

        # Render Matrix in Chinese
        c1, c2, c3, c4, c5 = st.columns(5)
        
        def matrix_cell(col, title, value, sub, status_color):
            with col:
                st.markdown(f"""
                <div class="matrix-card">
                    <div class="matrix-title">{title}</div>
                    <div class="matrix-value-{status_color}">{value}</div>
                    <div style="font-size: 0.8em; color: #888; margin-top: 5px;">{sub}</div>
                </div>
                """, unsafe_allow_html=True)
                
        matrix_cell(c1, "主要趨勢 (Trend)", trend_status, trend_desc, trend_color)
        matrix_cell(c2, "動能指標 (Mom)", mom_status, mom_desc, mom_color)
        matrix_cell(c3, "量能分析 (Vol)", vol_status, vol_desc, vol_color)
        matrix_cell(c4, "機構動向 (SMC)", smc_status, smc_desc, smc_color)
        matrix_cell(c5, "AI 信心 (Conf)", ai_status, ai_desc, ai_color)
        
        st.markdown("") 

        # ===========================================
        # 3. 風險評估 (Risk Assessment)
        # ===========================================
        # Try to get data from report, else estimation
        report_data = load_analysis_report()
        stock_report = None
        if report_data and 'recommendations' in report_data:
            for rec in report_data['recommendations']:
                if rec['stock'].startswith(str(stock_id)):
                    stock_report = rec
                    break
        
        invalidation_text = "N/A"
        entry_zone_text = "N/A"
        
        if stock_report:
            tp = stock_report['trade_plan']
            invalidation_text = tp.get('invalidation', 'N/A')
            ez = tp.get('entry_zone', {})
            entry_zone_text = f"{ez.get('low',0)} - {ez.get('high',0)}"
        else:
            # Fallback calculation
            stop_loss = latest['ma20'] * 0.98 # Use latest['ma20']
            invalidation_text = f"跌破月線 ${stop_loss:.1f}"
            entry_zone_text = f"${latest['close']:.1f} 左右" # Use latest['close']

        st.subheader("🛡️ 風險評估與交易計劃")
        rc1, rc2 = st.columns(2)
        with rc1:
            st.info(f"**🎯 建議進場區間**: {entry_zone_text}")
        with rc2:
            st.error(f"**🛑 停損/無效點**: {invalidation_text}")

        st.markdown("---")
        
        # ===========================================
        # 4. 技術詳解 (Chart & Deep Dive)
        # ===========================================
        st.subheader("📈 技術面詳解 (K線圖)")
        
        # Plot Function
        # Load more data (e.g., last 300 days for ~1.5 years history) to allow scrolling back
        display_data = stock_data.tail(300).copy()
        
        # Calculate range for the last 3 months (approx 90 days)
        if not display_data.empty:
            last_date = pd.to_datetime(display_data['date'].iloc[-1])
            start_view_date = last_date - timedelta(days=90)
            # Ensure start_view_date is not before the first available date
            first_date = pd.to_datetime(display_data['date'].iloc[0])
            if start_view_date < first_date:
                start_view_date = first_date
        else:
            start_view_date = None
            last_date = None

        from plotly.subplots import make_subplots
        import plotly.graph_objects as go
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
        
        # Candle
        if all(col in display_data.columns for col in ['open', 'high', 'low', 'close']):
            fig.add_trace(go.Candlestick(
                x=display_data['date'],
                open=display_data['open'],
                high=display_data['high'],
                low=display_data['low'],
                close=display_data['close'],
                name='價格',
                increasing_line_color='#FF3B30',  # 台股紅色 = 漲
                decreasing_line_color='#34C759',  # 台股綠色 = 跌
                increasing_fillcolor='#FF3B30',
                decreasing_fillcolor='#34C759'
            ), row=1, col=1)
        else:
            # Fallback to line
            fig.add_trace(go.Scatter(
                x=display_data['date'],
                y=display_data['close'],
                mode='lines',
                name='收盤價',
                line=dict(color='#1f77b4', width=2)
            ), row=1, col=1)
        
        # Add MA lines
        for ma_col, color, name in [('ma5', '#FF9500', 'MA5'), ('ma20', '#007AFF', 'MA20'), ('ma60', '#5856D6', 'MA60')]:
            if ma_col in display_data.columns:
                fig.add_trace(go.Scatter(
                    x=display_data['date'],
                    y=display_data[ma_col],
                    mode='lines',
                    name=name,
                    line=dict(color=color, width=1.5, dash='dot'),
                    showlegend=True
                ), row=1, col=1)
        
        # Add Bollinger Bands
        if all(col in display_data.columns for col in ['bb_upper', 'bb_lower']):
            fig.add_trace(go.Scatter(
                x=display_data['date'],
                y=display_data['bb_upper'],
                mode='lines',
                name='布林上軌',
                line=dict(color='rgba(100,100,100,0.3)', width=1, dash='dash'),
                showlegend=False
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=display_data['date'],
                y=display_data['bb_lower'],
                mode='lines',
                name='布林下軌',
                line=dict(color='rgba(100,100,100,0.3)', width=1, dash='dash'),
                fill='tonexty',
                fillcolor='rgba(100,100,100,0.1)',
                showlegend=False
            ), row=1, col=1)
        
        # === Bottom subplot: Volume with color based on price change ===
        if 'volume' in display_data.columns:
            # Calculate volume colors based on close vs open
            volume_colors = []
            for _, row in display_data.iterrows():
                if row['close'] >= row['open']:
                    volume_colors.append('#FF3B30')  # 紅色 = 漲
                else:
                    volume_colors.append('#34C759')  # 綠色 = 跌
            
            fig.add_trace(go.Bar(
                x=display_data['date'],
                y=display_data['volume'],
                name='成交量',
                marker_color=volume_colors,
                showlegend=False
            ), row=2, col=1)
        
        # Update layout
        fig.update_layout(
            hovermode='x unified',
            template='plotly_white',
            height=600,
            xaxis_rangeslider_visible=False, # Disable slider to avoid "duplicate K-line" look
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            # Set default view range to last 3 months
            # xaxis=dict(...) removed from here
        )
        
        # Update axes
        fig.update_yaxes(title_text="價格 (元)", row=1, col=1)
        fig.update_yaxes(title_text="成交量 (張)", row=2, col=1)
        
        # Force X-axis Range on ALL axes (since shared)
        if start_view_date and last_date:
            range_dates = [start_view_date.strftime('%Y-%m-%d'), last_date.strftime('%Y-%m-%d')]
            fig.update_xaxes(
                range=range_dates, 
                autorange=False,
                rangebreaks=[dict(bounds=["sat", "mon"])], # Hide weekends
                title_text="日期",
                row=2, col=1
            )
            # Also apply to top chart to be safe, though shared_xaxes should handle it
            fig.update_xaxes(range=range_dates, autorange=False, rangebreaks=[dict(bounds=["sat", "mon"])], row=1, col=1)
        else:
             fig.update_xaxes(title_text="日期", row=2, col=1)
        
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        # ===========================================
        # ===========================================
        # Section 4: 輔助指標 (技術面細節)
        # ===========================================
        
        # MACD
        st.subheader("📊 MACD 動能指標")
        if all(col in display_data.columns for col in ['macd', 'macd_signal', 'macd_hist']):
            fig_macd = go.Figure()
            fig_macd.add_trace(go.Scatter(x=display_data['date'], y=display_data['macd'], mode='lines', name='MACD', line=dict(color='#1f77b4', width=2)))
            fig_macd.add_trace(go.Scatter(x=display_data['date'], y=display_data['macd_signal'], mode='lines', name='Signal', line=dict(color='#ff7f0e', width=2)))
            
            colors = ['#FF3B30' if val >= 0 else '#34C759' for val in display_data['macd_hist']]
            fig_macd.add_trace(go.Bar(x=display_data['date'], y=display_data['macd_hist'], name='Histogram', marker_color=colors, opacity=0.5))
            
            fig_macd.update_layout(
                xaxis_title="", yaxis_title="MACD", hovermode='x unified', template='plotly_white',
                height=300, showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            # Sync Range with Main Chart
            if start_view_date and last_date:
                range_dates = [start_view_date.strftime('%Y-%m-%d'), last_date.strftime('%Y-%m-%d')]
                fig_macd.update_xaxes(range=range_dates, autorange=False, rangebreaks=[dict(bounds=["sat", "mon"])])
            
            st.plotly_chart(fig_macd, use_container_width=True)

        # KD
        st.subheader("📉 KD 指標")
        if all(col in display_data.columns for col in ['k', 'd']):
            fig_kd = go.Figure()
            fig_kd.add_trace(go.Scatter(x=display_data['date'], y=display_data['k'], mode='lines', name='K值', line=dict(color='#1f77b4', width=2)))
            fig_kd.add_trace(go.Scatter(x=display_data['date'], y=display_data['d'], mode='lines', name='D值', line=dict(color='#ff7f0e', width=2)))
            
            fig_kd.add_hline(y=80, line_dash="dash", line_color="red", opacity=0.5, annotation_text="超買")
            fig_kd.add_hline(y=20, line_dash="dash", line_color="green", opacity=0.5, annotation_text="超賣")
            
            fig_kd.update_layout(
                xaxis_title="", yaxis_title="KD值", hovermode='x unified', template='plotly_white',
                height=300, showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            # Sync Range with Main Chart
            if start_view_date and last_date:
                range_dates = [start_view_date.strftime('%Y-%m-%d'), last_date.strftime('%Y-%m-%d')]
                fig_kd.update_xaxes(range=range_dates, autorange=False, rangebreaks=[dict(bounds=["sat", "mon"])])
            
            st.plotly_chart(fig_kd, use_container_width=True)
        
        st.markdown("---")
        
        # ===========================================
        # 5. 詳細分析報告 (Detail Text from Markdown)
        # ===========================================
        st.markdown("### 📝 詳細分析報告")
        
        report_path = Path("artifacts/analysis_report.md")
        report_found = False
        
        if report_path.exists():
            try:
                with open(report_path, 'r', encoding='utf-8') as f:
                    full_report = f.read()
                
                # Regex to find the specific stock section
                # Pattern looks for "## 個股：1141" until the next "---" or EOF
                import re
                pattern = rf"## 個股：{stock_id}.*?(?=\n---\n|\Z)"
                match = re.search(pattern, full_report, re.DOTALL)
                
                if match:
                    report_found = True
                    stock_report_md = match.group(0)
                    
                    # Parse sections using regex
                    # Looking for "### X) Title"
                    sections = {}
                    sec_pat = r"### (\d+\)) (.+?)\n(.*?)(?=\n### \d+\)|$)"
                    for m in re.finditer(sec_pat, stock_report_md, re.DOTALL):
                        sec_key = f"{m.group(1)} {m.group(2)}"
                        sections[sec_key] = m.group(3).strip()
                    
                    if sections:
                        # Row 1: TL;DR + Trading Advice
                        c1, c2 = st.columns(2)
                        with c1:
                            if "2) TL;DR（三行結論）" in sections:
                                st.markdown("#### 2) TL;DR（三行結論）")
                                st.markdown(sections["2) TL;DR（三行結論）"])
                        with c2:
                            if "3) 交易建議（數字版）" in sections:
                                st.markdown("#### 3) 交易建議（數字版）")
                                st.markdown(sections["3) 交易建議（數字版）"])
                        
                        st.markdown("---")
                        
                        # Row 2: Reasons + Conditions
                        c3, c4 = st.columns(2)
                        with c3:
                            if "4) 買入理由（數字＋白話）" in sections:
                                st.markdown("#### 4) 買入理由（數字＋白話）")
                                st.markdown(sections["4) 買入理由（數字＋白話）"])
                        with c4:
                            if "5) 觀察與否決條件" in sections:
                                st.markdown("#### 5) 觀察與否決條件")
                                st.markdown(sections["5) 觀察與否決條件"])
                        
                        st.markdown("---")
                        
                        # Row 3: Snapshot + Notes
                        c5, c6 = st.columns(2)
                        with c5:
                            if "6) 數據快照" in sections:
                                st.markdown("#### 6) 數據快照")
                                st.markdown(sections["6) 數據快照"])
                        with c6:
                             # Dummy slot for future notes or layout balance
                             pass
                                
                    else:
                        # Fallback if regex parsing fails but stock found
                        st.markdown(stock_report_md)
                        
            except Exception as e:
                st.error(f"Error parsing report: {e}")
        
        if not report_found:
             st.warning("⚠️ 尚未生成此股的詳細分析報告 (請確認 agent_b_ranking 是否已執行)")

        st.markdown("---")
        
        # ===========================================
        # Section 5: 投資指南（整合版）
        # ===========================================
        with st.expander("📚 投資指南（點擊展開）", expanded=False):
            st.markdown("### 🎯 完整投資決策流程")
            
            st.markdown("""
            #### 第一步：確認進場條件
            
            在考慮買入前，請確認以下**四個核心條件**：
            
            | 指標 | 條件 | 說明 |
            |------|------|------|
            | 🤖 AI 評分 | > 0.45 | 模型預測未來 10 天正報酬機率超過 45% |
            | 📊 均線位置 | 站上 MA20 | 股價在 20 日均線之上，中期趨勢偏多 |
            | 📈 RSI 指標 | < 70 | 尚未進入超買區，仍有上漲空間 |
            | 🔄 KD 動能 | 黃金交叉 | K 值向上穿越 D 值，短期買盤增強 |
            
            ✅ **建議**：至少符合 **3 項以上**再考慮進場，全部符合勝率最高。
            
            ---
            
            #### 第二步：辨識警示訊號
            
            以下情況**不建議進場**，或應考慮停損出場：
            
            - 🚫 **RSI > 80**：嚴重超買，短線回檔風險極高
            - 🚫 **跌破 MA20 + KD 死亡交叉**：多空轉換，趨勢轉弱
            - 🚫 **成交量萎縮**：缺乏資金動能，上漲不健康
            
            ---
            
            #### 第三步：理解關鍵技術訊號
            
            以下是常見技術訊號的**白話解釋**：
            
            """)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("""
                **價格突破類**
                - **突破 20 日高**  
                  最近一個月的最高價被超過，通常會有「慣性續漲」效應
                
                - **站上布林中軌**  
                  回到多頭範圍，若能站穩則趨勢轉強
                
                **均線交叉類**
                - **MA5 上穿 MA20**  
                  短期趨勢翻多，若 MA20 沒下彎，勝率更好
                
                - **MACD 黃金交叉**  
                  動能由負轉正,買盤力道增強
                
                **SMC 機構模型 (新增)**
                - **BOS (結構破壞)**  
                  價格突破關鍵的高/低點並站穩，代表大資金確認趨勢延續。
                
                - **CHoCH (特徵改變)**  
                  趨勢發生初步的反向訊號，通常是反轉的關鍵點。
                """)
            
            with col2:
                st.markdown("""
                **量能籌碼類**
                - **量能放大**  
                  上漲有人追價，比只有價格漲更健康
                
                - **法人連買**  
                  大資金偏多，通常有延續性（但也要看大盤）
                
                **超買超賣類**
                - **RSI > 70**  
                  超買，短線可能回檔
                
                - **RSI < 30**  
                  超賣，可能出現反彈機會
                """)
            
            st.markdown("---")
            
            st.markdown("""
            #### 第四步：執行紀律與風險管理
            
            - 💰 **分批建倉**：不要一次投入全部資金，建議分 2-3 次買入
            - ⏱️ **建議持有期**：10 天（根據回測數據）
            - 🛡️ **停損設定**：跌破 MA20 或虧損超過 5-8% 應考慮停損
            - 📊 **倉位控制**：單一股票不超過總資金的 10-15%
            
            """)
            
            st.warning("""
            **⚠️ 投資警語**
            
            本系統僅供參考，不構成投資建議。投資有風險，請謹慎評估自身風險承受能力。
            過去績效不代表未來表現。建議搭配基本面分析與市場環境判斷。
            """)
        
    except Exception as e:
        st.error(f"載入資料時發生錯誤: {e}")
        import traceback
        st.code(traceback.format_exc())

# ========================================
# 頁面 4: 系統資訊
# ========================================

def show_system_info():
    st.header("ℹ️ 系統資訊")
    
    st.markdown("""
    ### 📚 tw-top10 選股系統
    
    **版本**: v2.1.0-ml
    
    **核心功能**:
    - 🤖 LightGBM 分類模型 + Isotonic 機率校準
    - 🔍 SHAP 可解釋性（AI 推薦理由）
    - 📊 中長期波段策略（持有 10 天）
    - 🔄 每日自動執行 (22:00)
    - 🔧 每日自動重訓 (02:00)
    - 📈 PSI 漂移監控
    
    **適用客群**: 股市小白、無時間盯盤的中長期投資者
    
    ---
    
    ### 🎯 績效摘要
    - **正報酬勝率**: 67.0%
    - **平均報酬**: +5.33% (10天持有)
    - **回測期間**: 2025/01 ~ 2026/01
    
    ---
    
    ### 📞 使用說明
    
    1. **查看選股**: 點選「今日選股」頁面
    2. **追蹤績效**: 點選「歷史績效」頁面
    3. **監控模型**: 點選「PSI 監控」頁面
    
    ---
    
    ### 📋 系統日誌 (System Logs)
    
    """)
    
    # Data Audit Report (New)
    audit_path = Path("artifacts/training_audit.md")
    if audit_path.exists():
        with st.expander("📝 數據完整性與訓練審核報告", expanded=True):
            st.markdown(audit_path.read_text())
            st.info("💡 如果連續性評分低於 98%，系統會自動啟動補齊程序。")
    
    # Log Viewer Logic
    if st.button("🔄 重新整理日誌"):
        st.rerun()
        
    log_dir = Path("logs")
    if log_dir.exists():
        log_files = list(log_dir.glob("*.log"))
        if log_files:
            # Sort by modification time, newest first
            latest_log = max(log_files, key=lambda x: x.stat().st_mtime)
            
            st.caption(f"最新日誌檔案: `{latest_log.name}` (最後更新: {datetime.fromtimestamp(latest_log.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')})")
            
            try:
                # Read last 200 lines to avoid huge load
                with open(latest_log, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    last_lines = lines[-200:]
                    log_content = "".join(last_lines)
                    
                st.code(log_content, language="text")
            except Exception as e:
                st.error(f"讀取日誌失敗: {e}")
        else:
            st.info("暫無日誌檔案")
    else:
        st.info("Logs 目錄不存在")



# ========================================
# 執行主程式
# ========================================

if __name__ == "__main__":
    main()

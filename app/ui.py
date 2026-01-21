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
        
        # If stock analysis selected, show stock selector
        if page == "📈 個股分析":
            st.markdown("---")
            st.markdown("### 選擇股票")
            
            # Load top 10 for quick access
            df, _ = load_latest_ranking()
            if df is not None and not df.empty:
                stock_options = [f"{row['stock_id']} {row.get('stock_name', '')}" 
                                for _, row in df.head(10).iterrows()]
                selected = st.selectbox("Top 10 快選", stock_options)
                
                if selected:
                    stock_id = selected.split()[0]
                    stock_name = ' '.join(selected.split()[1:])
                    st.session_state['selected_stock'] = stock_id
                    st.session_state['selected_stock_name'] = stock_name
        
        st.markdown("---")
        st.markdown("### 系統狀態")
        st.success("✅ 自動化運作中")
        st.info(f"🕐 更新時間: {datetime.now().strftime('%H:%M')}")
    
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
        avg_prob = df['model_prob'].mean() if 'model_prob' in df.columns else 0
        st.metric("🎲 平均勝率", f"{avg_prob*100:.1f}%")
    
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

def show_analysis_report():
    st.header("📝 結構化分析報告")
    
    report_path = Path("artifacts/analysis_report.md")
    
    if not report_path.exists():
        st.warning("⚠️ 尚無分析報告，請先執行 `python app/agent_b_ranking.py`")
        return
    
    # 顯示報告生成時間
    import os
    mod_time = datetime.fromtimestamp(os.path.getmtime(report_path))
    st.info(f"📅 報告生成時間: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 讀取並顯示 Markdown 報告
    with open(report_path, 'r', encoding='utf-8') as f:
        report_content = f.read()
    
    st.markdown(report_content, unsafe_allow_html=True)

# ========================================
# 頁面: 個股詳細資訊
# ========================================

def show_stock_detail():
    # Back button
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("← 返回"):
            st.session_state['page'] = None
            st.rerun()
    
    stock_id = st.session_state.get('selected_stock', None)
    stock_name = st.session_state.get('selected_stock_name', '')
    
    if not stock_id:
        st.warning("⚠️ 請先在左側選擇股票")
        return
    
    st.title(f"📊 {stock_id} {stock_name}")
    st.markdown("---")
    
    # Load data
    try:
        features_df = pd.read_parquet("data/clean/features.parquet")
        stock_data = features_df[features_df['stock_id'] == str(stock_id)].copy()
        
        if stock_data.empty:
            st.error(f"❌ 找不到 {stock_id} 的歷史資料")
            return
        
        # Sort by date and get latest
        stock_data = stock_data.sort_values('date')
        latest = stock_data.iloc[-1]
        
        # Load ranking data to get AI reasons
        ranking_df, _ = load_latest_ranking()
        stock_ranking = ranking_df[ranking_df['stock_id'] == str(stock_id)]
        
        # ===========================================
        # Section 1: AI 為什麼推薦這支股票？(左欄) + 技術位置(右欄)
        # ===========================================
        col_left, col_right = st.columns([1, 1])
        
        with col_left:
            st.header("🤖 AI 推薦理由")
            
            if not stock_ranking.empty:
                row = stock_ranking.iloc[0]
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    score = row.get('final_score', 0)
                    st.metric("綜合評分", f"{score:.3f}", help="AI 模型綜合評分，越高表示潛力越大")
                with col2:
                    prob = row.get('model_prob', 0)
                    st.metric("AI 預測勝率", f"{prob*100:.1f}%", help="未來 10 天正報酬的機率")  
                with col3:
                    rank = ranking_df[ranking_df['stock_id'] == str(stock_id)].index[0] + 1
                    st.metric("排名", f"#{rank}", help="在今日所有股票中的排名")
                
                st.markdown("### 🔍 關鍵訊號解析")
                
                reasons = row.get('reasons', '')
                if reasons and '| AI:' in reasons:
                    ai_part = reasons.split('| AI:')[1].strip()
                    features = ai_part.split()
                    
                    # Parse and explain each signal
                    explanations = {
                        'volume_ratio_20d': {
                            'name': '📊 20日量能比',
                            'positive': '成交量明顯放大，資金開始關注',
                            'negative': '成交量萎縮，市場觀望氣氛濃厚'
                        },
                        'bb_width': {
                            'name': '📏 布林通道寬度',
                            'positive': '盤整後即將突破，波動度增加',
                            'negative': '處於盤整狀態，等待方向明朗'
                        },
                        'macd': {
                            'name': '📈 MACD 動能',
                            'positive': 'MACD 出現黃金交叉，短期趨勢轉強',
                            'negative': 'MACD 死亡交叉，短期趨勢轉弱'
                        },
                        'macd_signal': {
                            'name': '📊 MACD 訊號',
                            'positive': 'MACD 訊號線向上，動能增強',
                            'negative': 'MACD 訊號線向下，動能減弱'
                        },
                        'd': {
                            'name': '📉 KD-D 值',
                            'positive': 'KD 指標向上，短期有支撐',
                            'negative': 'KD 指標向下，短期承壓'
                        },
                        'k': {
                            'name': '📈 KD-K 值',
                            'positive': 'KD-K 值向上，買盤進場',
                            'negative': 'KD-K 值向下，賣壓出現'
                        },
                        'pct_from_low_60d': {
                            'name': '📌 相對 60 日低點',
                            'positive': '股價接近 60 日低點，潛在反彈機會',
                            'negative': '股價遠離 60 日低點'
                        },
                        'pct_from_high_60d': {
                            'name': '📌 相對 60 日高點',
                            'positive': '股價接近 60 日高點，突破在即',
                            'negative': '股價遠離 60 日高點'
                        },
                        'ma20': {
                            'name': '📊 20日均線',
                            'positive': '站上 20 日均線，中期趨勢轉多',
                            'negative': '跌破 20 日均線，中期趨勢轉空'
                        },
                        'rsi': {
                            'name': '📊 RSI 強弱指標',
                            'positive': 'RSI 向上，買盤力道增強',
                            'negative': 'RSI 向下，賣壓增加'
                        }
                    }
                    
                    for feat in features:
                        if '(' in feat and ')' in feat:
                            name = feat[:feat.index('(')]
                            value = feat[feat.index('(')+1:feat.index(')')]
                            
                            if name in explanations:
                                info = explanations[name]
                                is_positive = value.startswith('+')
                                
                                if is_positive:
                                    st.success(f"✅ **{info['name']}** _{value}_  \n{info['positive']}")
                                else:
                                    st.warning(f"⚠️ **{info['name']}** _{value}_  \n{info['negative']}")
            else:
                st.info("此股票不在今日 Top 10 推薦清單中")
        
        with col_right:
            st.header("📍 目前技術位置")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("收盤價", f"${latest['close']:.2f}")
            with col2:
                ma20 = latest.get('ma20', latest['close'])
                diff_ma20 = ((latest['close'] - ma20) / ma20 * 100) if ma20 > 0 else 0
                st.metric("MA20", f"${ma20:.2f}", f"{diff_ma20:+.1f}%")
            
            col3, col4 = st.columns(2)
            with col3:
                rsi = latest.get('rsi', 50)
                rsi_status = "超買" if rsi > 70 else ("超賣" if rsi < 30 else "中性")
                st.metric("RSI", f"{rsi:.1f}", rsi_status)
            with col4:
                k_val = latest.get('k', 50)
                d_val = latest.get('d', 50)
                kd_status = "黃金交叉" if k_val > d_val else "死亡交叉"
                st.metric("KD", f"K:{k_val:.1f} D:{d_val:.1f}", kd_status)
            
            # Position interpretation
            st.markdown("### 💡 技術面解讀")
            
            # MA20 position
            if latest['close'] > ma20:
                st.success("✅ **多頭格局** - 股價站上 20 日均線，中期趋勢偏多")
            else:
                st.error("⚠️ **空頭格局** - 股價跌破 20 日均線，中期趋勢偏空")
            
            # RSI interpretation
            if rsi > 70:
                st.warning("⚠️ **RSI 超買** - 短期漲多，注意回檔風險")
            elif rsi < 30:
                st.info("💎 **RSI 超賤** - 短期跌深，可能出現反彈")
            else:
                st.info(f"📊 **RSI 中性區** - 目前 RSI {rsi:.1f}，尚未過熱或過冷")
            
            # KD interpretation  
            if k_val > d_val and k_val > 50:
                st.success("✅ **KD 黃金交叉 + 強勢** - 短期買盤力道強")
            elif k_val < d_val and k_val < 50:
                st.error("⚠️ **KD 死亡交叉 + 弱勢** - 短期賣壓較重")

        
        st.markdown("---")
        
        # ===========================================
        # Section 3: 價格走勢圖 (K線 + 成交量)
        # ===========================================
        st.header("📈 價格走勢圖（近 60 天）")
        
        # Get last 60 days
        display_data = stock_data.tail(60).copy()
        
        # Create subplots: K-line on top, volume on bottom
        from plotly.subplots import make_subplots
        
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.7, 0.3],
            subplot_titles=('價格', '成交量')
        )
        
        # === Top subplot: Candlestick + MA + Bollinger ===
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
            xaxis_rangeslider_visible=False,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        # Update axes
        fig.update_yaxes(title_text="價格 (元)", row=1, col=1)
        fig.update_yaxes(title_text="成交量 (張)", row=2, col=1)
        fig.update_xaxes(title_text="日期", row=2, col=1)
        
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        # ===========================================
        # Section 4: 輔助指標（簡化版）
        # ===========================================
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 MACD 動能指標")
            
            if all(col in display_data.columns for col in ['macd', 'macd_signal', 'macd_hist']):
                fig_macd = go.Figure()
                
                fig_macd.add_trace(go.Scatter(
                    x=display_data['date'],
                    y=display_data['macd'],
                    mode='lines',
                    name='MACD',
                    line=dict(color='#1f77b4', width=2)
                ))
                
                fig_macd.add_trace(go.Scatter(
                    x=display_data['date'],
                    y=display_data['macd_signal'],
                    mode='lines',
                    name='Signal',
                    line=dict(color='#ff7f0e', width=2)
                ))
                
                colors = ['green' if val >= 0 else 'red' for val in display_data['macd_hist']]
                fig_macd.add_trace(go.Bar(
                    x=display_data['date'],
                    y=display_data['macd_hist'],
                    name='Histogram',
                    marker_color=colors,
                    opacity=0.5
                ))
                
                fig_macd.update_layout(
                    xaxis_title="",
                    yaxis_title="MACD",
                    hovermode='x unified',
                    template='plotly_white',
                    height=300,
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                
                st.plotly_chart(fig_macd, use_container_width=True)
        
        with col2:
            st.subheader("📉 KD 指標")
            
            if all(col in display_data.columns for col in ['k', 'd']):
                fig_kd = go.Figure()
                
                fig_kd.add_trace(go.Scatter(
                    x=display_data['date'],
                    y=display_data['k'],
                    mode='lines',
                    name='K值',
                    line=dict(color='#1f77b4', width=2)
                ))
                
                fig_kd.add_trace(go.Scatter(
                    x=display_data['date'],
                    y=display_data['d'],
                    mode='lines',
                    name='D值',
                    line=dict(color='#ff7f0e', width=2)
                ))
                
                fig_kd.add_hline(y=80, line_dash="dash", line_color="red", opacity=0.5, annotation_text="超買")
                fig_kd.add_hline(y=20, line_dash="dash", line_color="green", opacity=0.5, annotation_text="超賣")
                
                fig_kd.update_layout(
                    xaxis_title="",
                    yaxis_title="KD值",
                    hovermode='x unified',
                    template='plotly_white',
                    height=300,
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                
                st.plotly_chart(fig_kd, use_container_width=True)
        
        st.markdown("---")
        
        # ===========================================
        # Section 4.5: 結構化投資說明（移到圖表之後，兩欄式佈局）
        # ===========================================
        report_path = Path("artifacts/analysis_report.md")
        if report_path.exists():
            try:
                with open(report_path, 'r', encoding='utf-8') as f:
                    full_report = f.read()
                
                # 解析出該股票的報告區塊
                import re
                pattern = rf"## 個股：{stock_id}.*?(?=\n---\n|\Z)"
                match = re.search(pattern, full_report, re.DOTALL)
                
                if match:
                    stock_report = match.group(0)
                    
                    # 顯示標題
                    st.markdown("## 📋 投資說明書")
                    
                    # 解析報告的各個區塊
                    sections = {}
                    section_pattern = r"### (\d+\)) (.+?)\n(.*?)(?=\n### \d+\)|$)"
                    for section_match in re.finditer(section_pattern, stock_report, re.DOTALL):
                        section_num = section_match.group(1)
                        section_title = section_match.group(2)
                        section_content = section_match.group(3).strip()
                        sections[f"{section_num} {section_title}"] = section_content
                    
                    # 如果成功解析出區塊，用兩欄顯示
                    if sections:
                        # 第一行：TL;DR + 交易建議
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            if "2) TL;DR（三行結論）" in sections:
                                st.markdown("### 2) TL;DR（三行結論）")
                                st.markdown(sections["2) TL;DR（三行結論）"])
                        
                        with col2:
                            if "3) 交易建議（數字版）" in sections:
                                st.markdown("### 3) 交易建議（數字版）")
                                st.markdown(sections["3) 交易建議（數字版）"])
                        
                        st.markdown("---")
                        
                        # 第二行：買入理由 + 風險
                        col3, col4 = st.columns(2)
                        
                        with col3:
                            if "4) 買入理由（數字＋白話）" in sections:
                                st.markdown("### 4) 買入理由（數字＋白話）")
                                st.markdown(sections["4) 買入理由（數字＋白話）"])
                        
                        with col4:
                            if "5) 觀察與否決條件" in sections:
                                st.markdown("### 5) 觀察與否決條件")
                                st.markdown(sections["5) 觀察與否決條件"])
                        
                        st.markdown("---")
                        
                        # 第三行：數據快照（全寬）
                        if "6) 數據快照" in sections:
                            st.markdown("### 6) 數據快照")
                            st.markdown(sections["6) 數據快照"])
                        
                        # 教學角落不顯示（已整合到下方的參考建議）
                    else:
                        # 如果解析失敗，直接顯示原始報告
                        st.markdown(stock_report, unsafe_allow_html=True)
                        
            except Exception as e:
                st.warning(f"無法載入報告: {e}")
        
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
    
    詳細文件請參考: [docs/AUTOMATION.md](https://github.com/bluemaple18-home/stcoktop10)
    """)

# ========================================
# 執行主程式
# ========================================

if __name__ == "__main__":
    main()

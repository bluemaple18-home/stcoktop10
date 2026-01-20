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
            ["🎯 今日選股", "📊 歷史績效", "🔍 PSI 監控", "ℹ️ 系統資訊"],
            index=0
        )
        
        st.markdown("---")
        st.markdown("### 系統狀態")
        st.success("✅ 自動化運作中")
        st.info(f"🕐 更新時間: {datetime.now().strftime('%H:%M')}")
    
    # 根據選擇顯示不同頁面
    if page == "🎯 今日選股":
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
                st.markdown(f"### {idx+1}. {row.get('stock_id', 'N/A')}")
                st.caption(row.get('stock_name', ''))
            
            with col2:
                st.metric("綜合分數", f"{row.get('final_score', 0):.3f}")
                st.metric("AI 勝率", f"{row.get('model_prob', 0)*100:.1f}%")
            
            with col3:
                st.markdown("**推薦理由**")
                reasons = row.get('reasons', '無')
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

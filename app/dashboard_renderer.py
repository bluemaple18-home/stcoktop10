#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
面板渲染模組
將 Top10 清單渲染為靜態圖片（使用 matplotlib）
支援結構化理由（Chips 樣式）與統計彙總
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
from pathlib import Path
import pandas as pd
from datetime import datetime
from typing import List, Dict, Union
import ast
from collections import Counter

# 引用 reason_generator 的常數 (避免循環引用，直接定義)
TYPE_POSITIVE = "POSITIVE"
TYPE_CAUTION = "CAUTION"

def parse_reasons(reasons_data):
    """解析 reasons 資料，支援列表或字串"""
    if isinstance(reasons_data, list):
        # 檢查是否為結構化資料 (List[Dict])
        if reasons_data and isinstance(reasons_data[0], dict):
            return reasons_data
        # 舊版純字串列表，轉換為結構化
        return [{"type": TYPE_POSITIVE, "text": r} for r in reasons_data]
    
    if isinstance(reasons_data, str):
        try:
            # 嘗試解析字串表示的列表
            parsed = ast.literal_eval(reasons_data)
            return parse_reasons(parsed)
        except:
            return []
    return []

def draw_chip(ax, x, y, text, chip_type, fontsize=10):
    """
    繪製單個 Chip
    Returns: Chip 的寬度 (用於下一個 Chip 的定位)
    """
    # 設定顏色
    if chip_type == TYPE_CAUTION:
        # facecolor='#fff3cd', edgecolor='#ffecb5', textcolor='#856404' (Bootstrap warning)
        facecolor = '#fbe9e7' # 淺橘/灰
        edgecolor = '#ffccbc'
        textcolor = '#d84315'
    else: # TYPE_POSITIVE
        # facecolor='#d4edda', edgecolor='#c3e6cb', textcolor='#155724' (Bootstrap success)
        facecolor = '#e3f2fd' # 淺藍
        edgecolor = '#bbdefb'
        textcolor = '#0d47a1'

    # 計算文字寬度 (估算)
    # matplotlib 的 get_window_extent 需要 renderer，這裡用簡單估算
    # 每個字寬約 0.6 * fontsize (normalized coords) ? 不，這是 transform 之後的
    # 這裡 x, y 是 0-1 的軸座標。
    # 為了簡化，我們假設固定寬度或基於字數的簡單乘法
    
    # 更好的方法是使用 renderer，但比較複雜。
    # 採用字數估算：中文字寬約 0.012 (在 figure 寬度 16 inch 下)
    char_width = 0.012 * (16/16) # 調整係數 
    # 英文減半
    length = sum(1 for c in text if ord(c) > 127) + sum(0.6 for c in text if ord(c) <= 127)
    width = length * char_width + 0.02 # padding
    height = 0.035
    
    # 繪製圓角矩形
    # FancyBboxPatch 的座標系轉換比較麻煩，改用 Text 的 bbox 屬性
    # 但 bbox 不支援圓角 (直到最近版本)。
    # 我們使用 Annotation 的 bbox 參數，style='round'
    
    ann = ax.annotate(
        text, 
        xy=(x, y), 
        xytext=(0, 0), 
        textcoords='offset points',
        ha='left', 
        va='center',
        color=textcolor,
        fontsize=fontsize,
        weight='bold',
        bbox=dict(boxstyle='round,pad=0.3', fc=facecolor, ec=edgecolor, alpha=1.0)
    )
    
    return width + 0.01 # 回傳佔用寬度 + gap

def render_dashboard_to_image(df: pd.DataFrame, output_path: Path, date_str: str = None):
    """
    將 Top10 面板渲染為圖片
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    
    # 設定中文字體
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'Microsoft JhengHei', 'SimHei']
    plt.rcParams['axes.unicode_minus'] = False
    
    # 準備資料與統計
    processed_rows = []
    all_reasons_text = []
    
    for _, row in df.iterrows():
        # 優先使用 reasons_json，若無則 fallback 到 reasons
        if 'reasons_json' in row:
            reasons = parse_reasons(row['reasons_json'])
        else:
            reasons = parse_reasons(row.get('reasons', []))
        
        # 統計 (只統計文字)
        for r in reasons:
            all_reasons_text.append(r['text'])
            
        processed_rows.append({
            'stock_id': row['stock_id'],
            'stock_name': row['stock_name'],
            'exp_ret': row['expected_return_5d'],
            'win_rate': row['win_rate'],
            'reasons': reasons[:3] # 最多顯示 3 個
        })
        
    # 計算 Top3 觸發
    top_triggers = Counter(all_reasons_text).most_common(3)
    top_triggers_text = " | ".join([f"{t[0]} ({t[1]})" for t in top_triggers])
    if not top_triggers_text:
        top_triggers_text = "無顯著觸發"

    # 建立 figure
    # 增加高度以容納統計資訊
    fig = plt.figure(figsize=(16, 13), facecolor='white')
    
    # ===== 標題區域 =====
    # (0,0) rowspan=2
    ax_title = plt.subplot2grid((22, 1), (0, 0), rowspan=2)
    ax_title.axis('off')
    ax_title.text(
        0.5, 0.5, 
        f'📈 TW Top10 選股系統 - {date_str}',
        ha='center', va='center',
        fontsize=28, fontweight='bold',
        color='#2c3e50'
    )
    
    # ===== 摘要統計區域 =====
    # (2,0) rowspan=2 (增加高度)
    ax_summary = plt.subplot2grid((22, 1), (2, 0), rowspan=2)
    ax_summary.axis('off')
    
    avg_return = df['expected_return_5d'].mean()
    avg_winrate = df['win_rate'].mean()
    
    # 使用兩個區塊顯示
    # 左：基本統計
    ax_summary.text(
        0.3, 0.6,
        f'平均期望報酬: {avg_return:.2f}%  |  平均勝率: {avg_winrate:.1f}%  |  推薦數: {len(df)}',
        ha='center', va='center', fontsize=14, color='#34495e',
        bbox=dict(boxstyle='round,pad=0.5', fc='#ecf0f1', ec='#bdc3c7')
    )
    
    # 右/下：熱門觸發
    ax_summary.text(
        0.5, 0.2,
        f'🔥 本日熱門觸發: {top_triggers_text}',
        ha='center', va='center', fontsize=14, color='#c0392b', fontweight='bold'
    )
    
    # ===== 表格區域 (手動繪製) =====
    # 從第 5 行開始
    ax_table = plt.subplot2grid((22, 1), (5, 0), rowspan=16)
    ax_table.axis('off')
    ax_table.set_xlim(0, 1)
    ax_table.set_ylim(0, 1) # y 軸向下為負? 不，正常是向上。我們從上往下畫
    # 為了方便，我們 map 列索引到 y 座標：y = 1 - (row_index * row_height)
    
    # 定義欄位寬度與位置
    # 排名(0.08), 代號/名稱(0.15), 報酬(0.12), 勝率(0.10), 理由(0.55)
    cols_x = {
        'rank': 0.04,
        'stock': 0.15,
        'ret': 0.30,
        'win': 0.42,
        'reason': 0.50 
    }
    
    header_height = 0.08
    row_height = 0.085 # 稍微加高以容納 Chips
    
    # 繪製標題列
    y_header = 0.95
    # 背景
    rect = mpatches.Rectangle((0, y_header - header_height/2), 1, header_height, color='#3498db', ec=None)
    ax_table.add_patch(rect)
    
    headers = [
        ('rank', '排名'), ('stock', '股票代號/名稱'), 
        ('ret', '5日期望報酬'), ('win', '勝率'), 
        ('reason', '推薦理由 (Top 3)')
    ]
    
    for key, text in headers:
        ax_table.text(
            cols_x[key], y_header, text, 
            ha='center' if key != 'reason' else 'left', 
            va='center', color='white', weight='bold', fontsize=12
        )
        
    # 繪製資料列
    y_curr = y_header - header_height
    
    for i, item in enumerate(processed_rows):
        # 斑馬紋背景
        bg_color = '#ecf0f1' if (i + 1) % 2 == 0 else 'white'
        rect = mpatches.Rectangle((0, y_curr - row_height/2), 1, row_height, color=bg_color, ec=None)
        ax_table.add_patch(rect)
        
        # 排名 (特殊顏色背景)
        rank = i + 1
        rank_color = 'white' # 預設透明/白
        rank_text_color = 'black'
        if rank == 1: rank_color = '#ffd700'; rank_text_color='white'
        elif rank == 2: rank_color = '#c0c0c0'; rank_text_color='white'
        elif rank == 3: rank_color = '#cd7f32'; rank_text_color='white'
        
        if rank <= 3:
            # 畫圓形或方塊作為排名背景
            circle = mpatches.Circle((cols_x['rank'], y_curr), 0.025, color=rank_color, zorder=2)
            ax_table.add_patch(circle)
        
        ax_table.text(
            cols_x['rank'], y_curr, str(rank),
            ha='center', va='center', weight='bold', color=rank_text_color, zorder=3
        )
        
        # 股票代號/名稱
        ax_table.text(
            cols_x['stock'], y_curr, f"{item['stock_id']}\n{item['stock_name']}",
            ha='center', va='center', fontsize=11, linespacing=1.4
        )
        
        # 報酬
        ret_val = item['exp_ret']
        ret_color = '#d35400' if ret_val >= 3 else 'black'
        ax_table.text(
            cols_x['ret'], y_curr, f"{ret_val:.2f}%",
            ha='center', va='center', fontsize=11, weight='bold', color=ret_color
        )
        
        # 勝率
        win_val = item['win_rate']
        win_color = '#27ae60' if win_val >= 70 else 'black'
        ax_table.text(
            cols_x['win'], y_curr, f"{win_val:.1f}%",
            ha='center', va='center', fontsize=11, color=win_color
        )
        
        # 推薦理由 (Chips)
        chip_x = cols_x['reason']
        for reason in item['reasons']:
            # 檢查理由類型
            r_type = reason.get('type', TYPE_POSITIVE)
            r_text = reason.get('text', str(reason))
            
            w = draw_chip(ax_table, chip_x, y_curr, r_text, r_type, fontsize=10)
            chip_x += w # 移動 x 座標
            
            # 若超過邊界則停止 (簡單處理)
            if chip_x > 0.98: break
            
        y_curr -= row_height
        
    # ===== 頁尾區域 =====
    ax_footer = plt.subplot2grid((22, 1), (21, 0), rowspan=1)
    ax_footer.axis('off')
    ax_footer.text(
        0.5, 0.5,
        '⚠️ 本系統產生的選股結果僅供參考，不構成投資建議。投資有風險，請謹慎評估。',
        ha='center', va='center',
        fontsize=10, color='#7f8c8d', style='italic'
    )
    
    # 儲存圖片
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    
    print(f"✅ 面板截圖已儲存 (Chips v2): {output_path}")

def render_simple_summary(df: pd.DataFrame, output_path: Path):
    """
    渲染簡單的文字摘要
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write(f"TW Top10 選股系統 - {datetime.now().strftime('%Y-%m-%d')}\n")
        f.write("=" * 60 + "\n\n")
        
        for idx, row in df.iterrows():
            rank = idx + 1
            f.write(f"【第 {rank} 名】{row['stock_id']} {row['stock_name']}\n")
            f.write(f"  期望報酬: {row['expected_return_5d']:.2f}%\n")
            f.write(f"  勝率: {row['win_rate']:.1f}%\n")
            
            # 處理 reasons，可能是結構化或字串
            if 'reasons_json' in row:
                reasons = parse_reasons(row['reasons_json'])
                text_reasons = [r['text'] for r in reasons]
            else:
                raw = row.get('reasons', [])
                if isinstance(raw, str):
                    try: raw = ast.literal_eval(raw)
                    except: raw = []
                text_reasons = raw
                
            if text_reasons:
                f.write(f"  推薦理由:\n")
                for r in text_reasons:
                    f.write(f"    • {r}\n")
            f.write("\n")
        
        f.write("=" * 60 + "\n")
        f.write("⚠️ 本系統產生的選股結果僅供參考，不構成投資建議。\n")
    
    print(f"✅ 文字摘要已儲存: {output_path}")

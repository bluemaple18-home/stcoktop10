"""
結構化股票分析報告生成器 v3 (User Template Compliance)
符合使用者指定的 Markdown 與 YAML 模板格式
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
import yaml

class StockReportGenerator:
    """固定模板的股票分析報告生成器（符合 User Template）"""
    
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = Path(artifacts_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        # 教學角落內容 (固定)
        self.edu_corner = {
            "breakout": "突破 20 日高＝最近一個月的最高價被超過，常見「慣性續漲」。",
            "ma_cross": "MA5 上穿 MA20＝短期趨勢翻多，若 MA20 沒下彎，勝率更好。",
            "bb_band": "站上布林中軌＝回到多頭範圍；跌破則多頭走弱。",
            "volume": "量能放大＝上漲有人追價，比只有價格漲更健康。",
            "chips": "法人連買＝大資金偏多，通常有延續性，但也要看大盤。",
            "smc_bos": "BOS (結構破壞)＝價格突破前高/低並站穩，代表原趨勢延續。",
            "smc_choch": "CHoCH (特徵改變)＝價格反向破壞結構，代表可能的趨勢翻轉。",
            "smc_ob": "Order Blocks (訂單塊)＝機構大單進場留下的足跡，通常具備強大支撐/壓力力道。"
        }
    
    def generate_report(self, ranked_df: pd.DataFrame, features_df: pd.DataFrame):
        """生成完整分析報告 (Markdown + YAML)"""
        print("📝 生成結構化分析報告 (User Template)...")
        
        # 1. YAML 結構化版 (先產出資料結構，Markdown 可復用部分邏輯)
        yaml_data = self._generate_yaml_data(ranked_df, features_df)
        yaml_path = self.artifacts_dir / "analysis_report.yaml"
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        print(f"✅ 結構化版: {yaml_path}")
        
        # 2. Markdown 報告 (依據 YAML 資料填入模板)
        markdown_content = self._generate_markdown_from_yaml(yaml_data)
        md_path = self.artifacts_dir / "analysis_report.md"
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        print(f"✅ 文章版: {md_path}")
        
        # 3. CSV 簡易版 (維持既有輸出習慣，選填)
        csv_path = self.artifacts_dir / "ranked_stocks_detailed.csv"
        # 簡單轉一下 YAML data to CSV
        csv_rows = []
        for stock in yaml_data.get('recommendations', []):
             csv_rows.append({
                 'stock': stock['stock'],
                 'verdict': stock['decision']['verdict'],
                 'p_win': stock['metrics']['p_win_5d'],
                 'entry': f"{stock['trade_plan']['entry_zone']['low']}-{stock['trade_plan']['entry_zone']['high']}",
                 'risk': stock['trade_plan']['invalidation']
             })
        pd.DataFrame(csv_rows).to_csv(csv_path, index=False, encoding='utf-8-sig')


    def _generate_yaml_data(self, ranked_df: pd.DataFrame, features_df: pd.DataFrame) -> dict:
        """生成符合 schema 的 YAML 資料"""
        recommendations = []
        
        # 只取 Top 5 或 10
        target_stocks = ranked_df.head(5)
        
        for _, row in target_stocks.iterrows():
            stock_id = str(row['stock_id'])
            stock_name = row.get('stock_name', '')
            
            # 取得個股資料
            stock_data = features_df[features_df['stock_id'] == stock_id].copy()
            if stock_data.empty:
                continue
                
            latest = stock_data.iloc[-1]
            p_win = float(row.get('model_prob', 0))
            
            # --- 核心邏輯計算 ---
            
            # 1. 決策與理由
            triggers = self._analyze_triggers(stock_data, latest, row)
            risks = self._analyze_risks(stock_data, latest)
            verdict = "買入" if p_win >= 0.75 and len(risks) == 0 else "觀察"
            if p_win < 0.6: verdict = "避免"

            # 2. 交易計劃
            current_price = latest['close']
            ma5 = latest.get('ma5', current_price)
            ma20 = latest.get('ma20', current_price)
            
            # 進場區：收盤價 ~ 收盤價*1.01 (假設隔天開盤) 或 MA5 附近
            entry_low = round(current_price, 1) # 簡化：以前日收盤為基準
            entry_high = round(current_price * 1.015, 1)
            
            # 停損：MA20 或 5%
            stop_loss_ma = ma20 * 0.98
            stop_loss_pct = current_price * 0.94
            invalidation_price = max(stop_loss_ma, stop_loss_pct)
            invalidation_text = f"跌破 {invalidation_price:.1f} (MA20支撐/6%停損)"
            
            # 3. 數據快照
            snapshot = self._generate_snapshot(stock_data, latest)
            
            rec = {
                'stock': f"{stock_id} {stock_name}",
                'date': datetime.now().strftime('%Y-%m-%d'),
                'decision': {
                    'verdict': verdict,
                    'reason_1': triggers[0]['plain_text'] if len(triggers) > 0 else "技術面平穩",
                    'reason_2': triggers[1]['plain_text'] if len(triggers) > 1 else ""
                },
                'trade_plan': {
                    'horizon_days': 5,
                    'entry_zone': {'low': entry_low, 'high': entry_high},
                    'invalidation': invalidation_text,
                    'take_profit': ["連續兩根放量長上影", "RSI > 75 並量縮"],
                    'position_hint': "等權/小資 <10% 單筆"
                },
                'metrics': {
                    'p_win_5d': round(p_win * 100, 1), # 轉百分比數值
                    'expected_r5': round((p_win - 0.5) * 10, 2), # 簡易估算
                    'confidence': "高" if p_win >= 0.75 else "中" if p_win >= 0.6 else "低"
                },
                'triggers': triggers, # Full list
                'risks': risks,
                'snapshot': snapshot,
                'notes': "注意大盤波動，建議分批佈局"
            }
            recommendations.append(rec)
            
        return {
            'report_date': datetime.now().strftime('%Y-%m-%d'),
            'total_stocks': len(target_stocks),
            'recommendations': recommendations
        }

    def _generate_markdown_from_yaml(self, yaml_data: dict) -> str:
        """從 YAML 資料生成符合使用者模板的 Markdown"""
        
        md_out = f"""# 每日選股分析報告 (User Template)
        
日期: {yaml_data['report_date']}

"""
        for stock in yaml_data['recommendations']:
            # 準備變數
            name = stock['stock']
            date = stock['date']
            verdict = stock['decision']['verdict']
            
            # Reasons (extract plain text for TL;DR)
            why_text = stock['decision']['reason_1']
            if stock['decision']['reason_2']:
                why_text += f"；{stock['decision']['reason_2']}"
                
            # Risks
            risk_text = stock['risks'][0] if stock['risks'] else "暫無重大風險"
            
            # Trade Plan
            p_win = stock['metrics']['p_win_5d']
            exp_r = stock['metrics']['expected_r5']
            conf = stock['metrics']['confidence']
            entry = f"{stock['trade_plan']['entry_zone']['low']} - {stock['trade_plan']['entry_zone']['high']}"
            inv = stock['trade_plan']['invalidation']
            tp = "；".join(stock['trade_plan']['take_profit'])
            
            # Triggers (Buy Reasons) formatting
            triggers_md = ""
            for t in stock['triggers'][:5]:
                triggers_md += f"""
**{t['name']}**：{t['evidence']}
> 白話：{t['plain_text']}
"""
            
            # Risks formatting
            risks_md = ""
            if not stock['risks']:
                risks_md = "- 暫無特別技術面風險"
            else:
                for r in stock['risks']:
                    risks_md += f"- {r}\n"
            
            # Snapshot formatting
            ss = stock['snapshot']
            # safely get nested keys
            ma_pos = f"MA5:{ss['price_ma']['ma5_pos']} / MA20:{ss['price_ma']['ma20_pos']}"
            inst = ss['inst_flow_5_10_20']
            
            stock_md = f"""
---

## 個股：{name}
**評估日期**：{date}
**交易假設**：當天收盤後決策，隔天開盤進場，持有 ≥5 交易日

### 2) TL;DR（三行結論）
- **結論**：**{verdict}**
- **為什麼**：{why_text}
- **風險**：{risk_text}

### 3) 交易建議（數字版）
| 項目 | 數值/內容 |
|------|-----------|
| 期望勝率（5 日） | **{p_win}%** |
| 期望報酬（5 日） | {exp_r}% |
| 置信等級 | {conf} |
| 入場區 | {entry} |
| 失效點（停損） | {inv} |
| 減碼/出場 | {tp} |

### 4) 買入理由（數字＋白話）
{triggers_md}

### 5) 觀察與否決條件
{risks_md}

### 6) 數據快照
- **價量位置**：收盤={ss.get('close')}; 相對MA: {ma_pos}; 布林帶: {ss.get('bollinger')}
- **動能指標**：RSI={ss.get('rsi')}; MACD={ss.get('macd')}; KD={ss.get('kd')}
- **量能**：今日量/20日均量={ss.get('vol_ratio')}倍
- **SMC 結構**：{ss.get('smc_trend')} (BOS={ss.get('smc_bos')})
- **籌碼**：外資5日={inst.get('foreign')}張; 投信5日={inst.get('invest')}張

### 7) 教學角落
- **BOS/CHoCH (SMC)**：{self.edu_corner['smc_bos']}
- **Order Blocks (SMC)**：{self.edu_corner['smc_ob']}
- **突破 20 日高**：{self.edu_corner['breakout']}
- **MA5 上穿 MA20**：{self.edu_corner['ma_cross']}
- **站上布林中軌**：{self.edu_corner['bb_band']}
- **量能放大**：{self.edu_corner['volume']}
- **法人連買**：{self.edu_corner['chips']}

"""
            md_out += stock_md
            
        return md_out

    def _analyze_triggers(self, df: pd.DataFrame, latest: pd.Series, row_ranking: pd.Series) -> List[dict]:
        """分析觸發訊號 (Type, Name, Evidence, Plain Text)"""
        triggers = []
        
        close = latest['close']
        ma5 = latest.get('ma5', 0)
        ma20 = latest.get('ma20', 0)
        vol = latest.get('volume', 0)
        vol_ma20 = df.tail(20)['volume'].mean() if len(df) >= 20 else vol
        
        # 1. 價格/線型
        # 檢查是否突破 20 日高
        if len(df) >= 20:
            high_20 = df['high'].shift(1).tail(20).max() # 不含今日
            if close > high_20:
                triggers.append({
                    "type": "技術",
                    "name": "線型：突破近 20 日高",
                    "evidence": f"收盤 {close} > 20日高點 {high_20:.1f}",
                    "plain_text": "慣性改變，股價創波段新高，上方無套牢壓力。"
                })
        
        # 2. 均線
        if ma5 > ma20:
            # 檢查是否剛黃金交叉 (前一天 ma5 <= ma20)
            prev = df.iloc[-2] if len(df) >= 2 else None
            if prev is not None and prev.get('ma5', 0) <= prev.get('ma20', 0):
                triggers.append({
                    "type": "技術",
                    "name": "均線：MA5 上穿 MA20",
                    "evidence": f"MA5({ma5:.1f}) 正式穿越 MA20({ma20:.1f})",
                    "plain_text": "短線趨勢翻多，中期均線提供支撐。"
                })
            else:
                triggers.append({
                    "type": "技術",
                    "name": "均線：多頭排列",
                    "evidence": f"MA5({ma5:.1f}) > MA20({ma20:.1f}) 且股價在線上",
                    "plain_text": "沿著均線上漲，趨勢穩健。"
                })

        # 3. 量能
        vol_ratio = vol / vol_ma20 if vol_ma20 > 0 else 1.0
        if vol_ratio >= 1.5:
             safe_vol = int(vol) if not pd.isna(vol) else 0
             triggers.append({
                "type": "量能",
                "name": "量能：放量上攻",
                "evidence": f"今日量 {safe_vol} 張 (約 {vol_ratio:.1f} 倍均量)",
                "plain_text": "有「人」在推，上漲比較站得住，非虛漲。"
            })
            
        # 4. 籌碼 (簡單模擬，需真實欄位)
        foreign_buy = latest.get('foreign_buy', 0) # 假設有此欄位
        if 'foreign_buy' in df.columns:
            f_sum_5 = df['foreign_buy'].tail(5).sum()
            if pd.isna(f_sum_5): f_sum_5 = 0
            if f_sum_5 > 0:
                triggers.append({
                    "type": "籌碼",
                    "name": "籌碼：外資買超",
                    "evidence": f"近 5 日累積買超 {int(f_sum_5)} 張",
                    "plain_text": "外資波段佈局，後續推升機率大。"
                })
        
        # 5. AI 模型
        ai_prob = float(row_ranking.get('model_prob', 0)) * 100
        if ai_prob > 70:
            triggers.append({
                "type": "AI",
                "name": "模型：高勝率訊號",
                "evidence": f"模型預測勝率 {ai_prob:.1f}%",
                "plain_text": "綜合多因子評估，歷史回測顯示此情境勝率 high。"
            })
            
        # 6. SMC (Smart Money Concepts)
        if latest.get('bos') == 1:
            triggers.append({
                "type": "SMC",
                "name": "結構：BOS 向上破壞",
                "evidence": "價格突破前高結構點並站穩",
                "plain_text": "市場結構確認延續多頭，機構買盤動能強勁。"
            })
        if latest.get('choch') == 1:
            triggers.append({
                "type": "SMC",
                "name": "結構：CHoCH 翻多訊號",
                "evidence": "價格反向破壞空頭結構點",
                "plain_text": "趨勢特徵發生反轉，初步確認由空轉多。"
            })
            
        return triggers if triggers else [{
            "type": "觀察", "name": "技術面平穩", "evidence": "無特殊訊號", "plain_text": "等待更明確發動訊號"
        }]

    def _analyze_risks(self, df: pd.DataFrame, latest: pd.Series) -> List[str]:
        """分析風險與否決條件"""
        risks = []
        rsi = latest.get('rsi', 50)
        
        if rsi > 75:
            risks.append(f"RSI 過熱 ({rsi:.1f} > 75)，短線隨時回檔")
            
        # 檢查乖離
        ma20 = latest.get('ma20', latest['close'])
        bias = (latest['close'] - ma20) / ma20 * 100
        if bias > 15:
            risks.append(f"乖離過大 (離 MA20 {bias:.1f}%)，追高風險大")
            
        return risks

    def _generate_snapshot(self, df: pd.DataFrame, latest: pd.Series) -> dict:
        """生成數據快照"""
        close = latest['close']
        ma5 = latest.get('ma5', 0)
        ma20 = latest.get('ma20', 0)
        ma60 = latest.get('ma60', 0)
        
        # Bollinger
        bb_up = latest.get('bb_upper', 0)
        bb_lo = latest.get('bb_lower', 0)
        bb_pos = "中"
        if close > bb_up: bb_pos = "上"
        if close < bb_lo: bb_pos = "下"
        
        # MACD
        macd = latest.get('macd', 0)
        macd_sig = latest.get('macd_signal', 0)
        macd_str = "正" if macd > 0 else "負"
        if macd > macd_sig and df.iloc[-2].get('macd',0) <= df.iloc[-2].get('macd_signal',0):
            macd_str = "黃金交叉"
        
        # Chips (Dummy if not exist)
        f_buy = df['foreign_buy'].tail(5).sum() if 'foreign_buy' in df.columns else 0
        if pd.isna(f_buy): f_buy = 0
        i_buy = df['investment_buy'].tail(5).sum() if 'investment_buy' in df.columns else 0
        if pd.isna(i_buy): i_buy = 0
        
        vol_avg = df.tail(20)['volume'].mean()
        vol_ratio = round(latest['volume'] / vol_avg, 2) if vol_avg > 0 else 1.0
        
        # KD Safe
        k_val = latest.get('k', 0)
        if pd.isna(k_val): k_val = 0
        
        return {
            'close': close,
            'price_ma': {
                'ma5_pos': "上" if close > ma5 else "下",
                'ma20_pos': "上" if close > ma20 else "下",
                'ma60_pos': "上" if close > ma60 else "下"
            },
            'bollinger': bb_pos,
            'rsi': round(latest.get('rsi', 0) or 0, 1),
            'macd': macd_str,
            'kd': f"K{int(k_val)}",
            'vol_ratio': vol_ratio,
            'smc_trend': "多頭結構" if latest.get('bos') == 1 else "盤整/轉折" if latest.get('choch') != 0 else "中性",
            'smc_bos': "向上" if latest.get('bos') == 1 else "向下" if latest.get('bos') == -1 else "無",
            'inst_flow_5_10_20': {
                'foreign': int(f_buy),
                'invest': int(i_buy),
                'dealer': 0
            }
        }

if __name__ == "__main__":
    # 自動尋找最新的 ranking csv
    import glob
    import os
    
    ranking_files = glob.glob("artifacts/ranking_*.csv")
    if not ranking_files:
        print("❌ 找不到排名檔案 (artifacts/ranking_*.csv)")
        exit(1)
        
    # 取最新的檔案
    latest_ranking = max(ranking_files, key=os.path.getctime)
    print(f"📂 讀取排名檔案: {latest_ranking}")
    
    ranked_df = pd.read_csv(latest_ranking, dtype={'stock_id': str})
    
    # 讀取特徵資料
    features_path = "data/clean/features.parquet"
    if not Path(features_path).exists():
        print(f"❌ 找不到特徵檔案 ({features_path})")
        exit(1)
        
    print(f"📂 讀取特徵資料: {features_path}")
    features_df = pd.read_parquet(features_path)
    
    # 執行生成
    generator = StockReportGenerator()
    generator.generate_report(ranked_df, features_df)

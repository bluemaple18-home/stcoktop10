#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent B - 主程式
統籌執行模型訓練、每日排名與回測報告
"""

import sys
from pathlib import Path
from datetime import datetime
import argparse

# 加入 app 目錄至路徑
sys.path.insert(0, str(Path(__file__).parent / "app"))

from agent_b_modeling import LightGBMTrainer
from agent_b_ranking import StockRanker
from agent_b_backtest import BacktestReporter


def check_data_availability(data_dir: Path = Path("data/clean")) -> bool:
    """
    檢查今日資料是否存在
    
    Args:
        data_dir: 資料目錄
        
    Returns:
        True 表示資料存在
    """
    features_path = data_dir / "features.parquet"
    universe_path = data_dir / "universe.parquet"
    
    if not features_path.exists():
        print(f"❌ 特徵檔案不存在: {features_path}")
        return False
    
    if not universe_path.exists():
        print(f"❌ Universe 檔案不存在: {universe_path}")
        return False
    
    print("✓ 資料檔案檢查通過")
    return True


def write_skip_log(reason: str, log_dir: Path = Path("artifacts")):
    """
    寫入 Skip 記錄
    
    Args:
        reason: 跳過原因
        log_dir: 記錄目錄
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "agent_b_skip_log.txt"
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] {reason}\n")
    
    print(f"📝 Skip 記錄已寫入: {log_file}")


def run_training(force: bool = False):
    """
    執行模型訓練（每週或強制執行）
    
    Args:
        force: 是否強制訓練
    """
    print("\n" + "=" * 60)
    print("🔬 模型訓練模組")
    print("=" * 60)
    
    # 檢查是否需要訓練
    model_path = Path("models/latest_lgbm.pkl")
    
    if not force and model_path.exists():
        # 檢查模型更新時間
        model_mtime = datetime.fromtimestamp(model_path.stat().st_mtime)
        days_since_update = (datetime.now() - model_mtime).days
        
        if days_since_update < 7:
            print(f"⏭ 模型於 {days_since_update} 天前更新，跳過訓練")
            print(f"   (模型路徑: {model_path})")
            return
    
    # 執行訓練
    try:
        from app.agent_b_modeling import main as train_main
        train_main()
        print("✅ 模型訓練完成")
    except Exception as e:
        print(f"❌ 模型訓練失敗: {e}")
        raise


def run_ranking():
    """執行每日排名"""
    print("\n" + "=" * 60)
    print("🏆 每日排名模組")
    print("=" * 60)
    
    try:
        from app.agent_b_ranking import main as ranking_main
        ranking_main()
        print("✅ 每日排名完成")
    except Exception as e:
        print(f"❌ 每日排名失敗: {e}")
        raise


def run_backtest():
    """執行回測報告"""
    print("\n" + "=" * 60)
    print("📊 回測報告模組")
    print("=" * 60)
    
    try:
        from app.agent_b_backtest import main as backtest_main
        backtest_main()
        print("✅ 回測報告完成")
    except Exception as e:
        print(f"❌ 回測報告失敗: {e}")
        # 回測失敗不影響主流程
        print("⚠️ 回測報告產生失敗，但不影響排名結果")


def main():
    """主程式進入點"""
    parser = argparse.ArgumentParser(description="Agent B - 模型訓練與排名系統")
    parser.add_argument("--train", action="store_true", help="強制執行模型訓練")
    parser.add_argument("--rank-only", action="store_true", help="僅執行排名（跳過訓練）")
    parser.add_argument("--backtest-only", action="store_true", help="僅執行回測報告")
    args = parser.parse_args()
    
    print("=" * 60)
    print("🤖 Agent B｜模型與排名（5日預測＋Top10）")
    print("=" * 60)
    print(f"執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 1. 檢查資料可用性
    if not check_data_availability():
        print("\n❌ 今日資料不可用，無法執行")
        write_skip_log("資料檔案不存在（Agent A 未完成）")
        return 1
    
    try:
        # 2. 模型訓練（每週或強制）
        if args.backtest_only:
            print("⏭ 跳過訓練與排名，僅執行回測")
        elif not args.rank_only:
            run_training(force=args.train)
        
        # 3. 每日排名
        if not args.backtest_only:
            run_ranking()
        
        # 4. 回測報告
        run_backtest()
        
        print("\n" + "=" * 60)
        print("✅ Agent B 執行完成！")
        print("=" * 60)
        
        # 顯示產出檔案
        print("\n📁 產出檔案:")
        artifacts_dir = Path("artifacts")
        if artifacts_dir.exists():
            for file in sorted(artifacts_dir.glob("*")):
                print(f"  - {file}")
        
        return 0
        
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ Agent B 執行失敗: {e}")
        print("=" * 60)
        write_skip_log(f"執行失敗: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

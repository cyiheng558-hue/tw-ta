# -*- coding: utf-8 -*-
"""訊號回測引擎(接近實戰版)。

採「同時間只持有一個部位」的事件式回測:
  逐根 K 棒,空手時若訊號觸發 → 隔日開盤/收盤進場;
  進場後每日檢查是否觸及停損/停利,否則持有到 N 日後出場。
  每筆交易扣手續費(買+賣)與證交稅(賣),串成權益曲線,算總報酬與最大回撤,
  並與同期 0050(大盤 ETF)買進持有比較。

⚠ 歷史統計僅供參考,不代表未來;真實交易還有滑價、流動性、跳空等風險。
"""
import numpy as np
import pandas as pd

from indicators import enrich, atr
from signals import BACKTESTABLE

# 預設交易成本(可調):手續費單邊 0.1425%,證交稅賣出 0.3%
FEE_RATE = 0.001425
TAX_RATE = 0.003


def _max_drawdown(equity: np.ndarray) -> float:
    """最大回撤(%),輸入為權益序列。"""
    if len(equity) == 0:
        return 0.0
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    return float(dd.min() * 100)


def backtest_signal(df: pd.DataFrame, signal_key: str, hold_days: int = 5,
                    stop_loss: float = None, take_profit: float = None,
                    fee: float = FEE_RATE, tax: float = TAX_RATE,
                    min_bars: int = 60) -> dict:
    """事件式回測單一訊號。

    stop_loss / take_profit 為百分比(如 5 代表 5%),None 表示不啟用。
    回傳含交易明細、勝率、淨報酬、最大回撤、權益曲線的 dict。
    """
    if signal_key not in BACKTESTABLE:
        raise ValueError(f"未知訊號 {signal_key}")
    name, fn = BACKTESTABLE[signal_key]
    e = enrich(df)
    n = len(e)
    closes = e["Close"].values
    highs = e["High"].values
    lows = e["Low"].values
    dates = e.index

    trades = []
    i = min_bars
    while i < n - 1:
        window = e.iloc[: i + 1]
        triggered = False
        try:
            triggered = fn(window)
        except Exception:
            triggered = False
        if not triggered:
            i += 1
            continue

        entry_price = closes[i + 1]  # 隔日收盤進場
        entry_date = dates[i + 1]
        exit_price = None
        exit_reason = "持有到期"
        exit_idx = min(i + hold_days, n - 1)

        for j in range(i + 2, min(i + 1 + hold_days, n)):
            if stop_loss is not None and lows[j] <= entry_price * (1 - stop_loss / 100):
                exit_price = entry_price * (1 - stop_loss / 100)
                exit_reason = "停損"
                exit_idx = j
                break
            if take_profit is not None and highs[j] >= entry_price * (1 + take_profit / 100):
                exit_price = entry_price * (1 + take_profit / 100)
                exit_reason = "停利"
                exit_idx = j
                break
        if exit_price is None:
            exit_price = closes[exit_idx]

        # 淨報酬(扣成本):買付手續費、賣付手續費+稅
        gross = exit_price / entry_price
        net = gross * (1 - fee) * (1 - fee - tax) - 1
        trades.append({
            "進場日": str(entry_date.date()), "進場價": round(float(entry_price), 2),
            "出場日": str(dates[exit_idx].date()), "出場價": round(float(exit_price), 2),
            "報酬%": round(net * 100, 2), "出場原因": exit_reason,
        })
        i = exit_idx + 1  # 出場後才找下一筆,避免重疊

    if not trades:
        return {"name": name, "trades": 0, "win_rate": None, "avg_return": None,
                "total_return": None, "max_drawdown": None, "equity": None,
                "trade_list": [], "hold_days": hold_days}

    rets = np.array([t["報酬%"] for t in trades]) / 100
    equity = np.cumprod(1 + rets)
    return {
        "name": name,
        "trades": len(trades),
        "win_rate": float((rets > 0).mean() * 100),
        "avg_return": float(rets.mean() * 100),
        "total_return": float((equity[-1] - 1) * 100),
        "max_drawdown": _max_drawdown(equity),
        "equity": equity,
        "equity_dates": [t["出場日"] for t in trades],
        "trade_list": trades,
        "hold_days": hold_days,
    }


def benchmark_return(period_df: pd.DataFrame, bench_df: pd.DataFrame) -> float:
    """大盤(0050)同期買進持有報酬%,用個股資料的起訖日對齊。"""
    if bench_df is None or bench_df.empty:
        return None
    b = bench_df["Close"]
    start, end = period_df.index[0], period_df.index[-1]
    b = b[(b.index >= start) & (b.index <= end)]
    if len(b) < 2:
        return None
    return float((b.iloc[-1] / b.iloc[0] - 1) * 100)


def backtest_all(df: pd.DataFrame, hold_days: int = 5,
                 stop_loss: float = None, take_profit: float = None) -> pd.DataFrame:
    """對所有可回測訊號跑一遍,回傳彙總表。"""
    rows = []
    for key in BACKTESTABLE:
        r = backtest_signal(df, key, hold_days=hold_days,
                            stop_loss=stop_loss, take_profit=take_profit)
        rows.append({
            "訊號": r["name"],
            "交易次數": r["trades"],
            "勝率%": round(r["win_rate"], 1) if r["win_rate"] is not None else None,
            "平均報酬%": round(r["avg_return"], 2) if r["avg_return"] is not None else None,
            "累積報酬%": round(r["total_return"], 1) if r["total_return"] is not None else None,
            "最大回撤%": round(r["max_drawdown"], 1) if r["max_drawdown"] is not None else None,
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    import sys
    from data import fetch
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    code = sys.argv[1] if len(sys.argv) > 1 else "2330"
    hold = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    df = fetch(code, period="2y")
    if df.empty:
        print("抓不到資料")
    else:
        print(f"回測 {code},持有 {hold} 日,停損5% 停利10%,含手續費+稅,2年資料:\n")
        print(backtest_all(df, hold_days=hold, stop_loss=5, take_profit=10).to_string(index=False))
        bench = fetch("0050", period="2y")
        print("\n同期 0050 買進持有報酬:", round(benchmark_return(df, bench), 1), "%")
        print("[注意] 歷史統計僅供參考,不代表未來,未計滑價/跳空。")

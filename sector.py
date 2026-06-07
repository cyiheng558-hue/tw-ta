# -*- coding: utf-8 -*-
"""類股強弱:算各產業近 N 個交易日的平均報酬,看資金流向哪些產業。

用股池(universe.txt)的個股,依 TaiwanStockInfo 的產業分類分組平均。
僅為客觀統計,非投資建議。
"""
import pandas as pd

from data import fetch_many
from fundamentals import load_industry


def sector_strength(codes, days: int = 20, period: str = "3mo",
                    min_count: int = 2, progress_cb=None) -> pd.DataFrame:
    """回傳各產業近 days 交易日平均報酬(%)。

    欄位:產業、平均報酬%、中位數%、檔數。只保留檔數 >= min_count 的產業。
    """
    ind = load_industry()
    data = fetch_many(codes, period=period, progress_cb=progress_cb)
    rows = []
    for code, df in data.items():
        if len(df) < days + 1:
            continue
        ret = (float(df["Close"].iloc[-1]) / float(df["Close"].iloc[-1 - days]) - 1) * 100
        rows.append({"產業": ind.get(code, "其他"), "報酬": ret})
    if not rows:
        return pd.DataFrame()
    d = pd.DataFrame(rows)
    g = d.groupby("產業")["報酬"].agg(["mean", "median", "count"]).reset_index()
    g = g[g["count"] >= min_count]
    g = g.rename(columns={"mean": "平均報酬%", "median": "中位數%", "count": "檔數"})
    g["平均報酬%"] = g["平均報酬%"].round(2)
    g["中位數%"] = g["中位數%"].round(2)
    return g.sort_values("平均報酬%", ascending=False).reset_index(drop=True)


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    def _uni():
        import os
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "universe.txt")
        codes = []
        for line in open(p, encoding="utf-8"):
            line = line.split("#")[0].strip()
            codes.extend(line.split())
        return codes

    days = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    print(f"類股強弱(近 {days} 交易日平均報酬):\n")
    print(sector_strength(_uni(), days=days).to_string(index=False))

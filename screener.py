# -*- coding: utf-8 -*-
"""自訂條件選股器:自由組合技術 + 籌碼 + 基本面條件,從股池篩出符合的股票。

設計:每檔先算出一組「特徵」(RSI、是否KD金叉、外資連買天數、本益比...),
再用使用者給的條件字典逐項過濾。只有被啟用的籌碼/基本面條件才會去打 API,
避免不必要的網路請求。

⚠ 篩出的清單只是「符合條件」,不代表會漲,仍須自行判斷。
"""
import os
import pandas as pd

from data import fetch, fetch_many
from indicators import enrich
from signals import (kd_golden_cross, ma_bullish_alignment, macd_turn_positive,
                     bollinger_breakout)
from chips import chip_summary
from fundamentals import valuation, revenue_yoy, name_of, load_stock_names

HERE = os.path.dirname(os.path.abspath(__file__))


def load_universe():
    path = os.path.join(HERE, "universe.txt")
    codes = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.split("#")[0].strip()
                codes.extend(line.split())
    return codes


# 條件預設(None = 不啟用該條件)
DEFAULT_CONDITIONS = {
    "rsi_min": None, "rsi_max": None,
    "require_kd_golden": False,      # 需 KD 黃金交叉
    "require_ma_bullish": False,     # 需均線多頭排列
    "require_macd_positive": False,  # 需 MACD 翻紅
    "require_bb_breakout": False,    # 需突破布林上軌
    "price_above_ma20": False,       # 收盤需站上月線
    "bias_max": None,                # 乖離率上限(避免追高)
    # 籌碼
    "foreign_buy_days_min": None,    # 外資(以合計近似)連續買超天數下限
    "chip_total_min": None,          # 近5日法人合計(張)下限
    # 基本面
    "per_max": None,                 # 本益比上限
    "yield_min": None,               # 殖利率下限(%)
    "yoy_min": None,                 # 月營收年增率下限(%)
}


def _need_chips(cond):
    return cond.get("foreign_buy_days_min") is not None or cond.get("chip_total_min") is not None


def _need_fund(cond):
    return any(cond.get(k) is not None for k in ("per_max", "yield_min", "yoy_min"))


def screen(codes, conditions: dict, period: str = "6mo", progress_cb=None) -> pd.DataFrame:
    """對 codes 套用 conditions,回傳符合的個股表(含相關數值)。"""
    cond = {**DEFAULT_CONDITIONS, **conditions}
    names = load_stock_names()
    data = fetch_many(codes, period=period, progress_cb=progress_cb)
    rows = []
    for code, df in data.items():
        if len(df) < 60:
            continue
        e = enrich(df)
        last = e.iloc[-1]
        rsi = float(last["RSI14"])
        biasv = float(last["BIAS10"])
        close = float(last["Close"])

        # --- 技術條件 ---
        if cond["rsi_min"] is not None and rsi < cond["rsi_min"]:
            continue
        if cond["rsi_max"] is not None and rsi > cond["rsi_max"]:
            continue
        if cond["bias_max"] is not None and biasv > cond["bias_max"]:
            continue
        if cond["price_above_ma20"] and not (close > float(last["MA20"])):
            continue
        if cond["require_kd_golden"] and not kd_golden_cross(e)[0]:
            continue
        if cond["require_ma_bullish"] and not ma_bullish_alignment(e)[0]:
            continue
        if cond["require_macd_positive"] and not macd_turn_positive(e)[0]:
            continue
        if cond["require_bb_breakout"] and not bollinger_breakout(e)[0]:
            continue

        row = {
            "代號": code, "名稱": names.get(code, ""),
            "收盤": round(close, 1), "RSI": round(rsi, 0), "乖離%": round(biasv, 1),
        }

        # --- 籌碼條件(需要才打 API) ---
        if _need_chips(cond):
            cs = chip_summary(code, days=5)
            if not cs:
                continue
            if cond["foreign_buy_days_min"] is not None and cs.get("連續買超天數", 0) < cond["foreign_buy_days_min"]:
                continue
            if cond["chip_total_min"] is not None and cs.get("合計", -1e18) < cond["chip_total_min"]:
                continue
            row["法人合計(張)"] = round(cs.get("合計", 0))
            row["連買天數"] = cs.get("連續買超天數", 0)

        # --- 基本面條件(需要才打 API) ---
        if _need_fund(cond):
            val = valuation(code)
            per = val.get("PER")
            yld = val.get("殖利率%")
            if cond["per_max"] is not None and (per is None or per > cond["per_max"]):
                continue
            if cond["yield_min"] is not None and (yld is None or yld < cond["yield_min"]):
                continue
            yoy = None
            if cond["yoy_min"] is not None:
                rev = revenue_yoy(code)
                yoy = rev.get("年增率%")
                if yoy is None or yoy < cond["yoy_min"]:
                    continue
                row["營收年增%"] = yoy
            row["本益比"] = per
            row["殖利率%"] = yld

        rows.append(row)

    return pd.DataFrame(rows)


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    # 範例:均線多頭、本益比<30、殖利率>1.5、營收年增>0
    cond = {"require_ma_bullish": True, "per_max": 30, "yield_min": 1.5, "yoy_min": 0}
    print("篩選條件:均線多頭 且 本益比<30 且 殖利率>1.5% 且 營收年增>0\n")
    df = screen(load_universe(), cond)
    if df.empty:
        print("沒有符合條件的股票")
    else:
        print(df.to_string(index=False))
    print("\n[注意] 符合條件不代表會漲,僅為篩選參考。")

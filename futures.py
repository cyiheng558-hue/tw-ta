# -*- coding: utf-8 -*-
"""大盤多空:三大法人台指期(TX)未平倉淨口數。

淨口數 = 多方未平倉 - 空方未平倉。正=偏多(法人站多方),負=偏空。
外資淨未平倉常被當成大盤方向的重要參考(但僅供參考,非投資建議)。
資料來源 FinMind TaiwanFuturesInstitutionalInvestors。
"""
import datetime as _dt
import pandas as pd

from finmind import fm_get, safe

_ORDER = ["外資", "投信", "自營商"]


@safe(pd.DataFrame)
def futures_net_oi(days: int = 40) -> pd.DataFrame:
    """近 days 日三大法人台指期淨未平倉口數。

    回傳以日期為索引的 DataFrame,欄位:外資、投信、自營商、三大法人合計。
    """
    start = (_dt.date.today() - _dt.timedelta(days=days * 2)).isoformat()
    data = fm_get("TaiwanFuturesInstitutionalInvestors", "TX", start)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df["net"] = (df["long_open_interest_balance_volume"]
                 - df["short_open_interest_balance_volume"])
    piv = df.pivot_table(index="date", columns="institutional_investors",
                         values="net", aggfunc="sum")
    # 只留三大法人,缺的補 0
    for c in _ORDER:
        if c not in piv.columns:
            piv[c] = 0
    piv = piv[_ORDER]
    piv["三大法人合計"] = piv.sum(axis=1)
    piv.index = pd.to_datetime(piv.index)
    return piv.sort_index().tail(days).round(0)


@safe(dict)
def summary(days: int = 40) -> dict:
    """最新一日的淨未平倉口數摘要 + 外資較前一日增減。"""
    df = futures_net_oi(days=days)
    if df.empty:
        return {}
    last = df.iloc[-1]
    foreign_chg = None
    if len(df) >= 2:
        foreign_chg = float(last["外資"] - df["外資"].iloc[-2])
    return {
        "日期": df.index[-1].strftime("%Y-%m-%d"),
        "外資淨": float(last["外資"]),
        "外資增減": foreign_chg,
        "投信淨": float(last["投信"]),
        "自營淨": float(last["自營商"]),
        "三大法人淨": float(last["三大法人合計"]),
    }


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("三大法人台指期淨未平倉口數(近10日):\n")
    df = futures_net_oi(40)
    if df.empty:
        print("抓不到資料")
    else:
        print(df.tail(10).to_string())
        print("\n摘要:", summary())

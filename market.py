# -*- coding: utf-8 -*-
"""盤勢:大盤(加權指數)技術狀態 + 全市場三大法人買賣超 + 綜合研判。

僅為客觀計算與整理,非投資建議。
"""
import datetime as _dt
import pandas as pd

from data import fetch
from indicators import enrich
from tw_time import taipei_today
from finmind import fm_get, safe
from futures import summary as fut_summary

# 全市場三大法人買賣超的法人名稱歸類
_FOREIGN = {"Foreign_Investor", "Foreign_Dealer_Self", "外資", "外資及陸資"}
_TRUST = {"Investment_Trust", "投信"}
_DEALER = {"Dealer_self", "Dealer_Hedging", "自營商", "自營商(自行買賣)", "自營商(避險)"}


@safe(dict)
def index_status() -> dict:
    """加權指數技術狀態 + 偏多/震盪/偏空研判(結合外資期貨多空)。"""
    df = fetch("^TWII", period="1y")
    if df.empty or len(df) < 60:
        return {}
    e = enrich(df)
    last = e.iloc[-1]
    close = float(last["Close"])
    chg = (close - float(e["Close"].iloc[-2])) / float(e["Close"].iloc[-2]) * 100
    ma20, ma60 = float(last["MA20"]), float(last["MA60"])
    rsi, k, d = float(last["RSI14"]), float(last["K"]), float(last["D"])

    score = 0
    reasons = []
    if close > ma20:
        score += 1; reasons.append("站上月線")
    else:
        score -= 1; reasons.append("跌破月線")
    if close > ma60:
        score += 1; reasons.append("站上季線")
    else:
        score -= 1; reasons.append("季線之下")
    if len(e) > 5 and e["MA20"].iloc[-1] > e["MA20"].iloc[-6]:
        score += 1; reasons.append("月線上彎")
    if k > d:
        score += 1; reasons.append("KD偏多")
    else:
        score -= 1; reasons.append("KD偏空")
    # 外資台指期淨未平倉
    fs = fut_summary()
    foreign_fut = fs.get("外資淨") if fs else None
    if foreign_fut is not None:
        if foreign_fut > 0:
            score += 1; reasons.append("外資期貨淨多")
        else:
            score -= 1; reasons.append("外資期貨淨空")

    if score >= 3:
        verdict = "偏多"
    elif score <= -3:
        verdict = "偏空"
    else:
        verdict = "震盪"
    return {
        "收盤": round(close, 1), "漲跌%": round(chg, 2),
        "月線MA20": round(ma20, 1), "季線MA60": round(ma60, 1),
        "RSI": round(rsi, 0), "KD": (round(k, 0), round(d, 0)),
        "研判": verdict, "理由": reasons,
        "外資期貨淨口數": foreign_fut,
    }


@safe(pd.DataFrame)
def inst_total(days: int = 30) -> pd.DataFrame:
    """全市場三大法人買賣超(淨額,億)。回傳外資/投信/自營商/合計 趨勢。"""
    start = (taipei_today() - _dt.timedelta(days=days * 2)).isoformat()
    data = fm_get("TaiwanStockTotalInstitutionalInvestors", start_date=start)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df["net"] = (pd.to_numeric(df["buy"], errors="coerce")
                 - pd.to_numeric(df["sell"], errors="coerce")) / 1e8  # 元 -> 億

    def grp(names):
        return df[df["name"].isin(names)].groupby("date")["net"].sum()

    out = pd.DataFrame({
        "外資": grp(_FOREIGN),
        "投信": grp(_TRUST),
        "自營商": grp(_DEALER),
    }).fillna(0)
    out["三大法人合計"] = out.sum(axis=1)
    out.index = pd.to_datetime(out.index)
    return out.sort_index().tail(days).round(0)


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("大盤技術狀態:")
    for k, v in index_status().items():
        print(f"  {k}: {v}")
    print("\n全市場三大法人買賣超(億,近5日):")
    print(inst_total(5).to_string())

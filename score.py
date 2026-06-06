# -*- coding: utf-8 -*-
"""綜合評分:把技術面、基本面、籌碼面各量化成 0~100 分,並給總評。

評分規則刻意簡單、透明(在下方各函式可看到加減分依據),
方便你理解與調整。分數只是把多項指標濃縮成一個方便比較的數字,
**不是買賣建議,也不保證準確**。
"""
import pandas as pd

from indicators import enrich
from signals import kd_golden_cross, ma_bullish_alignment
from fundamentals import valuation, revenue_yoy, financials, pe_valuation, dividend_history
from chips import chip_summary, foreign_holding


def _clamp(x):
    return max(0, min(100, x))


def technical_score(e: pd.DataFrame, swing_trend: str = None) -> tuple:
    """技術面分數(0~100)+ 說明清單。e 為 enrich 後的日線。"""
    s = 50
    notes = []
    last = e.iloc[-1]
    close = float(last["Close"])
    if pd.notna(last.get("MA20")) and close > last["MA20"]:
        s += 10; notes.append("站上月線+10")
    if pd.notna(last.get("MA60")) and close > last["MA60"]:
        s += 10; notes.append("站上季線+10")
    if ma_bullish_alignment(e)[0]:
        s += 15; notes.append("均線多頭+15")
    if pd.notna(last.get("K")) and pd.notna(last.get("D")) and last["K"] > last["D"]:
        s += 5; notes.append("KD偏多+5")
    if pd.notna(last.get("HIST")) and last["HIST"] > 0:
        s += 5; notes.append("MACD柱翻紅+5")
    rsi = float(last["RSI14"]) if pd.notna(last.get("RSI14")) else 50
    if rsi > 80:
        s -= 10; notes.append("RSI過熱-10")
    elif 50 <= rsi <= 70:
        s += 5; notes.append("RSI健康+5")
    if swing_trend in ("多頭", "偏多"):
        s += 10; notes.append(f"中線{swing_trend}+10")
    elif swing_trend in ("偏空", "空頭"):
        s -= 10; notes.append(f"中線{swing_trend}-10")
    return _clamp(s), notes


def fundamental_score(code: str) -> tuple:
    """基本面分數(0~100)+ 說明清單。"""
    s = 50
    notes = []
    fin = financials(code)
    roe = fin.get("ROE_TTM%")
    if roe is not None:
        if roe > 20:
            s += 20; notes.append(f"ROE{roe}%高+20")
        elif roe > 10:
            s += 10; notes.append(f"ROE{roe}%佳+10")
        elif roe < 0:
            s -= 20; notes.append(f"ROE為負-20")
    eps = fin.get("近四季EPS")
    if eps is not None:
        if eps <= 0:
            s -= 15; notes.append("近四季EPS虧損-15")
        else:
            s += 5; notes.append("EPS獲利+5")
    rev = revenue_yoy(code)
    yoy = rev.get("年增率%")
    if yoy is not None:
        if yoy > 20:
            s += 15; notes.append(f"營收年增{yoy}%+15")
        elif yoy > 0:
            s += 5; notes.append(f"營收年增{yoy}%+5")
        else:
            s -= 10; notes.append(f"營收年增{yoy}%-10")
    pe = pe_valuation(code)
    label = pe.get("評價", "")
    if "便宜" in label:
        s += 10; notes.append("本益比偏低+10")
    elif "合理" in label:
        s += 5; notes.append("本益比合理+5")
    elif "貴" in label:
        s -= 10; notes.append("本益比偏高-10")
    div = dividend_history(code)
    streak = div.get("連續配息年數", 0)
    if streak >= 10:
        s += 10; notes.append(f"連續配息{streak}年+10")
    elif streak >= 5:
        s += 5; notes.append(f"連續配息{streak}年+5")
    return _clamp(s), notes


def chips_score(code: str) -> tuple:
    """籌碼面分數(0~100)+ 說明清單。"""
    s = 50
    notes = []
    cs = chip_summary(code, days=5)
    if cs:
        streak = cs.get("連續買超天數", 0)
        if streak >= 3:
            s += 15; notes.append(f"法人連買{streak}日+15")
        elif streak >= 1:
            s += 5; notes.append(f"法人連買{streak}日+5")
        total = cs.get("合計", 0)
        if total > 0:
            s += 10; notes.append("近5日法人買超+10")
        elif total < 0:
            s -= 10; notes.append("近5日法人賣超-10")
    fh = foreign_holding(code, days=20)
    if not fh.empty and len(fh) >= 6:
        chg = float(fh["外資持股比率"].iloc[-1] - fh["外資持股比率"].iloc[-6])
        if chg > 0.1:
            s += 10; notes.append("外資持股上升+10")
        elif chg < -0.1:
            s -= 10; notes.append("外資持股下降-10")
    return _clamp(s), notes


def composite(code: str, e: pd.DataFrame = None, swing_trend: str = None,
              period: str = "1y") -> dict:
    """綜合評分。回傳三面向分數、總分、說明,以及雷達圖用的資料。"""
    if e is None:
        from data import fetch
        df = fetch(code, period=period)
        if df.empty or len(df) < 60:
            return {"error": "資料不足"}
        e = enrich(df)
    t, tn = technical_score(e, swing_trend)
    f, fn = fundamental_score(code)
    c, cn = chips_score(code)
    overall = round((t + f + c) / 3, 0)
    if overall >= 70:
        grade = "優"
    elif overall >= 55:
        grade = "良"
    elif overall >= 45:
        grade = "中性"
    else:
        grade = "偏弱"
    return {
        "技術面": t, "基本面": f, "籌碼面": c, "總分": overall, "評等": grade,
        "技術說明": tn, "基本說明": fn, "籌碼說明": cn,
        "雷達": {"技術面": t, "基本面": f, "籌碼面": c},
    }


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    from data import fetch
    code = sys.argv[1] if len(sys.argv) > 1 else "2330"
    r = composite(code, e=enrich(fetch(code, period="1y")))
    if "error" in r:
        print(r["error"])
    else:
        print(f"{code} 綜合評分:總分 {r['總分']:.0f}({r['評等']})")
        print(f"  技術面 {r['技術面']}:{r['技術說明']}")
        print(f"  基本面 {r['基本面']}:{r['基本說明']}")
        print(f"  籌碼面 {r['籌碼面']}:{r['籌碼說明']}")
    print("\n[注意] 評分為指標濃縮,非投資建議。")

# -*- coding: utf-8 -*-
"""風險管理:部位大小計算 + ATR 停損建議。

核心觀念(固定風險法):每筆交易最多只賠「本金 × 可承受風險%」,
由此反推「該買幾張」與「停損價設哪」。這是短線控制虧損最重要的紀律。

⚠ 僅為試算工具,不是投資建議;實際下單仍須考量流動性、跳空等風險。
"""
from data import fetch
from indicators import enrich

LOT = 1000  # 台股 1 張 = 1000 股


def atr_stop(entry: float, atr_value: float, k: float = 2.0) -> float:
    """ATR 停損價:進場價 - k 倍 ATR。波動越大,停損抓越寬。"""
    return entry - k * atr_value


def position_size(capital: float, risk_pct: float, entry: float, stop: float) -> dict:
    """依固定風險法算可買張數。

    capital  本金(元)
    risk_pct 單筆可承受風險(%),例如 2 表示最多賠本金的 2%
    entry    預計進場價
    stop     停損價(需 < entry)
    """
    if entry <= 0 or stop <= 0 or stop >= entry:
        return {"error": "停損價需小於進場價且皆為正數"}
    max_loss = capital * risk_pct / 100.0       # 容許最大虧損金額
    risk_per_share = entry - stop                # 每股風險
    raw_shares = max_loss / risk_per_share
    lots = int(raw_shares // LOT)                # 無條件捨去到整張

    # 若部位金額超過本金,改用本金上限可買的張數
    if lots * LOT * entry > capital:
        lots = int(capital // (LOT * entry))

    shares = lots * LOT
    cost = shares * entry
    actual_risk = shares * risk_per_share
    return {
        "可買張數": lots,
        "股數": shares,
        "投入金額": round(cost),
        "佔本金%": round(cost / capital * 100, 1) if capital else 0,
        "停損價": round(stop, 2),
        "每股風險": round(risk_per_share, 2),
        "實際最大虧損": round(actual_risk),
        "實際風險%": round(actual_risk / capital * 100, 2) if capital else 0,
        "停損跌幅%": round(risk_per_share / entry * 100, 2),
    }


def suggest(code: str, capital: float, risk_pct: float = 2.0,
            atr_k: float = 2.0, period: str = "6mo") -> dict:
    """抓個股最新價與 ATR,給出 ATR 停損價與建議張數。"""
    df = fetch(code, period=period)
    if df.empty:
        return {"error": "抓不到資料"}
    e = enrich(df)
    last = e.iloc[-1]
    entry = float(last["Close"])
    atr_value = float(last["ATR14"])
    stop = atr_stop(entry, atr_value, atr_k)
    res = position_size(capital, risk_pct, entry, stop)
    res.update({"進場價(現價)": round(entry, 2), "ATR": round(atr_value, 2),
                "停損倍數": atr_k})
    return res


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    code = sys.argv[1] if len(sys.argv) > 1 else "2330"
    capital = float(sys.argv[2]) if len(sys.argv) > 2 else 500000
    risk = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0
    print(f"{code}:本金 {capital:,.0f} 元,單筆風險 {risk}%,ATR×2 停損\n")
    r = suggest(code, capital, risk)
    for k, v in r.items():
        print(f"  {k}: {v}")
    print("\n[注意] 僅為試算,非投資建議。")

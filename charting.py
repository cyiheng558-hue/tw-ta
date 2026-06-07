# -*- coding: utf-8 -*-
"""進階看盤圖表計算:K線週期轉換、訊號標記、量價分佈、支撐壓力、K線型態。

純計算,不畫圖(畫圖在 app.py)。皆為客觀計算,非投資建議。
"""
import numpy as np
import pandas as pd


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """把日線重新取樣成 週(rule='W-FRI')或 月(rule='ME')K 線。"""
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    return df.resample(rule).agg(agg).dropna()


def signal_markers(e: pd.DataFrame):
    """逐根偵測訊號發生點。回傳 (看多清單, 看空清單),元素為 (日期, 價格, 標籤)。"""
    bull, bear = [], []
    K, D = e["K"].values, e["D"].values
    close, ma20 = e["Close"].values, e["MA20"].values
    dif, macd = e["DIF"].values, e["MACD"].values
    low, high = e["Low"].values, e["High"].values
    idx = e.index
    for i in range(1, len(e)):
        if K[i - 1] <= D[i - 1] and K[i] > D[i] and K[i] < 50:
            bull.append((idx[i], low[i], "KD金叉"))
        if K[i - 1] >= D[i - 1] and K[i] < D[i] and K[i] > 50:
            bear.append((idx[i], high[i], "KD死叉"))
        if not np.isnan(ma20[i]) and close[i - 1] <= ma20[i - 1] and close[i] > ma20[i]:
            bull.append((idx[i], low[i], "突破月線"))
        if dif[i - 1] <= macd[i - 1] and dif[i] > macd[i]:
            bull.append((idx[i], low[i], "MACD翻紅"))
    return bull, bear


def volume_profile(df: pd.DataFrame, bins: int = 26):
    """量價分佈:把成交量依收盤價落在的價格區間累加。

    回傳 (價格中心陣列, 各區間量, POC價格)。POC=成交量最大的價位。
    """
    lo, hi = float(df["Low"].min()), float(df["High"].max())
    if hi <= lo:
        return np.array([]), np.array([]), None
    edges = np.linspace(lo, hi, bins + 1)
    centers = (edges[:-1] + edges[1:]) / 2
    vol = np.zeros(bins)
    closes = df["Close"].values
    vols = df["Volume"].values
    b = np.clip(np.digitize(closes, edges) - 1, 0, bins - 1)
    for bi, v in zip(b, vols):
        vol[bi] += v
    poc = float(centers[int(np.argmax(vol))]) if vol.sum() > 0 else None
    return centers, vol, poc


def support_resistance(df: pd.DataFrame, window: int = 10, max_levels: int = 6):
    """用近期波段高低點(局部極值)找支撐壓力價位,合併相近者。"""
    highs, lows = df["High"].values, df["Low"].values
    n = len(df)
    levels = []
    for i in range(window, n - window):
        seg_h = highs[i - window:i + window + 1]
        seg_l = lows[i - window:i + window + 1]
        if highs[i] == seg_h.max():
            levels.append(highs[i])
        if lows[i] == seg_l.min():
            levels.append(lows[i])
    if not levels:
        return []
    levels = sorted(levels)
    # 合併距離 < 1.5% 的相近價位
    merged = [levels[0]]
    for lv in levels[1:]:
        if abs(lv - merged[-1]) / merged[-1] > 0.015:
            merged.append(lv)
    # 取最接近現價的幾條
    cur = float(df["Close"].iloc[-1])
    merged.sort(key=lambda x: abs(x - cur))
    return sorted(round(x, 2) for x in merged[:max_levels])


def candle_patterns(df: pd.DataFrame, lookback: int = 8):
    """辨識近 lookback 根的常見 K 線型態。回傳 [(日期, 價格, 標籤), ...]。"""
    out = []
    o = df["Open"].values
    h = df["High"].values
    low = df["Low"].values
    c = df["Close"].values
    idx = df.index
    n = len(df)
    start = max(1, n - lookback)
    for i in range(start, n):
        body = abs(c[i] - o[i])
        rng = h[i] - low[i]
        if rng <= 0:
            continue
        upper = h[i] - max(c[i], o[i])
        lower = min(c[i], o[i]) - low[i]
        # 十字星
        if body <= 0.1 * rng:
            out.append((idx[i], h[i], "十字星"))
            continue
        # 錘子(下影長、實體小、在低檔)
        if lower >= 2 * body and upper <= body and c[i] >= o[i]:
            out.append((idx[i], low[i], "錘子"))
            continue
        # 流星(上影長、實體小)
        if upper >= 2 * body and lower <= body:
            out.append((idx[i], h[i], "流星"))
            continue
        # 多頭吞噬
        if c[i] > o[i] and c[i - 1] < o[i - 1] and c[i] >= o[i - 1] and o[i] <= c[i - 1]:
            out.append((idx[i], low[i], "多頭吞噬"))
            continue
        # 空頭吞噬
        if c[i] < o[i] and c[i - 1] > o[i - 1] and o[i] >= c[i - 1] and c[i] <= o[i - 1]:
            out.append((idx[i], h[i], "空頭吞噬"))
    return out


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    from data import fetch
    from indicators import enrich
    code = sys.argv[1] if len(sys.argv) > 1 else "2330"
    df = fetch(code, period="6mo")
    e = enrich(df)
    bull, bear = signal_markers(e)
    print(f"看多訊號點 {len(bull)} 個、看空 {len(bear)} 個")
    centers, vol, poc = volume_profile(df)
    print("量價分佈 POC(最大量價位):", round(poc, 1) if poc else None)
    print("支撐壓力:", support_resistance(df))
    print("近期型態:", [(str(d.date()), lbl) for d, _, lbl in candle_patterns(df)])

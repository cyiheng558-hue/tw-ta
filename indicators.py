# -*- coding: utf-8 -*-
"""技術指標計算模組。

全部用 pandas 計算,不依賴 TA-Lib(避免 Windows 編譯問題)。
輸入皆為含 Open/High/Low/Close/Volume 欄位的 DataFrame。
"""
import pandas as pd


def sma(series: pd.Series, n: int) -> pd.Series:
    """簡單移動平均(SMA)。"""
    return series.rolling(window=n, min_periods=n).mean()


def ema(series: pd.Series, n: int) -> pd.Series:
    """指數移動平均(EMA)。"""
    return series.ewm(span=n, adjust=False).mean()


def add_moving_averages(df: pd.DataFrame, windows=(5, 10, 20, 60)) -> pd.DataFrame:
    """加入多條收盤價均線,欄位名稱為 MA5、MA10...。"""
    for n in windows:
        df[f"MA{n}"] = sma(df["Close"], n)
    return df


def kd(df: pd.DataFrame, n: int = 9, k_smooth: int = 3, d_smooth: int = 3) -> pd.DataFrame:
    """KD 隨機指標(台股慣用 9 日,K/D 各平滑 3)。

    回傳含 K、D 兩欄的 DataFrame。
    """
    low_n = df["Low"].rolling(window=n, min_periods=n).min()
    high_n = df["High"].rolling(window=n, min_periods=n).max()
    rng = (high_n - low_n).replace(0, pd.NA)  # 高=低(鎖死)時避免除以零
    rsv = (df["Close"] - low_n) / rng * 100
    rsv = rsv.replace([float("inf"), float("-inf")], pd.NA).fillna(50)
    # 台股 KD 用平滑遞迴(等同 EMA,alpha=1/平滑期)
    k = rsv.ewm(alpha=1 / k_smooth, adjust=False).mean()
    d = k.ewm(alpha=1 / d_smooth, adjust=False).mean()
    return pd.DataFrame({"K": k, "D": d}, index=df.index)


def macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACD。回傳 DIF、MACD(訊號線)、HIST(柱狀體)。"""
    dif = ema(df["Close"], fast) - ema(df["Close"], slow)
    signal_line = ema(dif, signal)
    hist = dif - signal_line
    return pd.DataFrame({"DIF": dif, "MACD": signal_line, "HIST": hist}, index=df.index)


def rsi(series: pd.Series, n: int = 14) -> pd.Series:
    """RSI 相對強弱指標(Wilder 平滑)。"""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False).mean()
    rs = avg_gain / avg_loss
    out = 100 - (100 / (1 + rs))
    # 全無下跌(avg_loss=0)→RSI=100;完全無波動(0/0=NaN)→中性50
    out = out.mask(avg_loss == 0, 100.0)
    return out.fillna(50)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """平均真實區間(ATR):衡量波動度,常用來設停損。"""
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def bias(series: pd.Series, n: int = 10) -> pd.Series:
    """乖離率(BIAS):收盤偏離 n 日均線的百分比。"""
    ma = sma(series, n)
    return (series - ma) / ma * 100


def obv(df: pd.DataFrame) -> pd.Series:
    """能量潮(OBV):收漲日加量、收跌日減量,看量價是否同步。"""
    direction = df["Close"].diff()
    sign = direction.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    return (sign * df["Volume"]).fillna(0).cumsum()


def bollinger(series: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    """布林通道。回傳 BB_MID、BB_UP、BB_LOW。"""
    mid = sma(series, n)
    std = series.rolling(window=n, min_periods=n).std()
    return pd.DataFrame(
        {"BB_MID": mid, "BB_UP": mid + k * std, "BB_LOW": mid - k * std},
        index=series.index,
    )


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """一次補上所有指標欄位,回傳新的 DataFrame。"""
    out = df.copy()
    out = add_moving_averages(out)
    out["VOL_MA5"] = sma(out["Volume"], 5)
    out["VOL_MA20"] = sma(out["Volume"], 20)
    out = out.join(kd(out))
    out = out.join(macd(out))
    out["RSI14"] = rsi(out["Close"])
    out["BIAS10"] = bias(out["Close"], 10)
    out["ATR14"] = atr(out, 14)
    out["OBV"] = obv(out)
    out["OBV_MA10"] = sma(out["OBV"], 10)
    out = out.join(bollinger(out["Close"]))
    return out

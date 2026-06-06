# -*- coding: utf-8 -*-
"""短線技術訊號偵測。

每個函式判斷「最近一根 K 棒」是否出現某種訊號,回傳 (bool, 說明字串)。
這些是常見的技術面參考訊號,不是買賣建議。
"""
import pandas as pd


def _cross_up(a: pd.Series, b: pd.Series) -> bool:
    """a 是否在最後一根 K 棒向上穿越 b(黃金交叉)。"""
    if len(a) < 2:
        return False
    return a.iloc[-2] <= b.iloc[-2] and a.iloc[-1] > b.iloc[-1]


def _cross_down(a: pd.Series, b: pd.Series) -> bool:
    """a 是否在最後一根 K 棒向下穿越 b(死亡交叉)。"""
    if len(a) < 2:
        return False
    return a.iloc[-2] >= b.iloc[-2] and a.iloc[-1] < b.iloc[-1]


def kd_golden_cross(df: pd.DataFrame):
    """KD 黃金交叉,且在相對低檔(K<50)時訊號較強。"""
    if not _cross_up(df["K"], df["D"]):
        return False, ""
    k = df["K"].iloc[-1]
    zone = "低檔(偏強)" if k < 50 else "高檔"
    return True, f"KD黃金交叉 K={k:.0f} {zone}"


def kd_dead_cross(df: pd.DataFrame):
    """KD 死亡交叉。"""
    if not _cross_down(df["K"], df["D"]):
        return False, ""
    return True, f"KD死亡交叉 K={df['K'].iloc[-1]:.0f}"


def macd_turn_positive(df: pd.DataFrame):
    """MACD 柱狀體由負翻正(DIF 上穿訊號線)。"""
    if _cross_up(df["DIF"], df["MACD"]):
        return True, "MACD翻紅(DIF上穿)"
    return False, ""


def ma_bullish_alignment(df: pd.DataFrame):
    """均線多頭排列:收盤 > MA5 > MA20,且 MA5 上彎。"""
    last = df.iloc[-1]
    if pd.isna(last.get("MA20")) or pd.isna(last.get("MA5")):
        return False, ""
    cond = last["Close"] > last["MA5"] > last["MA20"]
    rising = df["MA5"].iloc[-1] > df["MA5"].iloc[-3] if len(df) >= 3 else False
    if cond and rising:
        return True, "均線多頭排列(收盤>MA5>MA20)"
    return False, ""


def break_ma20_with_volume(df: pd.DataFrame):
    """帶量突破月線:收盤上穿 MA20 且成交量 > 5日均量 1.5 倍。"""
    if not _cross_up(df["Close"], df["MA20"]):
        return False, ""
    vol = df["Volume"].iloc[-1]
    vma5 = df["VOL_MA5"].iloc[-1]
    if pd.notna(vma5) and vol > vma5 * 1.5:
        return True, f"帶量突破月線(量{vol / vma5:.1f}倍均量)"
    return False, "突破月線(但量未明顯放大)"


def rsi_oversold_rebound(df: pd.DataFrame):
    """RSI 從超賣區(<30)回升。"""
    if len(df) < 2:
        return False, ""
    prev, cur = df["RSI14"].iloc[-2], df["RSI14"].iloc[-1]
    if prev < 30 and cur > prev:
        return True, f"RSI超賣回升({prev:.0f}→{cur:.0f})"
    return False, ""


def rsi_overbought(df: pd.DataFrame):
    """RSI 超買警示(>80)。"""
    cur = df["RSI14"].iloc[-1]
    if cur > 80:
        return True, f"RSI過熱({cur:.0f})"
    return False, ""


def bollinger_breakout(df: pd.DataFrame):
    """突破布林上軌:收盤由下方上穿布林上軌(強勢但留意追高)。"""
    if _cross_up(df["Close"], df["BB_UP"]):
        return True, "突破布林上軌(強勢)"
    return False, ""


def obv_rising_with_price(df: pd.DataFrame):
    """量價同步:OBV 站上其 10 日均線且股價也在 MA20 之上。"""
    last = df.iloc[-1]
    if pd.isna(last.get("OBV_MA10")) or pd.isna(last.get("MA20")):
        return False, ""
    if last["OBV"] > last["OBV_MA10"] and last["Close"] > last["MA20"]:
        return True, "量價同步走多(OBV轉強)"
    return False, ""


def bias_too_high(df: pd.DataFrame):
    """乖離過大警示:10 日乖離率 > 12%,短線過熱易拉回。"""
    b = df["BIAS10"].iloc[-1]
    if pd.notna(b) and b > 12:
        return True, f"乖離過大({b:.0f}%)"
    return False, ""


def volume_spike(df: pd.DataFrame):
    """爆量:成交量 > 20 日均量 2 倍。"""
    vol = df["Volume"].iloc[-1]
    vma20 = df["VOL_MA20"].iloc[-1]
    if pd.notna(vma20) and vol > vma20 * 2:
        return True, f"爆量({vol / vma20:.1f}倍月均量)"
    return False, ""


# 看多訊號(短線進場參考)
BULLISH = [
    kd_golden_cross,
    macd_turn_positive,
    ma_bullish_alignment,
    break_ma20_with_volume,
    rsi_oversold_rebound,
    bollinger_breakout,
    obv_rising_with_price,
]

# 看空/警示訊號
BEARISH = [
    kd_dead_cross,
    rsi_overbought,
    bias_too_high,
]


# 給回測用:可被歷史回測的訊號(key -> (顯示名稱, 判斷函式))
# 判斷函式接收「到某根 K 棒為止」的 DataFrame,回傳是否在最後一根觸發。
BACKTESTABLE = {
    "kd_golden": ("KD黃金交叉", lambda d: kd_golden_cross(d)[0]),
    "macd_positive": ("MACD翻紅", lambda d: macd_turn_positive(d)[0]),
    "ma_bullish": ("均線多頭排列", lambda d: ma_bullish_alignment(d)[0]),
    "break_ma20_vol": ("帶量突破月線", lambda d: break_ma20_with_volume(d)[0] and "帶量" in break_ma20_with_volume(d)[1]),
    "rsi_rebound": ("RSI超賣回升", lambda d: rsi_oversold_rebound(d)[0]),
    "bb_breakout": ("突破布林上軌", lambda d: bollinger_breakout(d)[0]),
}


def scan_one(df: pd.DataFrame):
    """對單一個股跑所有訊號,回傳 (看多訊號清單, 看空訊號清單)。"""
    bull, bear = [], []
    for fn in BULLISH:
        ok, msg = fn(df)
        if ok:
            bull.append(msg)
    for fn in BEARISH:
        ok, msg = fn(df)
        if ok:
            bear.append(msg)
    # 爆量歸類為中性提示,附在看多後面
    ok, msg = volume_spike(df)
    if ok:
        bull.append(msg)
    return bull, bear

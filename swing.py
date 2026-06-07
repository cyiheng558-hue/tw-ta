# -*- coding: utf-8 -*-
"""中線(波段)分析:持有數週到數月的角度。

與短線不同,中線看的是「趨勢」而非當日訊號:
  - 長天期均線:月線MA20、季線MA60、半年線MA120、年線MA240
  - 均線多頭/空頭排列、站上年線與否、季線是否翻揚
  - 週 KD(把日線匯總成週線算 KD),抓波段轉折
  - 波段突破(站上近一季高點)

需要較長資料(建議 2 年)才算得出年線。

⚠ 僅為客觀計算,非投資建議,請自行評估風險。
"""
import numpy as np
import pandas as pd

from indicators import enrich, sma, kd, macd
from backtest import _max_drawdown, FEE_RATE, TAX_RATE, benchmark_return


def add_medium_ma(df: pd.DataFrame) -> pd.DataFrame:
    """加入中線均線:MA120(半年線)、MA240(年線)。MA20/60 由 enrich 提供。"""
    df["MA120"] = sma(df["Close"], 120)
    df["MA240"] = sma(df["Close"], 240)
    return df


def weekly_kd(df: pd.DataFrame) -> pd.DataFrame:
    """把日線匯總成週線後計算 KD,回傳對齊回日線索引的 週K、週D。"""
    wk = df.resample("W-FRI").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    ).dropna()
    if len(wk) < 10:
        return pd.DataFrame({"週K": pd.Series(dtype=float), "週D": pd.Series(dtype=float)})
    wkd = kd(wk)
    out = pd.DataFrame({"週K": wkd["K"], "週D": wkd["D"]})
    # 對齊回日線:用前向填補
    return out.reindex(df.index, method="ffill")


def enrich_swing(df: pd.DataFrame) -> pd.DataFrame:
    """在 enrich 基礎上補中線需要的欄位。"""
    e = enrich(df)
    e = add_medium_ma(e)
    wkd = weekly_kd(df)
    e["週K"] = wkd["週K"]
    e["週D"] = wkd["週D"]
    # 週 MACD 柱(用週收盤)
    wk_close = df["Close"].resample("W-FRI").last().dropna()
    if len(wk_close) >= 26:
        wmacd = macd(pd.DataFrame({"Close": wk_close}))
        e["週MACD柱"] = wmacd["HIST"].reindex(e.index, method="ffill")
    else:
        e["週MACD柱"] = float("nan")
    return e


def trend_status(e: pd.DataFrame) -> dict:
    """判斷中線趨勢:多頭 / 偏多 / 盤整 / 偏空 / 空頭,附理由。"""
    last = e.iloc[-1]
    close = float(last["Close"])
    ma20, ma60 = last.get("MA20"), last.get("MA60")
    ma120, ma240 = last.get("MA120"), last.get("MA240")

    reasons = []
    score = 0
    # 站上各長均線
    if pd.notna(ma60) and close > ma60:
        score += 1; reasons.append("站上季線")
    elif pd.notna(ma60):
        score -= 1; reasons.append("跌破季線")
    if pd.notna(ma240) and close > ma240:
        score += 1; reasons.append("站上年線")
    elif pd.notna(ma240):
        score -= 1; reasons.append("年線之下")
    # 均線排列
    if all(pd.notna(x) for x in [ma20, ma60, ma120]):
        if ma20 > ma60 > ma120:
            score += 2; reasons.append("均線多頭排列")
        elif ma20 < ma60 < ma120:
            score -= 2; reasons.append("均線空頭排列")
    # 年線方向(用近 20 日比較)
    if pd.notna(ma240) and len(e) > 21 and pd.notna(e["MA240"].iloc[-21]):
        if ma240 > e["MA240"].iloc[-21]:
            score += 1; reasons.append("年線上彎")
        elif ma240 < e["MA240"].iloc[-21]:
            score -= 1; reasons.append("年線下彎")

    if score >= 4:
        label = "多頭"
    elif score >= 2:
        label = "偏多"
    elif score <= -4:
        label = "空頭"
    elif score <= -2:
        label = "偏空"
    else:
        label = "盤整"
    return {"趨勢": label, "分數": score, "理由": reasons}


def swing_signals(e: pd.DataFrame):
    """中線進場參考訊號,回傳清單。"""
    sig = []
    last = e.iloc[-1]
    close = float(last["Close"])

    # 季線黃金交叉(MA60 上穿 MA120):中期轉強
    if pd.notna(last.get("MA60")) and pd.notna(last.get("MA120")) and len(e) >= 3:
        if e["MA60"].iloc[-2] <= e["MA120"].iloc[-2] and e["MA60"].iloc[-1] > e["MA120"].iloc[-1]:
            sig.append("季線黃金交叉(MA60上穿MA120)")

    # 突破年線:由年線下方站上
    if pd.notna(last.get("MA240")) and len(e) >= 2:
        if e["Close"].iloc[-2] <= e["MA240"].iloc[-2] and close > last["MA240"]:
            sig.append("站上年線(中期轉多)")

    # 週KD 黃金交叉且在低檔
    if pd.notna(last.get("週K")) and pd.notna(last.get("週D")) and len(e) >= 6:
        prevK, prevD = e["週K"].iloc[-6], e["週D"].iloc[-6]  # 約一週前
        if pd.notna(prevK) and prevK <= prevD and last["週K"] > last["週D"] and last["週K"] < 60:
            sig.append(f"週KD黃金交叉(週K={last['週K']:.0f})")

    # 波段突破:站上近 60 日最高(不含當日)
    if len(e) >= 61:
        prior_high = e["Close"].iloc[-61:-1].max()
        if close > prior_high:
            sig.append("波段突破(創近季新高)")

    # 季線翻揚 + 站上季線(中期偏多續抱)
    if pd.notna(last.get("MA60")) and len(e) >= 11:
        if last["MA60"] > e["MA60"].iloc[-11] and close > last["MA60"]:
            sig.append("季線翻揚且站穩")

    return sig


# ==================== 中線(波段)回測 ====================
def _swing_triggers(e: pd.DataFrame) -> dict:
    """逐根 K 棒判斷各中線訊號是否觸發,回傳 {訊號名: bool 陣列}(對齊 e)。

    用已算好的欄位判斷,避免回測時重複 enrich,速度快很多。
    """
    n = len(e)
    ma60 = e["MA60"].values
    ma120 = e["MA120"].values
    ma240 = e["MA240"].values
    close = e["Close"].values
    wk = e["週K"].values
    wd = e["週D"].values

    qg = np.zeros(n, bool)   # 季線黃金交叉
    yl = np.zeros(n, bool)   # 站上年線
    bo = np.zeros(n, bool)   # 波段突破(創近季新高)
    wkd = np.zeros(n, bool)  # 週KD黃金交叉(低檔)
    for i in range(1, n):
        if not np.isnan(ma60[i]) and not np.isnan(ma120[i]):
            qg[i] = ma60[i - 1] <= ma120[i - 1] and ma60[i] > ma120[i]
        if not np.isnan(ma240[i]):
            yl[i] = close[i - 1] <= ma240[i - 1] and close[i] > ma240[i]
        if i >= 61:
            prior_high = np.nanmax(close[i - 60:i])  # 不含當日的近60日高
            bo[i] = close[i] > prior_high
        if not np.isnan(wk[i]) and not np.isnan(wd[i]):
            wkd[i] = wk[i - 1] <= wd[i - 1] and wk[i] > wd[i] and wk[i] < 60
    return {"季線黃金交叉": qg, "站上年線": yl, "波段突破": bo, "週KD黃金交叉": wkd}


def _backtest_triggers(e: pd.DataFrame, trig: np.ndarray, hold_days: int,
                       stop_loss, take_profit, fee=FEE_RATE, tax=TAX_RATE,
                       min_bars: int = 120) -> dict:
    """事件式回測:給定每根觸發布林陣列,模擬同時只持有一個部位。"""
    n = len(e)
    close = e["Close"].values
    high = e["High"].values
    low = e["Low"].values
    dates = e.index
    trades = []
    i = min_bars
    while i < n - 1:
        if not trig[i]:
            i += 1
            continue
        if i + 2 > n - 1:
            break
        entry = close[i + 1]
        exit_idx = min(i + 1 + hold_days, n - 1)
        exit_price = None
        reason = "持有到期"
        for j in range(i + 2, exit_idx + 1):
            if stop_loss is not None and low[j] <= entry * (1 - stop_loss / 100):
                exit_price = entry * (1 - stop_loss / 100); reason = "停損"; exit_idx = j; break
            if take_profit is not None and high[j] >= entry * (1 + take_profit / 100):
                exit_price = entry * (1 + take_profit / 100); reason = "停利"; exit_idx = j; break
        if exit_price is None:
            exit_price = close[exit_idx]
        net = (exit_price * (1 - fee - tax)) / (entry * (1 + fee)) - 1
        trades.append({"進場日": str(dates[i + 1].date()), "進場價": round(float(entry), 2),
                       "出場日": str(dates[exit_idx].date()), "出場價": round(float(exit_price), 2),
                       "報酬%": round(net * 100, 2), "出場原因": reason})
        i = exit_idx + 1

    if not trades:
        return {"trades": 0, "win_rate": None, "avg_return": None,
                "total_return": None, "max_drawdown": None, "equity": None, "trade_list": []}
    rets = np.array([t["報酬%"] for t in trades]) / 100
    equity = np.cumprod(1 + rets)
    return {
        "trades": len(trades),
        "win_rate": float((rets > 0).mean() * 100),
        "avg_return": float(rets.mean() * 100),
        "total_return": float((equity[-1] - 1) * 100),
        "max_drawdown": _max_drawdown(equity),
        "equity": equity,
        "equity_dates": [t["出場日"] for t in trades],
        "trade_list": trades,
    }


def backtest_swing(df: pd.DataFrame, hold_days: int = 20,
                   stop_loss=8.0, take_profit=20.0) -> pd.DataFrame:
    """回測所有中線訊號(預設持有20日、停損8%、停利20%)。回傳彙總表。"""
    e = enrich_swing(df)
    trigs = _swing_triggers(e)
    rows = []
    for name, arr in trigs.items():
        r = _backtest_triggers(e, arr, hold_days, stop_loss, take_profit)
        rows.append({
            "中線訊號": name, "交易次數": r["trades"],
            "勝率%": round(r["win_rate"], 1) if r["win_rate"] is not None else None,
            "平均報酬%": round(r["avg_return"], 2) if r["avg_return"] is not None else None,
            "累積報酬%": round(r["total_return"], 1) if r["total_return"] is not None else None,
            "最大回撤%": round(r["max_drawdown"], 1) if r["max_drawdown"] is not None else None,
        })
    return pd.DataFrame(rows)


def backtest_swing_one(df: pd.DataFrame, signal_name: str, hold_days: int = 20,
                       stop_loss=8.0, take_profit=20.0) -> dict:
    """回測單一中線訊號,回傳含權益曲線與交易明細的 dict。"""
    e = enrich_swing(df)
    trigs = _swing_triggers(e)
    if signal_name not in trigs:
        return {"trades": 0}
    return _backtest_triggers(e, trigs[signal_name], hold_days, stop_loss, take_profit)


def analyze(code: str, df: pd.DataFrame = None, period: str = "2y") -> dict:
    """單一個股中線分析。回傳趨勢、訊號與關鍵價位。"""
    if df is None:
        from data import fetch
        df = fetch(code, period=period)
    if df is None or df.empty or len(df) < 120:
        return {"error": "資料不足(中線分析建議用 2 年資料,至少需120個交易日)"}
    e = enrich_swing(df)
    last = e.iloc[-1]
    status = trend_status(e)
    sig = swing_signals(e)
    return {
        "趨勢": status["趨勢"],
        "理由": status["理由"],
        "中線訊號": sig,
        "收盤": round(float(last["Close"]), 1),
        "季線MA60": round(float(last["MA60"]), 1) if pd.notna(last.get("MA60")) else None,
        "年線MA240": round(float(last["MA240"]), 1) if pd.notna(last.get("MA240")) else None,
        "週KD": (round(float(last["週K"]), 0), round(float(last["週D"]), 0)) if pd.notna(last.get("週K")) else None,
        "_enriched": e,
    }


def scan_swing(codes, period: str = "2y", only_bull: bool = True, progress_cb=None) -> pd.DataFrame:
    """批次掃描中線趨勢與訊號。only_bull=True 只留趨勢偏多以上者。"""
    from data import fetch_many
    from fundamentals import load_stock_names
    names = load_stock_names()
    data = fetch_many(codes, period=period, progress_cb=progress_cb)
    rows = []
    for code, df in data.items():
        r = analyze(code, df)
        if "error" in r:
            continue
        if only_bull and r["趨勢"] not in ("多頭", "偏多"):
            continue
        rows.append({
            "代號": code, "名稱": names.get(code, ""),
            "收盤": r["收盤"], "趨勢": r["趨勢"],
            "中線訊號": " / ".join(r["中線訊號"]) if r["中線訊號"] else "—",
            "季線": r["季線MA60"], "年線": r["年線MA240"],
            "理由": " / ".join(r["理由"]),
        })
    order = {"多頭": 0, "偏多": 1, "盤整": 2, "偏空": 3, "空頭": 4}
    df_out = pd.DataFrame(rows)
    if not df_out.empty:
        df_out = df_out.sort_values("趨勢", key=lambda s: s.map(order))
    return df_out


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    code = sys.argv[1] if len(sys.argv) > 1 else "2330"
    from data import fetch
    r = analyze(code, fetch(code, period="2y"))
    print(f"{code} 中線分析:")
    for k, v in r.items():
        if k != "_enriched":
            print(f"  {k}: {v}")
    print("\n[注意] 僅為客觀計算,非投資建議。")

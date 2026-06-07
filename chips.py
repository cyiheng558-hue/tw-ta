# -*- coding: utf-8 -*-
"""籌碼面:三大法人買賣超(透過 FinMind 免費 API)。

FinMind 免 token 也能用,但有流量限制(約每小時數百次);
若常用建議到 https://finmindtrade.com 免費註冊拿 token,設環境變數 FINMIND_TOKEN。

回傳「淨買賣超(張)」:外資、投信、自營商,以及合計。
正值=買超(法人買進),負值=賣超。1 張 = 1000 股。
"""
import datetime as _dt
import pandas as pd

from finmind import fm_get, safe

# FinMind 的法人名稱 -> 中文歸類
_FOREIGN = {"Foreign_Investor", "Foreign_Dealer_Self"}
_TRUST = {"Investment_Trust"}
_DEALER = {"Dealer_self", "Dealer_Hedging"}


@safe(pd.DataFrame)
def fetch_institutional(code: str, days: int = 60) -> pd.DataFrame:
    """抓近 days 天三大法人買賣超,回傳以日期為索引的 DataFrame。

    欄位:外資、投信、自營商、合計(單位:張)。抓不到時回傳空表。
    """
    start = (_dt.date.today() - _dt.timedelta(days=days * 2)).isoformat()
    data = fm_get("TaiwanStockInstitutionalInvestorsBuySell", code, start)
    if not data:
        return pd.DataFrame()

    raw = pd.DataFrame(data)
    raw["net"] = (raw["buy"] - raw["sell"]) / 1000.0  # 股 -> 張

    def _group(names):
        sub = raw[raw["name"].isin(names)]
        return sub.groupby("date")["net"].sum()

    out = pd.DataFrame({
        "外資": _group(_FOREIGN),
        "投信": _group(_TRUST),
        "自營商": _group(_DEALER),
    }).fillna(0)
    out["合計"] = out.sum(axis=1)
    out.index = pd.to_datetime(out.index)
    out = out.sort_index().tail(days)
    return out.round(0)


@safe(dict)
def chip_summary(code: str, days: int = 5) -> dict:
    """近 days 日法人動向摘要,給掃描表用。

    回傳 {外資, 投信, 自營商, 合計, 連續買超天數}(單位:張)。
    """
    df = fetch_institutional(code, days=max(days, 20))
    if df.empty:
        return {}
    recent = df.tail(days)
    total = recent["合計"].sum()
    # 計算合計連續買超(>0)天數,從最後一天往回數
    streak = 0
    for v in df["合計"].iloc[::-1]:
        if v > 0:
            streak += 1
        else:
            break
    return {
        "外資": float(recent["外資"].sum()),
        "投信": float(recent["投信"].sum()),
        "自營商": float(recent["自營商"].sum()),
        "合計": float(total),
        "連續買超天數": streak,
    }


@safe(pd.DataFrame)
def cumulative_net(code: str, days: int = 60) -> pd.DataFrame:
    """三大法人合計的累計買賣超(張),看波段籌碼方向(持續流入/流出)。"""
    df = fetch_institutional(code, days=days)
    if df.empty:
        return pd.DataFrame()
    out = pd.DataFrame({"單日合計": df["合計"], "累計": df["合計"].cumsum()})
    return out


@safe(pd.DataFrame)
def foreign_holding(code: str, days: int = 60) -> pd.DataFrame:
    """外資持股比率(%)趨勢。"""
    start = (_dt.date.today() - _dt.timedelta(days=days * 2)).isoformat()
    data = fm_get("TaiwanStockShareholding", code, start)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    out = pd.DataFrame({"外資持股比率": pd.to_numeric(df["ForeignInvestmentSharesRatio"], errors="coerce")})
    out.index = pd.to_datetime(df["date"])
    return out.sort_index().dropna().tail(days)


@safe(dict)
def margin_short_ratio(code: str) -> dict:
    """券資比(%)= 融券餘額 / 融資餘額 * 100。比率高代表空方相對積極。"""
    start = (_dt.date.today() - _dt.timedelta(days=20)).isoformat()
    data = fm_get("TaiwanStockMarginPurchaseShortSale", code, start)
    if not data:
        return {}
    last = pd.DataFrame(data).iloc[-1]
    margin = float(last["MarginPurchaseTodayBalance"])
    short = float(last["ShortSaleTodayBalance"])
    ratio = (short / margin * 100) if margin else 0.0
    return {"融資餘額": margin, "融券餘額": short, "券資比%": round(ratio, 1)}


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    code = sys.argv[1] if len(sys.argv) > 1 else "2330"
    print(f"{code} 近 10 日三大法人買賣超(張):\n")
    df = fetch_institutional(code, days=10)
    if df.empty:
        print("抓不到籌碼資料")
    else:
        print(df.to_string())
        print("\n近 5 日摘要:", chip_summary(code, days=5))
        fh = foreign_holding(code, days=10)
        if not fh.empty:
            print("\n外資持股比率(近5日):")
            print(fh.tail(5).to_string())
        print("\n券資比:", margin_short_ratio(code))

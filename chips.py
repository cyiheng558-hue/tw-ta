# -*- coding: utf-8 -*-
"""籌碼面:三大法人買賣超(透過 FinMind 免費 API)。

FinMind 免 token 也能用,但有流量限制(約每小時數百次);
若常用建議到 https://finmindtrade.com 免費註冊拿 token,設環境變數 FINMIND_TOKEN。

回傳「淨買賣超(張)」:外資、投信、自營商,以及合計。
正值=買超(法人買進),負值=賣超。1 張 = 1000 股。
"""
import os
import datetime as _dt
import pandas as pd
import requests

API = "https://api.finmindtrade.com/api/v4/data"

# FinMind 的法人名稱 -> 中文歸類
_FOREIGN = {"Foreign_Investor", "Foreign_Dealer_Self"}
_TRUST = {"Investment_Trust"}
_DEALER = {"Dealer_self", "Dealer_Hedging"}


def _code_only(code: str) -> str:
    """去掉 .TW/.TWO 後綴,FinMind 只要純代號。"""
    return code.upper().replace(".TWO", "").replace(".TW", "").strip()


def fetch_institutional(code: str, days: int = 60) -> pd.DataFrame:
    """抓近 days 天三大法人買賣超,回傳以日期為索引的 DataFrame。

    欄位:外資、投信、自營商、合計(單位:張)。抓不到時回傳空表。
    """
    start = (_dt.date.today() - _dt.timedelta(days=days * 2)).isoformat()
    params = {
        "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
        "data_id": _code_only(code),
        "start_date": start,
    }
    token = os.environ.get("FINMIND_TOKEN")
    if token:
        params["token"] = token
    try:
        r = requests.get(API, params=params, timeout=20)
        j = r.json()
    except Exception as e:
        print(f"  [籌碼] {code} 抓取失敗:{e}")
        return pd.DataFrame()
    if j.get("msg") != "success" or not j.get("data"):
        return pd.DataFrame()

    raw = pd.DataFrame(j["data"])
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

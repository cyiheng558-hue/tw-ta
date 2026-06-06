# -*- coding: utf-8 -*-
"""個股新聞(FinMind TaiwanStockNews)。

回傳最新新聞:日期、來源、標題、連結。純資訊整理,不做情緒判斷,
新聞內容亦非投資建議,請自行查證。
"""
import os
import datetime as _dt
import pandas as pd
import requests

API = "https://api.finmindtrade.com/api/v4/data"


def _code_only(code: str) -> str:
    return str(code).upper().replace(".TWO", "").replace(".TW", "").strip()


def latest_news(code: str, days: int = 14, limit: int = 20) -> pd.DataFrame:
    """抓近 days 天的個股新聞,回傳含 日期/來源/標題/連結 的 DataFrame(最多 limit 則)。"""
    start = (_dt.date.today() - _dt.timedelta(days=days)).isoformat()
    params = {"dataset": "TaiwanStockNews", "data_id": _code_only(code), "start_date": start}
    token = os.environ.get("FINMIND_TOKEN")
    if token:
        params["token"] = token
    try:
        r = requests.get(API, params=params, timeout=20)
        j = r.json()
    except Exception as e:
        print(f"  [新聞] {code} 抓取失敗:{e}")
        return pd.DataFrame()
    if j.get("msg") != "success" or not j.get("data"):
        return pd.DataFrame()

    df = pd.DataFrame(j["data"])
    df = df.sort_values("date", ascending=False).head(limit)
    out = pd.DataFrame({
        "日期": pd.to_datetime(df["date"]).dt.strftime("%m/%d %H:%M"),
        "來源": df["source"],
        "標題": df["title"],
        "連結": df["link"],
    })
    return out.reset_index(drop=True)


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    code = sys.argv[1] if len(sys.argv) > 1 else "2330"
    df = latest_news(code)
    if df.empty:
        print("抓不到新聞")
    else:
        for _, r in df.iterrows():
            print(f"[{r['日期']}] ({r['來源']}) {r['標題'][:50]}")

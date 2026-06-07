# -*- coding: utf-8 -*-
"""個股新聞 — 改用 Google News RSS(免費、即時、免金鑰)。

原本用 FinMind,但其新聞資料更新嚴重落後(常停在兩三週前),故改用
Google News 搜尋 RSS,以個股名稱為關鍵字,取得最新新聞。

純資訊整理,新聞內容非投資建議,請自行查證。
"""
import datetime as _dt
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET

import pandas as pd
import requests

from fundamentals import load_stock_names

_HDR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
_RSS = "https://news.google.com/rss/search"


def _code_only(code):
    return str(code).upper().replace(".TWO", "").replace(".TW", "").strip()


def _fmt_time(pub: str) -> str:
    """RFC822(GMT)轉台灣時間 'MM/DD HH:MM'。"""
    try:
        dt = parsedate_to_datetime(pub)
        dt = dt.astimezone(_dt.timezone(_dt.timedelta(hours=8)))
        return dt.strftime("%m/%d %H:%M")
    except Exception:
        return pub[:16]


def latest_news(code: str, limit: int = 25, names: dict = None) -> pd.DataFrame:
    """抓個股最新新聞,回傳 日期/來源/標題/連結 DataFrame。"""
    cid = _code_only(code)
    if names is None:
        names = load_stock_names()
    name = names.get(cid, cid)
    query = f"{name} 股"
    params = {"q": query, "hl": "zh-TW", "gl": "TW", "ceid": "TW:zh-Hant"}
    try:
        r = requests.get(_RSS, params=params, headers=_HDR, timeout=20)
        root = ET.fromstring(r.content)
    except Exception as e:
        print(f"  [新聞] {code} 抓取失敗:{e}")
        return pd.DataFrame()

    rows = []
    for it in root.findall(".//item")[:limit]:
        title = it.findtext("title") or ""
        link = it.findtext("link") or ""
        pub = it.findtext("pubDate") or ""
        src_el = it.find("{*}source")
        source = src_el.text if src_el is not None and src_el.text else ""
        # 標題常是「標題 - 來源」,把尾巴來源去掉讓標題乾淨
        if source and title.endswith(f" - {source}"):
            title = title[: -len(f" - {source}")]
        rows.append({"_dt": pub, "日期": _fmt_time(pub), "來源": source,
                     "標題": title.strip(), "連結": link})
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    # 依實際時間排序(新到舊)
    try:
        df["_k"] = df["_dt"].apply(lambda s: parsedate_to_datetime(s))
        df = df.sort_values("_k", ascending=False)
    except Exception:
        pass
    return df[["日期", "來源", "標題", "連結"]].reset_index(drop=True)


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
        for _, r in df.head(12).iterrows():
            print(f"[{r['日期']}] ({r['來源']}) {r['標題'][:46]}")

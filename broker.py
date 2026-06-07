# -*- coding: utf-8 -*-
"""券商分點進出(免費來源:HiStock 網頁爬蟲)。

抓某檔在「當日 / 近N交易日」各券商分點的買賣超排行(買超前幾名 / 賣超前幾名)。
資料來源 HiStock(histock.tw),屬第三方網站爬蟲:
  ⚠ 非官方 API,網站改版或反爬時可能失效;資料僅供參考、非投資建議。

分點(地緣券商/主力券商)買賣超,常被用來推測主力動向,但分點不等於特定人,
且可能有借券、避險等雜訊,請斟酌使用。
"""
import re
import time
import datetime as _dt
import pandas as pd
import requests

from data import fetch

_HDR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
_BASE = "https://histock.tw/stock/branch.aspx"

# 解析每一列分點:券商名稱 / 買張 / 賣張 / 買超 / 均價
_ROW = re.compile(
    r'brokertrace[^>]*>([^<]+)</a></td>'
    r'<td class="hidecell">(-?[\d,]+)</td>'
    r'<td class="hidecell">(-?[\d,]+)</td>'
    r'<td>(-?[\d,]+)</td>'
    r'<td>([\d.]*)</td>'
)


def _code_only(code):
    return str(code).upper().replace(".TWO", "").replace(".TW", "").strip()


def _to_int(s):
    try:
        return int(str(s).replace(",", ""))
    except ValueError:
        return 0


def _latest_trading_day(code) -> _dt.date:
    """用股價資料的最後一筆當作最近交易日。"""
    df = fetch(code, period="1mo")
    if df is not None and not df.empty:
        return df.index[-1].date()
    return _dt.date.today()


def broker_branch(code: str, days: int = 1, top: int = 15) -> dict:
    """抓近 days 交易日的分點買賣超。

    回傳 {"買超": DataFrame, "賣超": DataFrame, "區間": "起~迄"}。
    DataFrame 欄位:券商、買張、賣張、買超(張)、均價。抓不到回傳空 dict。
    """
    cid = _code_only(code)
    end = _latest_trading_day(code)
    # 往前抓足夠日曆天數以涵蓋 days 個交易日(粗略 1.6 倍 + 緩衝)
    start = end - _dt.timedelta(days=max(days * 2 + 4, 5)) if days > 1 else end
    params = {"no": cid, "from": start.strftime("%Y%m%d"), "to": end.strftime("%Y%m%d")}
    html = None
    for attempt in range(3):  # HiStock 偶爾失敗/限流,自動重試
        try:
            r = requests.get(_BASE, params=params, headers=_HDR, timeout=20)
            if r.status_code == 200 and r.text:
                html = r.text
                break
        except Exception as e:
            if attempt == 2:
                print(f"  [分點] {code} 抓取失敗(已重試):{e}")
        time.sleep(1.0 + attempt)
    if not html:
        return {}

    rows = _ROW.findall(html)
    if not rows:
        return {}
    recs = []
    for name, buy, sell, net, avg in rows:
        recs.append({
            "券商": name.strip(),
            "買張": _to_int(buy),
            "賣張": _to_int(sell),
            "買超(張)": _to_int(net),
            "均價": float(avg) if avg else None,
        })
    df = pd.DataFrame(recs).drop_duplicates(subset=["券商"])
    buy_rank = df[df["買超(張)"] > 0].sort_values("買超(張)", ascending=False).head(top).reset_index(drop=True)
    sell_rank = df[df["買超(張)"] < 0].sort_values("買超(張)").head(top).reset_index(drop=True)
    return {
        "買超": buy_rank,
        "賣超": sell_rank,
        "區間": f"{start.isoformat()} ~ {end.isoformat()}" if days > 1 else end.isoformat(),
    }


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    code = sys.argv[1] if len(sys.argv) > 1 else "2330"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    r = broker_branch(code, days=days)
    if not r:
        print("抓不到分點資料(可能網站改版或當日無資料)")
    else:
        print(f"{code} 分點買賣超 區間 {r['區間']}\n")
        print("=== 買超前 10 ===")
        print(r["買超"].head(10).to_string(index=False))
        print("\n=== 賣超前 10 ===")
        print(r["賣超"].head(10).to_string(index=False))

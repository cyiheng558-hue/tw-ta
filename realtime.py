# -*- coding: utf-8 -*-
"""個股即時報價(證交所 MIS 官方即時行情 API)。

來源:https://mis.twse.com.tw —— 官方即時行情,免費。
特性與限制:
  - 只有「交易時間(平日 09:00–13:30)」才會即時跳動;盤後/假日顯示最後成交。
  - 屬近即時(官方本身約數秒~十數秒延遲),非逐筆 tick。
  - 雲端(如 Streamlit Cloud)可能被擋或限流;本機通常正常。
僅為資訊,非投資建議。
"""
import datetime as _dt
import requests
import pandas as pd

_BASE = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
_HDR = {"User-Agent": "Mozilla/5.0", "Referer": "https://mis.twse.com.tw/stock/index.jsp"}


def _code_only(code):
    return str(code).upper().replace(".TWO", "").replace(".TW", "").strip()


def _num(x):
    try:
        return float(x)
    except (ValueError, TypeError):
        return None


def _quote_chunk(cids) -> list:
    """抓一批(不超過 MIS 單次上限)的即時報價,回傳 msgArray。"""
    ex_ch = "|".join([f"tse_{c}.tw|otc_{c}.tw" for c in cids])
    try:
        r = requests.get(_BASE, params={"ex_ch": ex_ch, "json": "1", "delay": "0"},
                         headers=_HDR, timeout=10)
        if r.status_code != 200:
            return []
        j = r.json()
    except Exception as e:
        print(f"  [即時] 抓取失敗:{e}")
        return []
    if j.get("rtcode") != "0000" or not j.get("msgArray"):
        return []
    return j["msgArray"]


def quote(codes) -> pd.DataFrame:
    """抓即時報價(自動分批)。回傳:代號/名稱/成交/漲跌/漲跌%/開/高/低/累積量/時間。"""
    if isinstance(codes, str):
        codes = [codes]
    cids = [_code_only(c) for c in codes]
    # 每批最多 25 檔(× tse/otc = 50 個 ex_ch),分批查避免超過 MIS 單次上限
    msg = []
    for k in range(0, len(cids), 25):
        msg.extend(_quote_chunk(cids[k:k + 25]))
    if not msg:
        return pd.DataFrame()

    rows = []
    for m in msg:
        if not m.get("c"):             # 略過對方交易所回傳的空白項
            continue
        y = _num(m.get("y"))           # 昨收
        z = _num(m.get("z"))           # 當前成交
        if z is None:                  # 尚無成交,退而求其次用開盤/昨收
            z = _num(m.get("o")) or y
        chg = (z - y) if (z is not None and y is not None) else None
        pct = (chg / y * 100) if (chg is not None and y) else None
        rows.append({
            "代號": m.get("c"), "名稱": m.get("n"),
            "成交": round(z, 2) if z is not None else None,
            "漲跌": round(chg, 2) if chg is not None else None,
            "漲跌%": round(pct, 2) if pct is not None else None,
            "開": _num(m.get("o")), "高": _num(m.get("h")), "低": _num(m.get("l")),
            "累積量(張)": int(_num(m.get("v")) or 0),
            "時間": m.get("t"), "日期": m.get("d"),
        })
    return pd.DataFrame(rows)


def index_quote() -> dict:
    """即時大盤指數(加權 t00、櫃買 o00)。回傳 {名稱: {成交, 漲跌%}}。"""
    try:
        r = requests.get(_BASE, params={"ex_ch": "tse_t00.tw|otc_o00.tw",
                         "json": "1", "delay": "0"}, headers=_HDR, timeout=10)
        if r.status_code != 200:
            return {}
        j = r.json()
    except Exception:
        return {}
    out = {}
    for m in j.get("msgArray", []):
        z, y = _num(m.get("z")), _num(m.get("y"))
        pct = (z - y) / y * 100 if (z and y) else None
        nm = "加權指數" if m.get("c") == "t00" else "櫃買指數"
        out[nm] = {"成交": z, "漲跌%": round(pct, 2) if pct is not None else None}
    return out


def quote_detail(code) -> dict:
    """抓單一個股的即時五檔 + 漲跌停。回傳買賣盤、委買委賣量、距漲跌停等。"""
    cid = _code_only(code)
    msg = _quote_chunk([cid])
    m = next((x for x in msg if x.get("c")), None)
    if not m:
        return {}

    def _pairs(price_s, vol_s):
        # 價、量逐格對齊解析,'-'/空值→None;只保留價有效的檔位(避免 ValueError 與錯位)
        ps = [_num(x) for x in (price_s or "").split("_")]
        vs = [_num(x) for x in (vol_s or "").split("_")]
        out = []
        for i, p in enumerate(ps):
            if p is not None:
                out.append((p, vs[i] if i < len(vs) and vs[i] is not None else 0.0))
        return out

    bids = _pairs(m.get("b"), m.get("g"))   # [(價,量), ...] 由高到低
    asks = _pairs(m.get("a"), m.get("f"))
    bid_v = [v for _, v in bids]
    ask_v = [v for _, v in asks]
    z = _num(m.get("z")) or _num(m.get("o")) or _num(m.get("y"))
    y, u, w = _num(m.get("y")), _num(m.get("u")), _num(m.get("w"))
    return {
        "代號": m.get("c"), "名稱": m.get("n"), "成交": z, "昨收": y,
        "漲停": u, "跌停": w,
        "買盤": bids,   # [(價,量), ...] 由高到低
        "賣盤": asks,
        "委買量": sum(bid_v), "委賣量": sum(ask_v),
        "距漲停%": round((u - z) / z * 100, 2) if (u and z) else None,
        "距跌停%": round((z - w) / z * 100, 2) if (w and z) else None,
        "時間": m.get("t"),
    }


def is_market_hours() -> bool:
    """是否為台股交易時間(平日 09:00–13:30,台北時間)。"""
    from tw_time import taipei_now
    now = taipei_now()
    if now.weekday() >= 5:
        return False
    t = now.hour * 60 + now.minute
    return 9 * 60 <= t <= 13 * 60 + 30


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    codes = sys.argv[1:] or ["2330", "6488", "2603"]
    print("交易時間中" if is_market_hours() else "目前非交易時間(顯示最後成交)")
    df = quote(codes)
    print(df.to_string(index=False) if not df.empty else "抓不到報價")

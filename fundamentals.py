# -*- coding: utf-8 -*-
"""基本面 / 籌碼面資料(FinMind):股名、本益比、殖利率、月營收年增率、融資融券。

FinMind 免 token 可用但有流量限制;常用建議註冊拿 token 設環境變數 FINMIND_TOKEN。
股名清單較大,會快取到本地 cache/ 每日更新一次。
"""
import os
import json
import datetime as _dt
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)
API = "https://api.finmindtrade.com/api/v4/data"


def _params(dataset, code=None, start=None):
    p = {"dataset": dataset}
    if code is not None:
        p["data_id"] = str(code).upper().replace(".TWO", "").replace(".TW", "").strip()
    if start:
        p["start_date"] = start
    token = os.environ.get("FINMIND_TOKEN")
    if token:
        p["token"] = token
    return p


def _get(dataset, code=None, start=None, timeout=20):
    try:
        r = requests.get(API, params=_params(dataset, code, start), timeout=timeout)
        j = r.json()
    except Exception as e:
        print(f"  [FinMind] {dataset} {code} 失敗:{e}")
        return []
    if j.get("msg") != "success":
        return []
    return j.get("data", [])


# ---------------- 股票名稱 ----------------
def load_stock_names() -> dict:
    """回傳 {代號: 名稱} 字典(全市場),快取每日更新一次。"""
    today = _dt.date.today().isoformat()
    cache = os.path.join(CACHE_DIR, f"stock_names_{today}.json")
    if os.path.exists(cache):
        try:
            with open(cache, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    data = _get("TaiwanStockInfo", timeout=40)
    names = {}
    for d in data:
        sid = d.get("stock_id", "")
        # 只留 4 碼一般股票,濾掉權證/ETF以外雜項過長代號
        if sid and len(sid) == 4 and sid.isdigit():
            names[sid] = d.get("stock_name", "")
    if names:
        try:
            with open(cache, "w", encoding="utf-8") as f:
                json.dump(names, f, ensure_ascii=False)
        except Exception:
            pass
    return names


def name_of(code: str, names: dict = None) -> str:
    """單檔代號 -> 名稱;查不到回傳代號本身。"""
    if names is None:
        names = load_stock_names()
    key = str(code).upper().replace(".TWO", "").replace(".TW", "").strip()
    return names.get(key, key)


# ---------------- 本益比 / 殖利率 / PBR ----------------
def valuation(code: str) -> dict:
    """最新本益比、殖利率(%)、股價淨值比。抓不到回傳空 dict。"""
    start = (_dt.date.today() - _dt.timedelta(days=15)).isoformat()
    data = _get("TaiwanStockPER", code, start)
    if not data:
        return {}
    last = data[-1]
    return {
        "PER": last.get("PER"),
        "殖利率%": last.get("dividend_yield"),
        "PBR": last.get("PBR"),
        "date": last.get("date"),
    }


# ---------------- 月營收年增率 ----------------
def revenue_yoy(code: str) -> dict:
    """最新月營收與年增率(%)。需比較去年同月,故抓近 ~14 個月。"""
    start = (_dt.date.today() - _dt.timedelta(days=430)).isoformat()
    data = _get("TaiwanStockMonthRevenue", code, start)
    if not data:
        return {}
    df = pd.DataFrame(data)
    # 以 (年,月) 為鍵
    df = df.sort_values(["revenue_year", "revenue_month"])
    last = df.iloc[-1]
    y, m, rev = int(last["revenue_year"]), int(last["revenue_month"]), float(last["revenue"])
    prev = df[(df["revenue_year"] == y - 1) & (df["revenue_month"] == m)]
    yoy = None
    if not prev.empty:
        prev_rev = float(prev.iloc[0]["revenue"])
        if prev_rev:
            yoy = (rev - prev_rev) / prev_rev * 100
    return {
        "營收月份": f"{y}/{m:02d}",
        "營收(億)": round(rev / 1e8, 1),
        "年增率%": round(yoy, 1) if yoy is not None else None,
    }


# ---------------- 融資融券 ----------------
def margin_short(code: str, days: int = 20) -> pd.DataFrame:
    """近 days 日融資/融券餘額(張)。回傳含 融資餘額、融券餘額 的 DataFrame。"""
    start = (_dt.date.today() - _dt.timedelta(days=days * 2)).isoformat()
    data = _get("TaiwanStockMarginPurchaseShortSale", code, start)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    out = pd.DataFrame({
        "融資餘額": df["MarginPurchaseTodayBalance"],
        "融券餘額": df["ShortSaleTodayBalance"],
    })
    out.index = pd.to_datetime(df["date"])
    return out.sort_index().tail(days)


def margin_summary(code: str) -> dict:
    """融資近 5 日增減(張):正=散戶加碼(籌碼偏亂),負=融資減少。"""
    df = margin_short(code, days=10)
    if df.empty or len(df) < 6:
        return {}
    chg5 = float(df["融資餘額"].iloc[-1] - df["融資餘額"].iloc[-6])
    return {
        "融資餘額": float(df["融資餘額"].iloc[-1]),
        "融資5日增減": chg5,
        "融券餘額": float(df["融券餘額"].iloc[-1]),
    }


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    code = sys.argv[1] if len(sys.argv) > 1 else "2330"
    print(f"{code} {name_of(code)}")
    print("  估值:", valuation(code))
    print("  營收:", revenue_yoy(code))
    print("  融資券:", margin_summary(code))

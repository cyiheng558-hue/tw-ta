# -*- coding: utf-8 -*-
"""基本面 / 籌碼面資料(FinMind):股名、本益比、殖利率、月營收年增率、融資融券。

FinMind 免 token 可用但有流量限制;常用建議註冊拿 token 設環境變數 FINMIND_TOKEN。
股名清單較大,會快取到本地 cache/ 每日更新一次。
"""
import os
import json
import datetime as _dt
import pandas as pd

from finmind import fm_get

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def _get(dataset, code=None, start=None, timeout=20):
    """改走共用快取層(fm_get),同一天同查詢只打一次 API。"""
    return fm_get(dataset, code, start, timeout)


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


def load_industry() -> dict:
    """回傳 {代號: 產業類別},快取每日更新一次。"""
    today = _dt.date.today().isoformat()
    cache = os.path.join(CACHE_DIR, f"stock_industry_{today}.json")
    if os.path.exists(cache):
        try:
            with open(cache, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    data = _get("TaiwanStockInfo", timeout=40)
    ind = {}
    for d in data:
        sid = d.get("stock_id", "")
        if sid and len(sid) == 4 and sid.isdigit():
            ind[sid] = d.get("industry_category", "")
    if ind:
        try:
            with open(cache, "w", encoding="utf-8") as f:
                json.dump(ind, f, ensure_ascii=False)
        except Exception:
            pass
    return ind


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


# ---------------- 財報:EPS / 毛利率 / 營益率 / 淨利率 / ROE ----------------
def financials(code: str) -> dict:
    """最新一季獲利能力 + 近四季(TTM)EPS/ROE。抓不到回傳空 dict。"""
    start = (_dt.date.today() - _dt.timedelta(days=620)).isoformat()  # 約 5 季
    data = _get("TaiwanStockFinancialStatements", code, start)
    if not data:
        return {}
    df = pd.DataFrame(data)
    # 樞紐:每季一列,科目為欄
    piv = df.pivot_table(index="date", columns="type", values="value", aggfunc="first").sort_index()
    if piv.empty:
        return {}
    last = piv.iloc[-1]

    def pct(numer, denom):
        rev = last.get(denom)
        v = last.get(numer)
        if rev and pd.notna(rev) and pd.notna(v) and rev != 0:
            return round(float(v) / float(rev) * 100, 1)
        return None

    out = {
        "季別": str(piv.index[-1]),
        "毛利率%": pct("GrossProfit", "Revenue"),
        "營益率%": pct("OperatingIncome", "Revenue"),
        "淨利率%": pct("IncomeAfterTaxes", "Revenue"),
        "單季EPS": round(float(last["EPS"]), 2) if "EPS" in last and pd.notna(last.get("EPS")) else None,
    }
    # 近四季 EPS 合計(TTM)
    if "EPS" in piv.columns:
        eps_ttm = piv["EPS"].dropna().tail(4).sum()
        out["近四季EPS"] = round(float(eps_ttm), 2)
    # ROE(TTM):近四季稅後淨利 / 最新股東權益
    bs = _get("TaiwanStockBalanceSheet", code, start)
    if bs and "IncomeAfterTaxes" in piv.columns:
        bdf = pd.DataFrame(bs)
        eq = bdf[bdf["type"] == "Equity"].sort_values("date")
        ni_ttm = piv["IncomeAfterTaxes"].dropna().tail(4).sum()
        if not eq.empty:
            equity = float(eq.iloc[-1]["value"])
            if equity:
                out["ROE_TTM%"] = round(float(ni_ttm) / equity * 100, 1)
    return out


# ---------------- 配息歷史 ----------------
def dividend_history(code: str) -> dict:
    """近年現金股利與連續配息年數。"""
    data = _get("TaiwanStockDividend", code, start="2014-01-01")
    if not data:
        return {}
    df = pd.DataFrame(data)
    # 以股利所屬年度彙總現金股利(同年可能分次)
    df["cash"] = pd.to_numeric(df.get("CashEarningsDistribution", 0), errors="coerce").fillna(0) \
        + pd.to_numeric(df.get("CashStatutorySurplus", 0), errors="coerce").fillna(0)
    # year 形如 "114年第4季" 或 "2025" ,取前面數字當年度群組
    df["yr"] = df["year"].astype(str).str.extract(r"(\d+)").astype(float)
    by_year = df.groupby("yr")["cash"].sum().sort_index()
    by_year = by_year[by_year > 0]
    if by_year.empty:
        return {}
    # 連續配息年數:從最近年度往回數連續 > 0
    streak = 0
    for v in by_year.iloc[::-1]:
        if v > 0:
            streak += 1
        else:
            break
    recent = {str(int(y)): round(float(c), 2) for y, c in by_year.tail(6).items()}
    return {"連續配息年數": streak, "近年現金股利": recent,
            "最近年度現金股利": round(float(by_year.iloc[-1]), 2)}


# ---------------- 月營收趨勢(近12月) ----------------
def revenue_trend(code: str) -> pd.DataFrame:
    """近 ~13 個月營收 + 年增率,回傳 DataFrame(月份索引)。"""
    start = (_dt.date.today() - _dt.timedelta(days=800)).isoformat()
    data = _get("TaiwanStockMonthRevenue", code, start)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data).sort_values(["revenue_year", "revenue_month"])
    df["月份"] = df["revenue_year"].astype(str) + "/" + df["revenue_month"].astype(int).map(lambda m: f"{m:02d}")
    df["營收億"] = df["revenue"] / 1e8
    df["年增率%"] = df.groupby("revenue_month")["revenue"].pct_change() * 100  # 同月年比
    out = df[["月份", "營收億", "年增率%"]].tail(13).copy()
    out["營收億"] = out["營收億"].round(1)
    out["年增率%"] = out["年增率%"].round(1)
    return out.set_index("月份")


# ---------------- 本益比評價(歷史 percentile) ----------------
def pe_valuation(code: str) -> dict:
    """用近 ~3 年本益比算現在落在哪個區間(percentile),判斷相對貴/便宜。"""
    start = (_dt.date.today() - _dt.timedelta(days=1100)).isoformat()
    data = _get("TaiwanStockPER", code, start)
    if not data:
        return {}
    df = pd.DataFrame(data)
    per = pd.to_numeric(df["PER"], errors="coerce").dropna()
    per = per[per > 0]
    if len(per) < 30:
        return {}
    cur = float(per.iloc[-1])
    pct_rank = float((per < cur).mean() * 100)
    if pct_rank >= 80:
        label = "偏貴(近3年高檔)"
    elif pct_rank >= 60:
        label = "略高"
    elif pct_rank <= 20:
        label = "偏便宜(近3年低檔)"
    elif pct_rank <= 40:
        label = "略低"
    else:
        label = "合理區間"
    return {"目前本益比": round(cur, 1), "近3年百分位": round(pct_rank, 0),
            "評價": label, "近3年最低": round(float(per.min()), 1),
            "近3年最高": round(float(per.max()), 1)}


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
    print("  財報:", financials(code))
    print("  配息:", dividend_history(code))
    print("  本益比評價:", pe_valuation(code))

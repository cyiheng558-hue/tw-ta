# -*- coding: utf-8 -*-
"""FinMind API 共用抓取層 + 本地磁碟快取。

所有要打 FinMind 的模組(chips / fundamentals / news / score)都改用這裡的
fm_get(),好處:
  1. 同一天、同一個查詢只會真的打一次 API,之後讀本地快取 → 大幅減少請求數。
  2. 綜合評分與各區塊共用同一份快取,不會重複打。
  3. 自動帶上環境變數 FINMIND_TOKEN(有設的話額度更高)。

快取存在 cache/finmind/,每日自動清掉舊檔。失敗(含流量上限)不會被快取,
下次會重試。
"""
import os
import json
import time
import hashlib
import functools
import requests

from tw_time import taipei_today


def safe(default):
    """裝飾器:函式內出例外(如 FinMind 改欄位 KeyError)時,印警告並回傳預設值,
    避免單一資料異常讓整個頁面/掃描崩潰。default 可為值或回傳值的 callable。"""
    def deco(fn):
        @functools.wraps(fn)
        def wrap(*a, **k):
            try:
                return fn(*a, **k)
            except Exception as e:
                print(f"  [{fn.__name__}] 資料異常,降級:{e}")
                return default() if callable(default) else default
        return wrap
    return deco

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, "cache", "finmind")
os.makedirs(CACHE_DIR, exist_ok=True)
API = "https://api.finmindtrade.com/api/v4/data"


def _code_only(code):
    if code is None:
        return None
    return str(code).upper().replace(".TWO", "").replace(".TW", "").strip()


def _cache_path(params: dict) -> str:
    raw = json.dumps(params, sort_keys=True, ensure_ascii=False)
    h = hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]
    today = taipei_today().isoformat()
    return os.path.join(CACHE_DIR, f"{today}_{h}.json")


def _clean_old():
    today = taipei_today().isoformat()
    try:
        for fn in os.listdir(CACHE_DIR):
            if fn.endswith(".json") and not fn.startswith(today):
                try:
                    os.remove(os.path.join(CACHE_DIR, fn))
                except OSError:
                    pass
    except OSError:
        pass


def fm_get(dataset: str, data_id=None, start_date=None, timeout: int = 20,
           use_cache: bool = True) -> list:
    """抓 FinMind 一個 dataset,回傳 data 清單(失敗回空清單)。"""
    params = {"dataset": dataset}
    cid = _code_only(data_id)
    if cid is not None:
        params["data_id"] = cid
    if start_date:
        params["start_date"] = start_date

    cp = _cache_path(params)  # 快取鍵不含 token,確保共用
    if use_cache and os.path.exists(cp):
        try:
            with open(cp, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    req = dict(params)
    token = os.environ.get("FINMIND_TOKEN")
    if token:
        req["token"] = token

    # 自動重試:只對網路逾時/連線錯誤/伺服器忙碌(5xx)/限流(429)重試;4xx 直接放棄
    j = None
    for attempt in range(3):
        try:
            r = requests.get(API, params=req, timeout=timeout)
            if r.status_code == 200:
                j = r.json()
                break
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                wait = r.headers.get("Retry-After")
                time.sleep(float(wait) if wait and wait.isdigit() else 1.0 + attempt)
                continue
            if r.status_code in (402, 403):  # 權限/付費層級
                print(f"  [FinMind] {dataset} 需更高權限(HTTP {r.status_code},建議設 FINMIND_TOKEN)")
            return []
        except Exception as e:
            if attempt < 2:
                time.sleep(1.0 + attempt)
                continue
            print(f"  [FinMind] {dataset} {cid} 連線失敗(已重試):{e}")
            return []

    if not j or j.get("msg") != "success":
        msg = (j or {}).get("msg", "")
        if any(k in msg.lower() for k in ("level", "limit", "402")):
            print(f"  [FinMind] 流量/權限限制:{dataset} {cid}(建議設 FINMIND_TOKEN)")
        return []

    data = j.get("data", [])
    if use_cache and data:
        _clean_old()
        try:
            with open(cp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass
    return data


def has_token() -> bool:
    return bool(os.environ.get("FINMIND_TOKEN"))


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("FINMIND_TOKEN 已設定:" , has_token())
    d = fm_get("TaiwanStockPER", "2330", "2026-05-25")
    print("測試抓取 PER 筆數:", len(d))
    d2 = fm_get("TaiwanStockPER", "2330", "2026-05-25")  # 應命中快取
    print("第二次(快取)筆數:", len(d2))

# -*- coding: utf-8 -*-
"""台股股價資料抓取(yfinance)+ 本地快取 + 平行下載。

注意:yfinance 為免費延遲資料(約 15 分鐘延遲),日線收盤,
適合技術分析,但非即時報價,請勿用於當沖即時下單。

快取:同一天、同一檔、同一期間的資料只會下載一次,存在 cache/ 目錄,
之後重複掃描直接讀本地檔,大幅加速。想強制更新可刪 cache/ 或傳 use_cache=False。
"""
import os
import time

import pandas as pd
import yfinance as yf

from tw_time import taipei_today

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def to_yahoo_symbol(code: str) -> str:
    """台股代號轉 yahoo 格式。4 碼數字預設 .TW(上市);上櫃請傳 6488.TWO。"""
    code = code.strip().upper()
    if code.startswith("^") or code.endswith(".TW") or code.endswith(".TWO"):
        return code  # 指數(如 ^TWII)或已含後綴者原樣返回
    return f"{code}.TW"


def _cache_path(code: str, period: str) -> str:
    safe = code.replace(".", "_")
    today = taipei_today().isoformat()
    return os.path.join(CACHE_DIR, f"{safe}_{period}_{today}.pkl")


def _clean_old_cache(keep_today: bool = True):
    """刪掉非今天的舊快取,避免目錄無限長大。"""
    today = taipei_today().isoformat()
    for fn in os.listdir(CACHE_DIR):
        if fn.endswith(".pkl") and today not in fn:
            try:
                os.remove(os.path.join(CACHE_DIR, fn))
            except OSError:
                pass


def fetch(code: str, period: str = "6mo", interval: str = "1d",
          use_cache: bool = True) -> pd.DataFrame:
    """抓單一個股日線。回傳含 OHLCV 的 DataFrame(可能為空)。"""
    cp = _cache_path(code, period)
    if use_cache and os.path.exists(cp):
        try:
            return pd.read_pickle(cp)
        except Exception:
            pass  # 快取壞掉就重抓

    sym = to_yahoo_symbol(code)
    df = None
    for attempt in range(3):  # yfinance 偶爾失敗,自動重試
        try:
            df = yf.download(sym, period=period, interval=interval,
                             progress=False, auto_adjust=True, threads=False)
            if df is not None and not df.empty:
                break
        except Exception:
            pass
        if attempt < 2:
            time.sleep(1.0 + attempt)
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    if use_cache and not df.empty:
        try:
            df.to_pickle(cp)
        except Exception:
            pass
    return df


def fetch_many(codes, period: str = "6mo", use_cache: bool = True,
               batch: int = 40, progress_cb=None) -> dict:
    """批次抓多檔(一次請求帶多個代號,較不會被 yahoo 限流)。

    先讀今日快取,只對未快取者發批次請求;結果拆檔快取。
    progress_cb(done, total) 可選,用於 UI 進度條。
    回傳 {代號: DataFrame},失敗者略過,順序同輸入。
    """
    _clean_old_cache()
    codes = list(codes)
    out = {}
    todo = []
    # 先吃快取
    for c in codes:
        cp = _cache_path(c, period)
        if use_cache and os.path.exists(cp):
            try:
                out[c] = pd.read_pickle(cp)
                continue
            except Exception:
                pass
        todo.append(c)

    done = len(out)
    total = len(codes)
    if progress_cb:
        progress_cb(done, total)

    # 未快取者分批次,一次請求帶多檔
    for start in range(0, len(todo), batch):
        chunk = todo[start:start + batch]
        sym_map = {to_yahoo_symbol(c): c for c in chunk}
        try:
            raw = yf.download(list(sym_map.keys()), period=period, interval="1d",
                              progress=False, auto_adjust=True, group_by="ticker",
                              threads=True)
        except Exception as e:
            print(f"  [批次失敗] {chunk}: {e}")
            raw = None
        for sym, code in sym_map.items():
            df = pd.DataFrame()
            try:
                if raw is not None and isinstance(raw.columns, pd.MultiIndex) and sym in raw.columns.get_level_values(0):
                    sub = raw[sym][["Open", "High", "Low", "Close", "Volume"]].dropna()
                    df = sub
                elif raw is not None and not isinstance(raw.columns, pd.MultiIndex) and len(sym_map) == 1:
                    df = raw[["Open", "High", "Low", "Close", "Volume"]].dropna()
            except Exception:
                df = pd.DataFrame()
            if not df.empty:
                out[code] = df
                if use_cache:
                    try:
                        df.to_pickle(_cache_path(code, period))
                    except Exception:
                        pass
            done += 1
            if progress_cb:
                progress_cb(done, total)

    return {c: out[c] for c in codes if c in out}

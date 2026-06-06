# -*- coding: utf-8 -*-
"""主程式:掃描觀察清單,列出出現短線技術訊號的個股。

用法:
    python scan.py                      # 掃描 watchlist.txt
    python scan.py 2330 2454 2603       # 掃描指定代號
    python scan.py --bullish-only       # 只看有看多訊號的
    python scan.py --period 1y          # 抓更長歷史

免責:輸出僅為技術指標的客觀計算結果,屬於資訊整理,
非投資建議,不保證準確或獲利。實際下單請自行判斷並承擔風險。
"""
import argparse
import os
import sys

# Windows 主控台預設 cp950,強制改 UTF-8 以免中文亂碼 / emoji 編碼錯誤
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from data import fetch_many
from indicators import enrich
from signals import scan_one

HERE = os.path.dirname(os.path.abspath(__file__))


def load_watchlist(path: str):
    """讀取 watchlist.txt,去掉註解與空行,只取代號。"""
    codes = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.split("#")[0].strip()
            if line:
                codes.append(line)
    return codes


def main():
    p = argparse.ArgumentParser(description="台股短線技術訊號掃描器")
    p.add_argument("codes", nargs="*", help="股票代號(不給則讀 watchlist.txt)")
    p.add_argument("--period", default="6mo", help="抓取期間,如 3mo/6mo/1y")
    p.add_argument("--bullish-only", action="store_true", help="只顯示有看多訊號者")
    args = p.parse_args()

    if args.codes:
        codes = args.codes
    else:
        codes = load_watchlist(os.path.join(HERE, "watchlist.txt"))

    print(f"抓取 {len(codes)} 檔資料中(yfinance 延遲約15分鐘)...\n")
    data = fetch_many(codes, period=args.period)

    rows = []
    for code, df in data.items():
        if len(df) < 60:  # 資料太短算不出 MA60
            continue
        edf = enrich(df)
        bull, bear = scan_one(edf)
        last = edf.iloc[-1]
        close = float(last["Close"])
        # 當日漲跌幅
        prev_close = float(edf["Close"].iloc[-2])
        chg = (close - prev_close) / prev_close * 100
        rows.append({
            "code": code, "close": close, "chg": chg,
            "bull": bull, "bear": bear,
            "score": len(bull) - len(bear),
        })

    # 依看多訊號數量排序
    rows.sort(key=lambda r: (len(r["bull"]), r["score"]), reverse=True)

    print("=" * 70)
    print(f"{'代號':<8}{'收盤':>9}{'漲跌%':>8}  訊號")
    print("=" * 70)
    for r in rows:
        if args.bullish_only and not r["bull"]:
            continue
        sig = " / ".join(r["bull"]) if r["bull"] else "—"
        if r["bear"]:
            sig += "  [警示] " + " / ".join(r["bear"])
        print(f"{r['code']:<8}{r['close']:>9.1f}{r['chg']:>+7.1f}%  {sig}")
    print("=" * 70)

    n_bull = sum(1 for r in rows if r["bull"])
    print(f"\n共 {len(rows)} 檔成功分析,其中 {n_bull} 檔出現看多訊號。")
    print("[注意] 以上為技術指標客觀計算,非投資建議,請自行評估風險。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)

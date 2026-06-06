# -*- coding: utf-8 -*-
"""每日自動掃描:掃描觀察清單,整理出現看多訊號的個股,存報告並寄 Email。

手動執行:
    python daily_scan.py

排程(每個交易日收盤後自動跑)— Windows 工作排程器:
    1. 開「工作排程器」→ 建立基本工作
    2. 觸發程序:每天 14:30(台股收盤後)
    3. 動作:啟動程式
       程式:python   (或 python 完整路徑)
       引數:"C:\\...\\tw_ta\\daily_scan.py"
       開始位置:C:\\...\\tw_ta
    4. 若要收 Email,先設好 notify.py 說明的環境變數(系統環境變數)。

報告會存到 reports\\YYYY-MM-DD.txt。
"""
import os
import datetime as _dt

from data import fetch_many
from indicators import enrich
from signals import scan_one
from fundamentals import load_stock_names
from notify import send_email, email_configured
from swing import analyze as swing_analyze

HERE = os.path.dirname(os.path.abspath(__file__))
REPORT_DIR = os.path.join(HERE, "reports")
os.makedirs(REPORT_DIR, exist_ok=True)


def load_watchlist():
    path = os.path.join(HERE, "watchlist.txt")
    codes = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.split("#")[0].strip()
                if line:
                    codes.append(line)
    return codes


def build_report() -> str:
    codes = load_watchlist()
    names = load_stock_names()
    today = _dt.date.today().isoformat()

    # 短線:用 6 個月資料掃當日訊號
    data = fetch_many(codes, period="6mo")
    bull_lines, warn_lines = [], []
    for code, df in data.items():
        if len(df) < 60:
            continue
        e = enrich(df)
        bull, bear = scan_one(e)
        nm = names.get(code, "")
        close = float(e["Close"].iloc[-1])
        chg = (close - float(e["Close"].iloc[-2])) / float(e["Close"].iloc[-2]) * 100
        if bull:
            bull_lines.append(f"  {code} {nm} {close:.1f} ({chg:+.1f}%)：{' / '.join(bull)}")
        if bear:
            warn_lines.append(f"  {code} {nm} {close:.1f}：{' / '.join(bear)}")

    # 中線:用 2 年資料判趨勢,挑出多頭且有中線訊號者
    swing_data = fetch_many(codes, period="2y")
    swing_bull, swing_signal_lines = [], []
    for code, df in swing_data.items():
        r = swing_analyze(code, df)
        if "error" in r:
            continue
        nm = names.get(code, "")
        if r["趨勢"] in ("多頭", "偏多"):
            swing_bull.append(f"  {code} {nm} {r['收盤']}  [{r['趨勢']}]")
        if r["中線訊號"]:
            swing_signal_lines.append(f"  {code} {nm} {r['收盤']} [{r['趨勢']}]：{' / '.join(r['中線訊號'])}")

    parts = [f"台股每日訊號報告 {today}", "=" * 50]
    parts.append(f"\n■ 短線(當日技術訊號)")
    parts.append(f"\n【看多訊號】({len(bull_lines)} 檔)")
    parts.extend(bull_lines or ["  (無)"])
    parts.append(f"\n【警示訊號】({len(warn_lines)} 檔)")
    parts.extend(warn_lines or ["  (無)"])
    parts.append("\n" + "-" * 50)
    parts.append(f"\n■ 中線(波段趨勢)")
    parts.append(f"\n【出現中線訊號】({len(swing_signal_lines)} 檔)")
    parts.extend(swing_signal_lines or ["  (無)"])
    parts.append(f"\n【中線趨勢偏多以上】({len(swing_bull)} 檔)")
    parts.extend(swing_bull or ["  (無)"])
    parts.append("\n" + "=" * 50)
    parts.append("資料延遲約15分鐘日線。本報告為技術指標客觀計算,非投資建議,請自行評估風險。")
    return "\n".join(parts)


def main():
    report = build_report()
    print(report)
    today = _dt.date.today().isoformat()
    path = os.path.join(REPORT_DIR, f"{today}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n報告已存:{path}")
    if email_configured():
        send_email(f"台股每日訊號 {today}", report)
    else:
        print("(未設定 Email,僅存檔。設定方式見 notify.py)")


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()

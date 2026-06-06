# -*- coding: utf-8 -*-
"""畫單一個股的技術分析圖(收盤+均線+布林、KD、MACD、量能)。

用法:
    python plot.py 2330            # 存成 2330.png 並開啟
    python plot.py 2603 --period 1y
"""
import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")  # 只存檔不開視窗,跨環境最穩
import matplotlib.pyplot as plt

from data import fetch
from indicators import enrich
from signals import scan_one

# 嘗試用支援中文的字型(Windows 內建微軟正黑體),失敗就用預設
for font in ["Microsoft JhengHei", "Microsoft YaHei", "DejaVu Sans"]:
    try:
        plt.rcParams["font.sans-serif"] = [font]
        plt.rcParams["axes.unicode_minus"] = False
        break
    except Exception:
        continue

HERE = os.path.dirname(os.path.abspath(__file__))


def plot(code: str, period: str = "6mo"):
    df = fetch(code, period=period)
    if df.empty or len(df) < 60:
        print(f"{code}: 資料不足,無法繪圖")
        return
    e = enrich(df)
    bull, bear = scan_one(e)

    fig, (ax1, ax2, ax3) = plt.subplots(
        3, 1, figsize=(12, 9), sharex=True,
        gridspec_kw={"height_ratios": [3, 1, 1]},
    )

    # 主圖:收盤 + 均線 + 布林
    ax1.plot(e.index, e["Close"], label="收盤", color="black", linewidth=1.2)
    for n, lbl, c in [(5, "5日線", "orange"), (20, "月線(20)", "blue"), (60, "季線(60)", "purple")]:
        ax1.plot(e.index, e[f"MA{n}"], label=lbl, linewidth=0.9, color=c)
    ax1.fill_between(e.index, e["BB_UP"], e["BB_LOW"], color="gray", alpha=0.12, label="布林通道")
    title = f"{code}  收盤 {e['Close'].iloc[-1]:.1f}"
    if bull:
        title += "   看多: " + " / ".join(bull)
    if bear:
        title += "   警示: " + " / ".join(bear)
    ax1.set_title(title, fontsize=11)
    ax1.legend(loc="upper left", fontsize=8, ncol=3)
    ax1.grid(alpha=0.3)

    # KD
    ax2.plot(e.index, e["K"], label="K值", color="orange", linewidth=0.9)
    ax2.plot(e.index, e["D"], label="D值", color="blue", linewidth=0.9)
    ax2.axhline(80, color="red", linestyle="--", linewidth=0.6)
    ax2.axhline(20, color="green", linestyle="--", linewidth=0.6)
    ax2.set_ylabel("KD")
    ax2.legend(loc="upper left", fontsize=8)
    ax2.grid(alpha=0.3)

    # MACD 柱狀體
    colors = ["red" if v >= 0 else "green" for v in e["HIST"]]
    ax3.bar(e.index, e["HIST"], color=colors, width=1.0)
    ax3.plot(e.index, e["DIF"], label="DIF差離值", color="black", linewidth=0.8)
    ax3.plot(e.index, e["MACD"], label="訊號線", color="orange", linewidth=0.8)
    ax3.set_ylabel("MACD")
    ax3.legend(loc="upper left", fontsize=8)
    ax3.grid(alpha=0.3)

    fig.tight_layout()
    out = os.path.join(HERE, f"{code}.png")
    fig.savefig(out, dpi=110)
    plt.close(fig)
    print(f"已存圖:{out}")
    # 在 Windows 用預設看圖程式開啟
    try:
        os.startfile(out)  # noqa: only exists on Windows
    except Exception:
        pass


def main():
    p = argparse.ArgumentParser(description="台股個股技術分析圖")
    p.add_argument("code", help="股票代號,如 2330")
    p.add_argument("--period", default="6mo", help="期間,如 3mo/6mo/1y")
    args = p.parse_args()
    plot(args.code, args.period)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()

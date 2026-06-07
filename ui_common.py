# -*- coding: utf-8 -*-
"""UI 共用層:快取包裝、輔助函式、常數、即時報價、共用圖表 helper。

抽離自 app.py 以縮小主檔、集中重複邏輯。本模組只定義函式/常數,
不在 import 時渲染任何畫面,故可安全在 set_page_config 之後 import。
"""
import os
import io

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from data import fetch, fetch_many
from indicators import enrich
from fundamentals import (load_stock_names, load_industry, valuation, revenue_yoy,
                          margin_short, financials, dividend_history, revenue_trend,
                          pe_valuation, financials_history)
from chips import (fetch_institutional, chip_summary, cumulative_net,
                   foreign_holding, margin_short_ratio)
from news import latest_news
from score import composite
from broker import broker_branch
from sector import sector_strength
from futures import futures_net_oi, summary as fut_summary
from market import index_status, inst_total
from realtime import quote as rt_quote, is_market_hours
from swing import analyze as swing_analyze, scan_swing, backtest_swing

HERE = os.path.dirname(os.path.abspath(__file__))
WATCHLIST = os.path.join(HERE, "watchlist.txt")

__all__ = [
    "PLOTLY_CONFIG", "CHART_CONFIG", "INST_COLORS",
    "c_fetch", "c_fetch_many", "c_names", "c_industry", "c_chips", "c_chip_summary",
    "c_valuation", "c_revenue", "c_margin", "c_swing", "c_scan_swing", "c_swing_bt",
    "c_financials", "c_fin_hist", "c_dividend", "c_rev_trend", "c_pe_val",
    "c_cum_net", "c_foreign_hold", "c_margin_ratio", "c_news", "c_broker",
    "c_sector", "c_fut_oi", "c_fut_summary", "c_index_status", "c_inst_total", "c_score",
    "load_watchlist", "save_watchlist", "to_excel_bytes", "date_breaks",
    "cn_ohlc_hover", "jump_to_stock", "styled_table", "color_updown",
    "live_quote_panel", "hbar_sector",
]

# 三大法人配色(集中常數,避免各處重複硬寫)
INST_COLORS = {"外資": "#d62728", "投信": "#1f77b4", "自營商": "#2ca02c",
               "三大法人合計": "#000000"}

# Plotly 工具列繁體中文化
PLOTLY_CONFIG = {
    "locale": "zh-TW",
    "displaylogo": False,
    "locales": {
        "zh-TW": {
            "dictionary": {
                "Download plot as a png": "下載為 PNG 圖檔",
                "Download plot": "下載圖檔",
                "Zoom": "縮放",
                "Pan": "平移",
                "Box Select": "方框選取",
                "Lasso Select": "套索選取",
                "Zoom in": "放大",
                "Zoom out": "縮小",
                "Autoscale": "自動縮放",
                "Reset axes": "重設座標軸",
                "Reset view": "重設檢視",
                "Toggle Spike Lines": "切換指示線",
                "Show closest data on hover": "懸停顯示最接近的資料點",
                "Compare data on hover": "懸停比較同日資料",
                "Toggle show closest data on hover": "切換懸停最近資料",
                "Double-click to zoom back out": "雙擊縮回原狀",
                "Click to enter Pan mode": "點擊進入平移模式",
                "Produced with Plotly.js": "由 Plotly.js 製作",
            },
            "format": {},
        }
    },
}

# K線圖專用:繁中工具列 + 畫線工具
CHART_CONFIG = dict(PLOTLY_CONFIG, modeBarButtonsToAdd=[
    "drawline", "drawopenpath", "drawrect", "eraseshape"])


# ===================== 快取層 =====================
@st.cache_data(ttl=3600, show_spinner=False)  # 日線一天才更新,快取 1 小時
def c_fetch(code, period):
    return fetch(code, period=period)


@st.cache_data(ttl=3600, show_spinner=False)
def c_fetch_many(codes, period):
    return fetch_many(list(codes), period=period)


@st.cache_data(ttl=86400, show_spinner=False)
def c_names():
    return load_stock_names()


@st.cache_data(ttl=86400, show_spinner=False)
def c_industry():
    return load_industry()


@st.cache_data(ttl=1800, show_spinner=False)
def c_chips(code, days):
    return fetch_institutional(code, days=days)


@st.cache_data(ttl=1800, show_spinner=False)
def c_chip_summary(code, days):
    return chip_summary(code, days=days)


@st.cache_data(ttl=1800, show_spinner=False)
def c_valuation(code):
    return valuation(code)


@st.cache_data(ttl=1800, show_spinner=False)
def c_revenue(code):
    return revenue_yoy(code)


@st.cache_data(ttl=1800, show_spinner=False)
def c_margin(code, days):
    return margin_short(code, days=days)


@st.cache_data(ttl=1800, show_spinner=False)
def c_swing(code, period):
    return swing_analyze(code, c_fetch(code, period), period=period)


@st.cache_data(ttl=1800, show_spinner=False)
def c_scan_swing(codes, only_bull):
    return scan_swing(list(codes), only_bull=only_bull)


@st.cache_data(ttl=1800, show_spinner=False)
def c_swing_bt(code, hold, sl, tp):
    return backtest_swing(c_fetch(code, "5y"), hold_days=hold, stop_loss=sl, take_profit=tp)


@st.cache_data(ttl=1800, show_spinner=False)
def c_financials(code):
    return financials(code)


@st.cache_data(ttl=1800, show_spinner=False)
def c_fin_hist(code):
    return financials_history(code)


@st.cache_data(ttl=1800, show_spinner=False)
def c_dividend(code):
    return dividend_history(code)


@st.cache_data(ttl=1800, show_spinner=False)
def c_rev_trend(code):
    return revenue_trend(code)


@st.cache_data(ttl=1800, show_spinner=False)
def c_pe_val(code):
    return pe_valuation(code)


@st.cache_data(ttl=1800, show_spinner=False)
def c_cum_net(code, days):
    return cumulative_net(code, days)


@st.cache_data(ttl=1800, show_spinner=False)
def c_foreign_hold(code, days):
    return foreign_holding(code, days)


@st.cache_data(ttl=1800, show_spinner=False)
def c_margin_ratio(code):
    return margin_short_ratio(code)


@st.cache_data(ttl=300, show_spinner=False)  # 新聞快取 5 分鐘
def c_news(code, extra=""):
    return latest_news(code, extra=extra)


@st.cache_data(ttl=300, show_spinner=False)  # 盤後即時報價快取 5 分鐘
def c_quote_off(code):
    return rt_quote([code])


@st.cache_data(ttl=1800, show_spinner=False)
def c_broker(code, days):
    return broker_branch(code, days=days)


@st.cache_data(ttl=1800, show_spinner=False)
def c_sector(codes, days):
    return sector_strength(list(codes), days=days)


@st.cache_data(ttl=1800, show_spinner=False)
def c_fut_oi(days):
    return futures_net_oi(days=days)


@st.cache_data(ttl=1800, show_spinner=False)
def c_fut_summary():
    return fut_summary()


@st.cache_data(ttl=1800, show_spinner=False)
def c_index_status():
    return index_status()


@st.cache_data(ttl=1800, show_spinner=False)
def c_inst_total(days):
    return inst_total(days)


@st.cache_data(ttl=1800, show_spinner=False)
def c_score(code, swing_trend):
    return composite(code, e=enrich(c_fetch(code, "1y")), swing_trend=swing_trend)


# ===================== 即時報價面板 =====================
def _render_quote(code):
    df = rt_quote([code]) if is_market_hours() else c_quote_off(code)
    if df.empty:
        st.caption("📡 即時報價:暫時無法取得(盤後/假日,或來源限流/雲端被擋)。")
        return
    r = df.iloc[0]
    q = st.columns(6)
    q[0].metric("📡 即時成交", f"{r['成交']:.2f}",
                f"{r['漲跌%']:+.2f}%" if r["漲跌%"] is not None else None)
    q[1].metric("開", f"{r['開']:.2f}" if r["開"] is not None else "—")
    q[2].metric("高", f"{r['高']:.2f}" if r["高"] is not None else "—")
    q[3].metric("低", f"{r['低']:.2f}" if r["低"] is not None else "—")
    q[4].metric("累積量(張)", f"{r['累積量(張)']:,}")
    live = is_market_hours()
    q[5].metric("狀態", "🟢 交易中" if live else "盤後")
    st.caption(f"資料時間 {r.get('日期','')} {r.get('時間','')}｜"
               f"{'交易時間每3秒自動更新(MIS約3~5秒延遲)' if live else '非交易時間,顯示最後成交'}｜來源:證交所 MIS")


@st.fragment(run_every="3s")
def _live_quote_auto(code):
    _render_quote(code)


def live_quote_panel(code):
    """即時報價:勾選時交易時間每3秒自動更新;取消勾選則只抓一次(不持續打 MIS)。"""
    auto = st.checkbox("📡 即時自動更新(每3秒)", value=True, key="rt_auto")
    if auto:
        _live_quote_auto(code)
    else:
        _render_quote(code)


# ===================== 觀察清單存取 =====================
def load_watchlist():
    codes = []
    if os.path.exists(WATCHLIST):
        with open(WATCHLIST, encoding="utf-8") as f:
            for line in f:
                line = line.split("#")[0].strip()
                if line:
                    codes.append(line)
    return codes


def save_watchlist(codes):
    with open(WATCHLIST, "w", encoding="utf-8") as f:
        f.write("# 觀察清單:一行一檔(由介面管理)。上櫃加 .TWO\n")
        for c in codes:
            f.write(f"{c}\n")


# ===================== 表格 / 圖表 輔助 =====================
def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="分析結果")
    return buf.getvalue()


def date_breaks(index):
    """算出資料日期區間內『沒有資料』的日期(週末/假日),給 K 線圖跳過、消除空格。"""
    idx = pd.DatetimeIndex(index)
    full = pd.date_range(idx.min(), idx.max(), freq="D")
    missing = full.difference(idx)
    return [d.strftime("%Y-%m-%d") for d in missing]


def cn_ohlc_hover(e):
    """產生 K 線的中文懸停文字:日期 + 開/高/低/收。"""
    return [
        f"{d:%Y-%m-%d}<br>開 {o:.1f}　高 {h:.1f}<br>低 {lo:.1f}　收 {c:.1f}"
        for d, o, h, lo, c in zip(e.index, e["Open"], e["High"], e["Low"], e["Close"])
    ]


def jump_to_stock(codes, key):
    """結果表下方:選一檔帶入『個股分析』分頁(設定 st_code)。"""
    opts = ["—"] + [str(c) for c in codes]
    pick = st.selectbox("📊 選一檔帶入「個股分析」分頁查看", opts, key=key)
    if pick and pick != "—":
        st.session_state["st_code"] = pick
        st.success(f"已帶入 **{pick}**,點上方『📊 個股分析』分頁即可看到。")


def color_updown(val):
    """漲跌數值上色:正紅、負綠(台股慣例)。"""
    try:
        v = float(val)
    except (ValueError, TypeError):
        return ""
    if v > 0:
        return "color: #d62728; font-weight:600"
    if v < 0:
        return "color: #2ca02c; font-weight:600"
    return ""


def styled_table(df, color_cols=()):
    """統一表格格式:float 顯示 2 位小數、空值顯示「—」、指定欄位紅綠標色。"""
    sty = df.style.format(precision=2, na_rep="—")
    cc = [c for c in color_cols if c in df.columns]
    if cc:
        sty = sty.map(color_updown, subset=cc)
    return sty


def hbar_sector(df, title=""):
    """類股強弱橫條圖(紅=正報酬、綠=負報酬),比較頁與盤勢頁共用。"""
    colors = ["#d62728" if v >= 0 else "#2ca02c" for v in df["平均報酬%"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["平均報酬%"], y=df["產業"], orientation="h",
                         marker_color=colors,
                         text=[f"{v:+.1f}%" for v in df["平均報酬%"]],
                         textposition="outside"))
    fig.update_layout(height=max(300, 34 * len(df)), title=title,
                      margin=dict(l=10, r=10, t=40 if title else 20, b=10),
                      yaxis=dict(autorange="reversed"))
    return fig

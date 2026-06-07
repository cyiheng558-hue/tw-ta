# -*- coding: utf-8 -*-
"""UI 共用層:快取包裝、輔助函式、常數、即時報價、共用圖表 helper。

抽離自 app.py 以縮小主檔、集中重複邏輯。本模組只定義函式/常數,
不在 import 時渲染任何畫面,故可安全在 set_page_config 之後 import。
"""
import os
import io

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from data import fetch, fetch_many, fetch_intraday
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
from realtime import quote as rt_quote, quote_detail, index_quote, is_market_hours
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
    "live_quote_panel", "hbar_sector", "daytrade_board", "intraday_chart",
    "orderbook_panel", "daytrade_pnl", "intraday_movers",
    "index_strength_bar", "alerts_ui", "market_breadth",
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


# ===================== 當沖看盤 =====================
@st.cache_data(ttl=60, show_spinner=False)
def c_intraday(code, interval):
    return fetch_intraday(code, interval)


def _board_render(codes, names):
    df = rt_quote(codes)
    if df.empty:
        st.info("即時報價暫時無法取得(盤後/假日,或來源限流/雲端被擋)。")
        return
    df = df.copy()
    df["名稱"] = df["代號"].map(lambda c: names.get(str(c), ""))

    def _flag(r):
        f = []
        if r["成交"] is not None and r["高"] is not None and r["成交"] >= r["高"]:
            f.append("📈創高")
        if r["成交"] is not None and r["低"] is not None and r["成交"] <= r["低"]:
            f.append("📉創低")
        p = r["漲跌%"]
        if p is not None and p >= 9.5:
            f.append("🔴漲停近")
        elif p is not None and p <= -9.5:
            f.append("🟢跌停近")
        return " ".join(f)

    df["異動"] = df.apply(_flag, axis=1)
    # 相對強弱 = 個股漲跌% − 大盤漲跌%(>0 強於大盤)
    mkt = index_quote().get("加權指數", {}).get("漲跌%")
    cols = ["代號", "名稱", "成交", "漲跌%"]
    if mkt is not None:
        df["相對強弱"] = df["漲跌%"].apply(lambda p: round(p - mkt, 2) if p is not None else None)
        cols.append("相對強弱")
    cols += ["異動", "累積量(張)", "開", "高", "低"]
    df = df.sort_values("漲跌%", ascending=False)
    _check_alerts(df)  # 到價/漲跌提醒
    color_cols = ["漲跌%"] + (["相對強弱"] if mkt is not None else [])
    st.dataframe(styled_table(df[cols], color_cols),
                 width="stretch", hide_index=True, height=min(38 * len(df) + 40, 720))
    t = df.iloc[0].get("時間", "")
    live = is_market_hours()
    mtxt = f"｜大盤 {mkt:+.2f}%" if mkt is not None else ""
    st.caption(f"資料時間 {t}{mtxt}｜{'交易中,每5秒自動更新' if live else '盤後/最後成交'}｜"
               f"相對強弱>0=強於大盤｜來源:證交所 MIS")


@st.fragment(run_every="5s")
def _board_auto(codes, names):
    _board_render(codes, names)


def daytrade_board(codes, names):
    """整份清單即時報價看板:交易時間每5秒自動更新、依漲跌排序。"""
    auto = st.checkbox("⚡ 自動更新(每5秒)", value=True, key="board_auto")
    if auto and is_market_hours():
        _board_auto(codes, names)
    else:
        _board_render(codes, names)


def intraday_chart(code, interval="5m"):
    """當日分鐘K線 + VWAP(當沖均價參考)+ 量。"""
    df = c_intraday(code, interval)
    if df.empty:
        st.caption("分鐘K資料暫時無法取得(盤後初期、無資料或雲端被擋)。")
        return
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    vwap = (tp * df["Volume"]).cumsum() / df["Volume"].cumsum().replace(0, pd.NA)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.74, 0.26], vertical_spacing=0.03,
                        subplot_titles=(f"{interval} 分鐘K + VWAP", "成交量"))
    fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"],
                  low=df["Low"], close=df["Close"], name="分鐘K",
                  increasing_line_color="red", decreasing_line_color="green"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=vwap, name="VWAP",
                  line=dict(color="purple", width=1.6)), row=1, col=1)
    fig.add_hline(y=float(df["Open"].iloc[0]), line_dash="dot", line_color="gray",
                  row=1, col=1, annotation_text="開盤", annotation_position="right",
                  annotation_font_size=9)
    vcol = ["red" if df["Close"].iloc[i] >= df["Open"].iloc[i] else "green" for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="量", marker_color=vcol), row=2, col=1)
    fig.update_layout(height=500, xaxis_rangeslider_visible=False,
                      margin=dict(l=10, r=10, t=30, b=10),
                      legend=dict(orientation="h", y=1.06))
    st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)
    st.caption("分鐘K來自 yfinance(約15分鐘延遲);**紫線=VWAP**(成交量加權均價,當沖常用:價在VWAP上偏多、下偏空)。"
               "盤中即時價請看上方看板。")


def orderbook_panel(code):
    """即時五檔買賣盤 + 內外盤力道 + 距漲跌停。"""
    d = quote_detail(code)
    if not d:
        st.caption("五檔資料暫時無法取得(盤後/假日或雲端被擋)。")
        return
    bv, av = d["委買量"], d["委賣量"]
    ratio = bv / av if av else 0
    m = st.columns(3)
    m[0].metric("內外盤比(委買/委賣)", f"{ratio:.2f}",
                "委買強" if ratio > 1.2 else ("委賣強" if ratio < 0.83 else "平衡"))
    m[1].metric("距漲停", f"{d['距漲停%']}%" if d["距漲停%"] is not None else "—")
    m[2].metric("距跌停", f"{d['距跌停%']}%" if d["距跌停%"] is not None else "—")
    rows = []
    for p, v in reversed(d["賣盤"]):   # 賣5→賣1(由上往下越接近成交)
        rows.append({"買/賣": "賣", "價": p, "張數": int(v)})
    for p, v in d["買盤"]:             # 買1→買5
        rows.append({"買/賣": "買", "價": p, "張數": int(v)})
    bk = pd.DataFrame(rows)

    def _row_color(r):
        bg = "background-color:#eaffea" if r["買/賣"] == "賣" else "background-color:#ffecec"
        return [bg] * len(r)

    st.dataframe(bk.style.apply(_row_color, axis=1).format({"價": "{:.2f}"}),
                 width="stretch", hide_index=True, height=388)
    st.caption(f"資料時間 {d.get('時間','')}｜內外盤比 >1 = 委買較多(買盤積極)、<1 = 委賣較多;"
               "距漲跌停越小越可能鎖死。來源:證交所 MIS。")


@st.cache_data(ttl=3600, show_spinner=False)
def _avg_volume(codes):
    """各股近20日均量(張),供盤中『量比』用。"""
    daily = c_fetch_many(tuple(codes), "3mo")
    out = {}
    for c, df in daily.items():
        if len(df) >= 5:
            out[c] = float(df["Volume"].tail(20).mean()) / 1000.0  # 股 -> 張
    return out


def intraday_movers(codes, names):
    """盤中異動掃描:回傳含 漲跌%/量比/異動 的即時 DataFrame(從股池找當沖候選)。"""
    q = rt_quote(list(codes))
    if q.empty:
        return pd.DataFrame()
    avg = _avg_volume(tuple(codes))
    q = q.copy()
    q["名稱"] = q["代號"].map(lambda c: names.get(str(c), ""))

    def _ratio(r):
        a = avg.get(r["代號"])
        return round(r["累積量(張)"] / a, 2) if a else None

    def _flag(r):
        f = []
        if r["成交"] is not None and r["高"] is not None and r["成交"] >= r["高"]:
            f.append("📈創高")
        p = r["漲跌%"]
        if p is not None and p >= 9.5:
            f.append("🔴漲停近")
        elif p is not None and p <= -9.5:
            f.append("🟢跌停近")
        return " ".join(f)

    q["量比"] = q.apply(_ratio, axis=1)
    q["異動"] = q.apply(_flag, axis=1)
    return q[["代號", "名稱", "成交", "漲跌%", "量比", "異動", "累積量(張)", "高", "低"]]


@st.cache_data(ttl=60, show_spinner=False)
def _index_intraday():
    return fetch_intraday("^TWII", "5m")


def index_strength_bar():
    """大盤即時連動:加權/櫃買即時 + 加權分時走勢迷你圖。"""
    idx = index_quote()
    c = st.columns([1, 1, 2.4])
    tw = idx.get("加權指數", {})
    otc = idx.get("櫃買指數", {})
    c[0].metric("加權指數", f"{tw.get('成交','—'):,.0f}" if tw.get("成交") else "—",
                f"{tw.get('漲跌%'):+.2f}%" if tw.get("漲跌%") is not None else None)
    c[1].metric("櫃買指數", f"{otc.get('成交','—'):,.1f}" if otc.get("成交") else "—",
                f"{otc.get('漲跌%'):+.2f}%" if otc.get("漲跌%") is not None else None)
    with c[2]:
        d = _index_intraday()
        if not d.empty:
            up = float(d["Close"].iloc[-1]) >= float(d["Open"].iloc[0])
            fig = go.Figure(go.Scatter(x=d.index, y=d["Close"], mode="lines",
                            line=dict(color="#d62728" if up else "#2ca02c", width=1.5),
                            fill="tozeroy", fillcolor="rgba(214,39,40,0.06)" if up else "rgba(44,160,44,0.06)"))
            fig.add_hline(y=float(d["Open"].iloc[0]), line_dash="dot", line_color="gray")
            fig.update_layout(height=90, margin=dict(l=0, r=0, t=0, b=0),
                              showlegend=False, yaxis=dict(showticklabels=False),
                              xaxis=dict(showticklabels=False))
            fig.update_yaxes(range=[float(d["Close"].min()) * 0.999, float(d["Close"].max()) * 1.001])
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def _beep():
    components.html(
        "<script>try{var c=new(window.AudioContext||window.webkitAudioContext)();"
        "var o=c.createOscillator(),g=c.createGain();o.connect(g);g.connect(c.destination);"
        "o.frequency.value=880;o.type='square';o.start();g.gain.setValueAtTime(0.25,c.currentTime);"
        "g.gain.exponentialRampToValueAtTime(0.001,c.currentTime+0.5);o.stop(c.currentTime+0.5);}"
        "catch(e){}</script>", height=0)


def _check_alerts(df):
    """檢查到價/漲跌提醒,觸發時跳紅字 + toast + 響聲(同一條件只響一次)。"""
    alerts = st.session_state.get("dt_alerts", [])
    if not alerts:
        return
    fired = st.session_state.setdefault("dt_alert_fired", set())
    hits = []
    for a in alerts:
        row = df[df["代號"] == a["code"]]
        if row.empty:
            continue
        r = row.iloc[0]
        p, px = r["漲跌%"], r["成交"]
        key = (a["code"], a["kind"], a["value"])
        ok = ((a["kind"] == "漲跌%≥" and p is not None and p >= a["value"]) or
              (a["kind"] == "漲跌%≤" and p is not None and p <= a["value"]) or
              (a["kind"] == "價≥" and px is not None and px >= a["value"]) or
              (a["kind"] == "價≤" and px is not None and px <= a["value"]))
        if ok and key not in fired:
            hits.append(f"{a['code']} {r['名稱']} {a['kind']}{a['value']}(現 {px} / {p:+.2f}%)")
            fired.add(key)
        elif not ok:
            fired.discard(key)
    if hits:
        for h in hits:
            st.toast("🔔 " + h)
        st.error("🔔 觸發提醒:" + "；".join(hits))
        _beep()


def alerts_ui(names):
    """到價/漲跌提醒設定。"""
    with st.expander("🔔 到價 / 漲跌提醒(觸發跳紅字 + 響聲)"):
        a = st.columns([1, 1, 1, 0.7])
        code = a[0].text_input("代號", key="al_code").strip()
        kind = a[1].selectbox("條件", ["漲跌%≥", "漲跌%≤", "價≥", "價≤"], key="al_kind")
        val = a[2].number_input("值", value=0.0, step=0.5, key="al_val")
        a[3].write("")
        if a[3].button("加入") and code:
            st.session_state.setdefault("dt_alerts", []).append(
                {"code": code, "kind": kind, "value": val})
        alerts = st.session_state.get("dt_alerts", [])
        if alerts:
            for i, al in enumerate(list(alerts)):
                cc = st.columns([5, 1])
                cc[0].write(f"・{al['code']} {names.get(al['code'], '')} **{al['kind']} {al['value']}**")
                if cc[1].button("刪除", key=f"al_del{i}"):
                    alerts.pop(i)
                    st.rerun()
        else:
            st.caption("尚無提醒。例:設『2330 漲跌%≥ 3』,盤中漲超過3%就提醒你。")


def market_breadth(df):
    """市場寬度:上漲/下跌家數 + 漲跌分佈長條圖。"""
    p = pd.to_numeric(df["漲跌%"], errors="coerce").dropna()
    if p.empty:
        return
    up, dn, flat = int((p > 0).sum()), int((p < 0).sum()), int((p == 0).sum())
    m = st.columns(3)
    m[0].metric("上漲", f"{up} 檔")
    m[1].metric("下跌", f"{dn} 檔")
    m[2].metric("平盤", f"{flat} 檔")
    buckets = {"漲>5%": int((p > 5).sum()), "漲0~5%": int(((p > 0) & (p <= 5)).sum()),
               "跌0~5%": int(((p < 0) & (p >= -5)).sum()), "跌>5%": int((p < -5).sum())}
    bcolors = ["#a50f15", "#fb6a4a", "#74c476", "#006d2c"]
    fig = go.Figure(go.Bar(x=list(buckets.keys()), y=list(buckets.values()),
                    marker_color=bcolors, text=list(buckets.values()), textposition="outside"))
    fig.update_layout(height=200, margin=dict(l=10, r=10, t=10, b=10),
                      yaxis_title="檔數", showlegend=False)
    st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)
    tone = "普漲(當沖偏多)" if up > dn * 1.5 else ("普跌(偏空)" if dn > up * 1.5 else "漲跌互見(分歧)")
    st.caption(f"今日股池:{up} 漲 / {dn} 跌 → **{tone}**。")


def daytrade_pnl():
    """當沖損益試算:手續費(可折扣)+ 證交稅當沖減半(0.15%)。"""
    c = st.columns(4)
    entry = c[0].number_input("買進價", value=100.0, step=0.5, key="dt_entry")
    exit_ = c[1].number_input("賣出價", value=101.0, step=0.5, key="dt_exit")
    lots = c[2].number_input("張數", value=1, min_value=1, step=1, key="dt_lots")
    disc = c[3].number_input("手續費折數(如 0.6=六折)", value=1.0, min_value=0.1,
                             max_value=1.0, step=0.1, key="dt_disc")
    shares = lots * 1000
    fee_rate = 0.001425 * disc
    tax_rate = 0.0015  # 當沖證交稅減半
    buy_cost = entry * shares
    sell_amt = exit_ * shares
    fee = (buy_cost + sell_amt) * fee_rate
    tax = sell_amt * tax_rate
    net = (sell_amt - buy_cost) - fee - tax
    # 損益兩平:賣價需多少才能打平成本
    be = entry * (1 + fee_rate) / (1 - fee_rate - tax_rate)
    r = st.columns(4)
    r[0].metric("價差損益", f"{(exit_-entry)*shares:,.0f}")
    r[1].metric("手續費+稅", f"-{fee+tax:,.0f}")
    r[2].metric("淨損益", f"{net:,.0f}", f"{net/buy_cost*100:+.2f}%" if buy_cost else None)
    r[3].metric("損益兩平賣價", f"{be:.2f}", f"+{(be-entry)/entry*100:.2f}%")
    st.caption("當沖證交稅減半(0.15%);手續費單邊 0.1425%×折數。實際以你券商收費為準。")

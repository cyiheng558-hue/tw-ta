# -*- coding: utf-8 -*-
"""台股短線技術分析 — Streamlit 網頁介面(完整版)。

啟動:雙擊「開啟介面.bat」,或執行  streamlit run app.py
分頁:總覽 / 清單掃描 / 條件篩選 / 個股分析 / 自選股管理

免責:所有輸出為技術/籌碼/基本面資料的客觀計算與整理,非投資建議,
不保證準確或獲利;資料為延遲日線,請自行判斷並承擔風險。
"""
import os
import io
import datetime as _dt

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from data import fetch, fetch_many
from indicators import enrich
from signals import scan_one
from backtest import backtest_signal, backtest_all, benchmark_return
from chips import fetch_institutional, chip_summary
from fundamentals import (load_stock_names, name_of, valuation, revenue_yoy,
                          margin_short, financials, load_industry,
                          dividend_history, revenue_trend, pe_valuation,
                          financials_history)
from chips import cumulative_net, foreign_holding, margin_short_ratio
from news import latest_news
from score import composite, rank_codes
from broker import broker_branch
from sector import sector_strength
from futures import futures_net_oi, summary as fut_summary
from market import index_status, inst_total
from realtime import quote as rt_quote, is_market_hours
from screener import screen, load_universe, DEFAULT_CONDITIONS
from risk import suggest as risk_suggest
from backtest import BACKTESTABLE
from swing import analyze as swing_analyze, scan_swing, backtest_swing

HERE = os.path.dirname(os.path.abspath(__file__))
WATCHLIST = os.path.join(HERE, "watchlist.txt")

st.set_page_config(page_title="台股技術分析", page_icon="📈", layout="wide")

# 在 Streamlit Cloud 上,把 Secrets 的 FINMIND_TOKEN 橋接成環境變數,
# 讓 chips.py / fundamentals.py 沿用 os.environ 即可(本機沒設定也不會報錯)。
try:
    if "FINMIND_TOKEN" in st.secrets:
        os.environ.setdefault("FINMIND_TOKEN", str(st.secrets["FINMIND_TOKEN"]))
except Exception:
    pass


# ===================== 進站驗證碼 =====================
# 密碼預設 1524,可用 Secrets / 環境變數 APP_PASSWORD 覆蓋(改密碼不必動程式碼)。
def _app_password():
    try:
        if "APP_PASSWORD" in st.secrets:
            return str(st.secrets["APP_PASSWORD"])
    except Exception:
        pass
    return os.environ.get("APP_PASSWORD", "") or "1524"


APP_PASSWORD = _app_password()


def require_password():
    """未通過驗證前,只顯示輸入框並停住,不執行後面的內容。"""
    if st.session_state.get("auth_ok"):
        return

    def _check():
        if st.session_state.get("pwd_input", "") == APP_PASSWORD:
            st.session_state["auth_ok"] = True
            st.session_state["pwd_bad"] = False
        else:
            st.session_state["auth_ok"] = False
            st.session_state["pwd_bad"] = True
        st.session_state["pwd_input"] = ""  # 不保留輸入內容

    st.title("📈 台股技術分析")
    st.caption("本站需要驗證碼才能使用,請向提供者索取。")
    st.text_input("請輸入驗證碼", type="password", key="pwd_input", on_change=_check)
    if st.session_state.get("pwd_bad"):
        st.error("驗證碼錯誤,請再試一次。")
    st.stop()


require_password()

# Plotly 工具列(右上角按鈕)繁體中文化:內嵌 zh-TW 語系字典
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


# ===================== 快取層 =====================
@st.cache_data(ttl=900, show_spinner=False)
def c_fetch(code, period):
    return fetch(code, period=period)


@st.cache_data(ttl=900, show_spinner=False)
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
    return swing_analyze(code, fetch(code, period=period), period=period)


@st.cache_data(ttl=1800, show_spinner=False)
def c_scan_swing(codes, only_bull):
    return scan_swing(list(codes), only_bull=only_bull)


@st.cache_data(ttl=1800, show_spinner=False)
def c_swing_bt(code, hold, sl, tp):
    return backtest_swing(fetch(code, period="5y"), hold_days=hold, stop_loss=sl, take_profit=tp)


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


@st.fragment(run_every="3s")
def live_quote_panel(code):
    """即時報價面板:交易時間每 3 秒自動更新(盤後讀快取,不重複打)。"""
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
    return composite(code, e=enrich(fetch(code, period="1y")), swing_trend=swing_trend)


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


def styled_table(df, color_cols=()):
    """統一表格格式:float 顯示 2 位小數、空值顯示「—」、指定欄位紅綠標色。"""
    sty = df.style.format(precision=2, na_rep="—")
    cc = [c for c in color_cols if c in df.columns]
    if cc:
        sty = sty.map(color_updown, subset=cc)
    return sty


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


# ===================== 標題 + 大盤總覽 =====================
st.title("📈 台股技術分析")

ov = st.container()
with ov:
    cols = st.columns(3)
    for col, (sym, label) in zip(cols, [("^TWII", "加權指數"), ("0050", "元大台灣50"), ("^TWOII", "櫃買指數")]):
        try:
            d = c_fetch(sym, "1mo")
            if not d.empty and len(d) >= 2:
                last = float(d["Close"].iloc[-1])
                chg = (last - float(d["Close"].iloc[-2])) / float(d["Close"].iloc[-2]) * 100
                col.metric(label, f"{last:,.1f}", f"{chg:+.2f}%")
            else:
                col.metric(label, "—")
        except Exception:
            col.metric(label, "—")

st.caption("資料:yfinance(延遲約15分鐘日線)+ FinMind(籌碼/基本面)。"
           "以下皆為客觀計算,**非投資建議**,請自行評估風險。")

# 大盤多空:三大法人台指期淨未平倉(勾選才載入,避免拖慢首屏)
if st.checkbox("顯示大盤多空(三大法人台指期淨未平倉口數)", key="show_fut"):
    fs = c_fut_summary()
    if not fs:
        st.info("抓不到期貨資料(FinMind 流量上限或非交易日)。")
    else:
        fc = st.columns(4)
        fc[0].metric("外資淨未平倉(口)", f"{fs['外資淨']:+,.0f}",
                     f"{fs['外資增減']:+,.0f}" if fs.get("外資增減") is not None else None)
        fc[1].metric("投信淨(口)", f"{fs['投信淨']:+,.0f}")
        fc[2].metric("自營淨(口)", f"{fs['自營淨']:+,.0f}")
        fc[3].metric("三大法人淨(口)", f"{fs['三大法人淨']:+,.0f}")
        st.caption(f"資料日 {fs['日期']}。正=偏多(站多方)、負=偏空。外資淨未平倉常作大盤方向參考。")
        foi = c_fut_oi(40)
        if not foi.empty:
            foifig = go.Figure()
            for col, color in [("外資", "#d62728"), ("投信", "#1f77b4"),
                               ("自營商", "#2ca02c"), ("三大法人合計", "#000000")]:
                foifig.add_trace(go.Scatter(x=foi.index, y=foi[col], name=col,
                                 line=dict(color=color, width=1.5 if col == "三大法人合計" else 1)))
            foifig.add_hline(y=0, line_dash="dash", line_color="gray")
            foifig.update_layout(height=300, title="三大法人台指期淨未平倉口數趨勢",
                                 margin=dict(l=10, r=10, t=40, b=10),
                                 legend=dict(orientation="h", y=1.15))
            st.plotly_chart(foifig, width="stretch", config=PLOTLY_CONFIG)

tab_scan, tab_screen, tab_stock, tab_swing, tab_cmp, tab_market, tab_watch = st.tabs(
    ["🔍 清單掃描", "🎯 條件篩選", "📊 個股分析(短線)", "📈 中線分析", "🆚 比較",
     "🌡️ 盤勢/資金", "⚙️ 自選股管理"])


# ============================================================
# 分頁:清單掃描
# ============================================================
with tab_scan:
    c1, c2, c3 = st.columns([2, 1, 1])
    c1.subheader("掃描觀察清單的短線訊號")
    period = c2.selectbox("資料期間", ["3mo", "6mo", "1y"], index=1, key="scan_p")
    bullish_only = c3.checkbox("只看有看多訊號", value=True)
    include_chips = st.checkbox("加查近5日三大法人合計(較慢)", value=False)

    if st.button("開始掃描", type="primary", key="btn_scan"):
        codes = load_watchlist()
        names = c_names()
        with st.spinner(f"抓取 {len(codes)} 檔..."):
            data = c_fetch_many(tuple(codes), period)
        rows = []
        for code, df in data.items():
            if len(df) < 60:
                continue
            e = enrich(df)
            bull, bear = scan_one(e)
            close = float(e["Close"].iloc[-1])
            chg = (close - float(e["Close"].iloc[-2])) / float(e["Close"].iloc[-2]) * 100
            row = {
                "代號": code, "名稱": names.get(code, ""),
                "收盤": round(close, 1), "漲跌%": round(chg, 2),
                "看多訊號": " / ".join(bull) if bull else "—",
                "_n": len(bull),
                "警示": " / ".join(bear) if bear else "",
            }
            if include_chips:
                cs = c_chip_summary(code, 5)
                row["法人合計(張)"] = round(cs.get("合計", 0)) if cs else None
            rows.append(row)

        if not rows:
            st.warning("沒有成功分析的個股。")
        else:
            tbl = pd.DataFrame(rows).sort_values(["_n", "漲跌%"], ascending=False)
            if bullish_only:
                tbl = tbl[tbl["_n"] > 0]
            tbl = tbl.drop(columns=["_n"])
            st.success(f"完成,共 {len(rows)} 檔,符合 {len(tbl)} 檔。")
            st.dataframe(styled_table(tbl, ["漲跌%"]), width="stretch", hide_index=True)
            st.download_button("⬇ 匯出 Excel", to_excel_bytes(tbl),
                               file_name=f"scan_{_dt.date.today()}.xlsx",
                               key="dl_scan")
            st.session_state["scan_codes"] = list(tbl["代號"])

    if st.session_state.get("scan_codes"):
        jump_to_stock(st.session_state["scan_codes"], "scan_jump")


# ============================================================
# 分頁:條件篩選
# ============================================================
with tab_screen:
    st.subheader("自訂條件選股(掃描股池 universe.txt)")
    st.caption("勾選/設定要套用的條件,未啟用者留空白即可。籌碼與基本面條件會較慢。")

    colA, colB, colC = st.columns(3)
    with colA:
        st.markdown("**技術面**")
        use_rsi = st.checkbox("RSI 範圍")
        rsi_lo, rsi_hi = st.slider("RSI", 0, 100, (30, 60), disabled=not use_rsi)
        req_kd = st.checkbox("KD 黃金交叉")
        req_ma = st.checkbox("均線多頭排列")
        req_macd = st.checkbox("MACD 翻紅")
        req_bb = st.checkbox("突破布林上軌")
        above_ma20 = st.checkbox("收盤站上月線")
        use_bias = st.checkbox("乖離率上限(避免追高)")
        bias_max = st.number_input("乖離% ≤", value=10.0, disabled=not use_bias)
    with colB:
        st.markdown("**籌碼面**")
        use_streak = st.checkbox("法人連續買超天數")
        streak_min = st.number_input("連買天數 ≥", value=3, min_value=1, disabled=not use_streak)
        use_chiptot = st.checkbox("近5日法人合計")
        chiptot_min = st.number_input("合計(張) ≥", value=0, disabled=not use_chiptot)
    with colC:
        st.markdown("**基本面**")
        use_per = st.checkbox("本益比上限")
        per_max = st.number_input("本益比 ≤", value=20.0, disabled=not use_per)
        use_yield = st.checkbox("殖利率下限")
        yield_min = st.number_input("殖利率% ≥", value=3.0, disabled=not use_yield)
        use_yoy = st.checkbox("營收年增率下限")
        yoy_min = st.number_input("年增率% ≥", value=10.0, disabled=not use_yoy)

    if st.button("開始篩選", type="primary", key="btn_screen"):
        cond = dict(DEFAULT_CONDITIONS)
        if use_rsi:
            cond["rsi_min"], cond["rsi_max"] = rsi_lo, rsi_hi
        cond["require_kd_golden"] = req_kd
        cond["require_ma_bullish"] = req_ma
        cond["require_macd_positive"] = req_macd
        cond["require_bb_breakout"] = req_bb
        cond["price_above_ma20"] = above_ma20
        if use_bias:
            cond["bias_max"] = bias_max
        if use_streak:
            cond["foreign_buy_days_min"] = int(streak_min)
        if use_chiptot:
            cond["chip_total_min"] = chiptot_min
        if use_per:
            cond["per_max"] = per_max
        if use_yield:
            cond["yield_min"] = yield_min
        if use_yoy:
            cond["yoy_min"] = yoy_min

        universe = load_universe()
        prog = st.progress(0.0)
        with st.spinner(f"篩選 {len(universe)} 檔股池..."):
            res = screen(universe, cond, period="6mo",
                         progress_cb=lambda d, t: prog.progress(min(d / t, 1.0)))
        prog.empty()
        if res.empty:
            st.warning("沒有符合所有條件的股票,試著放寬條件。")
        else:
            st.success(f"篩出 {len(res)} 檔符合條件。")
            st.dataframe(styled_table(res, ["漲跌%"]), width="stretch", hide_index=True)
            st.download_button("⬇ 匯出 Excel", to_excel_bytes(res),
                               file_name=f"screen_{_dt.date.today()}.xlsx", key="dl_screen")
            st.session_state["screen_codes"] = list(res["代號"])

    if st.session_state.get("screen_codes"):
        jump_to_stock(st.session_state["screen_codes"], "screen_jump")


# ============================================================
# 分頁:個股分析
# ============================================================
with tab_stock:
    c1, c2, c3 = st.columns([1, 1, 1])
    st.session_state.setdefault("st_code", "2330")  # 可被掃描/篩選的「看個股」帶入
    code = c1.text_input("股票代號", key="st_code").strip()
    s_period = c2.selectbox("資料期間", ["3mo", "6mo", "1y", "2y"], index=1, key="st_p")
    hold_days = c3.selectbox("回測持有天數", [3, 5, 10, 20], index=1)

    if code:
        df = c_fetch(code, s_period)
        if df.empty or len(df) < 60:
            st.error("抓不到資料或資料不足(至少60個交易日)。確認代號,上櫃加 .TWO。")
        else:
            nm = name_of(code, c_names())
            e = enrich(df)
            bull, bear = scan_one(e)
            last = e.iloc[-1]
            close = float(last["Close"])
            chg = (close - float(e["Close"].iloc[-2])) / float(e["Close"].iloc[-2]) * 100
            st.markdown(f"### {code} {nm}")

            # 即時報價(交易時間自動更新)
            live_quote_panel(code)

            # 指標卡(日線收盤,含 KD/RSI/乖離等)
            m = st.columns(5)
            m[0].metric("收盤", f"{close:.1f}", f"{chg:+.2f}%")
            m[1].metric("KD", f"{last['K']:.0f}/{last['D']:.0f}")
            m[2].metric("RSI", f"{last['RSI14']:.0f}")
            m[3].metric("乖離", f"{last['BIAS10']:+.1f}%")
            val = c_valuation(code)
            m[4].metric("本益比/殖利率", f"{val.get('PER','—')} / {val.get('殖利率%','—')}%" if val else "—")

            if bull:
                st.success("看多:" + " / ".join(bull))
            if bear:
                st.warning("警示:" + " / ".join(bear))

            # 綜合評分 + 雷達圖
            sw = c_swing(code, "2y")
            sw_trend = sw.get("趨勢") if isinstance(sw, dict) and "error" not in sw else None
            sc = c_score(code, sw_trend)
            if "error" not in sc:
                st.subheader(f"綜合評分:{sc['總分']:.0f} 分({sc['評等']})")
                sca, scb = st.columns([1, 1])
                with sca:
                    radar = go.Figure()
                    cats = ["技術面", "基本面", "籌碼面"]
                    vals = [sc["技術面"], sc["基本面"], sc["籌碼面"]]
                    radar.add_trace(go.Scatterpolar(r=vals + [vals[0]], theta=cats + [cats[0]],
                                    fill="toself", line=dict(color="#d62728"), name="分數"))
                    radar.update_layout(height=300, margin=dict(l=30, r=30, t=20, b=20),
                                        polar=dict(radialaxis=dict(range=[0, 100], visible=True)),
                                        showlegend=False)
                    st.plotly_chart(radar, width="stretch", config=PLOTLY_CONFIG)
                with scb:
                    sm = st.columns(3)
                    sm[0].metric("技術面", sc["技術面"])
                    sm[1].metric("基本面", sc["基本面"])
                    sm[2].metric("籌碼面", sc["籌碼面"])
                    with st.expander("評分依據(各項加減分)"):
                        st.caption("**技術面**:" + "、".join(sc["技術說明"]) if sc["技術說明"] else "技術面:—")
                        st.caption("**基本面**:" + "、".join(sc["基本說明"]) if sc["基本說明"] else "基本面:—")
                        st.caption("**籌碼面**:" + "、".join(sc["籌碼說明"]) if sc["籌碼說明"] else "籌碼面:—")
                st.caption("評分是把多項指標濃縮成方便比較的數字,非買賣建議。")

            # === 詳細內容用分段選擇器,只渲染選中的那塊(延遲載入、首屏更快、省 API) ===
            _VIEWS = ["📈 技術線圖", "💲 基本面", "💰 籌碼面", "🧪 回測·部位", "📰 新聞"]
            view = st.segmented_control("檢視", _VIEWS, default="📈 技術線圖",
                                        key="stk_view", label_visibility="collapsed") or "📈 技術線圖"

            # ---------- 技術線圖 ----------
            if view == "📈 技術線圖":
                fig = make_subplots(rows=4, cols=1, shared_xaxes=True,
                                    row_heights=[0.5, 0.17, 0.17, 0.16], vertical_spacing=0.03,
                                    subplot_titles=("K線/均線/布林", "KD", "MACD", "成交量"))
                fig.add_trace(go.Candlestick(x=e.index, open=e["Open"], high=e["High"],
                              low=e["Low"], close=e["Close"], name="K線",
                              text=cn_ohlc_hover(e), hoverinfo="text",
                              increasing_line_color="red", decreasing_line_color="green"), row=1, col=1)
                for n, label, c in [("MA5", "5日線", "orange"), ("MA20", "月線(20日)", "blue"), ("MA60", "季線(60日)", "purple")]:
                    fig.add_trace(go.Scatter(x=e.index, y=e[n], name=label, line=dict(width=1, color=c)), row=1, col=1)
                fig.add_trace(go.Scatter(x=e.index, y=e["BB_UP"], line=dict(width=0.5, color="gray"), showlegend=False), row=1, col=1)
                fig.add_trace(go.Scatter(x=e.index, y=e["BB_LOW"], fill="tonexty",
                              fillcolor="rgba(150,150,150,0.12)", line=dict(width=0.5, color="gray"), showlegend=False), row=1, col=1)
                fig.add_trace(go.Scatter(x=e.index, y=e["K"], name="K值", line=dict(color="orange", width=1)), row=2, col=1)
                fig.add_trace(go.Scatter(x=e.index, y=e["D"], name="D值", line=dict(color="blue", width=1)), row=2, col=1)
                hist_colors = ["red" if v >= 0 else "green" for v in e["HIST"]]
                fig.add_trace(go.Bar(x=e.index, y=e["HIST"], name="柱狀體", marker_color=hist_colors), row=3, col=1)
                fig.add_trace(go.Scatter(x=e.index, y=e["DIF"], name="DIF差離值", line=dict(color="black", width=1)), row=3, col=1)
                fig.add_trace(go.Scatter(x=e.index, y=e["MACD"], name="訊號線", line=dict(color="orange", width=1)), row=3, col=1)
                vol_colors = ["red" if e["Close"].iloc[i] >= e["Open"].iloc[i] else "green" for i in range(len(e))]
                fig.add_trace(go.Bar(x=e.index, y=e["Volume"], name="成交量", marker_color=vol_colors), row=4, col=1)
                fig.update_layout(height=720, xaxis_rangeslider_visible=False,
                                  margin=dict(l=10, r=10, t=30, b=10),
                                  legend=dict(orientation="h", y=1.04))
                fig.update_xaxes(rangebreaks=[dict(values=date_breaks(e.index))])
                st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)

            # ---------- 基本面 ----------
            elif view == "💲 基本面":
                rev = c_revenue(code)
                fin = c_financials(code)
                pev = c_pe_val(code)
                div = c_dividend(code)
                f = st.columns(4)
                f[0].metric("本益比", val.get("PER", "—") if val else "—")
                f[1].metric("殖利率", f"{val.get('殖利率%','—')}%" if val else "—")
                f[2].metric("股價淨值比", val.get("PBR", "—") if val else "—")
                if pev:
                    f[3].metric("本益比評價", pev["評價"].split("(")[0],
                                f"近3年第{pev['近3年百分位']:.0f}百分位")
                if fin:
                    g = st.columns(5)
                    g[0].metric("毛利率", f"{fin.get('毛利率%','—')}%")
                    g[1].metric("營益率", f"{fin.get('營益率%','—')}%")
                    g[2].metric("淨利率", f"{fin.get('淨利率%','—')}%")
                    g[3].metric("近四季EPS", fin.get("近四季EPS", "—"))
                    g[4].metric("ROE(近四季)", f"{fin.get('ROE_TTM%','—')}%")
                    st.caption(f"財報季別:{fin.get('季別','—')}")
                rt = c_rev_trend(code)
                rc1, rc2 = st.columns([2, 1])
                with rc1:
                    if not rt.empty:
                        rfig = make_subplots(specs=[[{"secondary_y": True}]])
                        rfig.add_trace(go.Bar(x=rt.index, y=rt["營收億"], name="月營收(億)",
                                       marker_color="#9ecae1"), secondary_y=False)
                        rfig.add_trace(go.Scatter(x=rt.index, y=rt["年增率%"], name="年增率%",
                                       line=dict(color="#d62728", width=2)), secondary_y=True)
                        rfig.update_layout(height=260, title="月營收趨勢(近13個月)",
                                           margin=dict(l=10, r=10, t=30, b=10),
                                           legend=dict(orientation="h", y=1.2))
                        rfig.update_yaxes(title_text="營收(億)", secondary_y=False)
                        rfig.update_yaxes(title_text="年增率%", secondary_y=True)
                        st.plotly_chart(rfig, width="stretch", config=PLOTLY_CONFIG)
                with rc2:
                    if div:
                        st.metric("連續配息", f"{div['連續配息年數']} 年")
                        st.metric("最近年度現金股利", f"{div['最近年度現金股利']} 元")
                        if div.get("近年現金股利"):
                            hist = " / ".join(f"{y}:{c}" for y, c in div["近年現金股利"].items())
                            st.caption("近年現金股利:" + hist)

                # 獲利能力趨勢(季 / 年)
                st.markdown("**獲利能力趨勢**")
                fh = c_fin_hist(code)
                if not fh:
                    st.caption("(獲利歷史資料抓取中或無資料)")
                else:
                    fmode = st.radio("檢視", ["季", "年"], horizontal=True, key="fin_mode")
                    fdf = fh[fmode]
                    pfig = make_subplots(specs=[[{"secondary_y": True}]])
                    pfig.add_trace(go.Bar(x=fdf.index.astype(str), y=fdf["EPS"], name="EPS(元)",
                                   marker_color="#9ecae1"), secondary_y=True)
                    for col, color in [("毛利率%", "#d62728"), ("淨利率%", "#1f77b4"), ("ROE%", "#2ca02c")]:
                        pfig.add_trace(go.Scatter(x=fdf.index.astype(str), y=fdf[col], name=col,
                                       line=dict(color=color, width=2)), secondary_y=False)
                    pfig.update_layout(height=300, margin=dict(l=10, r=10, t=30, b=10),
                                       title=f"獲利能力({fmode})",
                                       legend=dict(orientation="h", y=1.18))
                    pfig.update_yaxes(title_text="比率 %", secondary_y=False)
                    pfig.update_yaxes(title_text="EPS(元)", secondary_y=True)
                    st.plotly_chart(pfig, width="stretch", config=PLOTLY_CONFIG)
                    st.dataframe(styled_table(fdf.reset_index()), width="stretch", hide_index=True)
                    if fmode == "季":
                        st.caption("季 ROE 為單季淨利/期末權益(約為年化的 1/4);年 ROE 為全年。最新年度可能僅累計到最近一季。")

            # ---------- 籌碼面 ----------
            elif view == "💰 籌碼面":
                cc1, cc2 = st.columns([2, 1])
                chips_df = c_chips(code, 30)
                with cc1:
                    if chips_df.empty:
                        st.info("抓不到三大法人資料(FinMind流量上限或無資料)。")
                    else:
                        cfig = go.Figure()
                        for col, color in [("外資", "#d62728"), ("投信", "#1f77b4"), ("自營商", "#2ca02c")]:
                            cfig.add_trace(go.Bar(x=chips_df.index, y=chips_df[col], name=col, marker_color=color))
                        cfig.update_layout(barmode="relative", height=280, title="三大法人買賣超(張)",
                                           margin=dict(l=10, r=10, t=30, b=10),
                                           legend=dict(orientation="h", y=1.15))
                        st.plotly_chart(cfig, width="stretch", config=PLOTLY_CONFIG)
                with cc2:
                    cs = c_chip_summary(code, 5)
                    if cs:
                        st.metric("外資 近5日(張)", f"{cs['外資']:+,.0f}")
                        st.metric("法人合計 近5日(張)", f"{cs['合計']:+,.0f}")
                        st.metric("合計連續買超", f"{cs['連續買超天數']} 天")
                    msr = c_margin_ratio(code)
                    if msr:
                        st.metric("融資餘額(張)", f"{msr['融資餘額']:,.0f}")
                        st.metric("券資比", f"{msr['券資比%']}%")
                dc1, dc2 = st.columns(2)
                with dc1:
                    cum = c_cum_net(code, 60)
                    if not cum.empty:
                        cumfig = go.Figure()
                        cumfig.add_trace(go.Scatter(x=cum.index, y=cum["累計"], fill="tozeroy",
                                         line=dict(color="#1f77b4"), name="累計買賣超"))
                        cumfig.update_layout(height=240, title="近60日累計法人買賣超(張)",
                                             margin=dict(l=10, r=10, t=30, b=10))
                        st.plotly_chart(cumfig, width="stretch", config=PLOTLY_CONFIG)
                with dc2:
                    fh = c_foreign_hold(code, 60)
                    if not fh.empty:
                        fhfig = go.Figure()
                        fhfig.add_trace(go.Scatter(x=fh.index, y=fh["外資持股比率"],
                                        line=dict(color="#d62728"), name="外資持股比率"))
                        fhfig.update_layout(height=240, title="外資持股比率(%)",
                                            margin=dict(l=10, r=10, t=30, b=10))
                        st.plotly_chart(fhfig, width="stretch", config=PLOTLY_CONFIG)
                    else:
                        st.caption("(外資持股比率資料抓取中或無資料)")

                # 融資融券餘額趨勢
                mtrend = c_margin(code, 60)
                if not mtrend.empty:
                    mfig = make_subplots(specs=[[{"secondary_y": True}]])
                    mfig.add_trace(go.Scatter(x=mtrend.index, y=mtrend["融資餘額"], name="融資餘額",
                                   line=dict(color="#d62728")), secondary_y=False)
                    mfig.add_trace(go.Scatter(x=mtrend.index, y=mtrend["融券餘額"], name="融券餘額",
                                   line=dict(color="#2ca02c")), secondary_y=True)
                    mfig.update_layout(height=260, title="融資 / 融券餘額趨勢(張)",
                                       margin=dict(l=10, r=10, t=40, b=10),
                                       legend=dict(orientation="h", y=1.2))
                    mfig.update_yaxes(title_text="融資(張)", secondary_y=False)
                    mfig.update_yaxes(title_text="融券(張)", secondary_y=True)
                    st.plotly_chart(mfig, width="stretch", config=PLOTLY_CONFIG)
                    st.caption("融資增=散戶加碼(籌碼偏亂);融券增=空方增加。")

                # 券商分點進出(HiStock 爬蟲)
                st.divider()
                st.markdown("**券商分點進出**(主力券商買賣超)")
                bk_label = st.radio("區間", ["當日", "近3日", "近5日"], horizontal=True, key="bk_days")
                bk_days = {"當日": 1, "近3日": 3, "近5日": 5}[bk_label]
                bk = c_broker(code, bk_days)
                if not bk:
                    st.info("抓不到分點資料(HiStock 改版/反爬或當日無資料)。分點為第三方爬蟲,僅供參考。")
                else:
                    st.caption(f"資料區間:{bk['區間']}(來源 HiStock,非官方、僅供參考)")
                    bkc1, bkc2 = st.columns(2)
                    with bkc1:
                        st.markdown("🟢 **買超前段**")
                        st.dataframe(styled_table(bk["買超"][["券商", "買超(張)", "均價"]].head(12)),
                                     width="stretch", hide_index=True)
                    with bkc2:
                        st.markdown("🔴 **賣超前段**")
                        st.dataframe(styled_table(bk["賣超"][["券商", "買超(張)", "均價"]].head(12)),
                                     width="stretch", hide_index=True)
                    st.caption("分點買賣超常用來推測主力動向,但分點不等於特定人,且含借券/避險等雜訊,請斟酌。")

            # ---------- 回測 · 部位 ----------
            elif view == "🧪 回測·部位":
                st.markdown(f"**訊號回測(持有{hold_days}日,含停損停利+手續費)**")
                bc1, bc2, bc3 = st.columns(3)
                use_sl = bc1.checkbox("啟用停損", value=True)
                sl = bc1.number_input("停損%", value=5.0, disabled=not use_sl)
                use_tp = bc2.checkbox("啟用停利", value=True)
                tp = bc2.number_input("停利%", value=10.0, disabled=not use_tp)
                sel_sig = bc3.selectbox("看權益曲線的訊號", [v[0] for v in BACKTESTABLE.values()])
                slv = sl if use_sl else None
                tpv = tp if use_tp else None
                bt = backtest_all(df, hold_days=hold_days, stop_loss=slv, take_profit=tpv)
                st.dataframe(styled_table(bt, ["平均報酬%", "累積報酬%"]),
                             width="stretch", hide_index=True)
                bench = c_fetch("0050", s_period)
                br = benchmark_return(df, bench)
                if br is not None:
                    st.caption(f"同期 0050 買進持有報酬:**{br:+.1f}%**(作為比較基準)")
                key = [k for k, v in BACKTESTABLE.items() if v[0] == sel_sig][0]
                r = backtest_signal(df, key, hold_days=hold_days, stop_loss=slv, take_profit=tpv)
                if r["trades"] > 0 and r["equity"] is not None:
                    efig = go.Figure()
                    efig.add_trace(go.Scatter(x=r["equity_dates"], y=(r["equity"] - 1) * 100,
                                   mode="lines+markers", name="累積報酬%", line=dict(color="#1f77b4")))
                    efig.update_layout(height=260, title=f"{sel_sig} 權益曲線(累積報酬%)",
                                       margin=dict(l=10, r=10, t=30, b=10))
                    st.plotly_chart(efig, width="stretch", config=PLOTLY_CONFIG)
                    with st.expander(f"看 {sel_sig} 的每筆交易明細({r['trades']} 筆)"):
                        st.dataframe(styled_table(pd.DataFrame(r["trade_list"]), ["報酬%"]),
                                     width="stretch", hide_index=True)
                else:
                    st.caption(f"「{sel_sig}」在此期間觸發次數不足,無法畫權益曲線。")

                st.divider()
                st.markdown("**部位計算 + ATR 停損建議**")
                pc1, pc2, pc3 = st.columns(3)
                capital = pc1.number_input("本金(元)", value=500000, step=50000)
                risk_pct = pc2.number_input("單筆可承受風險%", value=2.0, step=0.5)
                atr_k = pc3.number_input("ATR 停損倍數", value=2.0, step=0.5)
                rs = risk_suggest(code, capital, risk_pct, atr_k, period=s_period)
                if "error" in rs:
                    st.warning(rs["error"])
                else:
                    pcc = st.columns(4)
                    pcc[0].metric("建議買進", f"{rs['可買張數']} 張")
                    pcc[1].metric("投入金額", f"{rs['投入金額']:,.0f}")
                    pcc[2].metric("建議停損價", f"{rs['停損價']}", f"-{rs['停損跌幅%']}%")
                    pcc[3].metric("最大虧損", f"{rs['實際最大虧損']:,.0f}", f"{rs['實際風險%']}%")
                    if rs["可買張數"] == 0:
                        st.caption("以整張計算下買不起 1 張(股價×1000 > 本金或風險上限),可考慮零股。")

            # ---------- 新聞 ----------
            elif view == "📰 新聞":
                nc1, nc2, nc3 = st.columns([2, 2, 1])
                extra_kw = nc1.text_input("額外關鍵字(選填,空白分隔,如:法說 訂單 ADR)",
                                          key="news_kw").strip()
                nc3.write("")  # 對齊用
                if nc3.button("🔄 重新整理", key="news_refresh"):
                    c_news.clear()
                    st.rerun()
                news_df = c_news(code, extra_kw)
                if news_df.empty:
                    st.info("近期無相關新聞,或來源暫時無法連線,稍後再試。")
                else:
                    srcs = sorted([s for s in news_df["來源"].unique() if s])
                    excl = nc2.multiselect("排除來源(選填)", srcs, key="news_excl")
                    show = news_df[~news_df["來源"].isin(excl)] if excl else news_df
                    st.caption(f"共 {len(show)} 則(Google News,快取5分鐘;按🔄可立即更新)。"
                               "內容僅供參考、非投資建議,請自行查證。")
                    for _, nrow in show.iterrows():
                        src = f" **[{nrow['來源']}]**" if nrow["來源"] else ""
                        st.markdown(f"- `{nrow['日期']}`{src} [{nrow['標題']}]({nrow['連結']})")


# ============================================================
# 分頁:中線分析
# ============================================================
with tab_swing:
    st.subheader("中線(波段)分析 — 持有數週到數月的角度")
    st.caption("看的是趨勢而非當日訊號:季線/年線排列、週KD、波段突破。用 2 年資料。")

    sc1, sc2 = st.columns([1, 3])
    swing_code = sc1.text_input("個股中線體檢(代號)", value="2330", key="sw_code").strip()
    if swing_code:
        r = c_swing(swing_code, "2y")
        if "error" in r:
            st.error(r["error"])
        else:
            nm = name_of(swing_code, c_names())
            badge = {"多頭": "🟢 多頭", "偏多": "🟢 偏多", "盤整": "🟡 盤整",
                     "偏空": "🔴 偏空", "空頭": "🔴 空頭"}.get(r["趨勢"], r["趨勢"])
            st.markdown(f"### {swing_code} {nm} — 中線趨勢:{badge}")
            mm = st.columns(4)
            mm[0].metric("收盤", f"{r['收盤']}")
            mm[1].metric("季線 MA60", f"{r['季線MA60']}")
            mm[2].metric("年線 MA240", f"{r['年線MA240']}")
            if r["週KD"]:
                mm[3].metric("週KD", f"{r['週KD'][0]:.0f}/{r['週KD'][1]:.0f}")
            st.write("**趨勢理由**:" + "、".join(r["理由"]))
            if r["中線訊號"]:
                st.success("中線訊號:" + " / ".join(r["中線訊號"]))
            else:
                st.info("目前無特別中線進場訊號(趨勢續抱觀察即可)。")

            # 中線圖:K線(紅漲/綠跌)+ 長均線
            e = r["_enriched"]
            sfig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                 row_heights=[0.7, 0.3], vertical_spacing=0.04,
                                 subplot_titles=("K線 / 季線MA60 / 半年線MA120 / 年線MA240", "週KD"))
            sfig.add_trace(go.Candlestick(x=e.index, open=e["Open"], high=e["High"],
                           low=e["Low"], close=e["Close"], name="K線",
                           text=cn_ohlc_hover(e), hoverinfo="text",
                           increasing_line_color="red", decreasing_line_color="green"), row=1, col=1)
            for n, label, c in [("MA60", "季線(60日)", "blue"), ("MA120", "半年線(120日)", "orange"), ("MA240", "年線(240日)", "purple")]:
                sfig.add_trace(go.Scatter(x=e.index, y=e[n], name=label, line=dict(width=1, color=c)), row=1, col=1)
            sfig.add_trace(go.Scatter(x=e.index, y=e["週K"], name="週K值", line=dict(color="orange", width=1)), row=2, col=1)
            sfig.add_trace(go.Scatter(x=e.index, y=e["週D"], name="週D值", line=dict(color="blue", width=1)), row=2, col=1)
            sfig.update_layout(height=500, xaxis_rangeslider_visible=False,
                               margin=dict(l=10, r=10, t=30, b=10),
                               legend=dict(orientation="h", y=1.06))
            sfig.update_xaxes(rangebreaks=[dict(values=date_breaks(e.index))])
            st.plotly_chart(sfig, width="stretch", config=PLOTLY_CONFIG)

            # 波段回測
            st.subheader("中線訊號波段回測(5年資料,含停損停利+手續費)")
            wb1, wb2, wb3 = st.columns(3)
            w_hold = wb1.selectbox("持有天數", [10, 20, 40, 60], index=1)
            w_sl = wb2.number_input("停損%", value=8.0, step=1.0, key="sw_sl")
            w_tp = wb3.number_input("停利%", value=20.0, step=1.0, key="sw_tp")
            wbt = c_swing_bt(swing_code, w_hold, w_sl, w_tp)
            st.dataframe(styled_table(wbt, ["平均報酬%", "累積報酬%"]),
                         width="stretch", hide_index=True)
            wbench = c_fetch("0050", "5y")
            wdf5 = c_fetch(swing_code, "5y")
            from backtest import benchmark_return as _br
            wbr = _br(wdf5, wbench) if not wdf5.empty else None
            if wbr is not None:
                st.caption(f"同期(5年)0050 買進持有報酬:**{wbr:+.1f}%**(比較基準)")
            st.caption("中線訊號觸發次數通常較少,數字代表性有限;波段操作仍須嚴設停損。")

    st.divider()
    st.markdown("**掃描觀察清單的中線趨勢**")
    only_bull = st.checkbox("只看偏多以上", value=True, key="sw_bull")
    if st.button("開始中線掃描", type="primary", key="btn_swing"):
        codes = load_watchlist()
        with st.spinner(f"中線掃描 {len(codes)} 檔(2年資料,稍久)..."):
            sdf = c_scan_swing(tuple(codes), only_bull)
        if sdf.empty:
            st.warning("沒有符合的個股。")
        else:
            st.success(f"共 {len(sdf)} 檔。")
            st.dataframe(styled_table(sdf), width="stretch", hide_index=True)
            st.download_button("⬇ 匯出 Excel", to_excel_bytes(sdf),
                               file_name=f"swing_{_dt.date.today()}.xlsx", key="dl_swing")
            st.session_state["swing_codes"] = list(sdf["代號"])
    if st.session_state.get("swing_codes"):
        jump_to_stock(st.session_state["swing_codes"], "swing_jump")


# ============================================================
# 分頁:比較(同業比較 + 多股 PK)
# ============================================================
with tab_cmp:
    names = c_names()
    ind_map = c_industry()
    cmp_mode = st.radio("模式", ["同業比較", "多股 PK", "類股強弱"], horizontal=True, key="cmp_mode")

    if cmp_mode == "類股強弱":
        st.caption("各產業近 N 個交易日的平均報酬(取自股池 universe.txt),看資金流向哪些類股。")
        sdays = st.selectbox("期間(交易日)", [5, 10, 20, 60], index=2, key="sec_days")
        with st.spinner("計算類股強弱..."):
            secdf = c_sector(tuple(load_universe()), sdays)
        if secdf.empty:
            st.warning("資料不足。")
        else:
            secfig = go.Figure()
            colors = ["#d62728" if v >= 0 else "#2ca02c" for v in secdf["平均報酬%"]]
            secfig.add_trace(go.Bar(x=secdf["平均報酬%"], y=secdf["產業"], orientation="h",
                                    marker_color=colors,
                                    text=[f"{v:+.1f}%" for v in secdf["平均報酬%"]],
                                    textposition="outside"))
            secfig.update_layout(height=max(320, 36 * len(secdf)),
                                 title=f"類股強弱 — 近{sdays}交易日平均報酬",
                                 margin=dict(l=10, r=10, t=40, b=10),
                                 yaxis=dict(autorange="reversed"))
            st.plotly_chart(secfig, width="stretch", config=PLOTLY_CONFIG)
            st.dataframe(styled_table(secdf), width="stretch", hide_index=True)
    elif cmp_mode == "同業比較":
        base = st.text_input("以哪一檔為基準找同業", value=st.session_state.get("st_code", "2330"),
                             key="cmp_base").strip()
        if base:
            industry = ind_map.get(base, "")
            if not industry:
                st.info("查不到該股的產業分類。")
            else:
                st.caption(f"{base} {name_of(base, names)} 產業:**{industry}**(同業取自股池 universe.txt 中相同產業者)")
                peers = [c for c in load_universe() if ind_map.get(c) == industry]
                if base not in peers:
                    peers = [base] + peers
                peers = peers[:16]
                with st.spinner(f"比較 {len(peers)} 檔同業..."):
                    rows = []
                    for c in peers:
                        d = c_fetch(c, "3mo")
                        if d.empty or len(d) < 2:
                            continue
                        cl = float(d["Close"].iloc[-1])
                        chg = (cl - float(d["Close"].iloc[-2])) / float(d["Close"].iloc[-2]) * 100
                        v = c_valuation(c)
                        rv = c_revenue(c)
                        rows.append({"代號": c, "名稱": names.get(c, ""), "收盤": round(cl, 1),
                                     "漲跌%": round(chg, 2),
                                     "本益比": v.get("PER") if v else None,
                                     "殖利率%": v.get("殖利率%") if v else None,
                                     "營收年增%": rv.get("年增率%") if rv else None})
                if rows:
                    cdf = pd.DataFrame(rows)
                    st.dataframe(styled_table(cdf, ["漲跌%"]),
                                 width="stretch", hide_index=True)
                    st.caption("點欄位標題可排序(例如依本益比由低到高找相對便宜的同業)。")
                else:
                    st.warning("同業資料抓取失敗,稍後再試。")
    else:
        codes_in = st.text_input("輸入 2~4 檔代號(空白或逗號分隔)", value="2330 2303 2454", key="cmp_pk")
        pk = [x.strip() for x in codes_in.replace(",", " ").split() if x.strip()][:4]
        cmp_period = st.selectbox("期間", ["3mo", "6mo", "1y"], index=1, key="cmp_period")
        if len(pk) >= 2:
            pkfig = go.Figure()
            rows = []
            for c in pk:
                d = c_fetch(c, cmp_period)
                if d.empty:
                    continue
                norm = d["Close"] / float(d["Close"].iloc[0]) * 100
                pkfig.add_trace(go.Scatter(x=d.index, y=norm, name=f"{c} {name_of(c, names)}"))
                cl = float(d["Close"].iloc[-1])
                ret = (cl / float(d["Close"].iloc[0]) - 1) * 100
                v = c_valuation(c)
                rv = c_revenue(c)
                rows.append({"代號": c, "名稱": names.get(c, ""), "收盤": round(cl, 1),
                             f"{cmp_period}報酬%": round(ret, 1),
                             "本益比": v.get("PER") if v else None,
                             "殖利率%": v.get("殖利率%") if v else None,
                             "營收年增%": rv.get("年增率%") if rv else None})
            pkfig.update_layout(height=360, title="走勢比較(起點正規化=100)",
                                margin=dict(l=10, r=10, t=30, b=10),
                                legend=dict(orientation="h", y=1.12))
            st.plotly_chart(pkfig, width="stretch", config=PLOTLY_CONFIG)
            if rows:
                pkdf = pd.DataFrame(rows)
                st.dataframe(styled_table(pkdf, [f"{cmp_period}報酬%"]),
                             width="stretch", hide_index=True)
        else:
            st.info("請至少輸入 2 檔代號。")


# ============================================================
# 分頁:盤勢 / 資金
# ============================================================
with tab_market:
    st.caption("大盤技術狀態、全市場法人買賣超、本週資金流入族群。按下方按鈕載入(避免拖慢其他頁)。")
    if st.button("🔄 載入 / 更新盤勢", type="primary", key="btn_market"):
        st.session_state["market_loaded"] = True
        c_index_status.clear()
        c_inst_total.clear()

    if st.session_state.get("market_loaded"):
        # 盤勢概觀
        st.subheader("📊 盤勢概觀")
        ms = c_index_status()
        if not ms:
            st.info("抓不到大盤資料,稍後再試。")
        else:
            badge = {"偏多": "🟢 偏多", "偏空": "🔴 偏空", "震盪": "🟡 震盪"}.get(ms["研判"], ms["研判"])
            mc = st.columns(5)
            mc[0].metric("加權指數", f"{ms['收盤']:,.0f}", f"{ms['漲跌%']:+.2f}%")
            mc[1].metric("研判", badge)
            mc[2].metric("月線 / 季線", f"{ms['月線MA20']:,.0f} / {ms['季線MA60']:,.0f}")
            mc[3].metric("RSI / KD", f"{ms['RSI']:.0f} / {ms['KD'][0]:.0f}")
            if ms.get("外資期貨淨口數") is not None:
                mc[4].metric("外資期貨淨口數", f"{ms['外資期貨淨口數']:+,.0f}")
            st.caption("研判理由:" + "、".join(ms["理由"]) + "(綜合大盤均線/KD與外資期貨,僅供參考)")

        # 全市場三大法人買賣超
        it = c_inst_total(30)
        if not it.empty:
            itfig = go.Figure()
            colors = ["#d62728" if v >= 0 else "#2ca02c" for v in it["三大法人合計"]]
            itfig.add_trace(go.Bar(x=it.index, y=it["三大法人合計"], name="合計", marker_color=colors))
            for col, color in [("外資", "#d62728"), ("投信", "#1f77b4"), ("自營商", "#2ca02c")]:
                itfig.add_trace(go.Scatter(x=it.index, y=it[col], name=col, line=dict(width=1, color=color)))
            itfig.add_hline(y=0, line_dash="dash", line_color="gray")
            itfig.update_layout(height=320, title="全市場三大法人買賣超(億元)",
                                margin=dict(l=10, r=10, t=40, b=10),
                                legend=dict(orientation="h", y=1.15))
            st.plotly_chart(itfig, width="stretch", config=PLOTLY_CONFIG)
            last = it.iloc[-1]
            st.caption(f"最新({it.index[-1]:%m/%d}):外資 {last['外資']:+,.0f} 億、"
                       f"投信 {last['投信']:+,.0f} 億、合計 {last['三大法人合計']:+,.0f} 億。"
                       "正=買超、負=賣超。")

        # 本週資金流入族群
        st.divider()
        st.subheader("📈 本週資金流入族群(近5交易日類股平均報酬)")
        sec = c_sector(tuple(load_universe()), 5)
        if sec.empty:
            st.info("資料不足。")
        else:
            secf = go.Figure()
            scolors = ["#d62728" if v >= 0 else "#2ca02c" for v in sec["平均報酬%"]]
            secf.add_trace(go.Bar(x=sec["平均報酬%"], y=sec["產業"], orientation="h",
                                  marker_color=scolors,
                                  text=[f"{v:+.1f}%" for v in sec["平均報酬%"]], textposition="outside"))
            secf.update_layout(height=max(300, 34 * len(sec)),
                               margin=dict(l=10, r=10, t=20, b=10),
                               yaxis=dict(autorange="reversed"))
            st.plotly_chart(secf, width="stretch", config=PLOTLY_CONFIG)
            st.caption("紅=資金流入(上漲)、綠=流出(下跌);取自股池 universe.txt 各產業近5日平均報酬。")
    else:
        st.info("👆 按「載入 / 更新盤勢」開始。")


# ============================================================
# 分頁:自選股管理
# ============================================================
with tab_watch:
    # 健診排行:一鍵把自選股全部評分排序
    st.subheader("🩺 觀察清單健診排行")
    st.caption("把自選股全部綜合評分並排序,快速看哪幾檔體質最好/最弱。第一次較慢(要抓不少資料),之後讀快取。")
    if st.button("開始健診", type="primary", key="btn_health"):
        wl = load_watchlist()
        prog = st.progress(0.0)
        rows = rank_codes(wl, progress_cb=lambda d, t: prog.progress(min(d / t, 1.0)))
        prog.empty()
        st.session_state["health_rows"] = rows
    if st.session_state.get("health_rows"):
        nm = c_names()
        hdf = pd.DataFrame(st.session_state["health_rows"])
        hdf.insert(1, "名稱", hdf["代號"].map(lambda c: nm.get(c, "")))
        hdf = hdf.sort_values("總分", ascending=False).reset_index(drop=True)
        st.dataframe(styled_table(hdf), width="stretch", hide_index=True)
        st.caption("評分為技術+基本+籌碼的濃縮數字,非投資建議。")
    st.divider()

    st.subheader("管理觀察清單(watchlist.txt)")
    st.caption("掃描分頁會用這份清單。新增/刪除後按儲存即可。")
    current = load_watchlist()
    names = c_names()

    addc1, addc2 = st.columns([3, 1])
    new_code = addc1.text_input("新增代號(可一次多個,空白或逗號分隔)", key="add_code")
    if addc2.button("➕ 新增"):
        for tok in new_code.replace(",", " ").split():
            tok = tok.strip().upper()
            if tok and tok not in current:
                current.append(tok)
        save_watchlist(current)
        st.success("已新增,重新整理後生效。")
        st.rerun()

    if current:
        st.write(f"目前 {len(current)} 檔:")
        del_targets = []
        cols = st.columns(4)
        for i, c in enumerate(current):
            with cols[i % 4]:
                if st.checkbox(f"{c} {names.get(c, '')}", key=f"wl_{c}"):
                    del_targets.append(c)
        if st.button("🗑 刪除勾選的") and del_targets:
            current = [c for c in current if c not in del_targets]
            save_watchlist(current)
            st.success(f"已刪除 {len(del_targets)} 檔。")
            st.rerun()
    else:
        st.info("清單目前是空的,從上方新增。")

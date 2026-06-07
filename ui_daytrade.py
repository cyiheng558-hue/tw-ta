# -*- coding: utf-8 -*-
"""當沖看盤 UI:即時看板、異動掃描、分鐘K+VWAP、五檔、提醒、損益試算。

從 ui_common.py 拆出以縮小神模組。依賴 ui_common 的通用 helper/快取。
"""
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from data import fetch_intraday
from realtime import quote as rt_quote, quote_detail, index_quote, is_market_hours
from tw_time import taipei_now
from ui_common import styled_table, PLOTLY_CONFIG, c_fetch_many

__all__ = ["daytrade_board", "intraday_chart", "orderbook_panel", "intraday_movers",
           "index_strength_bar", "alerts_ui", "market_breadth", "daytrade_pnl"]


# ===================== 當沖看盤 =====================
@st.cache_data(ttl=60, show_spinner=False)
def c_intraday(code, interval):
    return fetch_intraday(code, interval)


def _movement_flag(pct):
    """依漲跌% 標異動(避免用『成交>=高』那種恆成立的創高判斷)。"""
    if pct is None:
        return ""
    if pct >= 9.5:
        return "🔴漲停近"
    if pct <= -9.5:
        return "🟢跌停近"
    if pct >= 5:
        return "📈強勢"
    if pct <= -5:
        return "📉弱勢"
    return ""


def _trade_progress():
    """當日交易時間進度(0~1),用來把盤中累積量正規化成『全日預估』。"""
    now = taipei_now()
    mins = now.hour * 60 + now.minute
    start, end = 9 * 60, 13 * 60 + 30
    if now.weekday() >= 5 or mins >= end:
        return 1.0          # 盤後/假日:視為整日
    if mins <= start:
        return 0.05
    return max(0.05, (mins - start) / (end - start))


def _board_render(codes, names):
    df = rt_quote(codes)
    if df.empty:
        st.info("即時報價暫時無法取得(盤後/假日,或來源限流/雲端被擋)。")
        return
    df = df.copy()
    df["名稱"] = df["代號"].map(lambda c: names.get(str(c), ""))

    df["異動"] = df["漲跌%"].apply(_movement_flag)
    # 相對強弱 = 個股漲跌% − 大盤漲跌%(>0 強於大盤)
    mkt = c_index_quote().get("加權指數", {}).get("漲跌%")
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
    m = st.columns(3)
    if av:
        ratio = bv / av
        m[0].metric("內外盤比(委買/委賣)", f"{ratio:.2f}",
                    "委買強" if ratio > 1.2 else ("委賣強" if ratio < 0.83 else "平衡"))
    else:
        m[0].metric("內外盤比", "委賣掛單為0", "可能鎖漲停")
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
        if len(df) >= 20:   # 須滿20日才算均量,量比基準才穩
            out[c] = float(df["Volume"].tail(20).mean()) / 1000.0  # 股 -> 張
    return out


def intraday_movers(codes, names):
    """盤中異動掃描:回傳含 漲跌%/量比/異動 的即時 DataFrame(從股池找當沖候選)。"""
    q = rt_quote(list(codes))
    if q.empty:
        return pd.DataFrame()
    avg = _avg_volume(tuple(codes))
    prog = _trade_progress()   # 盤中進度,把累積量正規化成全日預估
    q = q.copy()
    q["名稱"] = q["代號"].map(lambda c: names.get(str(c), ""))

    def _ratio(r):
        a = avg.get(r["代號"])
        # 量比 = 今日累積量 ÷ (20日均量 × 盤中進度);避免早盤累積量未滿被低估
        return round(r["累積量(張)"] / (a * prog), 2) if a else None

    q["量比"] = q.apply(_ratio, axis=1)
    q["異動"] = q["漲跌%"].apply(_movement_flag)
    return q[["代號", "名稱", "成交", "漲跌%", "量比", "異動", "累積量(張)", "高", "低"]]


@st.cache_data(ttl=5, show_spinner=False)
def c_index_quote():
    """即時大盤指數,短快取(5秒)以便看板與大盤列共用、不重複打 MIS。"""
    return index_quote()


@st.cache_data(ttl=60, show_spinner=False)
def _index_intraday():
    return fetch_intraday("^TWII", "5m")


def index_strength_bar():
    """大盤即時連動:加權/櫃買即時 + 加權分時走勢迷你圖。"""
    idx = c_index_quote()
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
    codemap = {str(c).upper().replace(".TWO", "").replace(".TW", "").strip(): i
               for i, c in df["代號"].items()}  # 正規化代號比對
    hits = []
    for a in alerts:
        ac = str(a["code"]).upper().replace(".TWO", "").replace(".TW", "").strip()
        if ac not in codemap:
            continue
        r = df.loc[codemap[ac]]
        p, px = r["漲跌%"], r["成交"]
        key = (ac, a["kind"], a["value"])
        ok = ((a["kind"] == "漲跌%≥" and p is not None and p >= a["value"]) or
              (a["kind"] == "漲跌%≤" and p is not None and p <= a["value"]) or
              (a["kind"] == "價≥" and px is not None and px >= a["value"]) or
              (a["kind"] == "價≤" and px is not None and px <= a["value"]))
        if ok and key not in fired:
            _ps = f"{p:+.2f}%" if p is not None else "—"
            hits.append(f"{a['code']} {r['名稱']} {a['kind']}{a['value']}(現 {px} / {_ps})")
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
                    _ac = str(al["code"]).upper().replace(".TWO", "").replace(".TW", "").strip()
                    st.session_state.get("dt_alert_fired", set()).discard((_ac, al["kind"], al["value"]))
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
    # 手續費單邊最低 20 元(多數券商;低價股/小單影響大)
    fee = max(buy_cost * fee_rate, 20) + max(sell_amt * fee_rate, 20)
    tax = sell_amt * tax_rate
    net = (sell_amt - buy_cost) - fee - tax
    # 損益兩平:賣價需多少才能打平成本
    be = entry * (1 + fee_rate) / (1 - fee_rate - tax_rate)
    r = st.columns(4)
    r[0].metric("價差損益", f"{(exit_-entry)*shares:,.0f}")
    r[1].metric("手續費+稅", f"-{fee+tax:,.0f}")
    r[2].metric("淨損益", f"{net:,.0f}", f"{net/buy_cost*100:+.2f}%" if buy_cost else None)
    r[3].metric("損益兩平賣價", f"{be:.2f}", f"+{(be-entry)/entry*100:.2f}%")
    st.caption("當沖證交稅減半(0.15%);手續費單邊 0.1425%×折數、最低20元。實際以你券商收費為準。")

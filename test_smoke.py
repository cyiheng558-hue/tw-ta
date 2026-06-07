# -*- coding: utf-8 -*-
"""煙霧測試:用合成資料離線驗證核心計算,確保改程式不會默默弄壞。

執行:在 tw_ta 資料夾下 `python -m pytest -q`(或雙擊 測試.bat)。
這些測試不連網路(不依賴 yfinance/FinMind),所以快又穩定。
"""
import math
import pandas as pd
import pytest


def make_ohlcv(n=600):
    """產生 n 天的合成日線(趨勢+波動,確定性,不用亂數)。"""
    idx = pd.date_range("2023-01-02", periods=n, freq="B")
    closes, highs, lows, opens, vols = [], [], [], [], []
    price = 100.0
    for i in range(n):
        price *= 1 + (0.0008 + 0.02 * math.sin(i / 15.0)) * 0.1
        o = price * (1 + 0.003 * math.sin(i / 3.0))
        c = price
        hi = max(o, c) * 1.01
        lo = min(o, c) * 0.99
        opens.append(o); closes.append(c); highs.append(hi); lows.append(lo)
        vols.append(1_000_000 + int(500_000 * abs(math.sin(i / 5.0))))
    return pd.DataFrame({"Open": opens, "High": highs, "Low": lows,
                         "Close": closes, "Volume": vols}, index=idx)


@pytest.fixture(scope="module")
def df():
    return make_ohlcv()


def test_all_modules_import():
    import indicators, signals, backtest, swing, risk, score  # noqa
    import data, chips, fundamentals, news, finmind, broker, screener  # noqa
    import sector, futures, market, realtime, charting, tw_time, assistant  # noqa
    import ui_common, ui_daytrade  # noqa


def test_indicators(df):
    from indicators import enrich
    e = enrich(df)
    for col in ["MA5", "MA20", "MA60", "K", "D", "DIF", "MACD", "HIST",
                "RSI14", "BIAS10", "ATR14", "OBV", "BB_UP", "BB_LOW"]:
        assert col in e.columns, f"缺欄位 {col}"
    last = e.iloc[-1]
    assert 0 <= last["RSI14"] <= 100
    assert 0 <= last["K"] <= 100
    assert last["ATR14"] > 0


def test_signals(df):
    from indicators import enrich
    from signals import scan_one
    bull, bear = scan_one(enrich(df))
    assert isinstance(bull, list) and isinstance(bear, list)


def test_backtest(df):
    from backtest import backtest_all
    bt = backtest_all(df, hold_days=5, stop_loss=5, take_profit=10)
    assert list(bt.columns) == ["訊號", "交易次數", "勝率%", "平均報酬%", "累積報酬%", "最大回撤%"]
    assert len(bt) >= 5


def test_swing(df):
    from swing import enrich_swing, trend_status, swing_signals, backtest_swing
    e = enrich_swing(df)
    assert "MA240" in e.columns and "週K" in e.columns
    status = trend_status(e)
    assert status["趨勢"] in ("多頭", "偏多", "盤整", "偏空", "空頭")
    assert isinstance(swing_signals(e), list)
    wb = backtest_swing(df, hold_days=20)
    assert "中線訊號" in wb.columns


def test_risk():
    from risk import position_size
    r = position_size(500000, 2.0, 100.0, 95.0)
    assert r["可買張數"] >= 0
    assert r["停損價"] == 95.0
    # 風險金額不超過設定上限(含整張捨去後)
    assert r["實際最大虧損"] <= 500000 * 0.02 + 1


def test_score_technical(df):
    from indicators import enrich
    from score import technical_score
    s, notes = technical_score(enrich(df), swing_trend="多頭")
    assert 0 <= s <= 100
    assert isinstance(notes, list)


def test_finmind_cache_key_no_token():
    """快取鍵不應包含 token(確保有無 token 共用同一份快取)。"""
    import finmind
    p = finmind._cache_path({"dataset": "X", "data_id": "2330"})
    assert "token" not in p.lower()


def test_assistant_kb():
    from assistant import answer
    assert "KD" in answer("KD是什麼")
    a = answer("可以買2330嗎")           # 問買賣 → 應觸發免責
    assert ("投資建議" in a) or ("明牌" in a)
    assert "我可以回答" in answer("zxcvbnm 隨機亂碼")  # 不相關 → fallback


def test_movement_flag():
    from ui_daytrade import _movement_flag
    assert _movement_flag(10) == "🔴漲停近"
    assert _movement_flag(-10) == "🟢跌停近"
    assert _movement_flag(6) == "📈強勢"
    assert _movement_flag(-6) == "📉弱勢"
    assert _movement_flag(0) == "" and _movement_flag(None) == ""

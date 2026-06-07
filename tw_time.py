# -*- coding: utf-8 -*-
"""時間工具:一律用台北時區(UTC+8)的「今天」,避免雲端 UTC 環境差一天。"""
import datetime as _dt

_TPE = _dt.timezone(_dt.timedelta(hours=8))


def taipei_today() -> _dt.date:
    return _dt.datetime.now(_TPE).date()


def taipei_now() -> _dt.datetime:
    return _dt.datetime.now(_TPE)

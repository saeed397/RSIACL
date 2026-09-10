# -*- coding: utf-8 -*-
"""
signal_filter.py
================
لایه‌ی Signal Filter — «تغییر مجاز شماره ۱».

⚠️ این فایل هیچ‌کدام از مراحل تشخیص واگرایی/همگرایی را دوباره پیاده‌سازی
یا بازمحاسبه نمی‌کند. فقط روی خروجی *نهایی و آماده*ی تابع بدون‌تغییر
detect_rsi_tops_bottoms (از rsi_div_core.py) یک فیلتر ساده‌ی زمانی
اعمال می‌کند: آیا کندل پایان رویداد (همان end_bar واقعی که قبلاً در
rsi_div_core.py برابر با خودِ کندل کف/سقف RSI است، نه کندل تأیید)
حداکثر ۹ کندل قبل از آخرین کندل موجود است یا نه.

قانون دقیق (طبق دستورالعمل):
    candles_ago_end == 1..9   -> معتبر
    candles_ago_end == 0      -> رویداد هنوز باز/تأیید نشده - نامعتبر
    candles_ago_end >= 10     -> نامعتبر
"""

from __future__ import annotations
from typing import List
from rsi_div_core import DivEvent  # فقط برای type hint، بدون فراخوانی هیچ منطقی از آن فایل


def filter_recent_events(
    events: List[DivEvent],
    last_bar_index: int,
    max_candles_ago: int = 9,
) -> List[DivEvent]:
    """
    events: خروجی خام و دست‌نخورده‌ی detect_rsi_tops_bottoms
    last_bar_index: ایندکس آخرین کندل موجود در دیتاست (len(df)-1)

    خروجی: فقط رویدادهایی که (last_bar_index - end_bar) بین ۱ تا
    max_candles_ago (شامل هر دو سر) باشد.
    """
    kept = []
    for ev in events:
        candles_ago_end = last_bar_index - ev.end_bar
        if 1 <= candles_ago_end <= max_candles_ago:
            kept.append(ev)
    return kept

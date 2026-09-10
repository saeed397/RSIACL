# -*- coding: utf-8 -*-
"""
app.py
======
UI بازطراحی‌شده (Mobile First) + اسکن گروهی ۵۰تایی رمزارز بر اساس Market Cap.

⚠️ نکته‌ی بسیار مهم درباره‌ی معماری این فایل:
تمام محاسبات مربوط به RSI، Heikin Ashi، و تشخیص واگرایی/همگرایی، دقیقاً
با همان توابع بدون‌تغییرِ فایل‌های rsi_div_core.py و heikin_ashi.py انجام
می‌شود — این فایل فقط UI، حلقه‌ی اسکن روی چند نماد، فیلتر ۹ کندل، و
فرمت خروجی متنی را اضافه می‌کند. هیچ فرمول یا شرطی از Strategy در اینجا
بازنویسی نشده است.
"""

import numpy as np
import pandas as pd
import streamlit as st

from data_feed import fetch_ohlcv, fetch_ohlcv_yearly
from rsi_div_core import detect_rsi_tops_bottoms, wilder_rsi, DivEvent
from heikin_ashi import to_heikin_ashi
from signal_filter import filter_recent_events
from market_cap import fetch_top_market_cap, get_group, to_exchange_symbol, GROUP_RANGES, group_label

st.set_page_config(page_title="RSI Tops & Bottoms", layout="centered")

# ----------------------------------------------------------------------
# استایل رنگی ساده (قرمز=واگرایی/نزولی ، سبز=همگرایی/صعودی) - فقط ظاهری
# ----------------------------------------------------------------------
st.markdown(
    """
    <style>
    .rsi-title { font-size: 1.3rem; font-weight: 700; margin-bottom: 0.2rem; }
    .signal-red {
        background-color: rgba(255,0,0,0.08); border-right: 4px solid #d32f2f;
        padding: 10px 12px; border-radius: 6px; margin-bottom: 8px; direction: rtl;
    }
    .signal-green {
        background-color: rgba(0,180,0,0.08); border-right: 4px solid #2e7d32;
        padding: 10px 12px; border-radius: 6px; margin-bottom: 8px; direction: rtl;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="rsi-title">RSI Tops &amp; Bottoms</div>', unsafe_allow_html=True)

# ----------------------------------------------------------------------
# تنظیمات اصلی (همیشه قابل‌مشاهده در صفحه‌ی اول - طبق درخواست)
# ----------------------------------------------------------------------
group_options = {group_label(s, e): (s, e) for s, e in GROUP_RANGES}
selected_group_label = st.selectbox("گروه رمزارزها (بر اساس Market Cap)", list(group_options.keys()))
start_rank, end_rank = group_options[selected_group_label]

TIMEFRAME_OPTIONS = ["1m", "5m", "15m", "30m", "1h", "4h", "6h", "12h", "1d", "1w", "1M", "1Y"]
timeframe = st.selectbox("تایم‌فریم", TIMEFRAME_OPTIONS, index=6)  # پیش‌فرض: 6h

run = st.button("دریافت داده و محاسبه", type="primary", use_container_width=True)

# ----------------------------------------------------------------------
# تنظیمات پیشرفته - مخفی، فقط با باز کردن Expander در دسترس است
# ----------------------------------------------------------------------
with st.expander("⚙️ تنظیمات پیشرفته"):
    limit = st.slider("تعداد کندل دریافتی برای هر رمزارز", min_value=200, max_value=1000, value=500, step=50)
    use_heikin_ashi = st.checkbox("استفاده از کندل Heikin Ashi", value=True)
    max_candles_ago = st.number_input("حداکثر فاصله‌ی سیگنال معتبر (کندل)", value=9, min_value=1)

    st.caption("پارامترهای اندیکاتور (دقیقاً مطابق Pine Script اصلی)")
    rsi_len = st.number_input("RSI Length", value=14, min_value=1)
    ob = st.number_input("Upper Band (ob)", value=70.0)
    os_level = st.number_input("Lower Band (os)", value=30.0)
    prd = st.number_input("Max Bars in OB/OS (prd)", value=10, min_value=1)
    mindis = st.number_input("Min Bars between Tops/Bottoms (mindis)", value=5, min_value=0)
    maxdis = st.number_input("Max Bars between Tops/Bottoms (maxdis)", value=100, min_value=1)


# ----------------------------------------------------------------------
# اجرای استراتژی برای یک نماد (بدون هیچ تغییری نسبت به نسخه‌ی قبل)
# ----------------------------------------------------------------------
def run_strategy_for_symbol(symbol: str, timeframe: str):
    """
    این تابع دقیقاً همان مراحل نسخه‌ی قبلی را طی می‌کند:
    fetch -> (Heikin Ashi) -> wilder_rsi -> detect_rsi_tops_bottoms
    هیچ فرمول یا شرطی نسبت به نسخه‌ی قبل تغییر نکرده است.
    """
    if timeframe == "1Y":
        df, source = fetch_ohlcv_yearly(symbol=symbol, years_back=max(10, limit // 12 + 2))
    else:
        df, source = fetch_ohlcv(symbol=symbol, timeframe=timeframe, limit=limit)

    calc_df = to_heikin_ashi(df) if use_heikin_ashi else df
    rsi = wilder_rsi(calc_df["close"].to_numpy(dtype=float), int(rsi_len))
    calc_df = calc_df.copy()
    calc_df["rsi"] = rsi

    events = detect_rsi_tops_bottoms(
        calc_df,
        rsi_len=int(rsi_len),
        ob=float(ob),
        os_level=float(os_level),
        prd=int(prd),
        mindis=int(mindis),
        maxdis=int(maxdis),
    )
    last_bar_index = len(df) - 1
    recent_events = filter_recent_events(events, last_bar_index, int(max_candles_ago))
    return recent_events, last_bar_index, df


def format_signal_line(base_symbol: str, ev: DivEvent, last_bar_index: int) -> str:
    start_ago = last_bar_index - ev.start_bar
    end_ago = last_bar_index - ev.end_bar
    if ev.kind == "top":
        return (
            f"🔴 رمزارز {base_symbol} واگرایی از RSI [{ev.start_rsi:.0f}] در {start_ago} "
            f"کندل قبلی شروع و در RSI [{ev.end_rsi:.0f}] در {end_ago} کندل قبلی به پایان رسیده است."
        )
    else:
        return (
            f"🟢 رمزارز {base_symbol} همگرایی از RSI [{ev.start_rsi:.0f}] در {start_ago} "
            f"کندل قبلی شروع و در RSI [{ev.end_rsi:.0f}] در {end_ago} کندل قبلی به پایان رسیده است."
        )


if run:
    with st.spinner("در حال دریافت رتبه‌بندی Market Cap از CoinGecko..."):
        try:
            ranked = fetch_top_market_cap(limit=500)
        except Exception as e:  # noqa: BLE001
            st.error(f"خطا در دریافت رتبه‌بندی Market Cap: {e}")
            st.stop()

    group = get_group(ranked, start_rank, end_rank)
    if not group:
        st.warning("هیچ رمزارزی در این بازه‌ی رتبه یافت نشد.")
        st.stop()

    st.caption(f"در حال بررسی {len(group)} رمزارز (رتبه {start_rank} تا {end_rank})...")
    progress = st.progress(0)
    not_found = []
    any_signal = False

    for idx, coin in enumerate(group):
        base_symbol = coin["symbol"]
        exch_symbol = to_exchange_symbol(base_symbol)
        try:
            recent_events, last_bar_index, df = run_strategy_for_symbol(exch_symbol, timeframe)
        except Exception as e:  # noqa: BLE001
            not_found.append(base_symbol)
            progress.progress((idx + 1) / len(group))
            continue

        for ev in recent_events:
            any_signal = True
            line = format_signal_line(base_symbol, ev, last_bar_index)
            css_class = "signal-red" if ev.kind == "top" else "signal-green"
            st.markdown(f'<div class="{css_class}">{line}</div>', unsafe_allow_html=True)

        progress.progress((idx + 1) / len(group))

    progress.empty()

    if not any_signal:
        st.info(
            f"هیچ واگرایی یا همگرایی واجد شرایطی در محدوده حداکثر {int(max_candles_ago)} "
            "کندل گذشته مشاهده نشد."
        )

    if not_found:
        with st.expander(f"رمزارزهای یافت‌نشده در صرافی‌های موجود ({len(not_found)} مورد)"):
            for s in not_found:
                st.write(f"رمز {s} در صرافی‌های موجود یافت نشد.")
else:
    pass

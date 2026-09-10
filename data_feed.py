# -*- coding: utf-8 -*-
"""
data_feed.py
============
دریافت آنلاین دیتای OHLCV با ccxt.
طبق درخواست کاربر:
  - صرافی اصلی: BingX  (اسپات)
  - صرافی پشتیبان (fallback خودکار در صورت قطعی/خطای اتصال): KuCoin
    (هر دو، پوشش وسیعی از بازار کریپتو دارند و اندپوینت‌های آن‌ها به
    دلیل تحریم ایران برای Binance مسدود نمی‌شوند - Binance عمداً استفاده
    نشده است).
  - در صورت نیاز می‌توانید لیست FALLBACK_EXCHANGES را تغییر دهید.
"""

from __future__ import annotations
import pandas as pd
import ccxt
from typing import Optional, Tuple, List

PRIMARY_EXCHANGE = "bingx"
FALLBACK_EXCHANGES: List[str] = ["kucoin", "okx", "gateio"]


def _make_exchange(exchange_id: str):
    klass = getattr(ccxt, exchange_id)
    return klass({"enableRateLimit": True})


def fetch_ohlcv(
    symbol: str = "DASH/USDT",
    timeframe: str = "1d",
    limit: int = 500,
) -> Tuple[pd.DataFrame, str]:
    """
    تلاش برای دریافت دیتا از BingX؛ در صورت هر نوع خطا (قطعی شبکه،
    نماد پیدا نشد، ریت‌لیمیت و ...) به صورت خودکار سراغ صرافی(های)
    پشتیبان می‌رود.

    خروجی: (DataFrame با ستون‌های open/high/low/close/volume و ایندکس
    datetime صعودی از قدیم به جدید، نام صرافی که دیتا از آن گرفته شد)
    """
    tried = []
    for exchange_id in [PRIMARY_EXCHANGE] + FALLBACK_EXCHANGES:
        try:
            ex = _make_exchange(exchange_id)
            ex.load_markets()
            if symbol not in ex.symbols:
                # برخی صرافی‌ها فرمت نماد را کمی متفاوت می‌خواهند
                alt = symbol.replace("/", "")
                candidates = [s for s in ex.symbols if s.replace("/", "") == alt]
                if not candidates:
                    raise ValueError(f"نماد {symbol} در {exchange_id} یافت نشد")
                symbol_use = candidates[0]
            else:
                symbol_use = symbol

            raw = ex.fetch_ohlcv(symbol_use, timeframe=timeframe, limit=limit)
            if not raw or len(raw) < 50:
                raise ValueError("داده‌ی کافی برگردانده نشد")

            df = pd.DataFrame(
                raw, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df = df.sort_values("timestamp").reset_index(drop=True)
            return df, exchange_id
        except Exception as e:  # noqa: BLE001
            tried.append(f"{exchange_id}: {e}")
            continue

    raise ConnectionError(
        "دریافت داده از هیچ‌کدام از صرافی‌ها ممکن نشد.\n" + "\n".join(tried)
    )


# ----------------------------------------------------------------------
# توابع زیر صرفاً برای «تغییر مجاز شماره ۳ (تایم‌فریم‌های جدید)» اضافه
# شده‌اند و به fetch_ohlcv بالا دست نمی‌زنند. منطق fetch_ohlcv عیناً حفظ
# شده؛ 6h و 12h و 1M همگی تایم‌فریم‌های استاندارد ccxt هستند و مستقیماً
# از طریق همان fetch_ohlcv (بدون هیچ تغییری) پشتیبانی می‌شوند. تنها 1Y
# (سالانه) نیاز به یک تابع جداگانه‌ی تجمیع (aggregation) دارد چون هیچ‌کدام
# از صرافی‌ها native candle سالانه ارائه نمی‌دهند.
# ----------------------------------------------------------------------
def fetch_ohlcv_yearly(
    symbol: str = "BTC/USDT",
    years_back: int = 10,
) -> Tuple[pd.DataFrame, str]:
    """
    ساخت کندل سالانه با تجمیع کندل‌های ماهانه (1M) که از fetch_ohlcv
    (بدون هیچ تغییری در آن تابع) گرفته می‌شوند.

    قانون تجمیع هر سال تقویمی (میلادی، ژانویه تا دسامبر):
        open   = open اولین ماه آن سال
        high   = بیشینه‌ی high تمام ماه‌های آن سال
        low    = کمینه‌ی low تمام ماه‌های آن سال
        close  = close آخرین ماه آن سال
        volume = مجموع volume تمام ماه‌های آن سال

    فقط سال‌هایی که دقیقاً ۱۲ کندل ماهانه‌ی کامل دارند لحاظ می‌شوند
    (سال جاری/ناقص کنار گذاشته می‌شود تا کندل نادرست ساخته نشود).
    """
    monthly_limit = years_back * 12 + 13  # کمی حاشیه برای اطمینان از پوشش کامل
    df_monthly, source = fetch_ohlcv(symbol=symbol, timeframe="1M", limit=monthly_limit)

    df_monthly["year"] = df_monthly["timestamp"].dt.year
    rows = []
    for year, grp in df_monthly.groupby("year"):
        if len(grp) != 12:
            continue  # سال ناقص - رد شود
        grp = grp.sort_values("timestamp")
        rows.append(
            {
                "timestamp": grp["timestamp"].iloc[0],
                "open": grp["open"].iloc[0],
                "high": grp["high"].max(),
                "low": grp["low"].min(),
                "close": grp["close"].iloc[-1],
                "volume": grp["volume"].sum(),
            }
        )

    if not rows:
        raise ValueError(
            "داده‌ی ماهانه‌ی کافی برای ساخت حتی یک کندل سالانه‌ی کامل موجود نیست."
        )

    df_yearly = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    return df_yearly, source

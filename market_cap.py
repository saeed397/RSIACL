# -*- coding: utf-8 -*-
"""
market_cap.py
=============
لایه‌ی Data Acquisition — گرفتن رتبه‌بندی Market Cap از CoinGecko (رایگان،
بدون نیاز به API Key) و آماده‌سازی نماد برای استفاده در fetch_ohlcv.

⚠️ این فایل هیچ منطق مربوط به RSI، Heikin Ashi، یا تشخیص واگرایی/همگرایی
ندارد و به هیچ‌کدام از این فایل‌ها (rsi_div_core.py, heikin_ashi.py)
وابسته نیست. فقط لیستی از نمادها (مثل "BTC/USDT") را به ترتیب Market Cap
برمی‌گرداند تا لایه‌ی Strategy (بدون تغییر) روی هرکدام جداگانه اجرا شود.

گروه‌بندی رتبه‌ها (طبق دستورالعمل):
  رتبه ۱-۵۰, ۵۱-۱۰۰, ..., ۴۵۱-۵۰۰  (۱۰ گروه، هرکدام ۵۰ رمزارز)
"""

from __future__ import annotations
import requests
from typing import List, Dict, Optional
import time

COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"

GROUP_RANGES = [
    (1, 50), (51, 100), (101, 150), (151, 200), (201, 250),
    (251, 300), (301, 350), (351, 400), (401, 450), (451, 500),
]


def group_label(start: int, end: int) -> str:
    return f"رتبه {start} تا {end}"


def fetch_top_market_cap(limit: int = 500) -> List[Dict]:
    """
    دریافت لیست رمزارزهای برتر بر اساس Market Cap از CoinGecko.
    خروجی: لیستی از دیکشنری‌ها به ترتیب نزولی Market Cap، هرکدام شامل:
        {'rank': int, 'symbol': 'BTC', 'name': 'Bitcoin', 'market_cap': float}

    CoinGecko هر صفحه حداکثر ۲۵۰ آیتم برمی‌گرداند، پس برای ۵۰۰ تا به ۲
    درخواست نیاز است.
    """
    results: List[Dict] = []
    per_page = 250
    pages_needed = (limit + per_page - 1) // per_page

    for page in range(1, pages_needed + 1):
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": per_page,
            "page": page,
            "sparkline": "false",
        }
        resp = requests.get(COINGECKO_MARKETS_URL, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        for item in data:
            results.append(
                {
                    "rank": item.get("market_cap_rank"),
                    "symbol": (item.get("symbol") or "").upper(),
                    "name": item.get("name"),
                    "market_cap": item.get("market_cap"),
                }
            )
        if page < pages_needed:
            time.sleep(1.2)  # رعایت Rate Limit رایگان CoinGecko

    results = [r for r in results if r["rank"] is not None]
    results.sort(key=lambda r: r["rank"])
    return results[:limit]


def get_group(all_ranked: List[Dict], start_rank: int, end_rank: int) -> List[Dict]:
    """فیلتر کردن لیست کامل رتبه‌بندی‌شده به یک بازه‌ی رتبه‌ی مشخص (مثلاً ۱ تا ۵۰)."""
    return [r for r in all_ranked if start_rank <= r["rank"] <= end_rank]


def to_exchange_symbol(coingecko_symbol: str, quote: str = "USDT") -> str:
    """تبدیل نماد CoinGecko (مثل 'btc') به فرمت ccxt (مثل 'BTC/USDT')."""
    return f"{coingecko_symbol.upper()}/{quote.upper()}"

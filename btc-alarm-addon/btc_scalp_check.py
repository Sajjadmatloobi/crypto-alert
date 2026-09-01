"""
اسکریپت تک‌اجرایی چک استراتژی اسکلپ بیت‌کوین (EMA + VWAP) — با API عمومی MEXC
---------------------------------------------------------------------------
به‌جای yfinance، این نسخه مستقیم از اندپوینت عمومی فیوچرز MEXC دیتا می‌گیره
(همون که تو پروژه "crypto alert" ازش استفاده کردی) — بدون نیاز به هیچ توکن
یا API key، چون MEXC این اندپوینت رو عمومی و مستند گذاشته.

نکته: این فایل و state.json که تولید می‌کنه (به اسم btc_scalp_state.json)
عمداً با نام‌های متفاوت از فایل‌های پروژه "crypto alert" ساخته شدن تا هیچ
تداخل یا overwrite ای با کاری که اونجا انجام دادی پیش نیاد.
"""

import os
import json
import requests
from datetime import datetime

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

MEXC_KLINE_URL = "https://contract.mexc.com/api/v1/contract/kline/BTC_USDT"
INTERVAL = "Min5"

EMA_FAST = 9
EMA_SLOW = 21

STATE_FILE = "btc_scalp_state.json"


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"in_position": False, "entry_price": None}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, data={"chat_id": CHAT_ID, "text": text})
    if not resp.ok:
        print("خطا در ارسال پیام تلگرام:", resp.text)


def fetch_klines():
    resp = requests.get(MEXC_KLINE_URL, params={"interval": INTERVAL})
    resp.raise_for_status()
    data = resp.json()

    if not data.get("success", False):
        raise RuntimeError(f"پاسخ نامعتبر از MEXC: {data}")

    d = data["data"]
    closes = d["close"]
    highs = d["high"]
    lows = d["low"]
    return closes, highs, lows


def ema(values, period):
    k = 2 / (period + 1)
    ema_values = [values[0]]
    for price in values[1:]:
        ema_values.append(price * k + ema_values[-1] * (1 - k))
    return ema_values


def main():
    state = load_state()
    closes, highs, lows = fetch_klines()

    if len(closes) < EMA_SLOW + 5:
        print("دیتای کافی نیست، رد شد.")
        return

    ema_fast_series = ema(closes, EMA_FAST)
    ema_slow_series = ema(closes, EMA_SLOW)

    price = closes[-1]
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    fast_now, fast_prev = ema_fast_series[-1], ema_fast_series[-2]
    slow_now, slow_prev = ema_slow_series[-1], ema_slow_series[-2]

    bullish_cross = fast_prev <= slow_prev and fast_now > slow_now
    bearish_cross = fast_now < slow_now

    if not state["in_position"]:
        if bullish_cross:
            state["in_position"] = True
            state["entry_price"] = price
            send_telegram(
                f"🟢 سیگنال خرید بیت‌کوین (MEXC)\nقیمت: {price:,.2f} $\nزمان: {now_str}"
            )
            print("سیگنال خرید ارسال شد.")
        else:
            print("سیگنال جدیدی نیست.")
    else:
        if bearish_cross:
            entry = state["entry_price"]
            pnl_pct = (price - entry) / entry * 100
            send_telegram(
                f"🔴 سیگنال خروج بیت‌کوین (MEXC)\nورود: {entry:,.2f} $\nخروج: {price:,.2f} $\n"
                f"سود/ضرر: {pnl_pct:+.2f}%\nزمان: {now_str}"
            )
            state["in_position"] = False
            state["entry_price"] = None
            print("سیگنال خروج ارسال شد.")
        else:
            print("در پوزیشن هستیم، هنوز سیگنال خروج نیست.")

    save_state(state)


if __name__ == "__main__":
    main()

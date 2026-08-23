#!/usr/bin/env python3
"""
Crypto 100%+ Growth Alert Bot (Direct MEXC Futures data - real-time)
=======================================================================
هر بار اجرا میشه:
  1) مستقیم از API خود MEXC (بدون واسطه) قیمت لحظه‌ای و درصد رشد ۲۴ ساعته‌ی
     همه‌ی نمادهای فیوچرز رو می‌گیره (endpoint: /api/v1/contract/ticker)
  2) هر نمادی که رشدش >= PCT_THRESHOLD بود رو آلارم می‌ده

چون دیتا مستقیم از خود MEXC میاد (نه CoinGecko)، مشکل تداخل نماد با
کوین‌های بی‌ربط و مشکل تاخیر داده حل میشه.

توکن‌ها از Environment Variables خونده میشن:
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
"""

import json
import time
import os
import urllib.request
import urllib.error

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

PCT_THRESHOLD = 100.0

STATE_FILE = "crypto_alert_state.json"

MEXC_TICKER_URL = "https://contract.mexc.com/api/v1/contract/ticker"


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_mexc_tickers():
    try:
        data = fetch_json(MEXC_TICKER_URL)
    except Exception as e:
        print(f"[!] خطا در گرفتن دیتای MEXC: {e}")
        return []

    tickers = data.get("data", [])
    if not isinstance(tickers, list):
        print("[!] فرمت پاسخ MEXC غیرمنتظره بود.")
        return []

    return tickers


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"alerted": {}, "reset_time": 0}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
    except urllib.error.URLError as e:
        print(f"[!] خطای تلگرام: {e}")


def main():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[!] TELEGRAM_BOT_TOKEN یا TELEGRAM_CHAT_ID تنظیم نشده.")
        return

    state = load_state()

    tickers = fetch_mexc_tickers()
    print(f"[*] تعداد نمادهای دریافت‌شده از MEXC: {len(tickers)}")
    if not tickers:
        print("[!] هیچ داده‌ای دریافت نشد.")
        save_state(state)
        return

    now = time.time()
    if now - state.get("reset_time", 0) > 24 * 3600:
        state["alerted"] = {}
        state["reset_time"] = now

    alerts_sent = 0
    for t in tickers:
        symbol = t.get("symbol")
        last_price = t.get("lastPrice")
        rise_fall_rate = t.get("riseFallRate")

        if symbol is None or last_price is None or rise_fall_rate is None:
            continue

        change_pct = rise_fall_rate * 100

        if change_pct >= PCT_THRESHOLD and not state["alerted"].get(symbol):
            msg = (
                f"🚀 <b>{symbol}</b>\n"
                f"✅ فیوچرز MEXC\n"
                f"رشد ۲۴ ساعته: {change_pct:.1f}٪\n"
                f"قیمت الان: ${last_price}"
            )
            print(msg)
            send_telegram_message(msg)
            state["alerted"][symbol] = True
            alerts_sent += 1

    save_state(state)
    print(f"Done. Symbols checked: {len(tickers)}, alerts sent: {alerts_sent}")


if __name__ == "__main__":
    main()

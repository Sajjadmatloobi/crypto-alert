#!/usr/bin/env python3
"""
Crypto 100%+ Growth Alert Bot (KCEX Futures coins only - via CoinGecko)
=========================================================================
هر بار اجرا میشه:
  1) لیست همه‌ی نمادهایی که تو صرافی KCEX Futures معامله میشن رو از CoinGecko می‌گیره
     (چون خود KCEX هیچ API عمومی برای دیتای بازار نداره، از دیتای CoinGecko
     که خودش از KCEX دیتا جمع‌آوری می‌کنه استفاده می‌کنیم)
  2) لیست ~2000 ارز برتر رو از CoinGecko با درصد رشد 24 ساعته می‌گیره
  3) فقط ارزهایی که هم شرط رشد >= PCT_THRESHOLD رو دارن هم تو لیست KCEX Futures
     هستن رو آلارم می‌ده

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
PAGES_TO_FETCH = 8
PER_PAGE = 250
SLEEP_BETWEEN_PAGES = 2

STATE_FILE = "crypto_alert_state.json"

COINGECKO_MARKETS_URL = (
    "https://api.coingecko.com/api/v3/coins/markets"
    "?vs_currency=usd&order=market_cap_desc&per_page={per_page}&page={page}"
    "&price_change_percentage=24h&sparkline=false"
)

KCEX_EXCHANGE_ID = "kcex-futures"
KCEX_TICKERS_URL = (
    "https://api.coingecko.com/api/v3/exchanges/{exchange_id}/tickers?page={page}"
)


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_kcex_futures_symbols():
    symbols = set()
    page = 1
    max_pages = 15
    while page <= max_pages:
        url = KCEX_TICKERS_URL.format(exchange_id=KCEX_EXCHANGE_ID, page=page)
        try:
            data = fetch_json(url)
        except Exception as e:
            print(f"[!] خطا در گرفتن صفحه {page} از KCEX tickers: {e}")
            break

        tickers = data.get("tickers", [])
        if not tickers:
            break

        for t in tickers:
            base = t.get("base")
            if base:
                symbols.add(base.upper())

        page += 1
        time.sleep(2)

    return symbols


def fetch_all_coins():
    coins = []
    for page in range(1, PAGES_TO_FETCH + 1):
        url = COINGECKO_MARKETS_URL.format(per_page=PER_PAGE, page=page)
        try:
            data = fetch_json(url)
        except Exception as e:
            print(f"[!] خطا در گرفتن صفحه {page}: {e}")
            break
        if not data:
            break
        coins.extend(data)
        time.sleep(SLEEP_BETWEEN_PAGES)
    return coins


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

    kcex_symbols = fetch_kcex_futures_symbols()
    print(f"[*] تعداد ارزهای دارای فیوچرز در KCEX: {len(kcex_symbols)}")
    if not kcex_symbols:
        print("[!] لیست فیوچرز KCEX خالیه، از اجرای این دور صرف‌نظر میشه.")
        return

    coins = fetch_all_coins()
    if not coins:
        print("[!] هیچ داده‌ای از CoinGecko دریافت نشد.")
        return

    now = time.time()
    if now - state.get("reset_time", 0) > 24 * 3600:
        state["alerted"] = {}
        state["reset_time"] = now

    alerts_sent = 0
    for coin in coins:
        symbol = (coin.get("symbol") or "").upper()
        name = coin.get("name")
        price = coin.get("current_price")
        change = coin.get("price_change_percentage_24h")
        coin_id = coin.get("id")

        if change is None or price is None or coin_id is None:
            continue

        if symbol not in kcex_symbols:
            continue

        if change >= PCT_THRESHOLD and not state["alerted"].get(coin_id):
            msg = (
                f"🚀 <b>{name} ({symbol})</b>\n"
                f"✅ دارای فیوچرز در KCEX\n"
                f"رشد ۲۴ ساعته: {change:.1f}٪\n"
                f"قیمت الان: ${price}"
            )
            print(msg)
            send_telegram_message(msg)
            state["alerted"][coin_id] = True
            alerts_sent += 1

    save_state(state)
    print(f"Done. Coins checked: {len(coins)}, alerts sent: {alerts_sent}")


if __name__ == "__main__":
    main()

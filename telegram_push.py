"""Telegram notifications for Trading OS v12 scanner results."""
import html
import logging
import os
from urllib.parse import quote

import requests


logger = logging.getLogger("TradingOS")

TELEGRAM_LIMIT = 3800


def chart_link(symbol):
    ticker = str(symbol).replace(".NS", "").upper()

    return (
        "https://www.tradingview.com/chart/"
        f"?symbol={quote(f'NSE:{ticker}', safe='')}"
    )


def send_telegram(message):
    raw_token = os.getenv("TELEGRAM_BOT_TOKEN") or ""
    token = "".join(raw_token.split())

    chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()

    if not token or not chat_id:
        logger.warning(
            "Telegram alert not sent: TELEGRAM_BOT_TOKEN or "
            "TELEGRAM_CHAT_ID is missing."
        )
        return False

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=20,
        )

        response.raise_for_status()

        return True

    except requests.RequestException as exc:
        response_text = getattr(exc.response, "text", "")

        logger.error(
            "Telegram alert failed: %s | Telegram response: %s",
            exc,
            response_text,
        )

        return False


def _money(value):
    try:
        return f"₹{float(value):,.2f}"
    except (TypeError, ValueError):
        return "-"


def _candidate_card(number, result):
    symbol = html.escape(
        str(result["symbol"]).replace(".NS", "").upper()
    )

    url = chart_link(symbol)

    return (
        f"\n<b>{number}. {symbol}</b>  |  Score: {result['score']}\n"
        f"Entry: {_money(result.get('entry'))}  |  "
        f"SL: {_money(result.get('stop'))}\n"
        f"T1: {_money(result.get('target1'))}  |  "
        f"T2: {_money(result.get('target2'))}  |  "
        f"T3: {_money(result.get('target3'))}\n"
        f'<a href="{url}">Open TradingView chart</a>\n'
    )


def send_scan_alert(results, profile, regime):
    title = (
        f"<b>Trading OS v12 — {profile.upper()}</b>\n"
        f"Market regime: <b>{html.escape(regime)}</b>\n"
        f"Selected stocks: <b>{len(results)}</b>\n"
    )

    if not results:
        return send_telegram(
            title + "\nNo qualifying stocks were found in this scan."
        )

    messages = []
    current = title

    for number, result in enumerate(results, start=1):
        card = _candidate_card(number, result)

        if len(current) + len(card) > TELEGRAM_LIMIT:
            messages.append(current)
            current = title + card
        else:
            current += card

    if current:
        messages.append(current)

    sent = True

    for message in messages:
        sent = send_telegram(message) and sent

    return sent

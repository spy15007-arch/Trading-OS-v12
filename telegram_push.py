# telegram_push.py
"""Telegram notifications for Trading OS v12 scanner results.

Behavior changes:
- Only the top N (default 30) ranked symbols are sent to Telegram.
- The remaining symbols are persisted to an SQLite DB so your web UI can display them.
- Telegram sends are performed asynchronously using aiohttp to avoid blocking and reduce
  message-delivery latency during busy windows.
"""

import html
import json
import logging
import os
import sqlite3
import time
from typing import Iterable, List

import aiohttp
import asyncio

logger = logging.getLogger("TradingOS")

# Maximum Telegram message length we'll target (conservative)
TELEGRAM_LIMIT = int(os.getenv("TELEGRAM_LIMIT", "3800"))

# How many top symbols to forward to Telegram
TELEGRAM_TOP_N = int(os.getenv("TELEGRAM_TOP_N", "30"))

# SQLite DB to store "other" results for web UI
DB_PATH = os.getenv("SCANNER_DB_PATH", "scanner_results.db")

# Concurrency and pacing for async sends (tune if you hit rate limits)
ASYNC_CONCURRENCY = int(os.getenv("TELEGRAM_ASYNC_CONCURRENCY", "6"))
DELAY_BETWEEN_MSGS = float(os.getenv("TELEGRAM_DELAY_BETWEEN_MSGS", "0.08"))
HTTP_TIMEOUT = int(os.getenv("TELEGRAM_HTTP_TIMEOUT", "20"))


def chart_link(symbol: str) -> str:
    ticker = str(symbol).replace(".NS", "").upper()
    return "https://www.tradingview.com/chart/" f"?symbol={ticker.replace(' ', '')}"


def _money(value):
    try:
        return f"₹{float(value):,.2f}"
    except (TypeError, ValueError):
        return "-"


def _candidate_card(number: int, result: dict) -> str:
    symbol = html.escape(str(result.get("symbol", "")).replace(".NS", "").upper())
    url = chart_link(symbol)
    # Use safe get() for numeric fields
    return (
        f"\n<b>{number}. {symbol}</b>  |  Score: {result.get('score')}\n"
        f"Entry: {_money(result.get('entry'))}  |  SL: {_money(result.get('stop'))}\n"
        f"T1: {_money(result.get('target1'))}  |  T2: {_money(result.get('target2'))}  |  T3: {_money(result.get('target3'))}\n"
        f'<a href="{url}">Open TradingView chart</a>\n'
    )


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS others (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts INTEGER,
        profile TEXT,
        regime TEXT,
        symbol TEXT,
        score REAL,
        json TEXT
    )
    """
    )
    conn.commit()
    conn.close()


def save_others(others: Iterable[dict], profile: str, regime: str):
    """Persist other (non-telegram) results into SQLite for UI consumption."""
    if not others:
        return
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    ts = int(time.time())
    for row in others:
        symbol = str(row.get("symbol", ""))
        score = row.get("score", None)
        cur.execute(
            "INSERT INTO others(ts, profile, regime, symbol, score, json) VALUES (?, ?, ?, ?, ?, ?)",
            (ts, profile, regime, symbol, score, json.dumps(row, default=str)),
        )
    conn.commit()
    conn.close()


async def _send_message_async(session: aiohttp.ClientSession, token: str, chat_id: str, text: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        async with session.post(url, json=payload, timeout=HTTP_TIMEOUT) as resp:
            if resp.status == 200:
                data = await resp.json()
                ok = data.get("ok", False)
                if not ok:
                    logger.error("Telegram API responded not ok: %s", data)
                return ok
            else:
                text = await resp.text()
                logger.error("Telegram HTTP %s: %s", resp.status, text)
                return False
    except asyncio.TimeoutError:
        logger.error("Telegram send timeout")
        return False
    except Exception as exc:
        logger.exception("Exception sending Telegram message: %s", exc)
        return False


async def send_messages_async(messages: List[str], token: str, chat_id: str) -> bool:
    sem = asyncio.Semaphore(ASYNC_CONCURRENCY)
    success_all = True

    async with aiohttp.ClientSession() as session:

        async def _send_with_sem(msg):
            nonlocal success_all
            async with sem:
                ok = await _send_message_async(session, token, chat_id, msg)
                success_all = success_all and ok
                # Small spacing between messages to avoid hitting burst limits
                await asyncio.sleep(DELAY_BETWEEN_MSGS)

        await asyncio.gather(*[_send_with_sem(m) for m in messages])

    return success_all


def _build_messages_from_cards(title: str, cards: List[str]) -> List[str]:
    messages = []
    current = title
    for card in cards:
        if len(current) + len(card) > TELEGRAM_LIMIT:
            messages.append(current)
            current = title + card
        else:
            current += card
    if current:
        messages.append(current)
    return messages


def _ensure_results_list(results):
    """Accept list-of-dicts or pandas DataFrame and normalize to list of dicts."""
    try:
        import pandas as pd  # local import to avoid hard requirement if not used

        if isinstance(results, pd.DataFrame):
            return results.to_dict(orient="records")
    except Exception:
        # pandas not installed or not a DataFrame — ignore
        pass
    # assume already a list-like of dicts
    return list(results)


def send_scan_alert(results, profile, regime) -> bool:
    """Main entry point — keeps the same signature as before.

    - Only top TELEGRAM_TOP_N are sent to Telegram.
    - Others get saved to DB for UI.
    - Returns True if all Telegram sends succeeded (best-effort).
    """
    results_list = _ensure_results_list(results)

    # If results might not be pre-sorted, sort descending by 'score' if present
    if results_list and isinstance(results_list[0], dict) and "score" in results_list[0]:
        try:
            results_list = sorted(results_list, key=lambda r: float(r.get("score", 0)), reverse=True)
        except Exception:
            # fallback: don't crash if score cannot be converted
            pass

    total = len(results_list)
    title = (
        f"<b>Trading OS v12 — {profile.upper()}</b>\n"
        f"Market regime: <b>{html.escape(str(regime))}</b>\n"
        f"Selected stocks: <b>{total}</b>\n"
    )

    if total == 0:
        # nothing to persist; just send a short message
        return _send_tele_short(title + "\nNo qualifying stocks were found in this scan.")

    top_n = TELEGRAM_TOP_N if total >= TELEGRAM_TOP_N else total
    top_candidates = results_list[:top_n]
    others = results_list[top_n:]

    # Persist others for UI
    if others:
        try:
            save_others(others, profile, regime)
        except Exception as exc:
            logger.exception("Failed to save 'others' to DB: %s", exc)

    # Build cards and messages only for top candidates
    cards = []
    for number, result in enumerate(top_candidates, start=1):
        cards.append(_candidate_card(number, result))

    messages = _build_messages_from_cards(title, cards)

    # Send messages asynchronously
    raw_token = os.getenv("TELEGRAM_BOT_TOKEN") or ""
    token = "".join(raw_token.split())
    chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()

    if not token or not chat_id:
        logger.warning(
            "Telegram alert not sent: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing."
        )
        return False

    try:
        ok = asyncio.run(send_messages_async(messages, token, chat_id))
        return ok
    except Exception as exc:
        logger.exception("Async Telegram sending failed: %s", exc)
        # as a fallback, try synchronous sending with requests to attempt delivery
        try:
            import requests

            sent_all = True
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            for msg in messages:
                resp = requests.post(
                    url,
                    json={
                        "chat_id": chat_id,
                        "text": msg,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                    timeout=HTTP_TIMEOUT,
                )
                try:
                    resp.raise_for_status()
                except Exception:
                    logger.error("Fallback sync send failed: %s %s", resp.status_code, resp.text)
                    sent_all = False
            return sent_all
        except Exception as exc2:
            logger.exception("Fallback sync Telegram send failed: %s", exc2)
            return False


def _send_tele_short(text: str) -> bool:
    raw_token = os.getenv("TELEGRAM_BOT_TOKEN") or ""
    token = "".join(raw_token.split())
    chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()

    if not token or not chat_id:
        logger.warning(
            "Telegram alert not sent: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing."
        )
        return False

    try:
        import requests

        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        return True
    except Exception as exc:
        logger.exception("Short Telegram send failed: %s", exc)
        return False

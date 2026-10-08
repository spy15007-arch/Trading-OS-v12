import os
from pathlib import Path

import pandas as pd
import requests


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_REPORT = Path(
    "reports/swing_scan.csv"
)

MAX_MESSAGE_LENGTH = 3900


# ============================================================
# TELEGRAM
# ============================================================

def _send_message(
    token,
    chat_id,
    message
):
    """
    Send one Telegram message.
    """

    url = (
        f"https://api.telegram.org/bot"
        f"{token}/sendMessage"
    )

    response = requests.post(
        url,
        data={
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": True,
        },
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


def _split_message(
    message,
    max_length=MAX_MESSAGE_LENGTH
):
    """
    Split large Telegram messages safely.
    """

    if len(message) <= max_length:
        return [message]

    lines = message.splitlines()

    chunks = []
    current = ""

    for line in lines:

        candidate = (
            current
            + line
            + "\n"
        )

        if len(candidate) > max_length:

            if current.strip():
                chunks.append(
                    current.rstrip()
                )

            current = (
                line
                + "\n"
            )

        else:

            current = candidate

    if current.strip():
        chunks.append(
            current.rstrip()
        )

    return chunks


def _fmt(value, decimals=2):
    try:
        return f"{float(value):.{decimals}f}"
    except Exception:
        return "-"


def _setup_icon(setup):

    setup = str(
        setup
    ).upper()

    if setup == "FRESH BREAKOUT":
        return "🚀"

    if setup == "PRE-BREAKOUT":
        return "👀"

    return "📊"


def _format_stock(row):
    """
    Phone-friendly detailed stock format.
    """

    symbol = str(
        row.get("Symbol", "")
    )

    setup = str(
        row.get("Setup", "")
    )

    score = _fmt(
        row.get("Score"),
        0
    )

    breakout = _fmt(
        row.get("BreakoutPct")
    )

    rsi = _fmt(
        row.get("RSI")
    )

    rvol = _fmt(
        row.get("RVOL")
    )

    extension = _fmt(
        row.get("Extension")
    )

    entry = _fmt(
        row.get("Entry")
    )

    sl = _fmt(
        row.get("SL")
    )

    t1 = _fmt(
        row.get("T1")
    )

    t2 = _fmt(
        row.get("T2")
    )

    t3 = _fmt(
        row.get("T3")
    )

    t4 = _fmt(
        row.get("T4")
    )

    icon = _setup_icon(
        setup
    )

    return (
        f"{icon} {symbol} | "
        f"{setup}\n"
        f"Score {score} | "
        f"Breakout {breakout}% | "
        f"RSI {rsi} | "
        f"RVOL {rvol}\n"
        f"Entry ₹{entry} | "
        f"SL ₹{sl}\n"
        f"T1 ₹{t1} | "
        f"T2 ₹{t2} | "
        f"T3 ₹{t3} | "
        f"T4 ₹{t4}\n"
        f"Extension {extension}%"
    )


def _format_compact(row):

    symbol = str(
        row.get("Symbol", "")
    )

    setup = str(
        row.get("Setup", "")
    )

    score = _fmt(
        row.get("Score"),
        0
    )

    entry = _fmt(
        row.get("Entry")
    )

    sl = _fmt(
        row.get("SL")
    )

    t1 = _fmt(
        row.get("T1")
    )

    t2 = _fmt(
        row.get("T2")
    )

    t3 = _fmt(
        row.get("T3")
    )

    t4 = _fmt(
        row.get("T4")
    )

    icon = _setup_icon(
        setup
    )

    return (
        f"{icon} {symbol} "
        f"| {setup} "
        f"| S{score} "
        f"| E{entry} "
        f"| SL{sl} "
        f"| T1 {t1} "
        f"| T2 {t2} "
        f"| T3 {t3} "
        f"| T4 {t4}"
    )


# ============================================================
# MAIN ALERT
# ============================================================

def send_scan_alert(
    report_path=DEFAULT_REPORT
):

    token = os.getenv(
        "TELEGRAM_BOT_TOKEN"
    )

    chat_id = os.getenv(
        "TELEGRAM_CHAT_ID"
    )

    if not token or not chat_id:

        print(
            "Telegram credentials not configured."
        )

        return False

    report_path = Path(
        report_path
    )

    if not report_path.exists():

        print(
            f"Report not found: {report_path}"
        )

        return False

    df = pd.read_csv(
        report_path
    )

    if df.empty:

        message = (
            "TRADING OS v12\n\n"
            "No qualifying swing setups today."
        )

        _send_message(
            token,
            chat_id,
            message
        )

        return True

    # --------------------------------------------------------
    # COUNTS
    # --------------------------------------------------------

    pre = df[
        df["Setup"] == "PRE-BREAKOUT"
    ]

    fresh = df[
        df["Setup"] == "FRESH BREAKOUT"
    ]

    top_score = _fmt(
        df["Score"].max(),
        0
    )

    # --------------------------------------------------------
    # HEADER
    # --------------------------------------------------------

    header = (
        "📊 TRADING OS v12\n"
        "TOP SWING SETUPS\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"Final Watchlist: {len(df)}\n"
        f"Pre-Breakout: {len(pre)}\n"
        f"Fresh Breakout: {len(fresh)}\n"
        f"Top Score: {top_score}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "T1=1R | T2=2R | T3=3R | T4=4R\n"
        "R = Entry − Stop Loss\n"
    )

    messages = []

    # --------------------------------------------------------
    # TOP 10 DETAILED
    # --------------------------------------------------------

    top_n = min(
        10,
        len(df)
    )

    top = df.head(
        top_n
    )

    detailed_parts = [
        header
    ]

    detailed_parts.append(
        "\n🏆 TOP RANKED SETUPS\n"
    )

    for _, row in top.iterrows():

        detailed_parts.append(
            "\n"
            + _format_stock(row)
            + "\n"
        )

    detailed_message = "\n".join(
        detailed_parts
    )

    messages.extend(
        _split_message(
            detailed_message
        )
    )

    # --------------------------------------------------------
    # REMAINING STOCKS
    # --------------------------------------------------------

    if len(df) > top_n:

        remaining = df.iloc[
            top_n:
        ]

        compact_lines = [
            "📋 REMAINING WATCHLIST\n"
        ]

        for _, row in remaining.iterrows():

            compact_lines.append(
                _format_compact(row)
            )

        messages.extend(
            _split_message(
                "\n".join(
                    compact_lines
                )
            )
        )

    # --------------------------------------------------------
    # SEND
    # --------------------------------------------------------

    for message in messages:

        _send_message(
            token,
            chat_id,
            message
        )

    print(
        f"Telegram sent successfully: "
        f"{len(messages)} message(s)"
    )

    return True


# ============================================================
# DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":

    send_scan_alert()

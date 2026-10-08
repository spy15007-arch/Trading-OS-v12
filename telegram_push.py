import os
from pathlib import Path

import pandas as pd
import requests


DEFAULT_REPORT = Path(
    "reports/swing_scan.csv"
)

MAX_MESSAGE_LENGTH = 3900


def _send_message(
    token,
    chat_id,
    message,
):

    url = (
        f"https://api.telegram.org/"
        f"bot{token}/sendMessage"
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


def _split_message(
    message,
    max_length=MAX_MESSAGE_LENGTH,
):

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


def _fmt(
    value,
    decimals=2,
):

    try:

        return (
            f"{float(value):."
            f"{decimals}f"
        )

    except Exception:

        return "-"


def _icon(
    setup
):

    if setup == "FRESH BREAKOUT":
        return "🚀"

    if setup == "PRE-BREAKOUT":
        return "👀"

    return "📊"


def _stock_message(
    row
):

    symbol = str(
        row["Symbol"]
    )

    setup = str(
        row["Setup"]
    )

    return (
        f"{_icon(setup)} "
        f"{symbol} | {setup}\n"
        f"Score: "
        f"{_fmt(row['Score'], 0)}/100\n"
        f"Breakout: "
        f"{_fmt(row['BreakoutPct'])}% | "
        f"RSI: "
        f"{_fmt(row['RSI'])} | "
        f"RVOL: "
        f"{_fmt(row['RVOL'])}\n"
        f"Entry: ₹{_fmt(row['Entry'])}\n"
        f"SL: ₹{_fmt(row['SL'])}\n"
        f"T1: ₹{_fmt(row['T1'])}\n"
        f"T2: ₹{_fmt(row['T2'])}\n"
        f"T3: ₹{_fmt(row['T3'])}\n"
        f"T4: ₹{_fmt(row['T4'])}\n"
        f"Extension: "
        f"{_fmt(row['Extension'])}%"
    )


def _compact_message(
    row
):

    return (
        f"{_icon(row['Setup'])} "
        f"{row['Symbol']} | "
        f"{row['Setup']} | "
        f"S{_fmt(row['Score'], 0)} | "
        f"E{_fmt(row['Entry'])} | "
        f"SL{_fmt(row['SL'])} | "
        f"T1 {_fmt(row['T1'])} | "
        f"T2 {_fmt(row['T2'])} | "
        f"T3 {_fmt(row['T3'])} | "
        f"T4 {_fmt(row['T4'])}"
    )


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
            "Telegram credentials "
            "not configured."
        )

        return False

    report_path = Path(
        report_path
    )

    if not report_path.exists():

        print(
            "Telegram report not found."
        )

        return False

    df = pd.read_csv(
        report_path
    )

    if df.empty:

        message = (
            "📊 TRADING OS v12\n\n"
            "NO HIGH-QUALITY SETUPS "
            "TODAY.\n\n"
            "The scanner intentionally "
            "did not fill the watchlist."
        )

        _send_message(
            token,
            chat_id,
            message
        )

        return True

    pre_count = len(
        df[
            df["Setup"]
            == "PRE-BREAKOUT"
        ]
    )

    fresh_count = len(
        df[
            df["Setup"]
            == "FRESH BREAKOUT"
        ]
    )

    top_score = float(
        df["Score"].max()
    )

    header = (
        "📊 TRADING OS v12\n"
        "HIGH-QUALITY SWING SETUPS\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"Qualified: {len(df)}\n"
        f"Pre-Breakout: {pre_count}\n"
        f"Fresh Breakout: {fresh_count}\n"
        f"Top Score: "
        f"{top_score:.0f}/100\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "T1=1R | T2=2R | "
        "T3=3R | T4=4R\n"
        "R = Entry - Stop Loss\n"
    )

    messages = []

    # Show every stock in detail when there
    # are only a few candidates.
    if len(df) <= 10:

        parts = [header]

        for _, row in df.iterrows():

            parts.append(
                "\n"
                + _stock_message(row)
                + "\n"
            )

        messages.extend(
            _split_message(
                "\n".join(parts)
            )
        )

    else:

        parts = [
            header,
            "\n🏆 TOP SETUPS\n",
        ]

        for _, row in (
            df.head(10).iterrows()
        ):

            parts.append(
                "\n"
                + _stock_message(row)
                + "\n"
            )

        messages.extend(
            _split_message(
                "\n".join(parts)
            )
        )

        remaining = df.iloc[10:]

        compact = [
            "📋 REMAINING "
            "QUALIFIED SETUPS\n"
        ]

        for _, row in (
            remaining.iterrows()
        ):

            compact.append(
                _compact_message(row)
            )

        messages.extend(
            _split_message(
                "\n".join(compact)
            )
        )

    for message in messages:

        _send_message(
            token,
            chat_id,
            message
        )

    print(
        f"Telegram sent: "
        f"{len(messages)} message(s)"
    )

    return True


if __name__ == "__main__":

    send_scan_alert()

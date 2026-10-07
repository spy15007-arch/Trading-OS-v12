"""
Trading OS v12 - Telegram Delivery

Purpose:
    Send a clean, phone-friendly swing trading shortlist to Telegram.

Telegram shows:
    - Market condition
    - Number of candidates
    - Top 10 detailed setups
    - Remaining ranks in compact format

The full CSV/Markdown report remains available in GitHub Actions.

Telegram failure is NON-FATAL.
"""

import os
from pathlib import Path
from typing import Optional

import pandas as pd
import requests


TELEGRAM_API = (
    "https://api.telegram.org/bot{token}/sendMessage"
)

MAX_MESSAGE_LENGTH = 3900


# ============================================================
# BASIC HELPERS
# ============================================================

def _fmt(value, digits=2):
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "-"


def _money(value):
    try:
        return f"₹{float(value):,.2f}"
    except (TypeError, ValueError):
        return "₹-"


def _setup_icon(setup):
    setup = str(setup).upper()

    if setup == "FRESH BREAKOUT":
        return "🚀"

    if setup == "PRE-BREAKOUT":
        return "👀"

    return "📊"


def _rank_icon(rank):
    if rank == 1:
        return "🥇"

    if rank == 2:
        return "🥈"

    if rank == 3:
        return "🥉"

    return f"{rank}."


# ============================================================
# MESSAGE SPLITTER
# ============================================================

def _split_message(
    text: str,
    limit: int = MAX_MESSAGE_LENGTH,
):
    """
    Split Telegram message without cutting lines unnecessarily.
    """

    if len(text) <= limit:
        return [text]

    chunks = []
    current = []
    current_length = 0

    for line in text.splitlines(keepends=True):

        if (
            current
            and current_length + len(line) > limit
        ):
            chunks.append(
                "".join(current).strip()
            )

            current = []
            current_length = 0

        if len(line) > limit:

            for i in range(
                0,
                len(line),
                limit,
            ):
                part = line[i:i + limit]

                if part:
                    chunks.append(
                        part.strip()
                    )

            continue

        current.append(line)
        current_length += len(line)

    if current:
        chunks.append(
            "".join(current).strip()
        )

    return [
        chunk
        for chunk in chunks
        if chunk
    ]


# ============================================================
# TELEGRAM SEND
# ============================================================

def _send_message(
    token: str,
    chat_id: str,
    text: str,
) -> bool:

    url = TELEGRAM_API.format(
        token=token
    )

    try:

        response = requests.post(
            url,
            data={
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": "true",
            },
            timeout=30,
        )

        if response.ok:
            return True

        print(
            "Telegram API error: "
            f"HTTP {response.status_code} | "
            f"{response.text[:500]}"
        )

        return False

    except requests.RequestException as exc:

        print(
            f"Telegram request failed: {exc}"
        )

        return False


# ============================================================
# LOAD CSV
# ============================================================

def _load_results(report_path: Optional[str] = None):

    """
    Read the scanner CSV.

    We deliberately use the CSV instead of trying to parse
    the Markdown report. This keeps Telegram formatting clean.
    """

    if report_path:

        report = Path(report_path)

        csv_path = (
            report.parent
            / "swing_scan.csv"
        )

    else:

        csv_path = (
            Path("reports")
            / "swing_scan.csv"
        )

    if not csv_path.exists():

        print(
            f"Telegram skipped: "
            f"CSV report not found: {csv_path}"
        )

        return None

    try:

        df = pd.read_csv(
            csv_path
        )

    except Exception as exc:

        print(
            f"Telegram skipped: "
            f"could not read CSV: {exc}"
        )

        return None

    if df.empty:
        return df

    return df


# ============================================================
# BUILD TELEGRAM MESSAGE
# ============================================================

def _build_message(df):

    if df is None:
        return ""

    if df.empty:

        return (
            "TRADING OS v12\n\n"
            "No qualifying PRE-BREAKOUT or "
            "FRESH BREAKOUT setups found today."
        )

    # --------------------------------------------------------
    # Sort again for safety.
    # --------------------------------------------------------

    sort_columns = []

    if "Score" in df.columns:
        sort_columns.append("Score")

    if "RS60" in df.columns:
        sort_columns.append("RS60")

    if "RVOL" in df.columns:
        sort_columns.append("RVOL")

    if sort_columns:

        df = df.sort_values(
            sort_columns,
            ascending=False,
            kind="mergesort",
        )

    # --------------------------------------------------------
    # Remove duplicates.
    # --------------------------------------------------------

    if "Symbol" in df.columns:

        df = df.drop_duplicates(
            subset=["Symbol"],
            keep="first",
        )

    # --------------------------------------------------------
    # Maximum 30.
    # --------------------------------------------------------

    df = df.head(30).reset_index(
        drop=True
    )

    # --------------------------------------------------------
    # Header.
    # --------------------------------------------------------

    generated = os.getenv(
        "TRADING_OS_GENERATED",
        "",
    ).strip()

    market = os.getenv(
        "TRADING_OS_MARKET",
        "UNKNOWN",
    ).strip()

    candidates = os.getenv(
        "TRADING_OS_CANDIDATES",
        "",
    ).strip()

    header = (
        "🚀 TRADING OS v12\n"
        "TOP SWING SETUPS\n"
    )

    if generated:
        header += f"{generated}\n"

    header += "\n"

    header += (
        f"🛡 Market: {market}\n"
    )

    if candidates:
        header += (
            f"📊 Candidates: {candidates}\n"
        )

    header += (
        f"🎯 Final Watchlist: {len(df)}\n"
    )

    header += (
        "\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🔥 TOP 10\n"
        "━━━━━━━━━━━━━━━━━━\n"
    )

    messages = [header]

    # ========================================================
    # TOP 10
    # ========================================================

    top10 = df.head(10)

    for _, row in top10.iterrows():

        rank = int(
            row.get(
                "Rank",
                _ + 1,
            )
        )

        symbol = str(
            row.get(
                "Symbol",
                "-",
            )
        )

        setup = str(
            row.get(
                "Setup",
                "-",
            )
        )

        score = _fmt(
            row.get("Score"),
            0,
        )

        rsi = _fmt(
            row.get("RSI"),
            1,
        )

        rvol = _fmt(
            row.get("RVOL"),
            2,
        )

        rs20 = _fmt(
            row.get("RS20"),
            1,
        )

        rs60 = _fmt(
            row.get("RS60"),
            1,
        )

        breakout = _fmt(
            row.get("BreakoutPct"),
            2,
        )

        entry = _money(
            row.get("Entry")
        )

        sl = _money(
            row.get("SL")
        )

        t1 = _money(
            row.get("T1")
        )

        t2 = _money(
            row.get("T2")
        )

        icon = _setup_icon(
            setup
        )

        rank_icon = _rank_icon(
            rank
        )

        block = (
            f"{rank_icon} "
            f"{symbol}\n"
            f"{icon} {setup} • "
            f"Score {score}\n"
            f"RS20 {rs20}% • "
            f"RS60 {rs60}%\n"
            f"RSI {rsi} • "
            f"RVOL {rvol}\n"
            f"Breakout gap {breakout}%\n"
            f"Entry {entry}\n"
            f"SL {sl}\n"
            f"T1 {t1} • "
            f"T2 {t2}\n"
            "\n"
        )

        messages.append(block)

    # ========================================================
    # RANK 11-30 COMPACT
    # ========================================================

    remaining = df.iloc[10:]

    if not remaining.empty:

        messages.append(
            "━━━━━━━━━━━━━━━━━━\n"
            "📋 RANK 11–30\n"
            "━━━━━━━━━━━━━━━━━━\n"
        )

        for _, row in remaining.iterrows():

            rank = int(
                row.get(
                    "Rank",
                    _ + 1,
                )
            )

            symbol = str(
                row.get(
                    "Symbol",
                    "-",
                )
            )

            setup = str(
                row.get(
                    "Setup",
                    "-",
                )
            )

            score = _fmt(
                row.get("Score"),
                0,
            )

            rsi = _fmt(
                row.get("RSI"),
                1,
            )

            rvol = _fmt(
                row.get("RVOL"),
                2,
            )

            icon = _setup_icon(
                setup
            )

            messages.append(
                f"{rank:>2}. "
                f"{symbol:<12} "
                f"{icon} "
                f"{score:>3}  "
                f"RSI {rsi}  "
                f"RVOL {rvol}\n"
            )

    messages.append(
        "\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "⚠️ Watchlist only — confirm "
        "price/volume action before entry.\n"
    )

    return "".join(messages)


# ============================================================
# MAIN TELEGRAM FUNCTION
# ============================================================

def send_scan_alert(
    report_path: Optional[str] = None,
) -> bool:

    """
    Send Trading OS v12 swing shortlist.

    Missing Telegram credentials or Telegram API errors
    are NON-FATAL.
    """

    token = os.getenv(
        "TELEGRAM_BOT_TOKEN",
        "",
    ).strip()

    chat_id = os.getenv(
        "TELEGRAM_CHAT_ID",
        "",
    ).strip()

    if not token:

        print(
            "Telegram skipped: "
            "TELEGRAM_BOT_TOKEN is not configured."
        )

        return False

    if not chat_id:

        print(
            "Telegram skipped: "
            "TELEGRAM_CHAT_ID is not configured."
        )

        return False

    df = _load_results(
        report_path
    )

    if df is None:

        return False

    message = _build_message(
        df
    )

    if not message:

        print(
            "Telegram skipped: "
            "message is empty."
        )

        return False

    chunks = _split_message(
        message
    )

    sent = 0

    for index, chunk in enumerate(
        chunks,
        start=1,
    ):

        if len(chunks) > 1:

            prefix = (
                "TRADING OS v12 — "
                f"Part {index}/{len(chunks)}\n\n"
            )

            chunk = (
                prefix
                + chunk
            )

        if _send_message(
            token,
            chat_id,
            chunk,
        ):

            sent += 1

        else:

            print(
                "Telegram delivery failed "
                f"on part {index}/{len(chunks)}."
            )

            return False

    print(
        "Telegram: successfully sent "
        f"{sent} message(s)."
    )

    return True


# ============================================================
# DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":

    send_scan_alert()

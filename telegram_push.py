"""Phone-friendly Telegram reporting for Trading OS v12."""
import math
import os
from pathlib import Path

import pandas as pd
import requests


TELEGRAM_API = "https://api.telegram.org/bot{}/sendMessage"
DEFAULT_CSV = Path("reports/swing_scan.csv")
MAX_RESULTS = 30
MAX_MESSAGE_LENGTH = 3800
ALLOWED_SETUPS = {"PRE-BREAKOUT", "FRESH BREAKOUT"}


def get_credentials():
    """Read Telegram credentials from environment variables."""
    return (
        os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        os.getenv("TELEGRAM_CHAT_ID", "").strip(),
    )


def fmt(value, decimals=2):
    """Format finite numeric values without displaying nan/inf."""
    try:
        number = float(value)
        return f"{number:.{decimals}f}" if math.isfinite(number) else "-"
    except (TypeError, ValueError):
        return "-"


def load_results(csv_path):
    """Load the scanner CSV; return an empty frame on recoverable errors."""
    path = Path(csv_path)
    if not path.exists():
        print(f"Telegram: CSV not found: {path}")
        return pd.DataFrame()

    try:
        return pd.read_csv(path)
    except Exception as exc:
        print(f"Telegram: unable to read CSV: {exc}")
        return pd.DataFrame()


def _prepare_results(df):
    """Filter to allowed setups, unique symbols, highest scores first."""
    if df is None or df.empty:
        return pd.DataFrame()

    data = df.copy()
    data.columns = [str(column).strip().lower() for column in data.columns]

    # Accept common legacy scorer/export column names as well.
    aliases = {
        "symbol": ("symbol", "ticker"),
        "setup": ("setup", "setup_type"),
        "score": ("score", "total_score"),
        "price": ("price", "close"),
        "rsi": ("rsi",),
        "rvol": ("rvol", "relative_volume"),
        "entry": ("entry", "entry_price"),
        "stop_loss": ("stop_loss", "stop", "sl"),
        "target_1": ("target_1", "t1"),
        "target_2": ("target_2", "t2"),
        "target_3": ("target_3", "t3"),
        "target_4": ("target_4", "t4"),
        "breakout_pct": ("breakout_pct", "breakoutdistance_pct"),
    }

    for canonical, choices in aliases.items():
        if canonical not in data.columns:
            source = next((name for name in choices if name in data.columns), None)
            if source is not None:
                data[canonical] = data[source]

    for column in ("symbol", "setup", "score"):
        if column not in data.columns:
            data[column] = "" if column != "score" else 0

    data["symbol"] = (
        data["symbol"].fillna("").astype(str).str.strip().str.upper()
        .str.replace(".NS", "", regex=False)
    )
    data["setup"] = (
        data["setup"].fillna("").astype(str).str.strip().str.upper()
        .str.replace("_", "-", regex=False)
    )
    data["score"] = pd.to_numeric(data["score"], errors="coerce").fillna(0)

    data = data[
        data["symbol"].ne("") & data["setup"].isin(ALLOWED_SETUPS)
    ].copy()

    data = data.sort_values("score", ascending=False)
    data = data.drop_duplicates(subset=["symbol"], keep="first")
    return data.head(MAX_RESULTS).reset_index(drop=True)


def build_telegram_message(df):
    """Build a compact report suitable for reading on a phone."""
    data = _prepare_results(df)
    lines = [
        "📊 TRADING OS v12",
        "PRE-BREAKOUT / FRESH BREAKOUT",
        "━━━━━━━━━━━━━━━━━━━━",
    ]

    if data.empty:
        lines.extend([
            "No qualified setups today.",
            "Weak candidates are not added to fill the list.",
        ])
        return "\n".join(lines)

    lines.append(f"Qualified: {len(data)} (max {MAX_RESULTS})")
    lines.append("")

    for index, row in data.iterrows():
        rank = index + 1
        symbol = str(row.get("symbol", "")).strip()
        setup = str(row.get("setup", "")).strip()
        lines.append(f"{rank}. {symbol} | {setup}")
        lines.append(
            f"Score {fmt(row.get('score'), 1)} | "
            f"Price ₹{fmt(row.get('price', row.get('entry')))}"
        )
        lines.append(
            f"RSI {fmt(row.get('rsi'), 1)} | RVOL {fmt(row.get('rvol'))}"
        )
        lines.append(
            f"Entry ₹{fmt(row.get('entry'))} | SL ₹{fmt(row.get('stop_loss'))}"
        )
        lines.append(
            f"T1 ₹{fmt(row.get('target_1'))} | T2 ₹{fmt(row.get('target_2'))} | "
            f"T3 ₹{fmt(row.get('target_3'))} | T4 ₹{fmt(row.get('target_4'))}"
        )
        lines.append("━━━━━━━━━━━━━━━━━━━━")

    lines.extend(["", "Targets: T1=1R | T2=2R | T3=3R | T4=4R", "R = Entry − Stop Loss"])
    return "\n".join(lines)


def split_telegram_message(message, max_length=MAX_MESSAGE_LENGTH):
    """Split long reports at line boundaries to respect Telegram's limit."""
    chunks = []
    current = ""

    for line in message.splitlines():
        candidate = line if not current else current + "\n" + line
        if len(candidate) <= max_length:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        # A single unusually long line should still be sent in safe pieces.
        while len(line) > max_length:
            chunks.append(line[:max_length])
            line = line[max_length:]
        current = line

    if current:
        chunks.append(current)

    return chunks or ["📊 TRADING OS v12\nNo report content available."]


def send_telegram_message(message, token=None, chat_id=None):
    """Send one Telegram message and report success/failure."""
    if token is None or chat_id is None:
        env_token, env_chat_id = get_credentials()
        token = env_token if token is None else token
        chat_id = env_chat_id if chat_id is None else chat_id

    if not token:
        print("Telegram: TELEGRAM_BOT_TOKEN is not configured.")
        return False
    if not chat_id:
        print("Telegram: TELEGRAM_CHAT_ID is not configured.")
        return False

    try:
        response = requests.post(
            TELEGRAM_API.format(token),
            json={
                "chat_id": chat_id,
                "text": message,
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        if response.status_code != 200:
            print(f"Telegram API error ({response.status_code}): {response.text}")
            return False

        data = response.json()
        if not data.get("ok", False):
            print(f"Telegram rejected message: {response.text}")
            return False
        return True
    except Exception as exc:
        print(f"Telegram connection failed: {exc}")
        return False


def send_telegram_report(csv_path=DEFAULT_CSV):
    """Send the report in one or more Telegram-safe chunks."""
    print("Preparing Telegram report...")
    df = load_results(csv_path)
    message = build_telegram_message(df)
    chunks = split_telegram_message(message)

    all_sent = True
    for index, chunk in enumerate(chunks, start=1):
        if len(chunks) > 1:
            chunk = f"📊 TRADING OS v12 ({index}/{len(chunks)})\n" + chunk
        if not send_telegram_message(chunk):
            all_sent = False
            break

    if all_sent:
        print(f"Telegram report sent successfully ({len(chunks)} message(s)).")
    else:
        print("Telegram report was not sent completely.")
    return all_sent


if __name__ == "__main__":
    send_telegram_report(DEFAULT_CSV)

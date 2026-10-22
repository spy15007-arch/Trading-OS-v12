"""Phone-friendly Telegram reporting for Trading OS v12."""
import argparse
import hashlib
import json
import math
import os
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests


TELEGRAM_API = "https://api.telegram.org/bot{}/sendMessage"
DEFAULT_CSV = Path("reports/swing_scan.csv")
MAX_RESULTS = 30
MAX_MESSAGE_LENGTH = 3800
ALLOWED_SETUPS = {"PRE-BREAKOUT", "FRESH BREAKOUT"}


def get_credentials():
    """Read Telegram credentials from environment variables."""
    token = (
        os.getenv("TELEGRAM_BOT_TOKEN")
        or os.getenv("BOT_TOKEN")
        or ""
    ).strip()
    chat_id = (
        os.getenv("TELEGRAM_CHAT_ID")
        or os.getenv("CHAT_ID")
        or os.getenv("TELEGRAM_CHAT_USERNAME")
        or os.getenv("CHAT_USERNAME")
        or ""
    ).strip()
    return token, str(chat_id)


def normalize_chat_id(chat_id):
    """Normalize chat IDs for Telegram; usernames are allowed for groups/channels."""
    if chat_id is None:
        return ""

    value = str(chat_id).strip()
    if not value:
        return ""

    if value.startswith("@"):
        return value

    try:
        return str(int(value))
    except ValueError:
        return value


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
    # The scanner CSV keeps legacy uppercase and canonical lowercase fields.
    # Lowercasing creates duplicate labels (e.g. Symbol and symbol); keep the
    # first canonical column so data["symbol"] is a Series, not a DataFrame.
    data = data.loc[:, ~data.columns.duplicated(keep="first")].copy()

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
        "resistance": ("resistance",),
        "stock_rs": ("stock_rs",),
        "extension": ("extension",),
        "closing_strength": ("closing_strength",),
        "risk_pct": ("risk_pct",),
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


def build_telegram_message(df, summary=None):
    """Build a compact, phone-friendly report grouped by setup category."""
    data = _prepare_results(df)
    summary = summary or {}
    market = str(summary.get("market_sentiment", "UNKNOWN")).upper()
    scan_mode = str(summary.get("scan_mode", "MANUAL")).upper()
    total = summary.get("stocks_in_universe", "—")
    valid = summary.get("valid_data_count", "—")
    raw = summary.get("raw_setup_count", "—")
    lines = [
        "📊 TRADING OS v12",
        f"Scan mode: {scan_mode}",
        f"Market sentiment: {market}",
        f"Stocks scanned: {total} | Valid history: {valid}",
        f"Raw setups: {raw} | Qualified: {len(data)} | Scan.md limit: {MAX_RESULTS}",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    if "tracked_signal_count" in summary:
        rate = summary.get("target_before_stop_rate")
        rate_text = "n/a" if rate is None else f"{fmt(rate, 1)}%"
        lines.insert(
            5,
            f"Outcome log: {summary.get('tracked_signal_count', 0)} tracked | "
            f"{summary.get('resolved_signal_count', 0)} resolved | "
            f"T1 before stop {rate_text}",
        )

    sections = [
        ("BREAKOUT STOCKS", "BREAKOUT"),
        ("PRE-BREAKOUT", "PRE-BREAKOUT"),
        ("FRESH BREAKOUT", "FRESH BREAKOUT"),
    ]

    rank = 0
    for heading, setup in sections:
        lines.extend([f"🔹 {heading}", "━━━━━━━━━━━━━━━━━━━━"])
        matches = data[data["setup"].eq(setup)] if not data.empty else data

        if matches.empty:
            if setup == "BREAKOUT":
                lines.append("No candidates cleared for the BREAKOUT category.")
            elif setup == "FRESH BREAKOUT":
                lines.append("No candidates cleared for the FRESH BREAKOUT category.")
            else:
                lines.append("No candidates cleared for the PRE-BREAKOUT category.")
            lines.append("")
            continue

        for _, row in matches.iterrows():
            rank += 1
            symbol = str(row.get("symbol", "")).strip()
            lines.append(f"<b>{rank}. {symbol}</b> | {setup}")
            lines.append(
                f"Score {fmt(row.get('score'), 1)} | "
                f"Price ₹{fmt(row.get('price', row.get('entry')))}"
            )
            lines.append(
                f"Resistance ₹{fmt(row.get('resistance'))} | "
                f"Distance {fmt(row.get('breakout_pct'))}%"
            )
            lines.append(
                f"RSI {fmt(row.get('rsi'), 1)} | RVOL {fmt(row.get('rvol'))} | "
                f"RS vs Nifty {fmt(row.get('stock_rs'))}%"
            )
            lines.append(
                f"Close strength {fmt(row.get('closing_strength'))} | "
                f"Extension {fmt(row.get('extension'))}% | "
                f"Risk {fmt(row.get('risk_pct'))}%"
            )
            lines.append(
                f"Entry ₹{fmt(row.get('entry'))} | SL ₹{fmt(row.get('stop_loss'))}"
            )
            lines.append(
                f"T1 ₹{fmt(row.get('target_1'))} | T2 ₹{fmt(row.get('target_2'))} | "
                f"T3 ₹{fmt(row.get('target_3'))} | T4 ₹{fmt(row.get('target_4'))}"
            )
            lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("")

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

    token = (token or "").strip()
    chat_id = normalize_chat_id(chat_id)

    if not token:
        print("Telegram: TELEGRAM_BOT_TOKEN is not configured.")
        return False
    if not chat_id:
        print("Telegram: TELEGRAM_CHAT_ID is not configured.")
        return False

    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(
            TELEGRAM_API.format(token),
            json=payload,
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


def _dedupe_state_path(csv_path):
    """Store the last successfully sent report beside the scan CSV."""
    return Path(csv_path).with_name("telegram_dedupe_state.json")


def _report_signature(message):
    """Ignore only the scheduled mode label; keep every actual report detail."""
    comparable = re.sub(
        r"(?m)^Scan mode: .*?$",
        "Scan mode: <same-day duplicate check>",
        message,
    )
    return hashlib.sha256(comparable.encode("utf-8")).hexdigest()


def _is_duplicate_report(message, csv_path):
    """Return True only when this same report was sent earlier today."""
    state_path = _dedupe_state_path(csv_path)
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False

    today = datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()
    return (
        state.get("date_ist") == today
        and state.get("signature") == _report_signature(message)
    )


def _save_report_signature(message, csv_path):
    """Persist the report signature after Telegram confirms successful delivery."""
    state_path = _dedupe_state_path(csv_path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "date_ist": datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat(),
        "signature": _report_signature(message),
    }
    state_path.write_text(json.dumps(state, indent=2) + "\\n", encoding="utf-8")


def send_telegram_report(csv_path=DEFAULT_CSV, token=None, chat_id=None):
    """Send the report in one or more Telegram-safe chunks."""
    print("Preparing Telegram report...")
    df = load_results(csv_path)
    summary_path = Path(csv_path).with_name("scan_summary.json")
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        summary = {}
    message = build_telegram_message(df, summary=summary)
    if _is_duplicate_report(message, csv_path):
        print(
            "Telegram: identical report already sent today; "
            "skipping duplicate scheduled notification."
        )
        return True
    chunks = split_telegram_message(message)

    resolved_token = (token or os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN") or "").strip()
    resolved_chat_id = normalize_chat_id(chat_id if chat_id is not None else (os.getenv("TELEGRAM_CHAT_ID") or os.getenv("CHAT_ID") or os.getenv("TELEGRAM_CHAT_USERNAME") or os.getenv("CHAT_USERNAME") or ""))

    if not resolved_token:
        print("Telegram: TELEGRAM_BOT_TOKEN is not configured.")
        return False
    if not resolved_chat_id:
        print("Telegram: TELEGRAM_CHAT_ID is not configured.")
        return False

    all_sent = True
    for index, chunk in enumerate(chunks, start=1):
        if len(chunks) > 1:
            chunk = f"📊 TRADING OS v12 ({index}/{len(chunks)})\n" + chunk
        if not send_telegram_message(chunk, token=resolved_token, chat_id=resolved_chat_id):
            all_sent = False
            break

    if all_sent:
        _save_report_signature(message, csv_path)
        print(f"Telegram report sent successfully ({len(chunks)} message(s)).")
    else:
        print("Telegram report was not sent completely.")
    return all_sent


def _parse_args():
    """Support CLI override for bot token and chat id."""
    parser = argparse.ArgumentParser(description="Send Trading OS Telegram scan report.")
    parser.add_argument("--token", dest="token", default=None, help="Telegram bot token")
    parser.add_argument("--chat-id", dest="chat_id", default=None, help="Telegram chat id or @username")
    parser.add_argument("--csv", dest="csv_path", default=str(DEFAULT_CSV), help="CSV report path")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    send_telegram_report(csv_path=args.csv_path, token=args.token, chat_id=args.chat_id)

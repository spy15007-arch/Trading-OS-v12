import os
from pathlib import Path

import pandas as pd
import requests


# ============================================================
# TRADING OS v12 — TELEGRAM PUSH
# ============================================================

TELEGRAM_API = "https://api.telegram.org/bot{}/sendMessage"

DEFAULT_CSV = Path("reports/swing_scan.csv")


# ============================================================
# TELEGRAM CREDENTIALS
# ============================================================

def get_credentials():
    """
    Read Telegram credentials from environment variables.

    GitHub Actions should provide:

        TELEGRAM_BOT_TOKEN
        TELEGRAM_CHAT_ID
    """

    token = os.getenv(
        "TELEGRAM_BOT_TOKEN",
        "",
    ).strip()

    chat_id = os.getenv(
        "TELEGRAM_CHAT_ID",
        "",
    ).strip()

    return token, chat_id


# ============================================================
# FORMAT NUMBER
# ============================================================

def fmt(value, decimals=2):

    try:
        return f"{float(value):.{decimals}f}"
    except Exception:
        return "-"


# ============================================================
# LOAD CSV
# ============================================================

def load_results(csv_path):

    path = Path(
        csv_path
    )

    if not path.exists():

        print(
            f"Telegram: CSV not found: {path}"
        )

        return pd.DataFrame()

    try:

        df = pd.read_csv(
            path
        )

        return df

    except Exception as exc:

        print(
            f"Telegram: unable to read CSV: {exc}"
        )

        return pd.DataFrame()


# ============================================================
# BUILD TELEGRAM MESSAGE
# ============================================================

def build_telegram_message(df):

    lines = []

    lines.append(
        "📊 TRADING OS v12"
    )

    lines.append(
        "TOP SWING SETUPS"
    )

    lines.append(
        "━━━━━━━━━━━━━━━━━━━━"
    )

    if df.empty:

        lines.append(
            "No high-quality swing setups today."
        )

        lines.append("")
        lines.append(
            "Scanner did not fill the list with weak candidates."
        )

        return "\n".join(lines)

    lines.append(
        f"Qualified: {len(df)}"
    )

    lines.append("")

    # --------------------------------------------------------
    # TOP 30
    # --------------------------------------------------------

    for index, row in df.head(30).iterrows():

        try:

            rank = int(
                row.get(
                    "rank",
                    index + 1,
                )
            )

        except Exception:

            rank = index + 1

        symbol = str(
            row.get(
                "symbol",
                "",
            )
        ).strip()

        setup = str(
            row.get(
                "setup",
                "",
            )
        ).strip()

        score = fmt(
            row.get(
                "score",
                0,
            ),
            1,
        )

        price = fmt(
            row.get(
                "price",
                0,
            ),
            2,
        )

        rsi = fmt(
            row.get(
                "rsi",
                0,
            ),
            1,
        )

        rvol = fmt(
            row.get(
                "rvol",
                0,
            ),
            2,
        )

        entry = fmt(
            row.get(
                "entry",
                0,
            ),
            2,
        )

        stop = fmt(
            row.get(
                "stop_loss",
                0,
            ),
            2,
        )

        t1 = fmt(
            row.get(
                "target_1",
                0,
            ),
            2,
        )

        t2 = fmt(
            row.get(
                "target_2",
                0,
            ),
            2,
        )

        t3 = fmt(
            row.get(
                "target_3",
                0,
            ),
            2,
        )

        t4 = fmt(
            row.get(
                "target_4",
                0,
            ),
            2,
        )

        lines.append(
            f"{rank}. {symbol} | "
            f"{setup}"
        )

        lines.append(
            f"Score {score} | "
            f"Price ₹{price} | "
            f"RSI {rsi} | "
            f"RVOL {rvol}"
        )

        lines.append(
            f"Entry ₹{entry} | "
            f"SL ₹{stop}"
        )

        lines.append(
            f"T1 ₹{t1} | "
            f"T2 ₹{t2} | "
            f"T3 ₹{t3} | "
            f"T4 ₹{t4}"
        )

        lines.append(
            "━━━━━━━━━━━━━━━━━━━━"
        )

    lines.append("")
    lines.append(
        "T1=1R | T2=2R | T3=3R | T4=4R"
    )

    lines.append(
        "R = Entry − Stop Loss"
    )

    return "\n".join(lines)


# ============================================================
# SEND TELEGRAM MESSAGE
# ============================================================

def send_telegram_message(
    message,
    token=None,
    chat_id=None,
):

    if token is None or chat_id is None:

        env_token, env_chat_id = get_credentials()

        if token is None:
            token = env_token

        if chat_id is None:
            chat_id = env_chat_id

    if not token:

        print(
            "Telegram: TELEGRAM_BOT_TOKEN is not configured."
        )

        return False

    if not chat_id:

        print(
            "Telegram: TELEGRAM_CHAT_ID is not configured."
        )

        return False

    url = TELEGRAM_API.format(
        token
    )

    payload = {
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": True,
    }

    try:

        response = requests.post(
            url,
            json=payload,
            timeout=30,
        )

        if response.status_code != 200:

            print(
                "Telegram API error:"
            )

            print(
                response.text
            )

            return False

        data = response.json()

        if not data.get(
            "ok",
            False,
        ):

            print(
                "Telegram rejected message:"
            )

            print(
                response.text
            )

            return False

        return True

    except Exception as exc:

        print(
            f"Telegram connection failed: {exc}"
        )

        return False


# ============================================================
# SEND REPORT
# ============================================================

def send_telegram_report(
    csv_path=DEFAULT_CSV,
):

    print(
        "Preparing Telegram report..."
    )

    df = load_results(
        csv_path
    )

    message = build_telegram_message(
        df
    )

    success = send_telegram_message(
        message
    )

    if success:

        print(
            "Telegram report sent successfully."
        )

    else:

        print(
            "Telegram report was not sent."
        )

    return success


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    send_telegram_report(
        DEFAULT_CSV
    )

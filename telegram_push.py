"""
Trading OS v12 Professional
Telegram Report Sender
"""

import os
from pathlib import Path

import requests


BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN"
)

CHAT_ID = os.getenv(
    "TELEGRAM_CHAT_ID"
)


REPORTS = [
    "strict_scan.md",
    "aggressive_scan.md",
    "budget_scan.md"
]


# ==========================================================
# Send Telegram Message
# ==========================================================

def send_message(text):

    if not BOT_TOKEN or not CHAT_ID:

        print(
            "Telegram credentials "
            "not configured."
        )

        return False

    url = (
        "https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }

    try:

        response = requests.post(
            url,
            json=payload,
            timeout=30
        )

        if response.status_code != 200:

            print(
                f"Telegram Error: "
                f"{response.text}"
            )

            return False

        return True

    except Exception as e:

        print(
            f"Telegram connection error: {e}"
        )

        return False


# ==========================================================
# Send Report
# ==========================================================

def send_report(
    report_name
):

    report_path = (
        Path("reports") /
        report_name
    )

    if not report_path.exists():

        print(
            f"{report_name} not found."
        )

        return

    with open(
        report_path,
        "r",
        encoding="utf-8"
    ) as file:

        text = file.read()

    telegram_limit = 4000

    while text:

        chunk = text[
            :telegram_limit
        ]

        if (
            len(text) >
            telegram_limit
        ):

            split = chunk.rfind(
                "\n"
            )

            if split > 0:

                chunk = chunk[
                    :split
                ]

        text = text[
            len(chunk):
        ]

        send_message(
            chunk
        )


# ==========================================================
# Main
# ==========================================================

def main():

    print(
        "Sending Telegram Reports..."
    )

    for report in REPORTS:

        send_report(
            report
        )

    print(
        "Telegram processing completed."
    )


if __name__ == "__main__":

    main()

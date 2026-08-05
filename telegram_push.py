"""
Trading OS v12 Professional
Telegram Report Sender
"""

import os
import requests
from pathlib import Path

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

REPORTS = [
    "strict_scan.md",
    "aggressive_scan.md",
    "budget_scan.md",
]


def send_message(text):

    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram credentials not configured.")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    r = requests.post(url, json=payload, timeout=30)

    if r.status_code != 200:
        print(f"Telegram Error: {r.text}")


def send_report(report_name):

    report_path = Path("reports") / report_name

    if not report_path.exists():
        print(f"{report_name} not found.")
        return

    with open(report_path, "r", encoding="utf-8") as f:
        text = f.read()

    telegram_limit = 4000

    while text:

        chunk = text[:telegram_limit]

        split = chunk.rfind("\n")

        if split > 0 and len(text) > telegram_limit:
            chunk = text[:split]
            text = text[split:]
        else:
            text = text[len(chunk):]

        send_message(chunk)


def main():

    print("Sending Telegram Reports...")

    for report in REPORTS:
        send_report(report)

    print("Done.")


if __name__ == "__main__":
    main()

"""Telegram delivery for Trading OS v12.

Uses requests only.

IMPORTANT:
Telegram failure never makes the stock scanner fail.
"""

import os
import re
from pathlib import Path
from typing import Optional

import requests


# ============================================================
# TELEGRAM SETTINGS
# ============================================================

TELEGRAM_API = (
    "https://api.telegram.org/bot{token}/sendMessage"
)

# Telegram allows approximately 4096 characters.
# We stay below that limit.
MAX_MESSAGE_LENGTH = 3900


# ============================================================
# CLEAN REPORT
# ============================================================

def _clean_for_telegram(text: str) -> str:
    """Convert Markdown report into readable Telegram text."""

    # Remove Markdown bold.
    text = text.replace(
        "**",
        "",
    )

    # Remove Markdown headings.
    text = re.sub(
        r"^#{1,6}\s*",
        "",
        text,
        flags=re.MULTILINE,
    )

    # Make tables more readable.
    text = text.replace(
        "|",
        "  ",
    )

    # Remove Markdown separator rows.
    text = re.sub(
        r"^-{3,}\s*$",
        "",
        text,
        flags=re.MULTILINE,
    )

    # Remove code markers.
    text = text.replace(
        "`",
        "",
    )

    # Remove excessive blank lines.
    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


# ============================================================
# SPLIT LONG MESSAGE
# ============================================================

def _split_message(
    text: str,
    limit: int = MAX_MESSAGE_LENGTH,
):

    if len(text) <= limit:

        return [text]


    chunks = []

    current = []

    current_len = 0


    for line in text.splitlines(
        keepends=True
    ):

        # Current chunk is full.
        if (
            current
            and current_len + len(line) > limit
        ):

            chunks.append(
                "".join(current).strip()
            )

            current = []

            current_len = 0


        # A single line is too long.
        if len(line) > limit:

            for i in range(
                0,
                len(line),
                limit,
            ):

                part = line[
                    i:i + limit
                ]

                if part:

                    chunks.append(
                        part.strip()
                    )

            continue


        current.append(line)

        current_len += len(line)


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
# SEND ONE TELEGRAM MESSAGE
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
# SEND SCAN REPORT
# ============================================================

def send_scan_alert(
    report_path: Optional[str] = None,
) -> bool:

    """Send the current swing report to Telegram.

    Missing secrets or Telegram failure are non-fatal.
    """


    # --------------------------------------------------------
    # READ GITHUB SECRETS
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # REPORT FILE
    # --------------------------------------------------------

    path = Path(
        report_path
        or "reports/swing_scan.md"
    )


    if not path.exists():

        print(
            f"Telegram skipped: "
            f"report not found: {path}"
        )

        return False


    # --------------------------------------------------------
    # READ REPORT
    # --------------------------------------------------------

    try:

        report = _clean_for_telegram(
            path.read_text(
                encoding="utf-8"
            )
        )

    except Exception as exc:

        print(
            f"Telegram skipped: "
            f"could not read report: {exc}"
        )

        return False


    if not report:

        print(
            "Telegram skipped: "
            "report is empty."
        )

        return False


    # --------------------------------------------------------
    # SPLIT IF REQUIRED
    # --------------------------------------------------------

    chunks = _split_message(
        report
    )


    sent = 0


    # --------------------------------------------------------
    # SEND ALL PARTS
    # --------------------------------------------------------

    for index, chunk in enumerate(
        chunks,
        start=1,
    ):

        if len(chunks) > 1:

            prefix = (
                "TRADING OS v12 — "
                "SWING SETUPS\n"
                f"Part {index}/{len(chunks)}\n\n"
            )

        else:

            prefix = (
                "TRADING OS v12 — "
                "SWING SETUPS\n\n"
            )


        message = (
            prefix
            + chunk
        )


        if _send_message(
            token,
            chat_id,
            message,
        ):

            sent += 1

        else:

            print(
                "Telegram delivery failed "
                f"on part {index}/{len(chunks)}."
            )

            return False


    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

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

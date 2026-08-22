"""
Trading OS v12 Professional
Utility Functions
"""

from pathlib import Path

import datetime
import logging


# ==========================================================
# Logging
# ==========================================================

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(message)s"
    )
)

logger = logging.getLogger(
    "TradingOS"
)


# ==========================================================
# Banner
# ==========================================================

def banner(title):

    return (
        "# ==========================================\n"
        f"# {title}\n"
        "# ==========================================\n\n"
    )


# ==========================================================
# IST Timestamp
# ==========================================================

def timestamp():

    utc_now = datetime.datetime.now(
        datetime.timezone.utc
    )

    ist = (
        utc_now +
        datetime.timedelta(
            hours=5,
            minutes=30
        )
    )

    return ist.strftime(
        "%d-%b-%Y %H:%M IST"
    )


# ==========================================================
# Reports Folder
# ==========================================================

def ensure_reports_folder():

    folder = Path("reports")

    folder.mkdir(
        parents=True,
        exist_ok=True
    )

    return folder


# ==========================================================
# Markdown Export
# ==========================================================

def export_markdown(
    content,
    filename
):

    folder = ensure_reports_folder()

    filepath = (
        folder /
        filename
    )

    with open(
        filepath,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(content)

    logger.info(
        f"Report saved : {filepath}"
    )

    return filepath


# ==========================================================
# Divider
# ==========================================================

def divider(
    char="-",
    width=60
):

    return char * width


# ==========================================================
# Heading
# ==========================================================

def heading(text):

    print(
        "\n" +
        divider("=")
    )

    print(text)

    print(
        divider("=")
    )

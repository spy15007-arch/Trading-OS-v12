"""
Trading OS v12 Professional
Utility Functions
"""

from pathlib import Path
import logging
import datetime

# ==========================================================
# Logging
# ==========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("TradingOS")


# ==========================================================
# Banner
# ==========================================================

def banner(title: str) -> str:
    """Returns a markdown banner."""
    return (
        "# ==========================================\n"
        f"# {title}\n"
        "# ==========================================\n\n"
    )


# ==========================================================
# Timestamp
# ==========================================================

def timestamp() -> str:
    """Returns current IST timestamp."""
    ist = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
    return ist.strftime("%d-%b-%Y %H:%M IST")


# ==========================================================
# Ensure reports folder exists
# ==========================================================

def ensure_reports_folder() -> Path:
    folder = Path("reports")
    folder.mkdir(parents=True, exist_ok=True)
    return folder


# ==========================================================
# Save Markdown Report
# ==========================================================

def export_markdown(content: str, filename: str) -> Path:
    """
    Save markdown report into reports folder.
    """

    folder = ensure_reports_folder()

    filepath = folder / filename

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"Report saved : {filepath}")

    return filepath


# ==========================================================
# Console Divider
# ==========================================================

def divider(char: str = "-", width: int = 60) -> str:
    return char * width


# ==========================================================
# Pretty Print Heading
# ==========================================================

def heading(text: str):
    print("\n" + divider("="))
    print(text)
    print(divider("="))

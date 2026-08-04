"""
core/utils.py

Shared utility functions for Trading OS v12
"""

import os
import time
import logging
import datetime
from pathlib import Path
import pandas as pd


# ==========================================================
# Logging
# ==========================================================

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "trading_os.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("TradingOS")


# ==========================================================
# Timer
# ==========================================================

class Timer:

    def __init__(self, name="Task"):
        self.name = name

    def __enter__(self):
        self.start = time.time()
        logger.info(f"{self.name} started")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        elapsed = time.time() - self.start
        logger.info(f"{self.name} completed in {elapsed:.2f} sec")


# ==========================================================
# Folder Helpers
# ==========================================================

def ensure_folder(path):

    Path(path).mkdir(parents=True, exist_ok=True)


ensure_folder("reports")
ensure_folder("logs")
ensure_folder("cache")


# ==========================================================
# Export Helpers
# ==========================================================

def export_csv(df, filename):

    ensure_folder("reports")

    filepath = Path("reports") / filename

    df.to_csv(filepath, index=False)

    logger.info(f"CSV saved -> {filepath}")

    return filepath


def export_markdown(text, filename):

    ensure_folder("reports")

    filepath = Path("reports") / filename

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)

    logger.info(f"Markdown saved -> {filepath}")

    return filepath


# ==========================================================
# Formatting
# ==========================================================

def money(value):

    return f"₹{value:,.2f}"


def pct(value):

    return f"{value:.2f}%"


# ==========================================================
# Date Helpers
# ==========================================================

def today():

    return datetime.date.today()


def timestamp():

    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ==========================================================
# Chunk Generator
# ==========================================================

def chunks(lst, size):

    for i in range(0, len(lst), size):

        yield lst[i:i + size]


# ==========================================================
# Retry Helper
# ==========================================================

def retry(func, retries=3, delay=1):

    for attempt in range(retries):

        try:

            return func()

        except Exception as e:

            logger.warning(

                f"Retry {attempt+1}/{retries} failed : {e}"

            )

            time.sleep(delay)

    return None


# ==========================================================
# DataFrame Cleaner
# ==========================================================

def clean_dataframe(df):

    if df is None:

        return pd.DataFrame()

    if df.empty:

        return pd.DataFrame()

    return df.dropna()


# ==========================================================
# Banner
# ==========================================================

def banner(title):

    line = "=" * 60

    return f"\n{line}\n{title}\n{line}\n"


# ==========================================================
# Progress
# ==========================================================

def progress(current, total):

    percent = round((current / total) * 100, 1)

    print(f"\rProgress : {percent}% ({current}/{total})", end="")


# ==========================================================
# End
# ==========================================================

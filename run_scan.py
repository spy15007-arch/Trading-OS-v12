import os
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd

from scanner.core.downloader import (
    get_nse_equity_symbols,
    download_all,
    download_index,
)

from scanner.core.market import (
    get_market_regime
)

from scanner.core.scoring import (
    score_stock
)


# ============================================================
# CONFIGURATION
# ============================================================

UNIVERSE_SIZE = 1800

# Maximum, NOT target quantity.
MAX_RESULTS = 30

# Only genuinely strong setups.
MIN_SCORE = 75

PERIOD = "1y"
INTERVAL = "1d"

REPORT_DIR = Path("reports")

CSV_FILE = REPORT_DIR / "swing_scan.csv"
MD_FILE = REPORT_DIR / "swing_scan.md"


# ============================================================
# HELPERS
# ============================================================

def safe_float(value, default=0.0):

    try:
        return float(value)

    except Exception:
        return default


def deduplicate_results(results):

    seen = set()
    output = []

    for row in results:

        symbol = str(
            row.get("Symbol", "")
        ).strip().upper()

        if not symbol:
            continue

        if symbol in seen:
            continue

        seen.add(symbol)
        output.append(row)

    return output


def build_markdown(
    df,
    market_regime
):

   

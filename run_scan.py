"""
trading os v12 professional
strict institutional scanner

main scanner launcher

project structure:

trading-os-v12/
│
├── run_scan.py
│
├── scanner/
│   ├── __init__.py
│   │
│   └── core/
│       ├── __init__.py
│       ├── downloader.py
│       ├── indicators.py
│       ├── market.py
│       ├── scoring.py
│       └── utils.py
│
└── reports/
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

import pandas as pd


# ==========================================================
# project path
# ==========================================================

root_dir = Path(__file__).resolve().parent

if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))


# ==========================================================
# imports
# ==========================================================

from scanner.core.downloader import (
    get_nse500,
    download_all,
)

from scanner.core.scoring import (
    score_stock,
)

from scanner.core.market import (
    get_market_status,
)

from scanner.core.utils import (
    banner,
    export_markdown,
    logger,
)


# ==========================================================
# configuration
# ==========================================================

top_results = 50

lookback = "1y"

interval = "1d"


# ==========================================================
# session
# ==========================================================

def get_session():

    utc_now = datetime.now(timezone.utc)

    ist = utc_now + timedelta(
        hours=5,
        minutes=30
    )

    if ist.hour < 12:

        return (
            "morning strict scan",
            "intraday"
        )

    return (
        "pre-close strict scan",
        "btst"
    )


# ==========================================================
# safe value
# ==========================================================

def safe_value(row, column, default="na"):

    try:

        value = row.get(
            column,
            default
        )

        if pd.isna(value):

            return default

        return value

    except Exception:

        return default


# ==========================================================
# build report
# ==========================================================

def build_report(
    title,
    session,
    market,
    report
):

    markdown = ""

    markdown += banner(
        "trading os v12 professional"
    )

    markdown += (
        f"# {title}\n\n"
    )

    markdown += (
        f"**session:** {session}\n\n"
    )

    markdown += (
        "## market status\n\n"
    )

    markdown += (
        f"- nifty : **"
        f"{market.get('nifty', 'na')}"
        f"**\n"
    )

    markdown += (
        f"- banknifty : **"
        f"{market.get('banknifty', 'na')}"
        f"**\n"
    )

    markdown += (
        f"- nifty rsi : **"
        f"{market.get('nifty_rsi', 'na')}"
        f"**\n"
    )

    markdown += (
        f"- banknifty rsi : **"
        f"{market.get('bank_rsi', 'na')}"
        f"**\n"
    )

    markdown += (
        f"- market mode : **"
        f"{market.get('mode', market.get('mode', 'unknown'))}"
        f"**\n"
    )

    markdown += (
        f"- total market score : **"
        f"{market.get('total_score', 'na')}"
        f"**\n\n"
    )

    markdown += "---\n\n"

    # ======================================================
    # no stocks
    # ======================================================

    if report.empty:

        markdown += (
            "## no qualifying institutional setups found\n\n"
        )

        markdown += (
            "The scanner completed successfully, "
            "but no stock passed the current strict "
            "institutional filters.\n"
        )

        return markdown

    # ======================================================
    # selected stocks
    # ======================================================

    markdown += (
        "## top institutional picks\n\n"
    )

    for _, row in report.iterrows():

        symbol = safe_value(
            row,
            "symbol"
        )

        grade = safe_value(
            row,
            "grade"
        )

        markdown += (
            f"### {symbol} ({grade})\n\n"
        )

        markdown += (
            f"- institutional score : **"
            f"{safe_value(row, 'score')}"
            f"**\n"
        )

        markdown += (
            f"- trade type : **"
            f"{safe_value(row, 'trade')}"
            f"**\n"
        )

        markdown += (
            f"- entry : ₹"
            f"{safe_value(row, 'entry')}\n"
        )

        markdown += (
            f"- stop loss : ₹"
            f"{safe_value(row, 'sl')}\n"
        )

        markdown += (
            f"- target 1 : ₹"
            f"{safe_value(row, 't1')}\n"
        )

        markdown += (
            f"- target 2 : ₹"
            f"{safe_value(row, 't2')}\n"
        )

        markdown += (
            f"- target 3 : ₹"
            f"{safe_value(row, 't3')}\n"
        )

        markdown += (
            f"- rsi : "
            f"{safe_value(row, 'rsi')}\n"
        )

        markdown += (
            f"- relative volume : "
            f"{safe_value(row, 'rvol')}\n"
        )

        markdown += (
            f"- lorentz score : "
            f"{safe_value(row, 'lorentz')}\n"
        )

        markdown += (
            f"- ema20 : "
            f"{safe_value(row, 'ema20')}\n"
        )

        markdown += (
            f"- ema50 : "
            f"{safe_value(row, 'ema50')}\n"
        )

        markdown += (
            f"- ema200 : "
            f"{safe_value(row, 'ema200')}\n"
        )

        markdown += (
            f"- vwap : "
            f"{safe_value(row, 'vwap')}\n"
        )

        markdown += "\n---\n\n"

    return markdown


# ==========================================================
# main scanner
# ==========================================================

def run_scan():

    title, session = get_session()

    logger.info(
        "=========================================="
    )

    logger.info(
        "trading os v12 professional"
    )

    logger.info(
        "strict institutional scanner"
    )

    logger.info(
        "=========================================="
    )

    logger.info(
        f"session: {session}"
    )

    # ======================================================
    # market regime
    # ======================================================

    logger.info(
        "loading market regime..."
    )

    try:

        raw_market = get_market_status()

        # normalize market dictionary
        market = {
            "mode": raw_market.get(
                "mode",
                raw_market.get(
                    "MODE",
                    "unknown"
                )
            ),

            "nifty": raw_market.get(
                "nifty",
                raw_market.get(
                    "NIFTY",
                    "na"
                )
            ),

            "banknifty": raw_market.get(
                "banknifty",
                raw_market.get(
                    "BANKNIFTY",
                    "na"
                )
            ),

            "nifty_rsi": raw_market.get(
                "nifty_rsi",
                raw_market.get(
                    "NIFTY_RSI",
                    "na"
                )
            ),

            "bank_rsi": raw_market.get(
                "bank_rsi",
                raw_market.get(
                    "BANK_RSI",
                    "na"
                )
            ),

            "total_score": raw_market.get(
                "total_score",
                raw_market.get(
                    "TOTAL_SCORE",
                    "na"
                )
            ),
        }

        logger.info(
            f"market mode: {market['mode']}"
        )

    except Exception as e:

        logger.warning(
            f"market regime unavailable: {e}"
        )

        market = {
            "mode": "unknown",
            "nifty": "na",
            "banknifty": "na",
            "nifty_rsi": "na",
            "bank_rsi": "na",
            "total_score": "na",
        }

    # ======================================================
    # universe
    # ======================================================

    logger.info(
        "loading stock universe..."
    )

    try:

        symbols = get_nse500()

    except Exception as e:

        logger.error(
            f"universe loading failed: {e}"
        )

        return

    if not symbols:

        logger.error(
            "stock universe is empty."
        )

        return

    # remove duplicates
    symbols = sorted(
        list(
            set(symbols)
        )
    )

    logger.info(
        f"{len(symbols)} symbols selected "
        f"for scanning"
    )

    # ======================================================
    # download data
    # ======================================================

    logger.info(
        "downloading historical market data..."
    )

    try:

        database = download_all(
            symbols,
            period=lookback,
            interval=interval,
            chunk=75
        )

    except TypeError:

        # compatibility with downloader versions
        # which do not expose chunk parameter

        database = download_all(
            symbols,
            period=lookback,
            interval=interval
        )

    except Exception as e:

        logger.error(
            f"market data download failed: {e}"
        )

        return

    if not database:

        logger.error(
            "no market data downloaded."
        )

        return

    logger.info(
        f"{len(database)} charts downloaded"
    )

    # ======================================================
    # scoring
    # ======================================================

    logger.info(
        "running institutional scoring engine..."
    )

    results = []

    processed = 0

    qualified = 0

    for symbol, df in database.items():

        processed += 1

        try:

            if df is None or df.empty:

                continue

            if len(df) < 220:

                continue

            stock = score_stock(
                df
            )

            if stock is None:

                continue

            qualified += 1

            # normalize symbol
            clean_symbol = (
                str(symbol)
                .replace(".NS", "")
                .strip()
                .upper()
            )

            # normalize scoring keys
            normalized = {}

            for key, value in stock.items():

                normalized[
                    str(key).lower()
                ] = value

            normalized["symbol"] = (
                clean_symbol
            )

            results.append(
                normalized
            )

        except Exception as e:

            logger.warning(
                f"{symbol}: scoring failed: {e}"
            )

            continue

    logger.info(
        f"charts processed: {processed}"
    )

    logger.info(
        f"qualifying stocks: {qualified}"
    )

    # ======================================================
    # dataframe
    # ======================================================

    if not results:

        logger.warning(
            "no qualifying institutional setups found."
        )

        empty_report = pd.DataFrame()

        markdown = build_report(
            title,
            session,
            market,
            empty_report
        )

        export_markdown(
            markdown,
            "strict_scan.md"
        )

        return

    report = pd.DataFrame(
        results
    )

    # ======================================================
    # sorting
    # ======================================================

    sort_columns = []

    for column in [
        "score",
        "rvol",
        "rsi"
    ]:

        if column in report.columns:

            sort_columns.append(
                column
            )

    if sort_columns:

        report = report.sort_values(
            by=sort_columns,
            ascending=False,
            na_position="last"
        )

    report = (
        report
        .head(top_results)
        .reset_index(drop=True)
    )

    # ======================================================
    # report
    # ======================================================

    markdown = build_report(
        title,
        session,
        market,
        report
    )

    export_markdown(
        markdown,
        "strict_scan.md"
    )

    # ======================================================
    # console
    # ======================================================

    print()
    print("=" * 70)
    print(
        "trading os v12 professional"
    )
    print(
        "strict institutional scanner"
    )
    print("=" * 70)

    print(
        f"\nmarket mode : "
        f"{market['mode']}"
    )

    print(
        f"universe : "
        f"{len(symbols)} stocks"
    )

    print(
        f"charts downloaded : "
        f"{len(database)}"
    )

    print(
        f"qualifying stocks : "
        f"{qualified}"
    )

    print(
        "\ntop institutional picks:\n"
    )

    # display friendly columns
    display_columns = [
        "symbol",
        "score",
        "grade",
        "trade",
        "entry",
        "sl",
        "t1",
        "rsi",
        "rvol",
    ]

    available_columns = [
        c
        for c in display_columns
        if c in report.columns
    ]

    if available_columns:

        print(
            report[
                available_columns
            ].to_string(
                index=False
            )
        )

    else:

        print(
            report.to_string(
                index=False
            )
        )

    print(
        "\nreport saved : "
        "reports/strict_scan.md"
    )

    logger.info(
        "strict scan completed successfully."
    )


# ==========================================================
# entry point
# ==========================================================

if __name__ == "__main__":

    run_scan()

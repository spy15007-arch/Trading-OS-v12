"""
Trading OS v12 Professional
Strict Institutional Scanner
"""

import datetime

import pandas as pd

from scanner.core.downloader import (
    get_fno_symbols,
    download_all
)

from scanner.core.scoring import (
    score_stock
)

from scanner.core.market import (
    get_market_status
)

from scanner.core.report import (
    build_report,
    results_dataframe
)

from scanner.core.utils import (
    export_markdown,
    logger
)


# ==========================================================
# CONFIGURATION
# ==========================================================

TOP_RESULTS = 25

LOOKBACK = "6mo"

INTERVAL = "1d"


# ==========================================================
# Trading Session
# ==========================================================

def get_session():

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

    if ist.hour < 12:

        return (
            "🌅 MORNING STRICT SCAN",
            "Intraday"
        )

    return (
        "🌙 PRE-CLOSE STRICT SCAN",
        "BTST"
    )


# ==========================================================
# Main Scanner
# ==========================================================

def run_scan():

    title, session = get_session()

    logger.info(
        "=========================================="
    )

    logger.info(
        "TRADING OS v12 PROFESSIONAL"
    )

    logger.info(
        "STRICT INSTITUTIONAL SCANNER"
    )

    logger.info(
        f"Session: {session}"
    )

    # ======================================================
    # MARKET REGIME
    # ======================================================

    logger.info(
        "Loading Market Regime..."
    )

    market = get_market_status()

    logger.info(
        f"Market Mode: {market['MODE']}"
    )

    # ======================================================
    # F&O UNIVERSE
    # ======================================================

    logger.info(
        "Downloading NSE F&O Universe..."
    )

    symbols = get_fno_symbols()

    if not symbols:

        logger.error(
            "No F&O symbols found."
        )

        return False

    logger.info(
        f"{len(symbols)} Symbols Found"
    )

    # ======================================================
    # DOWNLOAD DATA
    # ======================================================

    logger.info(
        "Downloading historical data..."
    )

    database = download_all(
        symbols,
        period=LOOKBACK,
        interval=INTERVAL
    )

    if not database:

        logger.error(
            "No market data downloaded."
        )

        return False

    logger.info(
        f"{len(database)} Charts Downloaded"
    )

    # ======================================================
    # SCORE
    # ======================================================

    results = []

    logger.info(
        "Running institutional scoring engine..."
    )

    for symbol, df in database.items():

        try:

            stock = score_stock(
                df
            )

            if stock is None:
                continue

            stock["Symbol"] = (
                symbol
                .replace(".NS", "")
            )

            results.append(
                stock
            )

        except Exception as e:

            logger.warning(
                f"{symbol}: {e}"
            )

    # ======================================================
    # RESULTS
    # ======================================================

    dataframe = results_dataframe(
        results
    )

    if dataframe.empty:

        logger.warning(
            "No qualifying institutional setups found."
        )

        # Still create a report
        markdown = build_report(
            title,
            market,
            dataframe
        )

        export_markdown(
            markdown,
            "strict_scan.md"
        )

        return True

    dataframe = (
        dataframe
        .head(TOP_RESULTS)
        .reset_index(drop=True)
    )

    # ======================================================
    # REPORT
    # ======================================================

    markdown = build_report(
        title,
        market,
        dataframe
    )

    export_markdown(
        markdown,
        "strict_scan.md"
    )

    # ======================================================
    # CONSOLE
    # ======================================================

    print()
    print("=" * 70)
    print(
        "TRADING OS v12 PROFESSIONAL"
    )
    print(title)
    print("=" * 70)

    print()
    print(
        f"MARKET MODE : "
        f"{market['MODE']}"
    )

    print()
    print(
        "TOP INSTITUTIONAL PICKS"
    )

    print()

    print(
        dataframe.to_string(
            index=False
        )
    )

    print()
    print(
        "Report Saved : "
        "reports/strict_scan.md"
    )

    logger.info(
        "Strict scan completed successfully."
    )

    return True


# ==========================================================
# MAIN
# ==========================================================

if __name__ == "__main__":

    success = run_scan()

    if not success:

        raise SystemExit(1)

"""
Trading OS v12 Professional
Strict Institutional Scanner

FIXED:
- Supports scanner/core project structure
- Correct Python import path
- Uses core.downloader
- Uses core.scoring
- Uses core.market
- Uses core.utils
"""

import os
import sys
import datetime

import pandas as pd


# ==========================================================
# PROJECT PATH FIX
# ==========================================================
# Repository structure:
#
# Trading-OS-v12/
# ├── run_scan.py
# └── scanner/
#     └── core/
#
# The existing core modules internally import:
#     from core.indicators import ...
#
# Therefore the scanner directory must be added to
# Python's module search path.
# ==========================================================

ROOT_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

SCANNER_DIR = os.path.join(
    ROOT_DIR,
    "scanner"
)

if SCANNER_DIR not in sys.path:
    sys.path.insert(
        0,
        SCANNER_DIR
    )


# ==========================================================
# CORE IMPORTS
# ==========================================================

from core.downloader import (
    get_fno_symbols,
    download_all,
)

from core.scoring import (
    score_stock,
)

from core.market import (
    get_market_status,
)

from core.utils import (
    banner,
    export_markdown,
    logger,
)


# ==========================================================
# CONFIGURATION
# ==========================================================

TOP_RESULTS = 25

LOOKBACK = "6mo"

INTERVAL = "1d"


# ==========================================================
# TRADING SESSION
# ==========================================================

def get_session():

    # Current UTC converted to IST
    utc_now = datetime.datetime.now(
        datetime.timezone.utc
    )

    ist = utc_now + datetime.timedelta(
        hours=5,
        minutes=30
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
# SCAN ENGINE
# ==========================================================

def run_scan():

    title, session = get_session()

    logger.info(
        "=============================================="
    )

    logger.info(
        "TRADING OS v12 PROFESSIONAL"
    )

    logger.info(
        "STRICT INSTITUTIONAL SCANNER"
    )

    logger.info(
        "=============================================="
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

    try:

        market = get_market_status()

    except Exception as e:

        logger.error(
            f"Market Regime Error: {e}"
        )

        market = {
            "MODE": "UNKNOWN",
            "NIFTY": "NA",
            "BANKNIFTY": "NA",
            "NIFTY_RSI": "NA",
            "BANK_RSI": "NA",
            "TOTAL_SCORE": "NA",
        }


    # ======================================================
    # F&O UNIVERSE
    # ======================================================

    logger.info(
        "Downloading NSE F&O Universe..."
    )

    try:

        symbols = get_fno_symbols()

    except Exception as e:

        logger.error(
            f"F&O Universe Error: {e}"
        )

        return


    if not symbols:

        logger.warning(
            "No F&O symbols found."
        )

        return


    logger.info(
        f"{len(symbols)} Symbols Found"
    )


    # ======================================================
    # DOWNLOAD MARKET DATA
    # ======================================================

    logger.info(
        "Downloading historical market data..."
    )

    try:

        database = download_all(
            symbols,
            period=LOOKBACK,
            interval=INTERVAL
        )

    except Exception as e:

        logger.error(
            f"Market data download failed: {e}"
        )

        return


    if not database:

        logger.warning(
            "No market data downloaded."
        )

        return


    logger.info(
        f"{len(database)} Charts Downloaded"
    )


    # ======================================================
    # SCORE STOCKS
    # ======================================================

    results = []

    logger.info(
        "Running institutional scoring engine..."
    )


    for symbol, df in database.items():

        try:

            if df is None or df.empty:

                continue


            stock = score_stock(df)


            if stock is None:

                continue


            stock["Symbol"] = symbol.replace(
                ".NS",
                ""
            )


            results.append(
                stock
            )


        except Exception as e:

            logger.warning(
                f"{symbol} : {e}"
            )

            continue


    # ======================================================
    # NO RESULTS
    # ======================================================

    if len(results) == 0:

        logger.warning(
            "No qualifying stocks found."
        )

        return


    # ======================================================
    # CREATE REPORT DATAFRAME
    # ======================================================

    report = pd.DataFrame(
        results
    )


    # ------------------------------------------------------
    # Make sure sorting columns exist
    # ------------------------------------------------------

    sort_columns = []

    for column in [
        "Score",
        "RVOL",
        "RSI"
    ]:

        if column in report.columns:

            sort_columns.append(
                column
            )


    if sort_columns:

        report = report.sort_values(
            by=sort_columns,
            ascending=False
        )


    report = (
        report
        .head(TOP_RESULTS)
        .reset_index(drop=True)
    )


    # ======================================================
    # BUILD MARKDOWN REPORT
    # ======================================================

    markdown = ""


    markdown += banner(
        "TRADING OS v12 PROFESSIONAL"
    )


    markdown += (
        f"# {title}\n\n"
    )


    markdown += (
        f"**Session:** {session}\n\n"
    )


    # ======================================================
    # MARKET STATUS
    # ======================================================

    markdown += (
        "## Market Status\n\n"
    )


    markdown += (
        f"- NIFTY : "
        f"{market.get('NIFTY', 'NA')}\n"
    )


    markdown += (
        f"- BANKNIFTY : "
        f"{market.get('BANKNIFTY', 'NA')}\n"
    )


    markdown += (
        f"- NIFTY RSI : "
        f"{market.get('NIFTY_RSI', 'NA')}\n"
    )


    markdown += (
        f"- BANKNIFTY RSI : "
        f"{market.get('BANK_RSI', 'NA')}\n"
    )


    markdown += (
        f"- MARKET MODE : "
        f"{market.get('MODE', 'UNKNOWN')}\n"
    )


    markdown += (
        f"- TOTAL MARKET SCORE : "
        f"{market.get('TOTAL_SCORE', 'NA')}\n\n"
    )


    markdown += (
        "---\n\n"
    )


    # ======================================================
    # TOP PICKS
    # ======================================================

    markdown += (
        "## Top Institutional Picks\n\n"
    )


    for _, row in report.iterrows():

        symbol = row.get(
            "Symbol",
            "UNKNOWN"
        )

        grade = row.get(
            "Grade",
            "N/A"
        )


        markdown += (
            f"### {symbol} ({grade})\n\n"
        )


        # --------------------------------------------------
        # Core scoring information
        # --------------------------------------------------

        markdown += (
            f"- Institutional Score : "
            f"**{row.get('Score', 'N/A')}**\n"
        )


        markdown += (
            f"- Trade Type : "
            f"**{row.get('Trade', 'N/A')}**\n"
        )


        markdown += (
            f"- Entry : "
            f"₹{row.get('Entry', 'N/A')}\n"
        )


        markdown += (
            f"- Stop Loss : "
            f"₹{row.get('SL', 'N/A')}\n"
        )


        markdown += (
            f"- Target 1 : "
            f"₹{row.get('T1', 'N/A')}\n"
        )


        markdown += (
            f"- Target 2 : "
            f"₹{row.get('T2', 'N/A')}\n"
        )


        markdown += (
            f"- Target 3 : "
            f"₹{row.get('T3', 'N/A')}\n"
        )


        # --------------------------------------------------
        # Technical information
        # --------------------------------------------------

        markdown += (
            f"- RSI : "
            f"{row.get('RSI', 'N/A')}\n"
        )


        markdown += (
            f"- Relative Volume : "
            f"{row.get('RVOL', 'N/A')}\n"
        )


        markdown += (
            f"- Lorentz Score : "
            f"{row.get('Lorentz', 'N/A')}\n"
        )


        markdown += (
            f"- EMA20 : "
            f"{row.get('EMA20', 'N/A')}\n"
        )


        markdown += (
            f"- EMA50 : "
            f"{row.get('EMA50', 'N/A')}\n"
        )


        markdown += (
            f"- EMA200 : "
            f"{row.get('EMA200', 'N/A')}\n"
        )


        markdown += (
            f"- VWAP : "
            f"{row.get('VWAP', 'N/A')}\n\n"
        )


        markdown += (
            "---\n\n"
        )


    # ======================================================
    # SAVE REPORT
    # ======================================================

    filename = (
        "strict_scan.md"
    )


    try:

        export_markdown(
            markdown,
            filename
        )

    except Exception as e:

        logger.error(
            f"Could not export report: {e}"
        )


    # ======================================================
    # CONSOLE OUTPUT
    # ======================================================

    print(
        "\n"
        + "=" * 70
    )


    print(
        "TRADING OS v12 PROFESSIONAL"
    )


    print(
        title
    )


    print(
        "=" * 70
    )


    print(
        "\nMARKET MODE : "
        + str(
            market.get(
                "MODE",
                "UNKNOWN"
            )
        )
    )


    print(
        "\nTOP INSTITUTIONAL PICKS\n"
    )


    print(
        report.to_string(
            index=False
        )
    )


    print(
        "\nReport Saved : reports/"
        + filename
    )


    logger.info(
        "Strict scan completed successfully."
    )


# ==========================================================
# MAIN
# ==========================================================

if __name__ == "__main__":

    run_scan()

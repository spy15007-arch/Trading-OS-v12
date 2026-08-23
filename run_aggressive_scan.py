"""
Trading OS v12 Professional
Aggressive Momentum Scanner
"""

import pandas as pd

from scanner.core.downloader import (
    get_broad_universe,
    download_all,
)

from scanner.core.scoring import (
    score_stock,
)

from scanner.core.market import (
    get_market_status,
)

from scanner.core.utils import (
    export_markdown,
    logger,
)


# ==========================================================
# CONFIGURATION
# ==========================================================

UNIVERSE_SIZE = 1800

TOP_RESULTS = 25

LOOKBACK = "6mo"

INTERVAL = "1d"


# ==========================================================
# AGGRESSIVE SCANNER
# ==========================================================

def run_aggressive():

    logger.info(
        "Starting Aggressive Momentum Scanner..."
    )

    # ------------------------------------------------------
    # Market
    # ------------------------------------------------------

    try:

        market = (
            get_market_status()
        )

    except Exception as e:

        logger.warning(
            f"Market regime unavailable: {e}"
        )

        market = {

            "MODE": "UNKNOWN",
            "NIFTY": "NA",
            "BANKNIFTY": "NA"

        }

    # ------------------------------------------------------
    # Universe
    # ------------------------------------------------------

    symbols = (
        get_broad_universe(
            UNIVERSE_SIZE
        )
    )

    if not symbols:

        logger.error(
            "No stock universe available."
        )

        return False

    # ------------------------------------------------------
    # Download
    # ------------------------------------------------------

    database = download_all(
        symbols,
        period=LOOKBACK,
        interval=INTERVAL
    )

    logger.info(
        f"Charts downloaded: "
        f"{len(database)}"
    )

    # ------------------------------------------------------
    # Score
    # ------------------------------------------------------

    results = []

    for symbol, df in (
        database.items()
    ):

        try:

            stock = score_stock(
                df
            )

            if stock is None:

                continue

            # Aggressive filter
            if stock["Score"] < 10:

                continue

            if stock["RVOL"] < 1.20:

                continue

            stock["Symbol"] = (
                symbol
                .replace(
                    ".NS",
                    ""
                )
            )

            results.append(
                stock
            )

        except Exception as e:

            logger.warning(
                f"{symbol}: {e}"
            )

    # ------------------------------------------------------
    # No results
    # ------------------------------------------------------

    if not results:

        logger.warning(
            "No aggressive setups found."
        )

        export_markdown(
            "# 🚀 Aggressive Momentum Scanner\n\n"
            "No qualifying setups found.\n",
            "aggressive_scan.md"
        )

        return True

    # ------------------------------------------------------
    # Sort
    # ------------------------------------------------------

    report = (
        pd.DataFrame(results)
        .sort_values(
            by=[
                "Score",
                "RVOL",
                "RSI"
            ],
            ascending=False
        )
        .head(
            TOP_RESULTS
        )
        .reset_index(
            drop=True
        )
    )

    # ------------------------------------------------------
    # Report
    # ------------------------------------------------------

    md = (
        "# 🚀 Aggressive Momentum Scanner\n\n"
    )

    md += (
        f"- Universe : **{len(symbols)}**\n"
    )

    md += (
        f"- Charts : **{len(database)}**\n"
    )

    md += (
        f"- NIFTY : "
        f"**{market.get('NIFTY', 'NA')}**\n"
    )

    md += (
        f"- BANKNIFTY : "
        f"**{market.get('BANKNIFTY', 'NA')}**\n"
    )

    md += (
        f"- Market Mode : "
        f"**{market.get('MODE', 'UNKNOWN')}**\n\n"
    )

    for _, row in report.iterrows():

        md += (
            f"## {row['Symbol']} "
            f"({row['Grade']})\n\n"
        )

        md += (
            f"- Score : **{row['Score']}**\n"
        )

        md += (
            f"- Trade : **{row['Trade']}**\n"
        )

        md += (
            f"- Entry : ₹{row['Entry']}\n"
        )

        md += (
            f"- Stop Loss : ₹{row['SL']}\n"
        )

        md += (
            f"- Target 1 : ₹{row['T1']}\n"
        )

        md += (
            f"- Target 2 : ₹{row['T2']}\n"
        )

        md += (
            f"- Target 3 : ₹{row['T3']}\n"
        )

        md += (
            f"- RSI : {row['RSI']}\n"
        )

        md += (
            f"- RVOL : {row['RVOL']}\n"
        )

        md += (
            f"- EMA20 : {row['EMA20']}\n"
        )

        md += (
            f"- EMA50 : {row['EMA50']}\n"
        )

        md += (
            f"- EMA200 : {row['EMA200']}\n\n"
        )

        md += "---\n\n"

    # ------------------------------------------------------
    # Save
    # ------------------------------------------------------

    export_markdown(
        md,
        "aggressive_scan.md"
    )

    print(
        report[
            [
                "Symbol",
                "Score",
                "Grade",
                "Trade",
                "Entry",
                "SL",
                "T1",
                "RSI",
                "RVOL"
            ]
        ].to_string(
            index=False
        )
    )

    logger.info(
        "Aggressive scan completed successfully."
    )

    return True


# ==========================================================
# MAIN
# ==========================================================

if __name__ == "__main__":

    run_aggressive()

"""
Trading OS v12 Professional
Budget Scanner (< ₹500)
"""

import pandas as pd

from scanner.core.downloader import (
    get_nse1800,
    download_all
)

from scanner.core.scoring import (
    score_stock
)

from scanner.core.market import (
    get_market_status
)

from scanner.core.utils import (
    export_markdown,
    logger
)


TOP_RESULTS = 25

MAX_PRICE = 500


# ==========================================================
# Scanner
# ==========================================================

def run_budget():

    logger.info(
        "Starting Budget Scanner..."
    )

    market = get_market_status()

    symbols = get_nse1800()

    if not symbols:

        logger.error(
            "No NSE1800 symbols available."
        )

        return False

    database = download_all(
        symbols,
        period="6mo",
        interval="1d"
    )

    results = []

    for symbol, df in database.items():

        try:

            stock = score_stock(
                df
            )

            if stock is None:
                continue

            if stock["Entry"] > MAX_PRICE:
                continue

            if stock["Score"] < 11:
                continue

            stock["Symbol"] = (
                symbol.replace(
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

    if not results:

        logger.warning(
            "No budget setups found."
        )

        return True

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
        .head(TOP_RESULTS)
        .reset_index(drop=True)
    )

    markdown = (
        "# 💰 Budget Scanner (< ₹500)\n\n"
    )

    markdown += (
        f"- NIFTY : "
        f"**{market['NIFTY']}**\n"
    )

    markdown += (
        f"- BANKNIFTY : "
        f"**{market['BANKNIFTY']}**\n"
    )

    markdown += (
        f"- MODE : "
        f"**{market['MODE']}**\n\n"
    )

    markdown += "---\n\n"

    for _, row in report.iterrows():

        markdown += (
            f"## {row['Symbol']} "
            f"({row['Grade']})\n\n"
        )

        markdown += (
            f"- Entry : ₹{row['Entry']}\n"
        )

        markdown += (
            f"- Score : **{row['Score']}**\n"
        )

        markdown += (
            f"- Trade : {row['Trade']}\n"
        )

        markdown += (
            f"- RSI : {row['RSI']}\n"
        )

        markdown += (
            f"- RVOL : {row['RVOL']}\n"
        )

        markdown += (
            f"- Stop Loss : ₹{row['SL']}\n"
        )

        markdown += (
            f"- Target 1 : ₹{row['T1']}\n"
        )

        markdown += (
            f"- Target 2 : ₹{row['T2']}\n"
        )

        markdown += (
            f"- Target 3 : ₹{row['T3']}\n\n"
        )

        markdown += "---\n\n"

    export_markdown(
        markdown,
        "budget_scan.md"
    )

    print(report)

    logger.info(
        "Budget scan completed."
    )

    return True


# ==========================================================
# MAIN
# ==========================================================

if __name__ == "__main__":

    if not run_budget():

        raise SystemExit(1)

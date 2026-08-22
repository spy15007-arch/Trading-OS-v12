"""
Trading OS v12 Professional
Aggressive Momentum Scanner
"""

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

from scanner.core.utils import (
    export_markdown,
    logger
)


TOP_RESULTS = 25


# ==========================================================
# Scanner
# ==========================================================

def run_aggressive():

    logger.info(
        "Starting Aggressive Momentum Scanner..."
    )

    market = get_market_status()

    symbols = get_fno_symbols()

    if not symbols:

        logger.error(
            "No symbols available."
        )

        return False

    database = download_all(
        symbols,
        period="3mo",
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

            if stock["Score"] < 10:
                continue

            if stock["RVOL"] < 1.2:
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
            "No aggressive setups found."
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
        "# 🚀 Aggressive Momentum Scanner\n\n"
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
            f"- Score : **{row['Score']}**\n"
        )

        markdown += (
            f"- Trade : **{row['Trade']}**\n"
        )

        markdown += (
            f"- Entry : ₹{row['Entry']}\n"
        )

        markdown += (
            f"- SL : ₹{row['SL']}\n"
        )

        markdown += (
            f"- T1 : ₹{row['T1']}\n"
        )

        markdown += (
            f"- T2 : ₹{row['T2']}\n"
        )

        markdown += (
            f"- T3 : ₹{row['T3']}\n"
        )

        markdown += (
            f"- RSI : {row['RSI']}\n"
        )

        markdown += (
            f"- RVOL : {row['RVOL']}\n"
        )

        markdown += "\n---\n\n"

    export_markdown(
        markdown,
        "aggressive_scan.md"
    )

    print(report)

    logger.info(
        "Aggressive scan completed."
    )

    return True


# ==========================================================
# MAIN
# ==========================================================

if __name__ == "__main__":

    if not run_aggressive():

        raise SystemExit(1)

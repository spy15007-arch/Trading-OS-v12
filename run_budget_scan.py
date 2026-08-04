"""
Trading OS v12 Professional
Budget Scanner (< ₹500)
"""

import pandas as pd

from core.downloader import (
    get_nse500,
    download_all,
)

from core.scoring import score_stock

from core.market import get_market_status

from core.utils import (
    export_markdown,
    logger,
)

TOP_RESULTS = 25
MAX_PRICE = 500


def run_budget():

    market = get_market_status()

    symbols = get_nse500()

    database = download_all(
        symbols,
        period="6mo",
        interval="1d"
    )

    results = []

    for symbol, df in database.items():

        try:

            stock = score_stock(df)

            if stock is None:
                continue

            if stock["Entry"] > MAX_PRICE:
                continue

            if stock["Score"] < 11:
                continue

            stock["Symbol"] = symbol.replace(".NS", "")

            results.append(stock)

        except Exception as e:

            logger.warning(f"{symbol}: {e}")

    if not results:

        logger.warning("No budget setups found")
        return

    report = (
        pd.DataFrame(results)
        .sort_values(
            by=["Score", "RVOL", "RSI"],
            ascending=False
        )
        .head(TOP_RESULTS)
    )

    md = "# 💰 Budget Scanner (< ₹500)\n\n"

    md += f"- NIFTY : **{market['NIFTY']}**\n"
    md += f"- BANKNIFTY : **{market['BANKNIFTY']}**\n"
    md += f"- MODE : **{market['MODE']}**\n\n"

    for _, row in report.iterrows():

        md += f"## {row['Symbol']} ({row['Grade']})\n\n"
        md += f"- Entry : ₹{row['Entry']}\n"
        md += f"- Score : **{row['Score']}**\n"
        md += f"- Trade : {row['Trade']}\n"
        md += f"- RSI : {row['RSI']}\n"
        md += f"- RVOL : {row['RVOL']}\n"
        md += f"- Stop Loss : ₹{row['SL']}\n"
        md += f"- Target 1 : ₹{row['T1']}\n"
        md += f"- Target 2 : ₹{row['T2']}\n"
        md += f"- Target 3 : ₹{row['T3']}\n\n"
        md += "---\n\n"

    export_markdown(
        md,
        "budget_scan.md"
    )

    print(report)

    logger.info("Budget scan completed.")


if __name__ == "__main__":

    run_budget()

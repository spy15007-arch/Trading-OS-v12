"""
Trading OS v12 Professional
Aggressive Momentum Scanner
"""

import pandas as pd

from core.downloader import (
    get_fno_symbols,
    download_all,
)

from core.scoring import score_stock

from core.market import get_market_status

from core.utils import (
    export_markdown,
    logger,
)

TOP_RESULTS = 25


def run_aggressive():

    market = get_market_status()

    symbols = get_fno_symbols()

    database = download_all(
        symbols,
        period="3mo",
        interval="1d"
    )

    results = []

    for symbol, df in database.items():

        try:

            stock = score_stock(df)

            if stock is None:
                continue

            # Aggressive relaxation
            if stock["Score"] < 10:
                continue

            if stock["RVOL"] < 1.2:
                continue

            stock["Symbol"] = symbol.replace(".NS", "")

            results.append(stock)

        except Exception as e:

            logger.warning(f"{symbol} : {e}")

    if not results:

        logger.warning("No aggressive setups found")
        return

    report = (
        pd.DataFrame(results)
        .sort_values(
            by=["Score", "RVOL", "RSI"],
            ascending=False
        )
        .head(TOP_RESULTS)
    )

    md = "# 🚀 Aggressive Momentum Scanner\n\n"

    md += f"- NIFTY : **{market['NIFTY']}**\n"
    md += f"- BANKNIFTY : **{market['BANKNIFTY']}**\n"
    md += f"- MODE : **{market['MODE']}**\n\n"

    for _, row in report.iterrows():

        md += f"## {row['Symbol']} ({row['Grade']})\n\n"
        md += f"- Score : **{row['Score']}**\n"
        md += f"- Trade : **{row['Trade']}**\n"
        md += f"- Entry : ₹{row['Entry']}\n"
        md += f"- SL : ₹{row['SL']}\n"
        md += f"- T1 : ₹{row['T1']}\n"
        md += f"- T2 : ₹{row['T2']}\n"
        md += f"- T3 : ₹{row['T3']}\n"
        md += f"- RSI : {row['RSI']}\n"
        md += f"- RVOL : {row['RVOL']}\n\n"
        md += "---\n\n"

    export_markdown(md, "aggressive_scan.md")

    print(report)

    logger.info("Aggressive scan completed")


if __name__ == "__main__":

    run_aggressive()

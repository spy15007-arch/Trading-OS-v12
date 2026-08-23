"""
Trading OS v12 Professional
Budget Scanner
"""

import pandas as pd

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
    export_markdown,
    logger,
)


TOP_RESULTS = 25

MAX_PRICE = 500


def run_budget():

    logger.info(
        "Starting Budget Scanner..."
    )

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

    symbols = get_nse500()

    if not symbols:

        logger.error(
            "NIFTY 500 universe unavailable."
        )

        return False

    database = download_all(
        symbols,
        period="6mo",
        interval="1d"
    )

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

        export_markdown(
            "# 💰 Budget Scanner\n\n"
            "No qualifying setups found.\n",
            "budget_scan.md"
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
        .head(
            TOP_RESULTS
        )
    )

    md = (
        "# 💰 Budget Scanner (< ₹500)\n\n"
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
        f"- MODE : "
        f"**{market.get('MODE', 'UNKNOWN')}**\n\n"
    )

    for _, row in report.iterrows():

        md += (
            f"## {row['Symbol']} "
            f"({row['Grade']})\n\n"
        )

        md += (
            f"- Entry : ₹{row['Entry']}\n"
        )

        md += (
            f"- Score : **{row['Score']}**\n"
        )

        md += (
            f"- Trade : {row['Trade']}\n"
        )

        md += (
            f"- RSI : {row['RSI']}\n"
        )

        md += (
            f"- RVOL : {row['RVOL']}\n"
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
            f"- Target 3 : ₹{row['T3']}\n\n"
        )

        md += "---\n\n"

    export_markdown(
        md,
        "budget_scan.md"
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
        "Budget scan completed successfully."
    )

    return True


if __name__ == "__main__":

    run_budget()

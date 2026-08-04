"""
Trading OS v12 Professional
Strict Institutional Scanner

Part 1 of 2
"""

import datetime
import pandas as pd

from core.downloader import (
    get_fno_symbols,
    download_all,
)

from core.scoring import score_stock

from core.market import (
    get_market_status,
)

from core.utils import (
    banner,
    export_markdown,
    logger,
)


# ==========================================================
# Configuration
# ==========================================================

TOP_RESULTS = 25

LOOKBACK = "6mo"

INTERVAL = "1d"


# ==========================================================
# Trading Session
# ==========================================================

def get_session():

    ist = (
        datetime.datetime.utcnow()
        + datetime.timedelta(hours=5, minutes=30)
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
# Scan Engine
# ==========================================================

def run_scan():

    title, session = get_session()

    logger.info("Loading Market Regime...")

    market = get_market_status()

    logger.info("Downloading NSE F&O Universe...")

    symbols = get_fno_symbols()

    logger.info(
        f"{len(symbols)} Symbols Found"
    )

    database = download_all(

        symbols,

        period=LOOKBACK,

        interval=INTERVAL

    )

    logger.info(

        f"{len(database)} Charts Downloaded"

    )

    results = []

    for symbol, df in database.items():

        try:

            stock = score_stock(df)

            if stock is None:

                continue

            stock["Symbol"] = symbol.replace(
                ".NS",
                ""
            )

            results.append(stock)

        except Exception as e:

            logger.warning(

                f"{symbol} : {e}"

            )

            continue

    if len(results) == 0:

        logger.warning(

            "No qualifying stocks found."

        )

        return

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

    markdown = ""

    markdown += banner(
        "TRADING OS v12 PROFESSIONAL"
    )

    markdown += f"# {title}\n\n"

    markdown += "## Market Status\n\n"

    markdown += (
        f"- NIFTY : {market['NIFTY']}\n"
    )

    markdown += (
        f"- BANKNIFTY : {market['BANKNIFTY']}\n"
    )

    markdown += (
        f"- MODE : {market['MODE']}\n\n"
    )

    markdown += "---\n\n"

    markdown += (
        "## Top Institutional Picks\n\n"
    )
        for _, row in report.iterrows():

        markdown += (
            f"### {row['Symbol']} ({row['Grade']})\n\n"
        )

        markdown += (
            f"- Institutional Score : **{row['Score']}**\n"
        )

        markdown += (
            f"- Trade Type : **{row['Trade']}**\n"
        )

        markdown += (
            f"- Entry : ₹{row['Entry']}\n"
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
            f"- Target 3 : ₹{row['T3']}\n"
        )

        markdown += (
            f"- RSI : {row['RSI']}\n"
        )

        markdown += (
            f"- Relative Volume : {row['RVOL']}\n"
        )

        markdown += (
            f"- Lorentz Score : {row['Lorentz']}\n"
        )

        markdown += (
            f"- EMA20 : {row['EMA20']}\n"
        )

        markdown += (
            f"- EMA50 : {row['EMA50']}\n"
        )

        markdown += (
            f"- EMA200 : {row['EMA200']}\n"
        )

        markdown += (
            f"- VWAP : {row['VWAP']}\n\n"
        )

        markdown += "---\n\n"

    filename = (
        "strict_scan.md"
    )

    export_markdown(
        markdown,
        filename
    )

    print(
        "\n"
        + "=" * 60
    )

    print(
        "TRADING OS v12 PROFESSIONAL"
    )

    print(
        title
    )

    print(
        "=" * 60
    )

    print(report)

    print(
        "\nReport Saved : reports/"
        + filename
    )

    logger.info(
        "Strict scan completed successfully."
    )


# ==========================================================
# Main
# ==========================================================

if __name__ == "__main__":

    run_scan()

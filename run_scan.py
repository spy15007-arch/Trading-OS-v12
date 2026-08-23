"""
Trading OS v12 Professional
Strict Institutional Scanner
"""

import datetime

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
    banner,
    export_markdown,
    logger,
)


# ==========================================================
# CONFIGURATION
# ==========================================================

UNIVERSE_SIZE = 1800

TOP_RESULTS = 50

LOOKBACK = "6mo"

INTERVAL = "1d"


# ==========================================================
# SESSION
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
# MAIN SCANNER
# ==========================================================

def run_scan():

    title, session = (
        get_session()
    )

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
        "=========================================="
    )

    logger.info(
        f"Session: {session}"
    )

    # ======================================================
    # MARKET
    # ======================================================

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

            "BANKNIFTY": "NA",

            "NIFTY_RSI": "NA",

            "BANK_RSI": "NA",

            "TOTAL_SCORE": 0

        }

    # ======================================================
    # UNIVERSE
    # ======================================================

    logger.info(
        "Loading stock universe..."
    )

    symbols = (
        get_broad_universe(
            UNIVERSE_SIZE
        )
    )

    if not symbols:

        logger.error(
            "Stock universe unavailable."
        )

        return False

    logger.info(
        f"{len(symbols)} symbols selected "
        "for scanning"
    )

    # ======================================================
    # DATA
    # ======================================================

    logger.info(
        "Downloading historical market data..."
    )

    database = download_all(
        symbols,
        period=LOOKBACK,
        interval=INTERVAL
    )

    logger.info(
        f"{len(database)} charts downloaded"
    )

    if not database:

        logger.error(
            "No market data downloaded."
        )

        return False

    # ======================================================
    # SCORING
    # ======================================================

    logger.info(
        "Running institutional scoring engine..."
    )

    results = []

    processed = 0

    for symbol, df in (
        database.items()
    ):

        processed += 1

        try:

            stock = score_stock(
                df
            )

            if stock is None:

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

    logger.info(
        f"Charts processed: {processed}"
    )

    logger.info(
        f"Qualifying stocks: "
        f"{len(results)}"
    )

    # ======================================================
    # REPORT
    # ======================================================

    report = pd.DataFrame(
        results
    )

    if report.empty:

        logger.warning(
            "No qualifying institutional setups found."
        )

        markdown = (
            banner(
                "TRADING OS v12 PROFESSIONAL"
            )
        )

        markdown += (
            "## Strict Institutional Scanner\n\n"
        )

        markdown += (
            "No qualifying stocks found.\n"
        )

        export_markdown(
            markdown,
            "strict_scan.md"
        )

        return True

    # ======================================================
    # SORT
    # ======================================================

    report = report.sort_values(
        by=[
            "Score",
            "RVOL",
            "RSI"
        ],
        ascending=False
    )

    report = (
        report
        .head(TOP_RESULTS)
        .reset_index(drop=True)
    )

    # ======================================================
    # MARKDOWN
    # ======================================================

    markdown = banner(
        "TRADING OS v12 PROFESSIONAL"
    )

    markdown += (
        f"# {title}\n\n"
    )

    markdown += (
        f"**Session:** {session}\n\n"
    )

    markdown += (
        f"**Universe:** "
        f"{len(symbols)} stocks\n\n"
    )

    markdown += (
        f"**Charts downloaded:** "
        f"{len(database)}\n\n"
    )

    markdown += (
        f"**Qualifying stocks:** "
        f"{len(results)}\n\n"
    )

    markdown += "## Market Status\n\n"

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
        f"- MARKET SCORE : "
        f"{market.get('TOTAL_SCORE', 0)}\n\n"
    )

    markdown += "---\n\n"

    markdown += (
        "## Top Institutional Picks\n\n"
    )

    for _, row in report.iterrows():

        markdown += (
            f"### {row['Symbol']} "
            f"({row['Grade']})\n\n"
        )

        markdown += (
            f"- Score : "
            f"**{row['Score']}**\n"
        )

        markdown += (
            f"- Trade : "
            f"**{row['Trade']}**\n"
        )

        markdown += (
            f"- Entry : "
            f"₹{row['Entry']}\n"
        )

        markdown += (
            f"- Stop Loss : "
            f"₹{row['SL']}\n"
        )

        markdown += (
            f"- Target 1 : "
            f"₹{row['T1']}\n"
        )

        markdown += (
            f"- Target 2 : "
            f"₹{row['T2']}\n"
        )

        markdown += (
            f"- Target 3 : "
            f"₹{row['T3']}\n"
        )

        markdown += (
            f"- RSI : "
            f"{row['RSI']}\n"
        )

        markdown += (
            f"- RVOL : "
            f"{row['RVOL']}\n"
        )

        markdown += (
            f"- Lorentz : "
            f"{row['Lorentz']}\n"
        )

        markdown += (
            f"- EMA20 : "
            f"{row['EMA20']}\n"
        )

        markdown += (
            f"- EMA50 : "
            f"{row['EMA50']}\n"
        )

        markdown += (
            f"- EMA200 : "
            f"{row['EMA200']}\n"
        )

        markdown += (
            f"- VWAP : "
            f"{row['VWAP']}\n\n"
        )

        markdown += (
            "---\n\n"
        )

    # ======================================================
    # SAVE
    # ======================================================

    export_markdown(
        markdown,
        "strict_scan.md"
    )

    # ======================================================
    # CONSOLE
    # ======================================================

    print(
        "\n" +
        "=" * 70
    )

    print(
        "TRADING OS v12 PROFESSIONAL"
    )

    print(
        "STRICT INSTITUTIONAL SCANNER"
    )

    print(
        "=" * 70
    )

    print(
        f"\nMARKET MODE : "
        f"{market.get('MODE', 'UNKNOWN')}"
    )

    print(
        f"UNIVERSE : "
        f"{len(symbols)} stocks"
    )

    print(
        f"CHARTS DOWNLOADED : "
        f"{len(database)}"
    )

    print(
        f"QUALIFYING STOCKS : "
        f"{len(results)}"
    )

    print(
        "\nTOP INSTITUTIONAL PICKS:\n"
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

    print(
        "\nReport saved : "
        "reports/strict_scan.md"
    )

    logger.info(
        "Strict scan completed successfully."
    )

    return True


# ==========================================================
# ENTRY POINT
# ==========================================================

if __name__ == "__main__":

    run_scan()

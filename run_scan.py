"""
Trading OS v12 - Master Swing Breakout Scanner

Final architecture:

1. Scan broad NSE equity universe
2. Download historical data
3. Identify:
       PRE-BREAKOUT
       FRESH BREAKOUT
4. Score every qualifying setup
5. Sort by score
6. Remove duplicates
7. Keep maximum 30
8. Create detailed Markdown + CSV reports
9. Send clean Telegram shortlist

Telegram failure is NON-FATAL.
"""

import os
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from scanner.core.downloader import (
    get_nse_equity_symbols,
    download_all,
    download_index,
)

from scanner.core.scoring import score_stock

from scanner.core.market import (
    get_market_status,
)

from scanner.core.utils import (
    export_markdown,
    ensure_reports_folder,
    logger,
    timestamp,
)


# ============================================================
# CONFIGURATION
# ============================================================

UNIVERSE_SIZE = 1800

TOP_RESULTS = 30

MIN_SCORE = 60


# ============================================================
# FORMATTER
# ============================================================

def _fmt(value, digits=2):

    try:
        return f"{float(value):.{digits}f}"

    except (
        TypeError,
        ValueError,
    ):

        return "-"


# ============================================================
# BUILD MARKDOWN REPORT
# ============================================================

def build_report(
    df,
    universe_count,
    chart_count,
    candidate_count,
    market,
):

    generated = timestamp()

    mode = market.get(
        "MODE",
        "UNKNOWN",
    )

    md = (
        "# TRADING OS v12 — "
        "TOP SWING SETUPS\n\n"
    )

    md += (
        f"Generated: **{generated}**\n\n"
    )

    md += (
        f"- Universe: **{universe_count} stocks**\n"
    )

    md += (
        f"- Charts downloaded: "
        f"**{chart_count}**\n"
    )

    md += (
        f"- Qualifying candidates: "
        f"**{candidate_count}**\n"
    )

    md += (
        f"- Final watchlist: "
        f"**{len(df)}**\n"
    )

    md += (
        f"- Market mode: **{mode}**\n\n"
    )

    # --------------------------------------------------------
    # EMPTY RESULT
    # --------------------------------------------------------

    if df.empty:

        md += (
            "## Ranking\n\n"
            "No qualifying PRE-BREAKOUT or "
            "FRESH BREAKOUT setups found today.\n"
        )

        return md


    # --------------------------------------------------------
    # MAIN TABLE
    # --------------------------------------------------------

    md += "## Ranking\n\n"

    md += (
        "| Rank | Symbol | Setup | Score | "
        "Breakout % | RS20 | RS60 | RSI | RVOL | "
        "Entry | SL | T1 | T2 |\n"
    )

    md += (
        "|---:|---|---|---:|---:|---:|---:|"
        "---:|---:|---:|---:|---:|---:|\n"
    )


    for _, row in df.iterrows():

        md += (
            f"| {int(row['Rank'])} "
            f"| **{row['Symbol']}** "
            f"| {row['Setup']} "
            f"| **{int(row['Score'])}** "
            f"| {_fmt(row['BreakoutPct'])}% "
            f"| {_fmt(row['RS20'])}% "
            f"| {_fmt(row['RS60'])}% "
            f"| {_fmt(row['RSI'], 1)} "
            f"| {_fmt(row['RVOL'])} "
            f"| ₹{_fmt(row['Entry'])} "
            f"| ₹{_fmt(row['SL'])} "
            f"| ₹{_fmt(row['T1'])} "
            f"| ₹{_fmt(row['T2'])} |\n"
        )


    # --------------------------------------------------------
    # FRESH BREAKOUTS
    # --------------------------------------------------------

    md += "\n## Fresh Breakouts\n\n"

    fresh = df[
        df["Setup"] == "FRESH BREAKOUT"
    ]


    if fresh.empty:

        md += "None in the final 30.\n"

    else:

        for _, row in fresh.iterrows():

            md += (
                f"- **#{int(row['Rank'])} "
                f"{row['Symbol']}** — "
                f"score {int(row['Score'])}, "
                f"breakout "
                f"{_fmt(row['BreakoutPct'])}%, "
                f"RS60 "
                f"{_fmt(row['RS60'])}%, "
                f"RVOL "
                f"{_fmt(row['RVOL'])}, "
                f"RSI "
                f"{_fmt(row['RSI'], 1)}\n"
            )


    # --------------------------------------------------------
    # PRE-BREAKOUTS
    # --------------------------------------------------------

    md += "\n## Pre-Breakouts\n\n"

    pre = df[
        df["Setup"] == "PRE-BREAKOUT"
    ]


    if pre.empty:

        md += "None in the final 30.\n"

    else:

        for _, row in pre.iterrows():

            md += (
                f"- **#{int(row['Rank'])} "
                f"{row['Symbol']}** — "
                f"score {int(row['Score'])}, "
                f"resistance gap "
                f"{_fmt(row['BreakoutPct'])}%, "
                f"base "
                f"{_fmt(row['BaseRangePct'])}%, "
                f"RS60 "
                f"{_fmt(row['RS60'])}%, "
                f"RVOL "
                f"{_fmt(row['RVOL'])}\n"
            )


    md += (
        "\n"
        "> Scanner output is a watchlist, not a "
        "guaranteed trade. Confirm price/volume "
        "action before entry.\n"
    )

    return md


# ============================================================
# MAIN SCANNER
# ============================================================

def run_scan():

    logger.info(
        "=========================================="
    )

    logger.info(
        "TRADING OS v12 - MASTER "
        "SWING BREAKOUT SCANNER"
    )

    logger.info(
        "=========================================="
    )


    # --------------------------------------------------------
    # REPORT DIRECTORY
    # --------------------------------------------------------

    ensure_reports_folder()


    # --------------------------------------------------------
    # MARKET REGIME
    # --------------------------------------------------------

    try:

        market = get_market_status()

    except Exception as exc:

        logger.warning(
            "Market regime unavailable; "
            f"continuing scan: {exc}"
        )

        market = {
            "MODE": "UNKNOWN"
        }


    market_mode = market.get(
        "MODE",
        "UNKNOWN",
    )


    logger.info(
        f"Market Mode: {market_mode}"
    )


    # --------------------------------------------------------
    # UNIVERSE
    # --------------------------------------------------------

    symbols = get_nse_equity_symbols(
        UNIVERSE_SIZE
    )


    logger.info(
        f"{len(symbols)} symbols selected "
        "for scanning"
    )


    # --------------------------------------------------------
    # DOWNLOAD STOCK DATA
    # --------------------------------------------------------

    database = download_all(
        symbols,
        period="1y",
        interval="1d",
        chunk=75,
    )


    logger.info(
        f"{len(database)} charts downloaded"
    )


    if not database:

        raise RuntimeError(
            "No stock charts were downloaded. "
            "Scanner cannot continue."
        )


    # --------------------------------------------------------
    # DOWNLOAD NIFTY BENCHMARK
    # --------------------------------------------------------

    try:

        benchmark = download_index(
            "^NSEI",
            period="1y",
            interval="1d",
        )

    except Exception as exc:

        logger.warning(
            "Nifty benchmark unavailable; "
            f"continuing without benchmark: {exc}"
        )

        benchmark = pd.DataFrame()


    # --------------------------------------------------------
    # SCORE STOCKS
    # --------------------------------------------------------

    results = []


    for symbol, df in database.items():

        try:

            result = score_stock(
                df,
                benchmark_df=benchmark,
            )

        except Exception as exc:

            logger.warning(
                f"Scoring failed for "
                f"{symbol}: {exc}"
            )

            continue


        if not result:

            continue


        if result["Score"] < MIN_SCORE:

            continue


        result["Symbol"] = (
            symbol.replace(
                ".NS",
                "",
            )
        )


        results.append(
            result
        )


    logger.info(
        f"Qualifying candidates: "
        f"{len(results)}"
    )


    # ========================================================
    # RANK RESULTS
    # ========================================================

    if results:

        result_df = pd.DataFrame(
            results
        )


        # ----------------------------------------------------
        # FINAL RANKING
        # ----------------------------------------------------

        sort_columns = [
            "Score",
            "RS60",
            "RVOL",
            "RSI",
        ]


        available_sort_columns = [
            column
            for column in sort_columns
            if column in result_df.columns
        ]


        result_df = result_df.sort_values(
            available_sort_columns,
            ascending=[
                False
                for _ in available_sort_columns
            ],
            kind="mergesort",
        )


        # ----------------------------------------------------
        # REMOVE DUPLICATES
        # ----------------------------------------------------

        result_df = result_df.drop_duplicates(
            subset=[
                "Symbol"
            ],
            keep="first",
        )


        # ----------------------------------------------------
        # MAXIMUM 30
        # ----------------------------------------------------

        result_df = result_df.head(
            TOP_RESULTS
        ).reset_index(
            drop=True
        )


        # ----------------------------------------------------
        # RANK
        # ----------------------------------------------------

        result_df.insert(
            0,
            "Rank",
            range(
                1,
                len(result_df) + 1,
            ),
        )


    else:

        result_df = pd.DataFrame()


    # ========================================================
    # BUILD REPORT
    # ========================================================

    md = build_report(
        result_df,
        universe_count=len(symbols),
        chart_count=len(database),
        candidate_count=len(results),
        market=market,
    )


    # ========================================================
    # SAVE MARKDOWN
    # ========================================================

    report_path = export_markdown(
        md,
        "swing_scan.md",
    )


    # ========================================================
    # SAVE CSV
    # ========================================================

    csv_path = (
        Path("reports")
        / "swing_scan.csv"
    )


    if result_df.empty:

        pd.DataFrame().to_csv(
            csv_path,
            index=False,
        )

    else:

        result_df.to_csv(
            csv_path,
            index=False,
        )


    logger.info(
        f"Report saved: {report_path}"
    )

    logger.info(
        f"CSV saved: {csv_path}"
    )


    # ========================================================
    # CONSOLE OUTPUT
    # ========================================================

    if result_df.empty:

        print(
            "\nNo qualifying "
            "PRE-BREAKOUT or "
            "FRESH BREAKOUT setups found."
        )

    else:

        print(
            "\n"
            + "=" * 120
        )

        print(
            "TRADING OS v12 — "
            "TOP SWING SETUPS"
        )

        print(
            "=" * 120
        )


        display_columns = [
            "Rank",
            "Symbol",
            "Setup",
            "Score",
            "BreakoutPct",
            "RSI",
            "RVOL",
            "Entry",
            "SL",
            "T1",
            "T2",
        ]


        available_display_columns = [
            column
            for column in display_columns
            if column in result_df.columns
        ]


        print(
            result_df[
                available_display_columns
            ].to_string(
                index=False
            )
        )


    # ========================================================
    # TELEGRAM METADATA
    #
    # The Telegram formatter reads these values.
    # They are generated by THIS scan, not manually configured.
    # ========================================================

    os.environ[
        "TRADING_OS_GENERATED"
    ] = timestamp()


    os.environ[
        "TRADING_OS_MARKET"
    ] = str(
        market_mode
    )


    os.environ[
        "TRADING_OS_CANDIDATES"
    ] = str(
        len(results)
    )


    # ========================================================
    # TELEGRAM
    # ========================================================

    try:

        from telegram_push import (
            send_scan_alert
        )


        telegram_ok = send_scan_alert(
            str(report_path)
        )


        if not telegram_ok:

            logger.warning(
                "Telegram notification was not "
                "delivered; scan itself completed "
                "successfully."
            )


    except Exception as exc:

        logger.warning(
            "Telegram notification failed; "
            f"scan itself completed successfully: "
            f"{exc}"
        )


    # ========================================================
    # COMPLETE
    # ========================================================

    logger.info(
        "Master swing scan completed successfully."
    )


    return 0


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:

        raise SystemExit(
            run_scan()
        )

    except Exception as exc:

        logger.exception(
            f"Scanner failed: {exc}"
        )

        raise SystemExit(1)

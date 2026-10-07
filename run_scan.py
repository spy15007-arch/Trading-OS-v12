"""Trading OS v12 - Master Swing Breakout Scanner.

Only two setup types are selected:

1. PRE-BREAKOUT
   Strong trend, tight base, close to resistance.

2. FRESH BREAKOUT
   Recent breakout, volume confirmation, limited extension.

Maximum 30 unique stocks, ranked by score.

Telegram is sent only after the report has been successfully written.
Telegram failure never makes the stock scan fail.
"""

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
from scanner.core.market import get_market_status

from scanner.core.utils import (
    export_markdown,
    ensure_reports_folder,
    logger,
    timestamp,
)


# ============================================================
# SETTINGS
# ============================================================

UNIVERSE_SIZE = 1800
TOP_RESULTS = 30
MIN_SCORE = 60


# ============================================================
# HELPERS
# ============================================================

def _fmt(value, digits=2):
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "-"


# ============================================================
# REPORT BUILDER
# ============================================================

def build_report(
    df,
    universe_count,
    chart_count,
    candidate_count,
    market,
):

    generated = timestamp()
    mode = market.get("MODE", "UNKNOWN")

    md = "# TRADING OS v12 — TOP SWING SETUPS\n\n"

    md += f"Generated: **{generated}**\n\n"

    md += f"- Universe: **{universe_count} stocks**\n"
    md += f"- Charts downloaded: **{chart_count}**\n"
    md += f"- Qualifying candidates: **{candidate_count}**\n"
    md += f"- Final watchlist: **{len(df)}**\n"
    md += f"- Market mode: **{mode}**\n\n"

    if df.empty:

        md += (
            "## Ranking\n\n"
            "No qualifying PRE-BREAKOUT or FRESH BREAKOUT "
            "setups found today.\n"
        )

        return md


    # ========================================================
    # MAIN RANKING
    # ========================================================

    md += "## Ranking\n\n"

    md += (
        "| Rank | Symbol | Setup | Score | Breakout % | "
        "RS20 | RS60 | RSI | RVOL | Entry | SL | T1 | T2 |\n"
    )

    md += (
        "|---:|---|---|---:|---:|---:|---:|---:|---:|"
        "---:|---:|---:|---:|\n"
    )


    for _, r in df.iterrows():

        md += (
            f"| {int(r['Rank'])} "
            f"| **{r['Symbol']}** "
            f"| {r['Setup']} "
            f"| **{int(r['Score'])}** "
            f"| {_fmt(r['BreakoutPct'])}% "
            f"| {_fmt(r['RS20'])}% "
            f"| {_fmt(r['RS60'])}% "
            f"| {_fmt(r['RSI'], 1)} "
            f"| {_fmt(r['RVOL'])} "
            f"| ₹{_fmt(r['Entry'])} "
            f"| ₹{_fmt(r['SL'])} "
            f"| ₹{_fmt(r['T1'])} "
            f"| ₹{_fmt(r['T2'])} |\n"
        )


    # ========================================================
    # FRESH BREAKOUT SECTION
    # ========================================================

    md += "\n## Fresh Breakouts\n\n"

    fresh = df[df["Setup"] == "FRESH BREAKOUT"]

    if fresh.empty:

        md += "None in the final 30.\n"

    else:

        for _, r in fresh.iterrows():

            md += (
                f"- **#{int(r['Rank'])} {r['Symbol']}** — "
                f"score {int(r['Score'])}, "
                f"breakout {_fmt(r['BreakoutPct'])}%, "
                f"RVOL {_fmt(r['RVOL'])}, "
                f"RSI {_fmt(r['RSI'], 1)}\n"
            )


    # ========================================================
    # PRE-BREAKOUT SECTION
    # ========================================================

    md += "\n## Pre-Breakouts\n\n"

    pre = df[df["Setup"] == "PRE-BREAKOUT"]

    if pre.empty:

        md += "None in the final 30.\n"

    else:

        for _, r in pre.iterrows():

            md += (
                f"- **#{int(r['Rank'])} {r['Symbol']}** — "
                f"score {int(r['Score'])}, "
                f"resistance gap {_fmt(r['BreakoutPct'])}%, "
                f"base {_fmt(r['BaseRangePct'])}%, "
                f"RVOL {_fmt(r['RVOL'])}, "
                f"RSI {_fmt(r['RSI'], 1)}\n"
            )


    md += (
        "\n> Scanner output is a watchlist, not a guaranteed trade. "
        "Confirm price/volume action before entry.\n"
    )

    return md


# ============================================================
# MAIN SCANNER
# ============================================================

def run_scan():

    logger.info("==========================================")
    logger.info(
        "TRADING OS v12 - MASTER SWING BREAKOUT SCANNER"
    )
    logger.info("==========================================")


    ensure_reports_folder()


    # ========================================================
    # MARKET REGIME
    # ========================================================

    try:

        market = get_market_status()

    except Exception as exc:

        logger.warning(
            f"Market regime unavailable; continuing scan: {exc}"
        )

        market = {
            "MODE": "UNKNOWN"
        }


    logger.info(
        f"Market Mode: {market.get('MODE', 'UNKNOWN')}"
    )


    # ========================================================
    # UNIVERSE
    # ========================================================

    symbols = get_nse_equity_symbols(
        UNIVERSE_SIZE
    )

    logger.info(
        f"{len(symbols)} symbols selected for scanning"
    )


    # ========================================================
    # DOWNLOAD STOCK DATA
    # ========================================================

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


    # ========================================================
    # NIFTY BENCHMARK
    # ========================================================

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


    # ========================================================
    # SCORE STOCKS
    # ========================================================

    results = []


    for symbol, df in database.items():

        result = score_stock(
            df,
            benchmark_df=benchmark,
        )


        if result and result["Score"] >= MIN_SCORE:

            result["Symbol"] = symbol.replace(
                ".NS",
                ""
            )

            results.append(result)


    # ========================================================
    # RANK RESULTS
    # ========================================================

    if results:

        result_df = pd.DataFrame(results)


        # IMPORTANT:
        # Highest score first.
        # Never alphabetical ranking.

        result_df = result_df.sort_values(
            [
                "Score",
                "RS60",
                "RVOL",
                "RSI",
            ],
            ascending=[
                False,
                False,
                False,
                False,
            ],
            kind="mergesort",
        )


        # One stock = one result.

        result_df = result_df.drop_duplicates(
            subset=["Symbol"],
            keep="first",
        )


        # Maximum 30.

        result_df = result_df.head(
            TOP_RESULTS
        ).reset_index(drop=True)


        # Add ranking.

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
    # CREATE REPORT
    # ========================================================

    md = build_report(
        result_df,
        universe_count=len(symbols),
        chart_count=len(database),
        candidate_count=len(results),
        market=market,
    )


    report_path = export_markdown(
        md,
        "swing_scan.md",
    )


    # ========================================================
    # CSV
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
            "No qualifying PRE-BREAKOUT or "
            "FRESH BREAKOUT setups found."
        )

    else:

        print("\n" + "=" * 110)

        print(
            "TRADING OS v12 — TOP SWING SETUPS"
        )

        print("=" * 110)


        print(
            result_df[
                [
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
            ].to_string(index=False)
        )


    # ========================================================
    # TELEGRAM
    #
    # VERY IMPORTANT:
    # Telegram is imported ONLY AFTER the scanner
    # and report have completed.
    #
    # Therefore a Telegram problem can NEVER stop
    # the stock scanner.
    # ========================================================

    try:

        from telegram_push import send_scan_alert


        telegram_ok = send_scan_alert(
            str(report_path)
        )


        if not telegram_ok:

            logger.warning(
                "Telegram notification was not delivered; "
                "scan itself completed successfully."
            )


    except Exception as exc:

        logger.warning(
            "Telegram notification failed; "
            f"scan itself completed successfully: {exc}"
        )


    # ========================================================
    # DONE
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

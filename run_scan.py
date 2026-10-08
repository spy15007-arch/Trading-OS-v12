import os
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd

from scanner.core.downloader import (
    get_nse_equity_symbols,
    download_all,
    download_index,
)

from scanner.core.market import get_market_regime
from scanner.core.scoring import score_stock


# ============================================================
# CONFIGURATION
# ============================================================

UNIVERSE_SIZE = 1800
TOP_RESULTS = 30
MIN_SCORE = 60

PERIOD = "1y"
INTERVAL = "1d"
CHUNK_SIZE = 75

REPORT_DIR = Path("reports")

CSV_FILE = REPORT_DIR / "swing_scan.csv"
MD_FILE = REPORT_DIR / "swing_scan.md"


# ============================================================
# HELPERS
# ============================================================

def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def deduplicate_results(results):
    """
    Make absolutely sure one symbol appears only once.
    """

    seen = set()
    output = []

    for row in results:

        symbol = str(
            row.get("Symbol", "")
        ).strip().upper()

        if not symbol:
            continue

        if symbol in seen:
            continue

        seen.add(symbol)
        output.append(row)

    return output


def build_markdown(df, market_regime):
    """
    Build human-readable report.
    """

    lines = []

    generated = datetime.now().strftime(
        "%d-%m-%Y %H:%M:%S"
    )

    lines.append(
        "# TRADING OS v12 — TOP SWING SETUPS"
    )

    lines.append("")

    lines.append(
        f"Generated: {generated}"
    )

    lines.append(
        f"Market Regime: {market_regime}"
    )

    lines.append(
        f"Final Candidates: {len(df)}"
    )

    lines.append("")

    lines.append(
        "## MASTER RANKING"
    )

    lines.append("")

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
        "T3",
        "T4",
    ]

    master = df[
        display_columns
    ].copy()

    lines.append(
        master.to_markdown(
            index=False
        )
    )

    lines.append("")

    # --------------------------------------------------------
    # PRE-BREAKOUT
    # --------------------------------------------------------

    pre = df[
        df["Setup"] == "PRE-BREAKOUT"
    ].copy()

    lines.append(
        "## PRE-BREAKOUT"
    )

    lines.append("")

    if pre.empty:

        lines.append(
            "No qualifying pre-breakout stocks today."
        )

    else:

        pre_columns = [
            "Rank",
            "Symbol",
            "Score",
            "BreakoutPct",
            "RSI",
            "RVOL",
            "Extension",
            "Entry",
            "SL",
            "T1",
            "T2",
            "T3",
            "T4",
        ]

        lines.append(
            pre[pre_columns].to_markdown(
                index=False
            )
        )

    lines.append("")

    # --------------------------------------------------------
    # FRESH BREAKOUT
    # --------------------------------------------------------

    fresh = df[
        df["Setup"] == "FRESH BREAKOUT"
    ].copy()

    lines.append(
        "## FRESH BREAKOUT"
    )

    lines.append("")

    if fresh.empty:

        lines.append(
            "No qualifying fresh-breakout stocks today."
        )

    else:

        fresh_columns = [
            "Rank",
            "Symbol",
            "Score",
            "BreakoutPct",
            "RSI",
            "RVOL",
            "Extension",
            "Entry",
            "SL",
            "T1",
            "T2",
            "T3",
            "T4",
        ]

        lines.append(
            fresh[fresh_columns].to_markdown(
                index=False
            )
        )

    lines.append("")

    lines.append(
        "---"
    )

    lines.append("")

    lines.append(
        "T1 = 1R | T2 = 2R | T3 = 3R | T4 = 4R"
    )

    lines.append(
        "R = Entry - Stop Loss"
    )

    lines.append("")

    lines.append(
        "This is a scanner/watchlist, not a guarantee of price movement."
    )

    return "\n".join(lines)


# ============================================================
# MAIN SCANNER
# ============================================================

def main():

    print("")
    print("=" * 60)
    print("TRADING OS v12 — INSTITUTIONAL SWING SCANNER")
    print("=" * 60)
    print("")

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # MARKET REGIME
    # --------------------------------------------------------

    try:

        market_regime = get_market_regime()

    except Exception as exc:

        print(
            f"Market regime unavailable: {exc}"
        )

        market_regime = "UNKNOWN"

    print(
        f"Market regime: {market_regime}"
    )

    # --------------------------------------------------------
    # STOCK UNIVERSE
    # --------------------------------------------------------

    print("")
    print("Loading stock universe...")

    try:

        symbols = get_nse_equity_symbols(
            limit=UNIVERSE_SIZE
        )

    except TypeError:

        symbols = get_nse_equity_symbols(
            UNIVERSE_SIZE
        )

    except Exception as exc:

        print(
            f"Unable to load universe: {exc}"
        )

        return 1

    if not symbols:

        print(
            "No symbols found."
        )

        return 1

    print(
        f"{len(symbols)} symbols selected for scanning"
    )

    # --------------------------------------------------------
    # DOWNLOAD DATA
    # --------------------------------------------------------

    print("")
    print(
        "Downloading historical market data..."
    )

    try:

        data_map = download_all(
            symbols,
            period=PERIOD,
            interval=INTERVAL,
            chunk_size=CHUNK_SIZE,
        )

    except Exception as exc:

        print(
            f"Data download failed: {exc}"
        )

        return 1

    if not data_map:

        print(
            "No historical data downloaded."
        )

        return 1

    print(
        f"{len(data_map)} charts downloaded"
    )

    # --------------------------------------------------------
    # BENCHMARK
    # --------------------------------------------------------

    print("")
    print("Downloading NIFTY benchmark...")

    try:

        benchmark = download_index(
            "^NSEI",
            period=PERIOD,
            interval=INTERVAL,
        )

    except Exception as exc:

        print(
            f"Benchmark unavailable: {exc}"
        )

        benchmark = None

    # --------------------------------------------------------
    # SCORING
    # --------------------------------------------------------

    print("")
    print(
        "Running institutional scoring engine..."
    )

    results = []

    processed = 0
    qualified = 0

    for symbol, data in data_map.items():

        processed += 1

        result = score_stock(
            data,
            benchmark=benchmark,
            symbol=symbol,
        )

        if result is None:
            continue

        if safe_float(
            result.get("Score")
        ) < MIN_SCORE:

            continue

        results.append(result)
        qualified += 1

    print(
        f"Charts processed: {processed}"
    )

    print(
        f"Qualifying stocks: {qualified}"
    )

    # --------------------------------------------------------
    # DEDUPLICATE
    # --------------------------------------------------------

    results = deduplicate_results(
        results
    )

    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    results.sort(
        key=lambda row: (
            safe_float(row.get("Score")),
            safe_float(row.get("StockRS")),
            safe_float(row.get("RS60")),
            safe_float(row.get("RS20")),
            safe_float(row.get("RVOL")),
        ),
        reverse=True,
    )

    # --------------------------------------------------------
    # TOP 30
    # --------------------------------------------------------

    results = results[
        :TOP_RESULTS
    ]

    # --------------------------------------------------------
    # DATAFRAME
    # --------------------------------------------------------

    df = pd.DataFrame(results)

    if df.empty:

        print("")
        print(
            "No stocks qualified today."
        )

        empty_columns = [
            "Rank",
            "Symbol",
            "Setup",
            "Score",
            "BreakoutPct",
            "RS20",
            "RS60",
            "StockRS",
            "RSI",
            "RVOL",
            "BaseRange",
            "Compression",
            "Extension",
            "Resistance",
            "ClosingStrength",
            "Entry",
            "SL",
            "T1",
            "T2",
            "T3",
            "T4",
            "RiskPct",
        ]

        df = pd.DataFrame(
            columns=empty_columns
        )

    else:

        df.insert(
            0,
            "Rank",
            range(
                1,
                len(df) + 1
            ),
        )

    # --------------------------------------------------------
    # SAVE CSV
    # --------------------------------------------------------

    df.to_csv(
        CSV_FILE,
        index=False
    )

    print("")
    print(
        f"CSV report saved: {CSV_FILE}"
    )

    # --------------------------------------------------------
    # SAVE MARKDOWN
    # --------------------------------------------------------

    report_text = build_markdown(
        df,
        market_regime
    )

    MD_FILE.write_text(
        report_text,
        encoding="utf-8"
    )

    print(
        f"Markdown report saved: {MD_FILE}"
    )

    # --------------------------------------------------------
    # ENVIRONMENT INFO
    # --------------------------------------------------------

    os.environ[
        "TRADING_OS_GENERATED"
    ] = datetime.now().isoformat()

    os.environ[
        "TRADING_OS_MARKET"
    ] = str(market_regime)

    os.environ[
        "TRADING_OS_CANDIDATES"
    ] = str(len(df))

    # --------------------------------------------------------
    # TELEGRAM
    # --------------------------------------------------------

    try:

        from telegram_push import send_scan_alert

        print("")
        print(
            "Sending Telegram alert..."
        )

        send_scan_alert(
            CSV_FILE
        )

    except Exception as exc:

        print(
            f"Telegram alert failed: {exc}"
        )

    # --------------------------------------------------------
    # FINAL CONSOLE SUMMARY
    # --------------------------------------------------------

    print("")
    print("=" * 60)
    print(
        f"FINAL WATCHLIST: {len(df)} STOCKS"
    )
    print("=" * 60)

    if not df.empty:

        print(
            df[
                [
                    "Rank",
                    "Symbol",
                    "Setup",
                    "Score",
                    "Entry",
                    "SL",
                    "T1",
                    "T2",
                    "T3",
                    "T4",
                ]
            ].to_string(
                index=False
            )
        )

    print("")
    print(
        "Scanner completed successfully."
    )

    return 0


if __name__ == "__main__":

    try:

        sys.exit(
            main()
        )

    except KeyboardInterrupt:

        print(
            "\nScanner interrupted."
        )

        sys.exit(1)

    except Exception as exc:

        print(
            f"\nFatal scanner error: {exc}"
        )

        sys.exit(1)

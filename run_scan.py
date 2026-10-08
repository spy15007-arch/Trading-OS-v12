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

from scanner.core.market import (
    get_market_regime
)

from scanner.core.scoring import (
    score_stock
)


# ============================================================
# CONFIGURATION
# ============================================================

UNIVERSE_SIZE = 1800

# Maximum, NOT target quantity.
MAX_RESULTS = 30

# Higher quality threshold.
MIN_SCORE = 75

PERIOD = "1y"
INTERVAL = "1d"

CHUNK_SIZE = 75

REPORT_DIR = Path(
    "reports"
)

CSV_FILE = (
    REPORT_DIR
    / "swing_scan.csv"
)

MD_FILE = (
    REPORT_DIR
    / "swing_scan.md"
)


# ============================================================
# HELPERS
# ============================================================

def safe_float(
    value,
    default=0.0
):

    try:
        return float(value)

    except Exception:

        return default


def deduplicate_results(
    results
):

    seen = set()

    output = []

    for row in results:

        symbol = str(
            row.get(
                "Symbol",
                ""
            )
        ).strip().upper()

        if not symbol:
            continue

        if symbol in seen:
            continue

        seen.add(symbol)

        output.append(row)

    return output


def build_markdown(
    df,
    market_regime
):

    lines = []

    generated = (
        datetime.now()
        .strftime(
            "%d-%m-%Y %H:%M:%S"
        )
    )

    lines.append(
        "# TRADING OS v12 — "
        "TOP SWING SETUPS"
    )

    lines.append("")

    lines.append(
        f"Generated: {generated}"
    )

    lines.append(
        f"Market Regime: "
        f"{market_regime}"
    )

    lines.append(
        f"Qualified Stocks: "
        f"{len(df)}"
    )

    lines.append("")

    lines.append(
        "## MASTER RANKING"
    )

    lines.append("")

    if df.empty:

        lines.append(
            "NO STOCKS PASSED THE "
            "QUALITY FILTER."
        )

    else:

        columns = [
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

        lines.append(
            df[columns]
            .to_markdown(
                index=False
            )
        )

    lines.append("")

    # --------------------------------------------------------
    # PRE-BREAKOUT
    # --------------------------------------------------------

    lines.append(
        "## PRE-BREAKOUT"
    )

    lines.append("")

    pre = df[
        df["Setup"]
        == "PRE-BREAKOUT"
    ]

    if pre.empty:

        lines.append(
            "No qualifying "
            "pre-breakout setups."
        )

    else:

        columns = [
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
            pre[columns]
            .to_markdown(
                index=False
            )
        )

    lines.append("")

    # --------------------------------------------------------
    # FRESH BREAKOUT
    # --------------------------------------------------------

    lines.append(
        "## FRESH BREAKOUT"
    )

    lines.append("")

    fresh = df[
        df["Setup"]
        == "FRESH BREAKOUT"
    ]

    if fresh.empty:

        lines.append(
            "No qualifying "
            "fresh-breakout setups."
        )

    else:

        columns = [
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
            fresh[columns]
            .to_markdown(
                index=False
            )
        )

    lines.append("")

    lines.append(
        "---"
    )

    lines.append(
        "T1 = 1R | T2 = 2R | "
        "T3 = 3R | T4 = 4R"
    )

    lines.append(
        "R = Entry - Stop Loss"
    )

    lines.append("")

    lines.append(
        "The number of stocks is "
        "NOT forced to 30. Only "
        "stocks clearing the quality "
        "threshold are included."
    )

    return "\n".join(
        lines
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("")
    print("=" * 65)
    print(
        "TRADING OS v12 — "
        "HIGH QUALITY SWING SCANNER"
    )
    print("=" * 65)
    print("")

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # MARKET
    # --------------------------------------------------------

    try:

        market_regime = (
            get_market_regime()
        )

    except Exception as exc:

        print(
            f"Market regime unavailable: "
            f"{exc}"
        )

        market_regime = "UNKNOWN"

    print(
        f"Market regime: "
        f"{market_regime}"
    )

    # --------------------------------------------------------
    # UNIVERSE
    # --------------------------------------------------------

    print("")
    print(
        "Loading stock universe..."
    )

    try:

        symbols = (
            get_nse_equity_symbols(
                limit=UNIVERSE_SIZE
            )
        )

    except TypeError:

        symbols = (
            get_nse_equity_symbols(
                UNIVERSE_SIZE
            )
        )

    except Exception as exc:

        print(
            f"Universe loading failed: "
            f"{exc}"
        )

        return 1

    if not symbols:

        print(
            "No symbols found."
        )

        return 1

    print(
        f"{len(symbols)} symbols "
        "selected for scanning"
    )

    # --------------------------------------------------------
    # DOWNLOAD
    # --------------------------------------------------------

    print("")
    print(
        "Downloading historical "
        "market data..."
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
            f"Data download failed: "
            f"{exc}"
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
    # NIFTY BENCHMARK
    # --------------------------------------------------------

    print("")
    print(
        "Downloading NIFTY benchmark..."
    )

    try:

        benchmark = (
            download_index(
                "^NSEI",
                period=PERIOD,
                interval=INTERVAL,
            )
        )

    except Exception as exc:

        print(
            f"Benchmark unavailable: "
            f"{exc}"
        )

        benchmark = None

    # --------------------------------------------------------
    # SCORING
    # --------------------------------------------------------

    print("")
    print(
        "Running high-quality "
        "scoring engine..."
    )

    results = []

    processed = 0

    classified = 0

    for symbol, data in (
        data_map.items()
    ):

        processed += 1

        result = score_stock(
            data,
            benchmark=benchmark,
            symbol=symbol,
        )

        if result is None:
            continue

        classified += 1

        if (
            safe_float(
                result.get(
                    "Score"
                )
            )
            < MIN_SCORE
        ):
            continue

        results.append(
            result
        )

    print(
        f"Charts processed: "
        f"{processed}"
    )

    print(
        f"Setup candidates before "
        f"quality threshold: "
        f"{classified}"
    )

    print(
        f"Stocks above quality "
        f"score {MIN_SCORE}: "
        f"{len(results)}"
    )

    # --------------------------------------------------------
    # DEDUPLICATION
    # --------------------------------------------------------

    results = (
        deduplicate_results(
            results
        )
    )

    # --------------------------------------------------------
    # RANKING
    # --------------------------------------------------------

    results.sort(
        key=lambda row: (
            safe_float(
                row.get(
                    "Score"
                )
            ),

            safe_float(
                row.get(
                    "StockRS"
                )
            ),

            safe_float(
                row.get(
                    "RS60"
                )
            ),

            safe_float(
                row.get(
                    "RS20"
                )
            ),

            safe_float(
                row.get(
                    "RVOL"
                )
            ),
        ),

        reverse=True,
    )

    # --------------------------------------------------------
    # MAXIMUM 30
    # --------------------------------------------------------

    results = results[
        :MAX_RESULTS
    ]

    # --------------------------------------------------------
    # DATAFRAME
    # --------------------------------------------------------

    df = pd.DataFrame(
        results
    )

    if df.empty:

        columns = [
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
            columns=columns
        )

    else:

        df.insert(
            0,
            "Rank",
            range(
                1,
                len(df) + 1
            )
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
        f"CSV saved: "
        f"{CSV_FILE}"
    )

    # --------------------------------------------------------
    # MARKDOWN
    # --------------------------------------------------------

    report = build_markdown(
        df,
        market_regime
    )

    MD_FILE.write_text(
        report,
        encoding="utf-8"
    )

    print(
        f"Report saved: "
        f"{MD_FILE}"
    )

    # --------------------------------------------------------
    # TELEGRAM
    # --------------------------------------------------------

    try:

        from telegram_push import (
            send_scan_alert
        )

        print("")
        print(
            "Sending Telegram alert..."
        )

        send_scan_alert(
            CSV_FILE
        )

    except Exception as exc:

        print(
            f"Telegram failed: "
            f"{exc}"
        )

    # --------------------------------------------------------
    # FINAL
    # --------------------------------------------------------

    print("")
    print("=" * 65)

    if df.empty:

        print(
            "NO HIGH-QUALITY SETUPS TODAY."
        )

        print(
            "This is intentional. "
            "The scanner does not fill "
            "the watchlist artificially."
        )

    else:

        print(
            f"FINAL HIGH-QUALITY "
            f"WATCHLIST: {len(df)}"
        )

        print("=" * 65)

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
        "Scanner completed."
    )

    return 0


if __name__ == "__main__":

    try:

        sys.exit(
            main()
        )

    except KeyboardInterrupt:

        print(
            "Scanner interrupted."
        )

        sys.exit(1)

    except Exception as exc:

        print(
            f"Fatal scanner error: "
            f"{exc}"
        )

        sys.exit(1)

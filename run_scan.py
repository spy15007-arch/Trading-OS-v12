import os
from pathlib import Path

import pandas as pd

from scanner.core.downloader import download_all
from scanner.core.market import get_market_regime
from scanner.core.scoring import score_stock
from scanner.core.report import save_report
from scanner.core.utils import get_nse_equity_symbols
from telegram_push import send_telegram_report


# ============================================================
# TRADING OS v12
# HIGH QUALITY SWING SCANNER
# ============================================================

UNIVERSE_SIZE = 1800
MAX_RESULTS = 30

# Quality threshold.
# 30 is a MAXIMUM, NOT A TARGET.
MIN_SCORE = 75

PERIOD = "1y"
INTERVAL = "1d"

REPORT_DIR = Path("reports")
REPORT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# HELPERS
# ============================================================

def clean_symbol(symbol):
    """Normalise NSE symbols."""
    if symbol is None:
        return ""

    symbol = str(symbol).strip().upper()

    if symbol.endswith(".NS"):
        symbol = symbol[:-3]

    return symbol


def normalise_dataframe(data):
    """
    Normalise downloaded OHLCV dataframe.

    Handles both normal columns and yfinance MultiIndex columns.
    """
    if data is None:
        return None

    if data.empty:
        return None

    df = data.copy()

    # Flatten MultiIndex columns if present.
    if isinstance(df.columns, pd.MultiIndex):
        new_columns = []

        for col in df.columns:
            if isinstance(col, tuple):
                new_columns.append(str(col[0]))
            else:
                new_columns.append(str(col))

        df.columns = new_columns

    # Standardise column names.
    rename_map = {}

    for col in df.columns:
        name = str(col).strip().lower()

        if name == "open":
            rename_map[col] = "Open"

        elif name == "high":
            rename_map[col] = "High"

        elif name == "low":
            rename_map[col] = "Low"

        elif name == "close":
            rename_map[col] = "Close"

        elif name == "adj close":
            rename_map[col] = "Adj Close"

        elif name == "volume":
            rename_map[col] = "Volume"

    df = df.rename(columns=rename_map)

    required = ["Open", "High", "Low", "Close", "Volume"]

    for column in required:
        if column not in df.columns:
            return None

    for column in required:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df = df.dropna(
        subset=["Open", "High", "Low", "Close"]
    )

    if df.empty:
        return None

    return df


def get_benchmark_data():
    """
    Download NIFTY 50 benchmark data.

    Used for relative-strength calculations.
    """
    try:
        benchmark_map = download_all(
            ["^NSEI"],
            period=PERIOD,
            interval=INTERVAL,
        )

        if not benchmark_map:
            return None

        if isinstance(benchmark_map, dict):
            benchmark = benchmark_map.get("^NSEI")

            if benchmark is None:
                benchmark = benchmark_map.get("NSEI")

            if benchmark is None and len(benchmark_map) == 1:
                benchmark = next(iter(benchmark_map.values()))

        else:
            benchmark = benchmark_map

        return normalise_dataframe(benchmark)

    except Exception as exc:
        print(f"Benchmark download failed: {exc}")
        return None


def score_universe(data_map, benchmark):
    """
    Score every downloaded stock.

    Returns only valid scanner candidates.
    """
    results = []

    if not data_map:
        return results

    total = len(data_map)

    print()
    print("Scoring stocks...")
    print("-" * 65)

    for index, (symbol, data) in enumerate(data_map.items(), start=1):

        symbol = clean_symbol(symbol)

        if not symbol:
            continue

        try:
            df = normalise_dataframe(data)

            if df is None:
                continue

            result = score_stock(
                symbol=symbol,
                data=df,
                benchmark=benchmark,
            )

            if result is None:
                continue

            # Make sure Stock field exists.
            if not result.get("Stock"):
                result["Stock"] = symbol

            results.append(result)

        except Exception as exc:
            print(
                f"Scoring failed for {symbol}: {exc}"
            )

        # Progress every 100 stocks.
        if index % 100 == 0 or index == total:
            print(
                f"  Processed {index}/{total} | "
                f"Qualified so far: {len(results)}"
            )

    return results


def deduplicate_results(results):
    """
    Remove duplicate stocks.

    Highest score is retained.
    """
    if not results:
        return []

    best_by_symbol = {}

    for result in results:

        symbol = clean_symbol(
            result.get("Stock", "")
        )

        if not symbol:
            continue

        try:
            score = float(
                result.get("Score", 0)
            )
        except Exception:
            score = 0.0

        if symbol not in best_by_symbol:
            best_by_symbol[symbol] = result
            continue

        try:
            old_score = float(
                best_by_symbol[symbol].get(
                    "Score",
                    0,
                )
            )
        except Exception:
            old_score = 0.0

        if score > old_score:
            best_by_symbol[symbol] = result

    return list(best_by_symbol.values())


def rank_results(results):
    """
    Rank candidates by quality.

    The scanner does NOT fill the list to 30.
    """
    if not results:
        return []

    for result in results:
        try:
            result["_score"] = float(
                result.get("Score", 0)
            )
        except Exception:
            result["_score"] = 0.0

        try:
            result["_rs"] = float(
                result.get("StockRS", 0)
            )
        except Exception:
            result["_rs"] = 0.0

        try:
            result["_rs60"] = float(
                result.get("RS60", 0)
            )
        except Exception:
            result["_rs60"] = 0.0

        try:
            result["_rs20"] = float(
                result.get("RS20", 0)
            )
        except Exception:
            result["_rs20"] = 0.0

        try:
            result["_rvol"] = float(
                result.get("RVOL", 0)
            )
        except Exception:
            result["_rvol"] = 0.0

    results.sort(
        key=lambda x: (
            x["_score"],
            x["_rs"],
            x["_rs60"],
            x["_rs20"],
            x["_rvol"],
        ),
        reverse=True,
    )

    for result in results:
        result.pop("_score", None)
        result.pop("_rs", None)
        result.pop("_rs60", None)
        result.pop("_rs20", None)
        result.pop("_rvol", None)

    return results[:MAX_RESULTS]


def build_markdown(results, market_regime):
    """
    Build human-readable Markdown report.
    """
    lines = []

    lines.append(
        "# TRADING OS v12 — TOP SWING SETUPS"
    )
    lines.append("")

    lines.append(
        f"**Market Regime:** {market_regime}"
    )

    lines.append(
        f"**Maximum Candidates:** {MAX_RESULTS}"
    )

    lines.append(
        f"**Minimum Score:** {MIN_SCORE}/100"
    )

    lines.append("")

    if not results:
        lines.append(
            "## NO HIGH-QUALITY SETUPS TODAY"
        )
        lines.append("")
        lines.append(
            "The scanner intentionally did not "
            "fill the watchlist."
        )
        lines.append(
            "Only stocks meeting the quality "
            "threshold are displayed."
        )

        return "\n".join(lines)

    pre_count = sum(
        1
        for r in results
        if str(
            r.get("Setup", "")
        ).upper() == "PRE-BREAKOUT"
    )

    fresh_count = sum(
        1
        for r in results
        if str(
            r.get("Setup", "")
        ).upper() == "FRESH BREAKOUT"
    )

    lines.append(
        f"**Qualified Stocks:** {len(results)}"
    )

    lines.append(
        f"**Pre-Breakout:** {pre_count}"
    )

    lines.append(
        f"**Fresh Breakout:** {fresh_count}"
    )

    lines.append("")

    headers = [
        "Rank",
        "Stock",
        "Setup",
        "Score",
        "Breakout %",
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
        "| " + " | ".join(headers) + " |"
    )

    lines.append(
        "|" + "|".join(
            ["---"] * len(headers)
        ) + "|"
    )

    for rank, result in enumerate(
        results,
        start=1,
    ):

        def value(key, default=""):
            return result.get(key, default)

        lines.append(
            "| "
            + " | ".join(
                [
                    str(rank),
                    str(value("Stock")),
                    str(value("Setup")),
                    str(value("Score")),
                    str(value("BreakoutPct")),
                    str(value("RSI")),
                    str(value("RVOL")),
                    str(value("Entry")),
                    str(value("StopLoss")),
                    str(value("T1")),
                    str(value("T2")),
                    str(value("T3")),
                    str(value("T4")),
                ]
            )
            + " |"
        )

    lines.append("")

    lines.append(
        "### Scanner Philosophy"
    )

    lines.append("")

    lines.append(
        "- PRE-BREAKOUT = close to a potential breakout "
        "while still relatively controlled."
    )

    lines.append(
        "- FRESH BREAKOUT = recent breakout with "
        "volume and momentum confirmation."
    )

    lines.append(
        "- Stocks already excessively extended "
        "receive a chase penalty."
    )

    lines.append(
        "- Maximum 30 candidates; fewer is acceptable."
    )

    lines.append(
        "- No duplicate stocks."
    )

    lines.append(
        "- Targets are based on risk multiples:"
    )

    lines.append(
        "  - T1 = 1R"
    )

    lines.append(
        "  - T2 = 2R"
    )

    lines.append(
        "  - T3 = 3R"
    )

    lines.append(
        "  - T4 = 4R"
    )

    return "\n".join(lines)


def save_csv(results):
    """
    Save scanner results to CSV.
    """
    csv_path = REPORT_DIR / "swing_scan.csv"

    if results:
        df = pd.DataFrame(results)

        # Remove internal columns if any remain.
        internal_columns = [
            column
            for column in df.columns
            if str(column).startswith("_")
        ]

        if internal_columns:
            df = df.drop(
                columns=internal_columns,
                errors="ignore",
            )

        df.to_csv(
            csv_path,
            index=False,
        )

    else:
        # Always create the file so downstream
        # Telegram/App processes have something to read.
        pd.DataFrame().to_csv(
            csv_path,
            index=False,
        )

    return csv_path


def save_markdown(markdown_text):
    """
    Save Markdown report.
    """
    md_path = REPORT_DIR / "swing_scan.md"

    md_path.write_text(
        markdown_text,
        encoding="utf-8",
    )

    return md_path


# ============================================================
# MAIN SCANNER
# ============================================================

def main():
    print()
    print("=" * 65)
    print(
        "TRADING OS v12 — HIGH QUALITY SWING SCANNER"
    )
    print("=" * 65)

    # --------------------------------------------------------
    # MARKET REGIME
    # --------------------------------------------------------

    try:
        market_regime = get_market_regime()
    except Exception as exc:
        print(
            f"Market regime calculation failed: {exc}"
        )
        market_regime = "UNKNOWN"

    print()
    print(
        f"Market regime: {market_regime}"
    )

    # --------------------------------------------------------
    # STOCK UNIVERSE
    # --------------------------------------------------------

    print()
    print("Loading stock universe...")
    print(
        "Downloading NSE equity universe..."
    )

    try:
        symbols = get_nse_equity_symbols()
    except Exception as exc:
        print(
            f"Universe download failed: {exc}"
        )
        return 1

    if not symbols:
        print(
            "No symbols received from NSE universe."
        )
        return 1

    cleaned_symbols = []

    for symbol in symbols:

        symbol = clean_symbol(symbol)

        if symbol:
            cleaned_symbols.append(symbol)

    # Remove duplicates while preserving order.
    cleaned_symbols = list(
        dict.fromkeys(cleaned_symbols)
    )

    if UNIVERSE_SIZE:
        cleaned_symbols = cleaned_symbols[
            :UNIVERSE_SIZE
        ]

    print(
        f"broad nse universe: {len(symbols)} symbols"
    )

    print(
        f"{len(cleaned_symbols)} symbols "
        "selected for scanning"
    )

    # --------------------------------------------------------
    # HISTORICAL DATA
    # --------------------------------------------------------

    print()
    print(
        "Downloading historical market data..."
    )

    try:
        # IMPORTANT:
        # Do NOT pass chunk_size here.
        # The current downloader does not accept
        # a chunk_size keyword argument.
        data_map = download_all(
            cleaned_symbols,
            period=PERIOD,
            interval=INTERVAL,
        )

    except Exception as exc:
        print(
            f"Data download failed: {exc}"
        )
        return 1

    if not data_map:
        print(
            "No historical market data received."
        )
        return 1

    print(
        f"Downloaded data for "
        f"{len(data_map)} symbols"
    )

    # --------------------------------------------------------
    # BENCHMARK
    # --------------------------------------------------------

    print()
    print(
        "Downloading NIFTY 50 benchmark..."
    )

    benchmark = get_benchmark_data()

    if benchmark is None:
        print(
            "Warning: NIFTY benchmark unavailable."
        )
        print(
            "Relative-strength calculations may "
            "be unavailable."
        )

    # --------------------------------------------------------
    # SCORE STOCKS
    # --------------------------------------------------------

    scored_results = score_universe(
        data_map=data_map,
        benchmark=benchmark,
    )

    print()
    print(
        f"Scoring produced "
        f"{len(scored_results)} candidates."
    )

    # --------------------------------------------------------
    # QUALITY FILTER
    # --------------------------------------------------------

    qualified_results = []

    for result in scored_results:

        try:
            score = float(
                result.get("Score", 0)
            )
        except Exception:
            score = 0.0

        if score >= MIN_SCORE:
            qualified_results.append(result)

    print(
        f"Candidates above quality threshold "
        f"{MIN_SCORE}: "
        f"{len(qualified_results)}"
    )

    # --------------------------------------------------------
    # REMOVE DUPLICATES
    # --------------------------------------------------------

    qualified_results = deduplicate_results(
        qualified_results
    )

    print(
        f"After duplicate removal: "
        f"{len(qualified_results)}"
    )

    # --------------------------------------------------------
    # RANK + TOP 30 MAXIMUM
    # --------------------------------------------------------

    results = rank_results(
        qualified_results
    )

    print()
    print(
        f"FINAL HIGH-QUALITY SETUPS: "
        f"{len(results)}"
    )

    # --------------------------------------------------------
    # REPORT
    # --------------------------------------------------------

    markdown_text = build_markdown(
        results,
        market_regime,
    )

    csv_path = save_csv(results)
    md_path = save_markdown(
        markdown_text
    )

    print()
    print(
        f"CSV report saved: {csv_path}"
    )

    print(
        f"Markdown report saved: {md_path}"
    )

    # --------------------------------------------------------
    # OPTIONAL CORE REPORT MODULE
    # --------------------------------------------------------

    try:
        save_report(
            results,
            market_regime=market_regime,
            output_dir=str(REPORT_DIR),
        )
    except TypeError:
        try:
            save_report(
                results,
                str(REPORT_DIR),
            )
        except Exception as exc:
            print(
                f"Additional report module skipped: {exc}"
            )
    except Exception as exc:
        print(
            f"Additional report module skipped: {exc}"
        )

    # --------------------------------------------------------
    # DISPLAY FINAL RESULTS
    # --------------------------------------------------------

    print()
    print("=" * 65)

    if not results:

        print(
            "NO HIGH-QUALITY SETUPS TODAY"
        )

        print(
            "The scanner intentionally did not "
            "fill the TOP 30."
        )

    else:

        print(
            "TOP SWING SETUPS"
        )

        print("=" * 65)

        display_columns = [
            "Stock",
            "Setup",
            "Score",
            "BreakoutPct",
            "RSI",
            "RVOL",
            "Entry",
            "StopLoss",
            "T1",
            "T2",
            "T3",
            "T4",
        ]

        display_rows = []

        for rank, result in enumerate(
            results,
            start=1,
        ):

            row = {
                "Rank": rank,
            }

            for column in display_columns:
                row[column] = result.get(
                    column,
                    "",
                )

            display_rows.append(row)

        display_df = pd.DataFrame(
            display_rows
        )

        print(
            display_df.to_string(
                index=False
            )
        )

    print("=" * 65)

    # --------------------------------------------------------
    # TELEGRAM
    # --------------------------------------------------------

    print()
    print(
        "Sending Telegram report..."
    )

    try:
        send_telegram_report(
            csv_path=str(csv_path)
        )

        print(
            "Telegram report sent."
        )

    except Exception as exc:
        print(
            f"Telegram report failed: {exc}"
        )

        # Telegram failure should not make
        # the scanner itself fail.
        pass

    print()
    print(
        "TRADING OS v12 SCAN COMPLETE"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

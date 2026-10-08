import os
from pathlib import Path

import pandas as pd

from scanner.core.downloader import download_all
from scanner.core.market import get_market_regime
from scanner.core.scoring import score_stock
from scanner.core.utils import get_nse_equity_symbols
from telegram_push import send_telegram_report


# ============================================================
# TRADING OS v12 — HIGH QUALITY SWING SCANNER
# ============================================================

PERIOD = "1y"
INTERVAL = "1d"

MAX_RESULTS = 30

# Minimum quality required.
# The scanner is allowed to return fewer than 30 stocks.
MIN_SCORE = 75

REPORT_DIR = Path("reports")

CSV_FILE = REPORT_DIR / "swing_scan.csv"
MARKDOWN_FILE = REPORT_DIR / "swing_scan.md"


# ============================================================
# DATA NORMALISATION
# ============================================================

def normalise_dataframe(data):
    """
    Normalise yfinance/downloaded dataframe columns.

    Handles:
    - normal OHLCV columns
    - MultiIndex columns
    - missing/invalid rows
    """

    if data is None:
        return None

    if not isinstance(data, pd.DataFrame):
        return None

    if data.empty:
        return None

    df = data.copy()

    # --------------------------------------------------------
    # Flatten MultiIndex columns
    # --------------------------------------------------------

    if isinstance(df.columns, pd.MultiIndex):
        flattened = []

        for col in df.columns:
            if isinstance(col, tuple):
                flattened.append(str(col[0]))
            else:
                flattened.append(str(col))

        df.columns = flattened

    # --------------------------------------------------------
    # Standardise column names
    # --------------------------------------------------------

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

    required = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    for column in required:

        if column not in df.columns:
            return None

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df = df.dropna(
        subset=[
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]
    )

    if df.empty:
        return None

    return df


# ============================================================
# BENCHMARK DATA
# ============================================================

def get_benchmark_data():
    """
    Download NIFTY 50 benchmark data.

    This is used by the scoring engine for relative strength.
    """

    try:

        print("Downloading NIFTY 50 benchmark data...")

        benchmark_map = download_all(
            ["^NSEI"],
            period=PERIOD,
            interval=INTERVAL,
        )

        if not benchmark_map:
            print("Benchmark data unavailable.")
            return None

        benchmark = benchmark_map.get("^NSEI")

        benchmark = normalise_dataframe(benchmark)

        if benchmark is None:
            print("Benchmark data could not be normalised.")
            return None

        if len(benchmark) < 100:
            print("Insufficient benchmark history.")
            return None

        print(
            f"Benchmark loaded: {len(benchmark)} sessions"
        )

        return benchmark

    except Exception as exc:

        print(
            f"Benchmark download failed: {exc}"
        )

        return None


# ============================================================
# RESULT NORMALISATION
# ============================================================

def clean_result(result, symbol):
    """
    Convert scoring output into a consistent dictionary.

    This also protects the scanner from slightly different
    scoring-engine field names.
    """

    if result is None:
        return None

    if not isinstance(result, dict):
        return None

    output = dict(result)

    output["symbol"] = (
        output.get("symbol")
        or output.get("ticker")
        or symbol
    )

    # --------------------------------------------------------
    # Standard fields
    # --------------------------------------------------------

    output["setup"] = (
        output.get("setup")
        or output.get("setup_type")
        or ""
    )

    output["score"] = output.get(
        "score",
        output.get("total_score", 0),
    )

    output["price"] = output.get(
        "price",
        output.get("close", 0),
    )

    output["breakout_pct"] = output.get(
        "breakout_pct",
        output.get("breakout_distance_pct", 0),
    )

    output["rsi"] = output.get(
        "rsi",
        0,
    )

    output["rvol"] = output.get(
        "rvol",
        output.get("relative_volume", 0),
    )

    output["entry"] = output.get(
        "entry",
        output.get("entry_price", output["price"]),
    )

    output["stop_loss"] = output.get(
        "stop_loss",
        output.get(
            "stop",
            output.get("sl", 0),
        ),
    )

    # --------------------------------------------------------
    # Four target levels
    # --------------------------------------------------------

    entry = output.get("entry", 0)
    stop = output.get("stop_loss", 0)

    try:

        entry = float(entry)
        stop = float(stop)

        risk = entry - stop

        output["risk"] = risk

        if risk > 0:

            output["target_1"] = output.get(
                "target_1",
                output.get("t1", entry + risk),
            )

            output["target_2"] = output.get(
                "target_2",
                output.get("t2", entry + (2 * risk)),
            )

            output["target_3"] = output.get(
                "target_3",
                output.get("t3", entry + (3 * risk)),
            )

            output["target_4"] = output.get(
                "target_4",
                output.get("t4", entry + (4 * risk)),
            )

        else:

            output["target_1"] = 0
            output["target_2"] = 0
            output["target_3"] = 0
            output["target_4"] = 0

    except Exception:

        output["risk"] = 0

        output["target_1"] = output.get(
            "target_1",
            output.get("t1", 0),
        )

        output["target_2"] = output.get(
            "target_2",
            output.get("t2", 0),
        )

        output["target_3"] = output.get(
            "target_3",
            output.get("t3", 0),
        )

        output["target_4"] = output.get(
            "target_4",
            output.get("t4", 0),
        )

    return output


# ============================================================
# DUPLICATE REMOVAL
# ============================================================

def remove_duplicates(results):
    """
    Keep only one entry per stock.

    If somehow the same symbol appears multiple times,
    retain the highest scoring version.
    """

    best = {}

    for result in results:

        symbol = str(
            result.get("symbol", "")
        ).strip().upper()

        if not symbol:
            continue

        current = best.get(symbol)

        if current is None:
            best[symbol] = result
            continue

        try:
            new_score = float(
                result.get("score", 0)
            )
        except Exception:
            new_score = 0

        try:
            old_score = float(
                current.get("score", 0)
            )
        except Exception:
            old_score = 0

        if new_score > old_score:
            best[symbol] = result

    return list(best.values())


# ============================================================
# FINAL QUALITY FILTER
# ============================================================

def final_quality_filter(results):
    """
    Final safety filter.

    Important:
    MAX_RESULTS is a maximum, NOT a target.

    If only 7 stocks genuinely qualify, return 7.
    """

    filtered = []

    for result in results:

        try:
            score = float(
                result.get("score", 0)
            )
        except Exception:
            score = 0

        if score < MIN_SCORE:
            continue

        setup = str(
            result.get("setup", "")
        ).upper()

        # Only our two desired setups.
        if setup not in {
            "PRE-BREAKOUT",
            "FRESH BREAKOUT",
        }:
            continue

        # ----------------------------------------------------
        # Validate entry / stop
        # ----------------------------------------------------

        try:

            entry = float(
                result.get("entry", 0)
            )

            stop = float(
                result.get("stop_loss", 0)
            )

        except Exception:

            continue

        if entry <= 0:
            continue

        if stop <= 0:
            continue

        if stop >= entry:
            continue

        # ----------------------------------------------------
        # Validate risk
        # ----------------------------------------------------

        risk = entry - stop

        if risk <= 0:
            continue

        result["risk"] = risk

        # ----------------------------------------------------
        # Ensure four targets exist
        # ----------------------------------------------------

        result["target_1"] = entry + risk
        result["target_2"] = entry + (2 * risk)
        result["target_3"] = entry + (3 * risk)
        result["target_4"] = entry + (4 * risk)

        filtered.append(result)

    return filtered


# ============================================================
# MARKDOWN REPORT
# ============================================================

def build_markdown(results, market_regime):

    lines = []

    lines.append(
        "# TRADING OS v12 — TOP SWING SETUPS"
    )

    lines.append("")

    lines.append(
        f"**Market Regime:** {market_regime}"
    )

    lines.append("")

    lines.append(
        f"**Qualified Setups:** {len(results)}"
    )

    lines.append("")

    lines.append(
        "> Maximum 30 stocks. The scanner does not "
        "fill the list with weak setups."
    )

    lines.append("")

    if not results:

        lines.append(
            "No high-quality PRE-BREAKOUT or "
            "FRESH BREAKOUT setups met the current "
            "quality threshold."
        )

        return "\n".join(lines)

    lines.append(
        "| Rank | Stock | Setup | Score | Price | "
        "Breakout % | RSI | RVOL | Entry | SL | "
        "T1 | T2 | T3 | T4 |"
    )

    lines.append(
        "|---:|---|---|---:|---:|---:|---:|---:|"
        "---:|---:|---:|---:|---:|---:|"
    )

    for rank, result in enumerate(
        results,
        start=1,
    ):

        symbol = result.get(
            "symbol",
            "",
        )

        setup = result.get(
            "setup",
            "",
        )

        score = result.get(
            "score",
            0,
        )

        price = result.get(
            "price",
            0,
        )

        breakout_pct = result.get(
            "breakout_pct",
            0,
        )

        rsi = result.get(
            "rsi",
            0,
        )

        rvol = result.get(
            "rvol",
            0,
        )

        entry = result.get(
            "entry",
            0,
        )

        stop = result.get(
            "stop_loss",
            0,
        )

        t1 = result.get(
            "target_1",
            0,
        )

        t2 = result.get(
            "target_2",
            0,
        )

        t3 = result.get(
            "target_3",
            0,
        )

        t4 = result.get(
            "target_4",
            0,
        )

        def fmt(value):

            try:
                return f"{float(value):.2f}"
            except Exception:
                return "-"

        lines.append(
            f"| {rank} | {symbol} | {setup} | "
            f"{fmt(score)} | "
            f"{fmt(price)} | "
            f"{fmt(breakout_pct)} | "
            f"{fmt(rsi)} | "
            f"{fmt(rvol)} | "
            f"{fmt(entry)} | "
            f"{fmt(stop)} | "
            f"{fmt(t1)} | "
            f"{fmt(t2)} | "
            f"{fmt(t3)} | "
            f"{fmt(t4)} |"
        )

    lines.append("")

    lines.append(
        "### Target Method"
    )

    lines.append("")

    lines.append(
        "T1 = 1R, T2 = 2R, T3 = 3R, T4 = 4R"
    )

    lines.append("")

    lines.append(
        "R = Entry − Stop Loss"
    )

    lines.append("")

    lines.append(
        "The scanner penalises excessive extension/chasing "
        "and prioritises stocks that are close to or have "
        "just completed a technically confirmed breakout."
    )

    return "\n".join(lines)


# ============================================================
# SAVE REPORTS
# ============================================================

def save_reports(results, market_regime):

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # CSV
    # --------------------------------------------------------

    if results:

        df = pd.DataFrame(results)

        # Put the important columns first.
        preferred_columns = [
            "symbol",
            "setup",
            "score",
            "price",
            "breakout_pct",
            "rsi",
            "rvol",
            "entry",
            "stop_loss",
            "risk",
            "target_1",
            "target_2",
            "target_3",
            "target_4",
        ]

        ordered = []

        for column in preferred_columns:

            if column in df.columns:
                ordered.append(column)

        remaining = [
            column
            for column in df.columns
            if column not in ordered
        ]

        df = df[
            ordered + remaining
        ]

    else:

        df = pd.DataFrame(
            columns=[
                "symbol",
                "setup",
                "score",
                "price",
                "breakout_pct",
                "rsi",
                "rvol",
                "entry",
                "stop_loss",
                "risk",
                "target_1",
                "target_2",
                "target_3",
                "target_4",
            ]
        )

    df.to_csv(
        CSV_FILE,
        index=False,
    )

    # --------------------------------------------------------
    # Markdown
    # --------------------------------------------------------

    markdown = build_markdown(
        results,
        market_regime,
    )

    MARKDOWN_FILE.write_text(
        markdown,
        encoding="utf-8",
    )

    print(
        f"CSV report saved: {CSV_FILE}"
    )

    print(
        f"Markdown report saved: {MARKDOWN_FILE}"
    )


# ============================================================
# CONSOLE SUMMARY
# ============================================================

def print_results(results, market_regime):

    print("")
    print("=" * 70)
    print(
        "TRADING OS v12 — TOP SWING SETUPS"
    )
    print("=" * 70)

    print(
        f"Market regime : {market_regime}"
    )

    print(
        f"Qualified     : {len(results)}"
    )

    print(
        f"Maximum       : {MAX_RESULTS}"
    )

    print("=" * 70)

    if not results:

        print(
            "NO HIGH-QUALITY SWING SETUPS FOUND."
        )

        print(
            "The scanner will not manufacture "
            "weak candidates to fill the list."
        )

        print("=" * 70)

        return

    print(
        f"{'RK':<4}"
        f"{'STOCK':<14}"
        f"{'SETUP':<17}"
        f"{'SCORE':>6}"
        f"{'PRICE':>11}"
        f"{'RSI':>7}"
        f"{'RVOL':>7}"
    )

    print("-" * 70)

    for rank, result in enumerate(
        results,
        start=1,
    ):

        symbol = str(
            result.get(
                "symbol",
                "",
            )
        )

        setup = str(
            result.get(
                "setup",
                "",
            )
        )

        try:
            score = float(
                result.get(
                    "score",
                    0,
                )
            )
        except Exception:
            score = 0

        try:
            price = float(
                result.get(
                    "price",
                    0,
                )
            )
        except Exception:
            price = 0

        try:
            rsi = float(
                result.get(
                    "rsi",
                    0,
                )
            )
        except Exception:
            rsi = 0

        try:
            rvol = float(
                result.get(
                    "rvol",
                    0,
                )
            )
        except Exception:
            rvol = 0

        print(
            f"{rank:<4}"
            f"{symbol:<14}"
            f"{setup:<17}"
            f"{score:>6.1f}"
            f"{price:>11.2f}"
            f"{rsi:>7.1f}"
            f"{rvol:>7.2f}"
        )

    print("=" * 70)

    print("")
    print(
        "Four targets: T1 = 1R | T2 = 2R | "
        "T3 = 3R | T4 = 4R"
    )

    print("=" * 70)


# ============================================================
# MAIN SCANNER
# ============================================================

def main():

    print("")
    print("=" * 70)
    print(
        "TRADING OS v12 — HIGH QUALITY SWING SCANNER"
    )
    print("=" * 70)

    # --------------------------------------------------------
    # MARKET REGIME
    # --------------------------------------------------------

    market_regime = get_market_regime()

    print(
        f"Market regime: {market_regime}"
    )

    # --------------------------------------------------------
    # LOAD NSE UNIVERSE
    # --------------------------------------------------------

    print("")
    print(
        "Loading stock universe..."
    )

    try:

        symbols = get_nse_equity_symbols()

    except Exception as exc:

        print(
            f"Universe loading failed: {exc}"
        )

        return

    if not symbols:

        print(
            "No symbols available."
        )

        return

    # Remove duplicates immediately.

    symbols = sorted(
        set(
            str(symbol).strip().upper()
            for symbol in symbols
            if str(symbol).strip()
        )
    )

    print(
        f"{len(symbols)} symbols selected for scanning"
    )

    # --------------------------------------------------------
    # BENCHMARK
    # --------------------------------------------------------

    benchmark = get_benchmark_data()

    if benchmark is None:

        print(
            "WARNING: Benchmark unavailable."
        )

        print(
            "Relative-strength calculations may "
            "be unavailable."
        )

    # --------------------------------------------------------
    # DOWNLOAD STOCK DATA
    # --------------------------------------------------------

    print("")
    print(
        "Downloading historical market data..."
    )

    try:

        # IMPORTANT:
        # Do NOT pass chunk_size here.
        # The current downloader does not accept it.

        data_map = download_all(
            symbols,
            period=PERIOD,
            interval=INTERVAL,
        )

    except Exception as exc:

        print(
            f"Data download failed: {exc}"
        )

        return

    if not data_map:

        print(
            "No market data returned."
        )

        return

    print(
        f"Downloaded data for "
        f"{len(data_map)} symbols"
    )

    # --------------------------------------------------------
    # SCORE EACH STOCK
    # --------------------------------------------------------

    results = []

    total = len(data_map)

    processed = 0

    print("")
    print(
        "Scanning for PRE-BREAKOUT and "
        "FRESH BREAKOUT setups..."
    )

    for symbol, raw_data in data_map.items():

        processed += 1

        symbol = str(
            symbol
        ).strip().upper()

        if not symbol:
            continue

        df = normalise_dataframe(
            raw_data
        )

        if df is None:
            continue

        # ----------------------------------------------------
        # Minimum history requirement
        # ----------------------------------------------------

        if len(df) < 220:
            continue

        try:

            result = score_stock(
                symbol=symbol,
                data=df,
                benchmark=benchmark,
            )

        except TypeError:

            # Compatibility fallback in case the scoring
            # engine uses positional arguments.

            try:

                result = score_stock(
                    symbol,
                    df,
                    benchmark,
                )

            except Exception:
                continue

        except Exception:
            continue

        result = clean_result(
            result,
            symbol,
        )

        if result is None:
            continue

        results.append(
            result
        )

        # Progress every 250 symbols.

        if processed % 250 == 0:

            print(
                f"Processed "
                f"{processed}/{total} symbols..."
            )

    print("")
    print(
        f"Raw qualifying results: "
        f"{len(results)}"
    )

    # --------------------------------------------------------
    # REMOVE DUPLICATES
    # --------------------------------------------------------

    results = remove_duplicates(
        results
    )

    print(
        f"After duplicate removal: "
        f"{len(results)}"
    )

    # --------------------------------------------------------
    # FINAL QUALITY FILTER
    # --------------------------------------------------------

    results = final_quality_filter(
        results
    )

    print(
        f"After quality filter: "
        f"{len(results)}"
    )

    # --------------------------------------------------------
    # RANK
    # --------------------------------------------------------

    results.sort(
        key=lambda item: float(
            item.get(
                "score",
                0,
            )
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
    # FINAL RANK ASSIGNMENT
    # --------------------------------------------------------

    for rank, result in enumerate(
        results,
        start=1,
    ):

        result["rank"] = rank

    # --------------------------------------------------------
    # REPORTS
    # --------------------------------------------------------

    save_reports(
        results,
        market_regime,
    )

    # --------------------------------------------------------
    # CONSOLE
    # --------------------------------------------------------

    print_results(
        results,
        market_regime,
    )

    # --------------------------------------------------------
    # TELEGRAM
    # --------------------------------------------------------

    print("")
    print(
        "Sending Telegram report..."
    )

    try:

        send_telegram_report(
            csv_path=str(CSV_FILE)
        )

        print(
            "Telegram report sent."
        )

    except TypeError:

        # Compatibility fallback for a Telegram function
        # that accepts the CSV path positionally.

        try:

            send_telegram_report(
                str(CSV_FILE)
            )

            print(
                "Telegram report sent."
            )

        except Exception as exc:

            print(
                f"Telegram report failed: {exc}"
            )

    except Exception as exc:

        print(
            f"Telegram report failed: {exc}"
        )

    print("")
    print("=" * 70)
    print(
        "TRADING OS v12 SCAN COMPLETE"
    )
    print("=" * 70)

    if results:

        print(
            f"Final candidates: {len(results)}"
        )

    else:

        print(
            "No high-quality candidates today."
        )

    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()

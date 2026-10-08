import io
from pathlib import Path

import pandas as pd
import requests

from scanner.core.downloader import download_all
from scanner.core.market import get_market_regime
from scanner.core.scoring import score_stock
from telegram_push import send_telegram_report


# ============================================================
# TRADING OS v12 — HIGH QUALITY SWING SCANNER
# ============================================================

PERIOD = "1y"
INTERVAL = "1d"

# Maximum, NOT target.
# If only 8 stocks qualify, output 8.
MAX_RESULTS = 30

# Minimum quality score.
MIN_SCORE = 75

REPORT_DIR = Path("reports")

CSV_FILE = REPORT_DIR / "swing_scan.csv"
MARKDOWN_FILE = REPORT_DIR / "swing_scan.md"


# ============================================================
# NSE UNIVERSE
# ============================================================

NSE_EQUITY_URL = (
    "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
)

NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/csv,application/csv,text/plain,"
        "application/json,*/*"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}


def get_nse_equity_symbols():
    """
    Download the current NSE equity list directly from NSE.

    Returns:
        list[str]
    """

    print(
        "Downloading NSE equity universe..."
    )

    try:

        response = requests.get(
            NSE_EQUITY_URL,
            headers=NSE_HEADERS,
            timeout=30,
        )

        response.raise_for_status()

        content = response.content

        if not content:
            raise RuntimeError(
                "NSE returned an empty response."
            )

        df = pd.read_csv(
            io.BytesIO(content)
        )

        if df.empty:
            raise RuntimeError(
                "NSE equity list is empty."
            )

        # ----------------------------------------------------
        # Find SYMBOL column safely
        # ----------------------------------------------------

        symbol_column = None

        for column in df.columns:

            if str(column).strip().upper() == "SYMBOL":
                symbol_column = column
                break

        if symbol_column is None:
            raise RuntimeError(
                "SYMBOL column not found in NSE equity list."
            )

        symbols = (
            df[symbol_column]
            .astype(str)
            .str.strip()
            .str.upper()
        )

        # ----------------------------------------------------
        # Basic cleanup
        # ----------------------------------------------------

        symbols = symbols[
            symbols.notna()
        ]

        symbols = symbols[
            symbols != ""
        ]

        symbols = symbols[
            symbols != "NAN"
        ]

        # Remove obviously invalid values.
        symbols = symbols[
            ~symbols.str.contains(
                "SYMBOL",
                case=False,
                na=False,
            )
        ]

        # Remove duplicate symbols.
        symbols = sorted(
            set(symbols.tolist())
        )

        print(
            f"broad nse universe: "
            f"{len(symbols)} symbols"
        )

        return symbols

    except Exception as exc:

        print(
            f"NSE universe download failed: {exc}"
        )

        return []


# ============================================================
# DATA NORMALISATION
# ============================================================

def normalise_dataframe(data):

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
                flattened.append(
                    str(col[0])
                )
            else:
                flattened.append(
                    str(col)
                )

        df.columns = flattened

    # --------------------------------------------------------
    # Standardise OHLCV names
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

    df = df.rename(
        columns=rename_map
    )

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
        subset=required
    )

    if df.empty:
        return None

    return df


# ============================================================
# BENCHMARK DATA
# ============================================================

def get_benchmark_data():

    try:

        print(
            "Downloading NIFTY 50 benchmark data..."
        )

        benchmark_map = download_all(
            ["^NSEI"],
            period=PERIOD,
            interval=INTERVAL,
        )

        if not benchmark_map:
            print(
                "Benchmark data unavailable."
            )
            return None

        benchmark = benchmark_map.get(
            "^NSEI"
        )

        benchmark = normalise_dataframe(
            benchmark
        )

        if benchmark is None:

            print(
                "Benchmark data could not "
                "be normalised."
            )

            return None

        if len(benchmark) < 100:

            print(
                "Insufficient benchmark history."
            )

            return None

        print(
            f"Benchmark loaded: "
            f"{len(benchmark)} sessions"
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
        output.get(
            "breakout_distance_pct",
            0,
        ),
    )

    output["rsi"] = output.get(
        "rsi",
        0,
    )

    output["rvol"] = output.get(
        "rvol",
        output.get(
            "relative_volume",
            0,
        ),
    )

    output["entry"] = output.get(
        "entry",
        output.get(
            "entry_price",
            output["price"],
        ),
    )

    output["stop_loss"] = output.get(
        "stop_loss",
        output.get(
            "stop",
            output.get(
                "sl",
                0,
            ),
        ),
    )

    # --------------------------------------------------------
    # Calculate four targets
    # --------------------------------------------------------

    try:

        entry = float(
            output["entry"]
        )

        stop = float(
            output["stop_loss"]
        )

        risk = entry - stop

        output["risk"] = risk

        if risk > 0:

            output["target_1"] = (
                entry + risk
            )

            output["target_2"] = (
                entry + (2 * risk)
            )

            output["target_3"] = (
                entry + (3 * risk)
            )

            output["target_4"] = (
                entry + (4 * risk)
            )

        else:

            output["target_1"] = 0
            output["target_2"] = 0
            output["target_3"] = 0
            output["target_4"] = 0

    except Exception:

        output["risk"] = 0
        output["target_1"] = 0
        output["target_2"] = 0
        output["target_3"] = 0
        output["target_4"] = 0

    return output


# ============================================================
# REMOVE DUPLICATES
# ============================================================

def remove_duplicates(results):

    best = {}

    for result in results:

        symbol = str(
            result.get(
                "symbol",
                "",
            )
        ).strip().upper()

        if not symbol:
            continue

        try:

            new_score = float(
                result.get(
                    "score",
                    0,
                )
            )

        except Exception:

            new_score = 0

        if symbol not in best:

            best[symbol] = result

        else:

            try:

                old_score = float(
                    best[symbol].get(
                        "score",
                        0,
                    )
                )

            except Exception:

                old_score = 0

            if new_score > old_score:

                best[symbol] = result

    return list(
        best.values()
    )


# ============================================================
# FINAL QUALITY FILTER
# ============================================================

def final_quality_filter(results):

    filtered = []

    for result in results:

        try:

            score = float(
                result.get(
                    "score",
                    0,
                )
            )

        except Exception:

            score = 0

        if score < MIN_SCORE:
            continue

        setup = str(
            result.get(
                "setup",
                "",
            )
        ).strip().upper()

        # Only the two setups we actually want.
        if setup not in {
            "PRE-BREAKOUT",
            "FRESH BREAKOUT",
        }:
            continue

        try:

            entry = float(
                result.get(
                    "entry",
                    0,
                )
            )

            stop = float(
                result.get(
                    "stop_loss",
                    0,
                )
            )

        except Exception:

            continue

        if entry <= 0:
            continue

        if stop <= 0:
            continue

        if stop >= entry:
            continue

        risk = entry - stop

        if risk <= 0:
            continue

        result["risk"] = risk

        result["target_1"] = (
            entry + risk
        )

        result["target_2"] = (
            entry + (2 * risk)
        )

        result["target_3"] = (
            entry + (3 * risk)
        )

        result["target_4"] = (
            entry + (4 * risk)
        )

        filtered.append(
            result
        )

    return filtered


# ============================================================
# MARKDOWN REPORT
# ============================================================

def build_markdown(
    results,
    market_regime,
):

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
        f"**Qualified Setups:** "
        f"{len(results)}"
    )

    lines.append("")

    lines.append(
        "> Maximum 30 stocks. "
        "The scanner does not fill the list "
        "with weak setups."
    )

    lines.append("")

    if not results:

        lines.append(
            "No high-quality PRE-BREAKOUT "
            "or FRESH BREAKOUT setups met "
            "the current quality threshold."
        )

        return "\n".join(lines)

    lines.append(
        "| Rank | Stock | Setup | Score | "
        "Price | Breakout % | RSI | RVOL | "
        "Entry | SL | T1 | T2 | T3 | T4 |"
    )

    lines.append(
        "|---:|---|---|---:|---:|---:|"
        "---:|---:|---:|---:|---:|---:|"
        "---:|---:|"
    )

    def fmt(value):

        try:
            return f"{float(value):.2f}"
        except Exception:
            return "-"

    for rank, result in enumerate(
        results,
        start=1,
    ):

        lines.append(
            f"| {rank} | "
            f"{result.get('symbol', '')} | "
            f"{result.get('setup', '')} | "
            f"{fmt(result.get('score', 0))} | "
            f"{fmt(result.get('price', 0))} | "
            f"{fmt(result.get('breakout_pct', 0))} | "
            f"{fmt(result.get('rsi', 0))} | "
            f"{fmt(result.get('rvol', 0))} | "
            f"{fmt(result.get('entry', 0))} | "
            f"{fmt(result.get('stop_loss', 0))} | "
            f"{fmt(result.get('target_1', 0))} | "
            f"{fmt(result.get('target_2', 0))} | "
            f"{fmt(result.get('target_3', 0))} | "
            f"{fmt(result.get('target_4', 0))} |"
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
        "The scanner prioritises stocks that "
        "are close to or have just completed "
        "a technically confirmed breakout and "
        "penalises excessive extension/chasing."
    )

    return "\n".join(lines)


# ============================================================
# SAVE REPORTS
# ============================================================

def save_reports(
    results,
    market_regime,
):

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    preferred_columns = [
        "rank",
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

    if results:

        df = pd.DataFrame(
            results
        )

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
            columns=preferred_columns
        )

    df.to_csv(
        CSV_FILE,
        index=False,
    )

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
        f"Markdown report saved: "
        f"{MARKDOWN_FILE}"
    )


# ============================================================
# CONSOLE RESULTS
# ============================================================

def print_results(
    results,
    market_regime,
):

    print("")
    print("=" * 75)
    print(
        "TRADING OS v12 — TOP SWING SETUPS"
    )
    print("=" * 75)

    print(
        f"Market regime : {market_regime}"
    )

    print(
        f"Qualified     : {len(results)}"
    )

    print(
        f"Maximum       : {MAX_RESULTS}"
    )

    print("=" * 75)

    if not results:

        print(
            "NO HIGH-QUALITY SWING SETUPS FOUND."
        )

        print(
            "The scanner will NOT manufacture "
            "weak candidates to fill TOP 30."
        )

        print("=" * 75)

        return

    print(
        f"{'RK':<4}"
        f"{'STOCK':<14}"
        f"{'SETUP':<18}"
        f"{'SCORE':>7}"
        f"{'PRICE':>11}"
        f"{'RSI':>7}"
        f"{'RVOL':>7}"
    )

    print("-" * 75)

    for rank, result in enumerate(
        results,
        start=1,
    ):

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
            f"{str(result.get('symbol', '')):<14}"
            f"{str(result.get('setup', '')):<18}"
            f"{score:>7.1f}"
            f"{price:>11.2f}"
            f"{rsi:>7.1f}"
            f"{rvol:>7.2f}"
        )

    print("=" * 75)

    print(
        "Targets: T1 = 1R | T2 = 2R | "
        "T3 = 3R | T4 = 4R"
    )

    print("=" * 75)


# ============================================================
# MAIN
# ============================================================

def main():

    print("")
    print("=" * 75)
    print(
        "TRADING OS v12 — HIGH QUALITY SWING SCANNER"
    )
    print("=" * 75)

    # --------------------------------------------------------
    # MARKET REGIME
    # --------------------------------------------------------

    market_regime = get_market_regime()

    print(
        f"Market regime: {market_regime}"
    )

    # --------------------------------------------------------
    # NSE UNIVERSE
    # --------------------------------------------------------

    print("")
    print(
        "Loading stock universe..."
    )

    symbols = get_nse_equity_symbols()

    if not symbols:

        print(
            "ERROR: NSE equity universe could "
            "not be loaded."
        )

        return

    print(
        f"{len(symbols)} symbols selected "
        f"for scanning"
    )

    # --------------------------------------------------------
    # BENCHMARK
    # --------------------------------------------------------

    benchmark = get_benchmark_data()

    # --------------------------------------------------------
    # STOCK DATA
    # --------------------------------------------------------

    print("")
    print(
        "Downloading historical market data..."
    )

    try:

        # IMPORTANT:
        # No chunk_size parameter.
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
            "No stock market data returned."
        )

        return

    print(
        f"Downloaded data for "
        f"{len(data_map)} symbols"
    )

    # --------------------------------------------------------
    # SCAN
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

        # Minimum data requirement.
        if len(df) < 220:
            continue

        try:

            result = score_stock(
                symbol=symbol,
                data=df,
                benchmark=benchmark,
            )

        except TypeError:

            # Compatibility fallback.
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
    # DUPLICATES
    # --------------------------------------------------------

    results = remove_duplicates(
        results
    )

    print(
        f"After duplicate removal: "
        f"{len(results)}"
    )

    # --------------------------------------------------------
    # QUALITY FILTER
    # --------------------------------------------------------

    results = final_quality_filter(
        results
    )

    print(
        f"After quality filter: "
        f"{len(results)}"
    )

    # --------------------------------------------------------
    # RANK BY SCORE
    # --------------------------------------------------------

    results.sort(
        key=lambda x: float(
            x.get(
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
    # FINAL RANK
    # --------------------------------------------------------

    for rank, result in enumerate(
        results,
        start=1,
    ):

        result["rank"] = rank

    # --------------------------------------------------------
    # REPORT
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
            csv_path=str(
                CSV_FILE
            )
        )

        print(
            "Telegram report sent."
        )

    except TypeError:

        try:

            send_telegram_report(
                str(CSV_FILE)
            )

            print(
                "Telegram report sent."
            )

        except Exception as exc:

            print(
                f"Telegram report failed: "
                f"{exc}"
            )

    except Exception as exc:

        print(
            f"Telegram report failed: "
            f"{exc}"
        )

    print("")
    print("=" * 75)
    print(
        "TRADING OS v12 SCAN COMPLETE"
    )
    print("=" * 75)

    if results:

        print(
            f"Final candidates: "
            f"{len(results)}"
        )

    else:

        print(
            "No high-quality candidates today."
        )

    print("=" * 75)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()

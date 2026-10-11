"""Trading OS v12: selective Nifty 500 swing scanner."""
from pathlib import Path
import math

import pandas as pd

from scanner.core.downloader import (
    download_all,
    get_nifty500_symbols,
)
from scanner.core.market import get_market_regime
from scanner.core.scoring import score_stock
from telegram_push import send_telegram_report


PERIOD = "1y"
INTERVAL = "1d"

MAX_RESULTS = 30
MIN_SCORE = 75
MIN_COVERAGE = 0.65
MIN_HISTORY_BARS = 220

REPORT_DIR = Path("reports")
CSV_FILE = REPORT_DIR / "swing_scan.csv"
MARKDOWN_FILE = REPORT_DIR / "swing_scan.md"

REPORT_COLUMNS = [
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

ALLOWED_SETUPS = {"PRE-BREAKOUT", "FRESH BREAKOUT"}


def normalise_dataframe(data):
    """Normalize downloaded OHLCV data into a consistent format."""
    if (
        data is None
        or not isinstance(data, pd.DataFrame)
        or data.empty
    ):
        return None

    df = data.copy()

    if isinstance(df.columns, pd.MultiIndex):
        flattened = []

        for column in df.columns:
            parts = column if isinstance(column, tuple) else (column,)

            match = next(
                (
                    str(part).strip()
                    for part in parts
                    if str(part).strip().lower()
                    in {"open", "high", "low", "close", "volume"}
                ),
                str(parts[0]),
            )

            flattened.append(match)

        df.columns = flattened

    rename = {
        column: {
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }.get(str(column).strip().lower(), column)
        for column in df.columns
    }

    df = df.rename(columns=rename)
    df = df.loc[:, ~df.columns.duplicated(keep="first")]

    required = ["Open", "High", "Low", "Close", "Volume"]

    if not all(column in df.columns for column in required):
        return None

    for column in required:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df = df.dropna(subset=required).sort_index()

    return df if not df.empty else None


def get_benchmark_data():
    """Download Nifty 50 benchmark history."""
    try:
        data = download_all(
            ["^NSEI"],
            period="2y",
            interval=INTERVAL,
            chunk=1,
        )

        benchmark = normalise_dataframe(data.get("^NSEI"))

        if benchmark is None or len(benchmark) < 100:
            print(
                "Benchmark unavailable or insufficient; "
                "scan is incomplete."
            )
            return None

        print(
            f"NIFTY 50 benchmark loaded: {len(benchmark)} sessions"
        )

        return benchmark

    except Exception as exc:
        print(f"Benchmark download failed: {exc}")
        return None


def _num(value, default=0.0):
    """Convert a value to a finite float safely."""
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def clean_result(result, symbol):
    """Normalize scorer output from either lowercase or legacy keys."""
    if not isinstance(result, dict):
        return None

    out = dict(result)

    def pick(*keys, default=None):
        for key in keys:
            value = out.get(key)
            if value is not None and value != "":
                return value
        return default

    out["symbol"] = (
        str(pick("symbol", "Symbol", "ticker", "Ticker", default=symbol))
        .strip()
        .upper()
        .replace(".NS", "")
    )

    out["setup"] = (
        str(pick("setup", "Setup", "setup_type", default=""))
        .strip()
        .upper()
        .replace("_", "-")
    )

    out["score"] = _num(
        pick("score", "Score", "total_score", default=0)
    )

    # The scorer's current output calls its closing price "Entry".
    out["price"] = _num(
        pick("price", "Price", "close", "Close", "Entry", default=0)
    )

    out["breakout_pct"] = _num(
        pick(
            "breakout_pct",
            "BreakoutPct",
            "breakout_distance_pct",
            default=0,
        )
    )

    out["rsi"] = _num(pick("rsi", "RSI", default=0))
    out["rvol"] = _num(
        pick("rvol", "RVOL", "relative_volume", default=0)
    )

    out["entry"] = _num(
        pick("entry", "Entry", "entry_price", default=out["price"])
    )

    out["stop_loss"] = _num(
        pick("stop_loss", "StopLoss", "SL", "stop", "sl", default=0)
    )

    out["risk"] = out["entry"] - out["stop_loss"]

    for multiple in range(1, 5):
        out[f"target_{multiple}"] = (
            round(out["entry"] + multiple * out["risk"], 2)
            if out["risk"] > 0
            else 0.0
        )

    return out


def remove_duplicates(results):
    """Keep only the highest-scoring result for each symbol."""
    best = {}

    for result in results:
        symbol = str(result.get("symbol", "")).strip().upper()

        if not symbol:
            continue

        if (
            symbol not in best
            or _num(result.get("score"))
            > _num(best[symbol].get("score"))
        ):
            best[symbol] = result

    return list(best.values())


def final_quality_filter(results):
    """Apply minimum score, setup and risk validation."""
    accepted = []

    for result in results:
        entry = _num(result.get("entry"))
        stop = _num(result.get("stop_loss"))
        score = _num(result.get("score"))
        setup = str(result.get("setup", "")).strip().upper()

        if score < MIN_SCORE:
            continue

        if setup not in ALLOWED_SETUPS:
            continue

        if entry <= 0 or stop <= 0 or stop >= entry:
            continue

        risk = entry - stop

        result["risk"] = risk

        for multiple in range(1, 5):
            result[f"target_{multiple}"] = entry + multiple * risk

        accepted.append(result)

    return accepted


def _fmt(value):
    number = _num(value, float("nan"))

    return f"{number:.2f}" if math.isfinite(number) else "-"


def build_markdown(results, market_regime, status, coverage_text):
    lines = [
        "# TRADING OS v12 — SWING SCAN",
        "",
        f"**Status:** {status}",
        f"**Market regime:** {market_regime}",
        f"**Data coverage:** {coverage_text}",
        f"**Qualified setups:** {len(results)}",
        "",
        (
            "> Universe: official Nifty 50 + Nifty Next 50 "
            "+ Nifty Midcap 150 + Nifty Smallcap 250 constituents."
        ),
        "> Maximum 30 candidates; weak setups are not added to fill the list.",
        "> R = Entry − Stop Loss; targets are T1=1R, T2=2R, T3=3R, T4=4R.",
        "",
    ]

    if status != "COMPLETE":
        lines += [
            "## Important: scan incomplete",
            "",
            (
                "The shortlist is not reliable because the benchmark, "
                "constituents, or enough stock histories could not be downloaded."
            ),
            (
                "Do not interpret zero candidates as a market signal. "
                "Retry after data access is restored."
            ),
            "",
        ]

    elif not results:
        lines += [
            (
                "No PRE-BREAKOUT or FRESH BREAKOUT setup met "
                "the quality threshold today."
            ),
            "",
        ]

    else:
        lines += [
            (
                "| Rank | Symbol | Setup | Score | Price | Breakout % "
                "| RSI | RVOL | Entry | SL | R | T1 | T2 | T3 | T4 |"
            ),
            (
                "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|"
                "---:|---:|---:|---:|---:|"
            ),
        ]

        for rank, result in enumerate(results, 1):
            values = [
                str(rank),
                str(result.get("symbol", "")),
                str(result.get("setup", "")),
            ]

            values.extend(
                _fmt(result.get(column))
                for column in (
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
                )
            )

            lines.append("| " + " | ".join(values) + " |")

    return "\n".join(lines) + "\n"


def save_reports(
    results,
    market_regime,
    status="COMPLETE",
    coverage_text="not available",
):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    df = (
        pd.DataFrame(results)
        if results
        else pd.DataFrame(columns=REPORT_COLUMNS)
    )

    for column in REPORT_COLUMNS:
        if column not in df.columns:
            df[column] = pd.Series(dtype="object")

    df = df[
        REPORT_COLUMNS
        + [
            column
            for column in df.columns
            if column not in REPORT_COLUMNS
        ]
    ]

    df.to_csv(CSV_FILE, index=False)

    MARKDOWN_FILE.write_text(
        build_markdown(
            results,
            market_regime,
            status,
            coverage_text,
        ),
        encoding="utf-8",
    )

    print(f"CSV report saved: {CSV_FILE}")
    print(f"Markdown report saved: {MARKDOWN_FILE}")


def print_results(results, market_regime, status, coverage_text):
    print("\n" + "=" * 78)
    print("TRADING OS v12 — HIGH QUALITY SWING SCANNER")
    print(
        f"Status: {status} | Market regime: {market_regime} "
        f"| Coverage: {coverage_text}"
    )
    print(
        f"Qualified candidates: {len(results)} "
        f"| Maximum: {MAX_RESULTS}"
    )
    print("=" * 78)

    if status != "COMPLETE":
        print(
            "SCAN INCOMPLETE — do not treat an empty list "
            "as a valid market signal."
        )
        return

    if not results:
        print(
            "NO HIGH-QUALITY SWING SETUPS FOUND. "
            "No weak candidates will be added to fill the list."
        )
        return

    print(
        f"{'RK':<4}{'STOCK':<16}{'SETUP':<19}"
        f"{'SCORE':>7}{'PRICE':>11}{'RSI':>7}{'RVOL':>7}"
    )

    for result_rank, result in enumerate(results, 1):
        print(
            f"{result_rank:<4}"
            f"{result['symbol']:<16}"
            f"{result['setup']:<19}"
            f"{_num(result['score']):>7.1f}"
            f"{_num(result['price']):>11.2f}"
            f"{_num(result['rsi']):>7.1f}"
            f"{_num(result['rvol']):>7.2f}"
        )

    print(
        "Targets: T1=1R | T2=2R | T3=3R | T4=4R; "
        "R=Entry−Stop Loss"
    )


def _send_telegram_if_possible(context_label, reason):
    """Send a fallback Telegram message even when the scan is incomplete."""
    try:
        save_reports([], "UNKNOWN", "INCOMPLETE", reason)
        send_telegram_report(csv_path=str(CSV_FILE))
        print(f"Telegram fallback sent for {context_label}.")
    except Exception as exc:
        print(f"Telegram fallback failed for {context_label}: {exc}")


def main():
    print(
        "\n"
        + "=" * 78
        + "\nTRADING OS v12 — SELECTIVE NIFTY 500 SWING SCANNER\n"
        + "=" * 78
    )

    try:
        market_regime = get_market_regime()
    except Exception as exc:
        market_regime = "UNKNOWN"
        print(f"Market regime unavailable: {exc}")

    print(f"Market regime: {market_regime}")

    try:
        symbols = get_nifty500_symbols()

    except Exception as exc:
        print(f"Universe loading failed: {exc}")

        save_reports(
            [],
            market_regime,
            "INCOMPLETE",
            "0% (official universe unavailable)",
        )

        print_results(
            [],
            market_regime,
            "INCOMPLETE",
            "0% (official universe unavailable)",
        )

        try:
            send_telegram_report(csv_path=str(CSV_FILE))
            print("Telegram report sent for incomplete scan.")
        except Exception as telegram_exc:
            print(f"Telegram report failed: {telegram_exc}")

        print("Telegram shortlist suppressed: scan is incomplete.")
        return

    benchmark = get_benchmark_data()

    if benchmark is None:
        save_reports(
            [],
            market_regime,
            "INCOMPLETE",
            "benchmark unavailable",
        )

        print_results(
            [],
            market_regime,
            "INCOMPLETE",
            "benchmark unavailable",
        )

        try:
            send_telegram_report(csv_path=str(CSV_FILE))
            print("Telegram report sent for missing benchmark.")
        except Exception as telegram_exc:
            print(f"Telegram report failed: {telegram_exc}")

        print("Telegram shortlist suppressed: benchmark unavailable.")
        return

    try:
        data_map = download_all(
            symbols,
            period=PERIOD,
            interval=INTERVAL,
            chunk=10,
        )

    except Exception as exc:
        print(f"Stock data download failed: {exc}")
        data_map = {}

    valid_count = 0

    for data in data_map.values():
        df = normalise_dataframe(data)

        if df is not None and len(df) >= MIN_HISTORY_BARS:
            valid_count += 1

    coverage = valid_count / len(symbols) if symbols else 0.0
    coverage_text = f"{valid_count}/{len(symbols)} ({coverage:.0%})"

    print(
        f"Valid historical data coverage: {coverage_text}; "
        f"required: {MIN_COVERAGE:.0%}"
    )

    if coverage < MIN_COVERAGE:
        save_reports(
            [],
            market_regime,
            "INCOMPLETE",
            coverage_text,
        )

        print_results(
            [],
            market_regime,
            "INCOMPLETE",
            coverage_text,
        )

        try:
            send_telegram_report(csv_path=str(CSV_FILE))
            print("Telegram report sent for incomplete coverage.")
        except Exception as telegram_exc:
            print(f"Telegram report failed: {telegram_exc}")

        print(
            "Telegram shortlist suppressed: "
            "incomplete Yahoo Finance data coverage."
        )
        return

    results = []

    print(
        "Scanning for PRE-BREAKOUT and FRESH BREAKOUT setups..."
    )

    for symbol in symbols:
        df = normalise_dataframe(data_map.get(symbol))

        if df is None or len(df) < MIN_HISTORY_BARS:
            continue

        try:
            candidate = score_stock(
                data=df,
                benchmark=benchmark,
                symbol=symbol,
            )

        except Exception as exc:
            print(f"Scoring skipped for {symbol}: {exc}")
            continue

        cleaned = clean_result(candidate, symbol)

        if cleaned:
            results.append(cleaned)

    print(f"Raw qualifying results: {len(results)}")

    results = final_quality_filter(
        remove_duplicates(results)
    )

    results.sort(
        key=lambda result: _num(result.get("score")),
        reverse=True,
    )

    results = results[:MAX_RESULTS]

    for rank, result in enumerate(results, 1):
        result["rank"] = rank

    save_reports(
        results,
        market_regime,
        "COMPLETE",
        coverage_text,
    )

    print_results(
        results,
        market_regime,
        "COMPLETE",
        coverage_text,
    )

    try:
        send_telegram_report(csv_path=str(CSV_FILE))
        print("Telegram report sent.")

    except TypeError:
        try:
            send_telegram_report(str(CSV_FILE))
            print("Telegram report sent.")

        except Exception as exc:
            print(f"Telegram report failed: {exc}")

    except Exception as exc:
        print(f"Telegram report failed: {exc}")

    print("\nTRADING OS v12 SCAN COMPLETE")
    print(f"Final candidates: {len(results)}")


if __name__ == "__main__":
    main()

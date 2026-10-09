"""Trading OS v12: selective Nifty 50 + Nifty Next 50 swing scanner."""

from pathlib import Path
import math

import pandas as pd

from scanner.core.downloader import (
    download_all,
    get_nifty50_next50_symbols,
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
    if data is None or not isinstance(data, pd.DataFrame) or data.empty:
        return None

    df = data.copy()

    if isinstance(df.columns, pd.MultiIndex):
        names = []

        for column in df.columns:
            parts = [
                str(value).strip()
                for value in (
                    column if isinstance(column, tuple) else (column,)
                )
            ]

            wanted = next(
                (
                    value
                    for value in parts
                    if value.lower()
                    in {"open", "high", "low", "close", "volume"}
                ),
                parts[0],
            )

            names.append(wanted)

        df.columns = names

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
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df.dropna(subset=required).sort_index()

    return df if not df.empty else None


def get_benchmark_data():
    try:
        benchmark_map = download_all(
            ["^NSEI"],
            period="2y",
            interval=INTERVAL,
            chunk=1,
        )

        benchmark = normalise_dataframe(benchmark_map.get("^NSEI"))

        if benchmark is None or len(benchmark) < 100:
            print(
                "Benchmark unavailable or insufficient; "
                "scan will be marked incomplete."
            )
            return None

        print(f"NIFTY 50 benchmark loaded: {len(benchmark)} sessions")
        return benchmark

    except Exception as exc:
        print(f"Benchmark download failed: {exc}")
        return None


def _num(value, default=0.0):
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def clean_result(result, symbol):
    if not isinstance(result, dict):
        return None

    out = dict(result)

    out["symbol"] = (
        str(out.get("symbol") or out.get("ticker") or symbol)
        .strip()
        .upper()
        .replace(".NS", "")
    )

    out["setup"] = str(
        out.get("setup") or out.get("setup_type") or ""
    ).strip().upper()

    out["score"] = _num(
        out.get("score", out.get("total_score", 0))
    )

    out["price"] = _num(
        out.get("price", out.get("close", 0))
    )

    out["breakout_pct"] = _num(
        out.get("breakout_pct", out.get("breakout_distance_pct", 0))
    )

    out["rsi"] = _num(out.get("rsi", 0))

    out["rvol"] = _num(
        out.get("rvol", out.get("relative_volume", 0))
    )

    out["entry"] = _num(
        out.get("entry", out.get("entry_price", out["price"]))
    )

    out["stop_loss"] = _num(
        out.get("stop_loss", out.get("stop", out.get("sl", 0)))
    )

    out["risk"] = out["entry"] - out["stop_loss"]

    if out["risk"] > 0:
        for multiple in range(1, 5):
            out[f"target_{multiple}"] = (
                out["entry"] + multiple * out["risk"]
            )
    else:
        for multiple in range(1, 5):
            out[f"target_{multiple}"] = 0.0

    return out


def remove_duplicates(results):
    best = {}

    for result in results:
        symbol = str(result.get("symbol", "")).strip().upper()

        if symbol and (
            symbol not in best
            or _num(result.get("score"))
            > _num(best[symbol].get("score"))
        ):
            best[symbol] = result

    return list(best.values())


def final_quality_filter(results):
    accepted = []

    for result in results:
        score = _num(result.get("score"))
        setup = str(result.get("setup", "")).strip().upper()
        entry = _num(result.get("entry"))
        stop = _num(result.get("stop_loss"))

        if score < MIN_SCORE or setup not in ALLOWED_SETUPS:
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
        "> Universe: official Nifty 50 + Nifty Next 50 constituents.",
        "> Maximum 30 candidates; weak setups are not added to fill the list.",
        "> R = Entry − Stop Loss; targets are T1=1R, T2=2R, T3=3R, T4=4R.",
        "",
    ]

    if status != "COMPLETE":
        lines.extend([
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
        ])

    elif not results:
        lines.extend([
            "No PRE-BREAKOUT or FRESH BREAKOUT setup met the quality threshold today.",
            "",
        ])

    else:
        lines.extend([
            "| Rank | Symbol | Setup | Score | Price | Breakout % | RSI | RVOL | Entry | SL | R | T1 | T2 | T3 | T4 |",
            "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ])

        for rank, result in enumerate(results, 1):
            values = [
                str(rank),
                str(result.get("symbol", "")),
                str(result.get("setup", "")),
                _fmt(result.get("score")),
                _fmt(result.get("price")),
                _fmt(result.get("breakout_pct")),
                _fmt(result.get("rsi")),
                _fmt(result.get("rvol")),
                _fmt(result.get("entry")),
                _fmt(result.get("stop_loss")),
                _fmt(result.get("risk")),
                _fmt(result.get("target_1")),
                _fmt(result.get("target_2")),
                _fmt(result.get("target_3")),
                _fmt(result.get("target_4")),
            ]

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
        + [column for column in df.columns if column not in REPORT_COLUMNS]
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
        f"Status: {status} | Market regime: {market_regime} | "
        f"Coverage: {coverage_text}"
    )
    print(f"Qualified candidates: {len(results)} | Maximum: {MAX_RESULTS}")
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

    for rank, result in enumerate(results, 1):
        print(
            f"{rank:<4}{result['symbol']:<16}{result['setup']:<19}"
            f"{_num(result['score']):>7.1f}"
            f"{_num(result['price']):>11.2f}"
            f"{_num(result['rsi']):>7.1f}"
            f"{_num(result['rvol']):>7.2f}"
        )

    print("Targets: T1=1R | T2=2R | T3=3R | T4=4R; R=Entry−Stop Loss")


def main():
    print(
        "\n"
        + "=" * 78
        + "\nTRADING OS v12 — SELECTIVE NIFTY 100 SWING SCANNER\n"
        + "=" * 78
    )

    market_regime = get_market_regime()
    print(f"Market regime: {market_regime}")

    # Fail closed if either official constituents file cannot be loaded.
    try:
        symbols = get_nifty50_next50_symbols()

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

        print(
            "Telegram shortlist suppressed: "
            "incomplete Yahoo Finance data coverage."
        )
        return

    results = []

    print("Scanning for PRE-BREAKOUT and FRESH BREAKOUT setups...")

    for symbol in symbols:
        raw = data_map.get(symbol)
        df = normalise_dataframe(raw)

        if df is None or len(df) < MIN_HISTORY_BARS:
            continue

        try:
            candidate = score_stock(
                symbol=symbol,
                data=df,
                benchmark=benchmark,
            )

        except TypeError:
            try:
                candidate = score_stock(symbol, df, benchmark)

            except Exception as exc:
                print(f"Scoring skipped for {symbol}: {exc}")
                continue

        except Exception as exc:
            print(f"Scoring skipped for {symbol}: {exc}")
            continue

        cleaned = clean_result(candidate, symbol)

        if cleaned:
            results.append(cleaned)

    print(f"Raw qualifying results: {len(results)}")

    results = final_quality_filter(remove_duplicates(results))

    results.sort(
        key=lambda item: _num(item.get("score")),
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

    # Only send a shortlist when data coverage is sufficient.
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

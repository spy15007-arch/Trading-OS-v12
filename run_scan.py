"""Trading OS v12: selective Nifty 500 swing scanner."""
from pathlib import Path
from datetime import datetime, timezone
import json
import math
import os

import pandas as pd

from scanner.core.downloader import (
    download_all,
    get_nifty500_symbols,
)
from scanner.core.market import get_market_regime
from scanner.core.outcome_tracker import update_trade_outcomes
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
SUMMARY_FILE = REPORT_DIR / "scan_summary.json"
DATA_COVERAGE_FILE = REPORT_DIR / "data_coverage.csv"

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
    "resistance",
    "rs20",
    "rs60",
    "stock_rs",
    "base_range",
    "compression",
    "range_contraction",
    "volume_dryup_ratio",
    "extension",
    "closing_strength",
    "candle_body_ratio",
    "upper_wick_ratio",
    "risk_pct",
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
    for field, aliases in {
        "resistance": ("resistance", "Resistance"),
        "rs20": ("rs20", "RS20"),
        "rs60": ("rs60", "RS60"),
        "stock_rs": ("stock_rs", "StockRS"),
        "base_range": ("base_range", "BaseRange"),
        "compression": ("compression", "Compression"),
        "range_contraction": ("range_contraction", "RangeContraction"),
        "volume_dryup_ratio": ("volume_dryup_ratio", "VolumeDryupRatio"),
        "extension": ("extension", "Extension"),
        "closing_strength": ("closing_strength", "ClosingStrength"),
        "candle_body_ratio": ("candle_body_ratio", "CandleBodyRatio"),
        "upper_wick_ratio": ("upper_wick_ratio", "UpperWickRatio"),
        "risk_pct": ("risk_pct", "RiskPct"),
    }.items():
        out[field] = _num(pick(*aliases, default=0))

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

        breakout_pct = _num(result.get("breakout_pct"))
        rvol = _num(result.get("rvol"))
        rsi_value = _num(result.get("rsi"))
        extension = _num(result.get("extension"))
        risk_pct = _num(result.get("risk_pct"))
        resistance = _num(result.get("resistance"))
        closing_strength = _num(result.get("closing_strength"))
        body_ratio = _num(result.get("candle_body_ratio"))
        upper_wick_ratio = _num(result.get("upper_wick_ratio"))

        # Hard gates prevent a high aggregate score from overriding weak
        # breakout confirmation or an unacceptably wide stop.
        if risk_pct > 8.0:
            continue

        if setup == "FRESH BREAKOUT":
            if not (0 < breakout_pct <= 5.0):
                continue
            if resistance <= 0 or rvol < 1.50 or rsi_value < 58:
                continue
            if closing_strength < 0.65 or body_ratio < 0.30:
                continue
            if upper_wick_ratio > 0.40 or extension > 10.0:
                continue
        else:
            if not (-4.0 <= breakout_pct <= 0):
                continue
            if resistance <= 0 or rvol < 0.65 or rsi_value < 55:
                continue
            if _num(result.get("base_range")) > 15.0:
                continue
            if _num(result.get("compression")) < 5.0:
                continue
            if extension > 10.0:
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


def build_markdown(results, market_regime, status, coverage_text, summary=None):
    """Build a current-run report with the same strict shortlist as Telegram."""
    summary = summary or {}
    stocks_in_universe = int(summary.get("stocks_in_universe", 0))
    valid_data_count = int(summary.get("valid_data_count", 0))
    raw_setup_count = int(summary.get("raw_setup_count", 0))
    lines = [
        "# TRADING OS v12 — SWING SCAN",
        "",
        f"**Status:** {status}",
        f"**Market regime:** {market_regime}",
        f"**Scan mode:** {str(summary.get('scan_mode', os.getenv('SCAN_MODE', 'MANUAL'))).upper()}",
        f"**Data coverage:** {coverage_text}",
        f"**Stocks scanned:** {stocks_in_universe}",
        f"**Stocks with valid history:** {valid_data_count}",
        f"**Raw setup candidates:** {raw_setup_count}",
        f"**Qualified setups:** {len(results)} (maximum {MAX_RESULTS})",
        "",
        (
            "> Universe: official Nifty 50 + Nifty Next 50 "
            "+ Nifty Midcap 150 + Nifty Smallcap 250 constituents."
        ),
        "> Strict filters: score >= 75, valid risk levels, and PRE-BREAKOUT/FRESH BREAKOUT only.",
        f"> Shortlist capacity: {MAX_RESULTS}; only qualified stocks are listed below.",
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
        return "\n".join(lines) + "\n"

    if not results:
        lines += [
            "No PRE-BREAKOUT or FRESH BREAKOUT setup met the strict quality threshold today.",
            "",
        ]
    else:
        lines += [
            "## Ranked shortlist",
            "",
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
                    "score", "price", "breakout_pct", "rsi", "rvol",
                    "entry", "stop_loss", "risk", "target_1", "target_2",
                    "target_3", "target_4",
                )
            )
            lines.append("| " + " | ".join(values) + " |")

        lines.append("")

    # Keep the requested three headings without weakening the scanner filters.
    # The current scorer emits PRE-BREAKOUT and FRESH BREAKOUT, not generic BREAKOUT.
    sections = [
        ("BREAKOUT STOCKS", "BREAKOUT"),
        ("PRE-BREAKOUT", "PRE-BREAKOUT"),
        ("FRESH BREAKOUT", "FRESH BREAKOUT"),
    ]
    for heading, setup in sections:
        lines.extend([f"## {heading}", ""])
        matches = [item for item in results if str(item.get("setup", "")).upper() == setup]
        if not matches:
            if setup == "BREAKOUT":
                lines.append("No candidates cleared the BREAKOUT category.")
            elif setup == "FRESH BREAKOUT":
                lines.append("No candidates cleared the FRESH BREAKOUT category.")
            else:
                lines.append("No candidates cleared the PRE-BREAKOUT category.")
            lines.append("")
            continue

        for result in matches:
            lines.append(
                f"- **{result.get('symbol', '')}** — score {_fmt(result.get('score'))}, "
                f"breakout {_fmt(result.get('breakout_pct'))}%, "
                f"RSI {_fmt(result.get('rsi'))}, RVOL {_fmt(result.get('rvol'))}; "
                f"Entry {_fmt(result.get('entry'))}, SL {_fmt(result.get('stop_loss'))}, "
                f"T1 {_fmt(result.get('target_1'))}, T2 {_fmt(result.get('target_2'))}, "
                f"T3 {_fmt(result.get('target_3'))}, T4 {_fmt(result.get('target_4'))}"
            )
        lines.append("")

    return "\n".join(lines) + "\n"

def save_data_coverage(symbols, data_map):
    """Write one auditable row per universe symbol, including missing history."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for raw_symbol in symbols:
        symbol = str(raw_symbol).strip().upper().replace(".NS", "")
        frame = normalise_dataframe(data_map.get(raw_symbol))
        if frame is None:
            rows.append({
                "symbol": symbol,
                "status": "DOWNLOAD_FAILED_OR_EMPTY",
                "valid_bars": 0,
                "last_date": "",
            })
        elif len(frame) < MIN_HISTORY_BARS:
            rows.append({
                "symbol": symbol,
                "status": "INSUFFICIENT_HISTORY",
                "valid_bars": len(frame),
                "last_date": str(frame.index[-1])[:10],
            })
        else:
            rows.append({
                "symbol": symbol,
                "status": "VALID",
                "valid_bars": len(frame),
                "last_date": str(frame.index[-1])[:10],
            })
    report = pd.DataFrame(rows, columns=["symbol", "status", "valid_bars", "last_date"])
    report.to_csv(DATA_COVERAGE_FILE, index=False)
    missing = report[report["status"] != "VALID"]
    missing_symbols = missing["symbol"].astype(str).tolist()
    print(f"Data coverage diagnostics saved: {DATA_COVERAGE_FILE}")
    print(f"Unavailable/short-history symbols ({len(missing_symbols)}): "
          + (", ".join(missing_symbols) if missing_symbols else "none"))
    return {
        "data_coverage_file": str(DATA_COVERAGE_FILE),
        "missing_data_count": len(missing_symbols),
        "missing_data_symbols": missing_symbols,
    }


def save_reports(
    results,
    market_regime,
    status="COMPLETE",
    coverage_text="not available",
    summary=None,
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
            summary,
        ),
        encoding="utf-8",
    )

    report_summary = {
        "market_sentiment": market_regime,
        "scan_mode": str((summary or {}).get("scan_mode", os.getenv("SCAN_MODE", "MANUAL"))).upper(),
        "status": status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stocks_in_universe": int((summary or {}).get("stocks_in_universe", 0)),
        "valid_data_count": int((summary or {}).get("valid_data_count", 0)),
        "raw_setup_count": int((summary or {}).get("raw_setup_count", 0)),
        "qualified_count": len(results),
        "max_shortlist": MAX_RESULTS,
        "coverage": coverage_text,
        "missing_data_count": int((summary or {}).get("missing_data_count", 0)),
        "missing_data_symbols": list((summary or {}).get("missing_data_symbols", [])),
    }
    SUMMARY_FILE.write_text(json.dumps(report_summary, indent=2), encoding="utf-8")

    print(f"CSV report saved: {CSV_FILE}")
    print(f"Markdown report saved: {MARKDOWN_FILE}")
    print(f"Scan summary saved: {SUMMARY_FILE}")


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
        sent = send_telegram_report(csv_path=str(CSV_FILE))
        if sent:
            print(f"Telegram fallback sent for {context_label}.")
        else:
            print(f"Telegram fallback was NOT sent for {context_label}.")
    except Exception as exc:
        print(f"Telegram fallback failed for {context_label}: {exc}")


def main():
    scan_mode = os.getenv("SCAN_MODE", "MANUAL").strip().upper()
    print(
        "\n"
        + "=" * 78
        + "\nTRADING OS v12 — SELECTIVE NIFTY 500 SWING SCANNER\n"
        + f"\nSCAN MODE: {scan_mode}\n"
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
            sent = send_telegram_report(csv_path=str(CSV_FILE))
            print("Telegram report sent for incomplete scan." if sent else "Telegram report NOT sent for incomplete scan.")
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
            sent = send_telegram_report(csv_path=str(CSV_FILE))
            print("Telegram report sent for missing benchmark." if sent else "Telegram report NOT sent for missing benchmark.")
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
    coverage_diagnostics = save_data_coverage(symbols, data_map)

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
            {
                "stocks_in_universe": len(symbols),
                "valid_data_count": valid_count,
                "scan_mode": scan_mode,
                **coverage_diagnostics,
            },
        )

        print_results(
            [],
            market_regime,
            "INCOMPLETE",
            coverage_text,
        )

        try:
            sent = send_telegram_report(csv_path=str(CSV_FILE))
            print("Telegram report sent for incomplete coverage." if sent else "Telegram report NOT sent for incomplete coverage.")
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

    raw_setup_count = len(results)
    print(f"Raw setup candidates: {raw_setup_count}")

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

    # Update the persistent outcome tracker using normalized daily OHLCV history.
    histories = {}
    for raw_symbol, raw_history in data_map.items():
        clean_symbol = str(raw_symbol).strip().upper().replace(".NS", "")
        normalized_history = normalise_dataframe(raw_history)
        if clean_symbol and normalized_history is not None:
            histories[clean_symbol] = normalized_history
    try:
        update_trade_outcomes(results, histories)
    except Exception as exc:
        # Tracking should never prevent a valid scan report or Telegram message.
        print(f"Trade outcome tracker update failed: {exc}")

    scan_summary = {
        "stocks_in_universe": len(symbols),
        "valid_data_count": valid_count,
        "raw_setup_count": raw_setup_count,
        "scan_mode": scan_mode,
        **coverage_diagnostics,
    }

    save_reports(
        results,
        market_regime,
        "COMPLETE",
        coverage_text,
        scan_summary,
    )

    print_results(
        results,
        market_regime,
        "COMPLETE",
        coverage_text,
    )

    try:
        sent = send_telegram_report(csv_path=str(CSV_FILE))
        print("Telegram report sent." if sent else "Telegram report NOT sent; inspect Telegram diagnostics above.")

    except TypeError:
        try:
            sent = send_telegram_report(str(CSV_FILE))
            print("Telegram report sent." if sent else "Telegram report NOT sent; inspect Telegram diagnostics above.")

        except Exception as exc:
            print(f"Telegram report failed: {exc}")

    except Exception as exc:
        print(f"Telegram report failed: {exc}")

    print("\nTRADING OS v12 SCAN COMPLETE")
    print(f"Final candidates: {len(results)}")


if __name__ == "__main__":
    main()

"""Console, CSV, and Markdown reports for all scan profiles."""
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import pandas as pd


REPORT_COLUMNS = [
    "symbol",
    "score",
    "price",
    "rsi",
    "relative_volume",
    "near_20d_high_pct",
    "entry",
    "stop",
    "target1",
    "target2",
    "target3",
    "reward_risk_t3",
]


def chart_link(symbol):
    ticker = str(symbol).replace(".NS", "").upper()
    return (
        "https://www.tradingview.com/chart/"
        f"?symbol={quote(f'NSE:{ticker}', safe='')}"
    )


def _number(value):
    if value is None:
        return "-"

    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "-"


def _markdown_report(results, profile, regime):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"# Trading OS v12 — {profile.title()} Scan",
        "",
        f"- **Market regime:** {regime}",
        f"- **Generated:** {timestamp}",
        f"- **Selected candidates:** {len(results)}",
        "",
    ]

    if not results:
        lines.append("No qualifying candidates were found.")
        return "\n".join(lines)

    lines.extend(
        [
            "| Symbol | Score | Entry | Stop-loss | Target 1 | Target 2 | Target 3 | Chart |",
            "|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )

    for result in results:
        symbol = result["symbol"]

        lines.append(
            f"| {symbol} "
            f"| {result['score']} "
            f"| ₹{_number(result.get('entry'))} "
            f"| ₹{_number(result.get('stop'))} "
            f"| ₹{_number(result.get('target1'))} "
            f"| ₹{_number(result.get('target2'))} "
            f"| ₹{_number(result.get('target3'))} "
            f"| [Open chart]({chart_link(symbol)}) |"
        )

    return "\n".join(lines)


def write_report(results, profile, regime, output_dir="reports"):
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    csv_path = Path(output_dir) / f"{profile}_scan_{timestamp}.csv"
    markdown_path = Path(output_dir) / f"{profile}_scan_{timestamp}.md"

    frame = pd.DataFrame(results, columns=REPORT_COLUMNS)

    frame.to_csv(csv_path, index=False)
    markdown_path.write_text(
        _markdown_report(results, profile, regime),
        encoding="utf-8",
    )

    print(
        f"\n{profile.upper()} scan | "
        f"market: {regime} | "
        f"candidates: {len(frame)}"
    )

    print(
        frame.to_string(index=False)
        if not frame.empty
        else "No qualifying candidates today."
    )

    print(f"CSV report: {csv_path}")
    print(f"Markdown report: {markdown_path}")

    return {
        "csv": csv_path,
        "markdown": markdown_path,
    }

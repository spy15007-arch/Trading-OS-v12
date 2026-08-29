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

LATEST_NAMES = {
    "strict": "00_LATEST_STRICT",
    "aggressive": "01_LATEST_AGGRESSIVE",
    "budget": "02_LATEST_BUDGET",
}


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
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    profile = profile.lower()

    timestamp_csv = output_path / f"{profile}_scan_{timestamp}.csv"
    timestamp_markdown = output_path / f"{profile}_scan_{timestamp}.md"

    latest_name = LATEST_NAMES[profile]
    latest_csv = output_path / f"{latest_name}.csv"
    latest_markdown = output_path / f"{latest_name}.md"

    frame = pd.DataFrame(results, columns=REPORT_COLUMNS)
    markdown = _markdown_report(results, profile, regime)

    # Timestamped files are retained in the GitHub Actions artifact.
    frame.to_csv(timestamp_csv, index=False)
    timestamp_markdown.write_text(markdown, encoding="utf-8")

    # Stable latest files are committed back to the repository.
    frame.to_csv(latest_csv, index=False)
    latest_markdown.write_text(markdown, encoding="utf-8")

    # Track last scan timestamp in ISO format for visibility
    last_scan_file = output_path / ".last_scan"
    last_scan_file.write_text(datetime.now().isoformat(), encoding="utf-8")

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

    print(f"CSV report: {timestamp_csv}")
    print(f"Markdown report: {timestamp_markdown}")
    print(f"Latest CSV: {latest_csv}")
    print(f"Latest Markdown: {latest_markdown}")
    print(f"Last scan tracked: {last_scan_file}")

    return {
        "csv": timestamp_csv,
        "markdown": timestamp_markdown,
        "latest_csv": latest_csv,
        "latest_markdown": latest_markdown,
    }

"""Console and CSV reports for all scan profiles."""
from datetime import datetime
from pathlib import Path

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
    "target",
    "reward_risk",
]


def write_report(results, profile, regime, output_dir="reports"):
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = Path(output_dir) / f"{profile}_scan_{timestamp}.csv"

    frame = pd.DataFrame(results, columns=REPORT_COLUMNS)
    frame.to_csv(path, index=False)

    print(f"\n{profile.upper()} scan | market: {regime} | candidates: {len(frame)}")
    print(
        frame.to_string(index=False)
        if not frame.empty
        else "No qualifying candidates today."
    )
    print(f"Saved: {path}")

    return path

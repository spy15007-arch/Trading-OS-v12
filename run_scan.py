"""Trading OS v12 - Master Swing Breakout Scanner.
Finds only PRE-BREAKOUT and FRESH BREAKOUT swing setups and ranks them 1..30.
"""
import os
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scanner.core.downloader import get_nse_equity_symbols, download_all, download_index
from scanner.core.scoring import score_stock
from scanner.core.market import get_market_status
from scanner.core.utils import export_markdown, logger, timestamp

UNIVERSE_SIZE = 1800
TOP_RESULTS = 30
MIN_SCORE = 60


def run_scan():
    logger.info("==========================================")
    logger.info("TRADING OS v12 - MASTER SWING BREAKOUT SCANNER")
    logger.info("==========================================")

    market = get_market_status()
    logger.info(f"Market Mode: {market.get('MODE')}")

    symbols = get_nse_equity_symbols(UNIVERSE_SIZE)
    logger.info(f"{len(symbols)} symbols selected for scanning")

    database = download_all(symbols, period="1y", interval="1d", chunk=75)
    logger.info(f"{len(database)} charts downloaded")

    benchmark = download_index("^NSEI", period="1y", interval="1d")
    results = []

    for symbol, df in database.items():
        result = score_stock(df, benchmark_df=benchmark)
        if result and result["Score"] >= MIN_SCORE:
            result["Symbol"] = symbol.replace(".NS", "")
            results.append(result)

    if not results:
        logger.warning("No pre-breakout or fresh-breakout setups found.")
        export_markdown(f"# Trading OS v12\n\nGenerated: {timestamp()}\n\nNo qualifying swing setups found.\n", "swing_scan.md")
        return 0

    df = pd.DataFrame(results)
    # One stock = one row. Ranking is strictly score-first, never alphabetical.
    df = df.sort_values(["Score", "RS60", "RVOL", "RSI"], ascending=[False, False, False, False], kind="mergesort")
    df = df.drop_duplicates(subset=["Symbol"], keep="first").head(TOP_RESULTS).reset_index(drop=True)
    df.insert(0, "Rank", range(1, len(df) + 1))

    # Prefer a balanced presentation, but do not distort the global ranking.
    breakout = df[df["Setup"] == "BREAKOUT"]
    pre = df[df["Setup"] == "PRE-BREAKOUT"]

    md = f"# TRADING OS v12 — TOP SWING SETUPS\n\nGenerated: **{timestamp()}**\n\n"
    md += f"- Universe: **{len(symbols)} stocks**\n- Charts downloaded: **{len(database)}**\n- Qualifying candidates: **{len(results)}**\n- Final watchlist: **{len(df)}**\n- Market mode: **{market.get('MODE')}**\n\n"
    md += "## Ranking\n\n"
    md += "| Rank | Symbol | Setup | Score | Breakout % | RS20 | RS60 | RSI | RVOL | Entry | SL | T1 | T2 |\n"
    md += "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n"
    for _, r in df.iterrows():
        md += f"| {int(r.Rank)} | **{r.Symbol}** | {r.Setup} | **{int(r.Score)}** | {r.BreakoutPct}% | {r.RS20}% | {r.RS60}% | {r.RSI} | {r.RVOL} | ₹{r.Entry} | ₹{r.SL} | ₹{r.T1} | ₹{r.T2} |\n"

    md += "\n## Fresh Breakouts\n\n"
    for _, r in breakout.iterrows():
        md += f"- **#{int(r.Rank)} {r.Symbol}** — score {int(r.Score)}, breakout {r.BreakoutPct}%, RVOL {r.RVOL}, RSI {r.RSI}\n"

    md += "\n## Pre-Breakouts\n\n"
    for _, r in pre.iterrows():
        md += f"- **#{int(r.Rank)} {r.Symbol}** — score {int(r.Score)}, resistance gap {r.BreakoutPct}%, base {r.BaseRangePct}%, RVOL {r.RVOL}, RSI {r.RSI}\n"

    export_markdown(md, "swing_scan.md")

    # Move Symbol column to be immediately after Rank so CSVs match Streamlit layout
    try:
        if "Symbol" in df.columns:
            cols = [c for c in df.columns if c != "Symbol"]
            if "Rank" in cols:
                # place Symbol right after Rank
                other = [c for c in cols if c != "Rank"]
                new_cols = ["Rank", "Symbol"] + other
            else:
                new_cols = ["Symbol"] + cols
            df = df[new_cols]
    except Exception:
        logger.exception("Failed to reorder columns for CSV output")

    df.to_csv(Path("reports") / "swing_scan.csv", index=False)

    print("\n" + "=" * 95)
    print("TRADING OS v12 — TOP SWING SETUPS")
    print("=" * 95)
    print(df[["Rank", "Symbol", "Setup", "Score", "BreakoutPct", "RSI", "RVOL", "Entry", "SL", "T1", "T2"]].to_string(index=False))
    print("\nReport saved : reports/swing_scan.md")
    print("CSV saved    : reports/swing_scan.csv")
    logger.info("Master swing scan completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_scan())

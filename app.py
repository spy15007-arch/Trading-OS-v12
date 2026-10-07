"""Trading OS v12 — latest scanner report dashboard."""
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="Trading OS v12",
    page_icon="📈",
    layout="wide",
)


# Original multi-file report configuration. The app will prefer these if they exist.
ORIGINAL_REPORTS = {
    "Strict": {
        "csv": Path("reports/00_LATEST_STRICT.csv"),
        "markdown": Path("reports/00_LATEST_STRICT.md"),
        "description": "Higher-conviction momentum setups.",
    },
    "Aggressive": {
        "csv": Path("reports/01_LATEST_AGGRESSIVE.csv"),
        "markdown": Path("reports/01_LATEST_AGGRESSIVE.md"),
        "description": "Broader momentum setups with looser filters.",
    },
    "Budget": {
        "csv": Path("reports/02_LATEST_BUDGET.csv"),
        "markdown": Path("reports/02_LATEST_BUDGET.md"),
        "description": "Momentum setups priced at ₹500 or below.",
    },
}


# Fallback single-file scanner output used by the current automation
SINGLE_REPORT_CSV = Path("reports/swing_scan.csv")
SINGLE_REPORT_MD = Path("reports/swing_scan.md")


def chart_link(symbol):
    ticker = str(symbol).replace(".NS", "").upper()

    return (
        "https://www.tradingview.com/chart/"
        f"?symbol={quote(f'NSE:{ticker}', safe='')}"
    )


def normalize_report_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize CSV field names to the app's expected lowercase schema.

    This is needed because newer scanner exports use PascalCase columns like
    `Rank,Symbol,Entry,...`, while older reports use lowercase names.
    """
    if frame.empty:
        return frame

    normalized = frame.copy()
    normalized.columns = [str(col).strip() for col in normalized.columns]

    rename_map = {
        "Rank": "rank",
        "Symbol": "symbol",
        "Entry": "entry",
        "Score": "score",
        "Setup": "setup",
        "RSI": "rsi",
        "RVOL": "relative_volume",
        "RS20": "rs20",
        "RS60": "rs60",
        "BreakoutPct": "breakout_pct",
        "BaseRangePct": "base_range_pct",
        "ExtensionPct": "extension_pct",
        "SL": "stop",
        "T1": "target1",
        "T2": "target2",
        "T3": "target3",
        "ATR": "atr",
        "Trade": "trade",
        "Price": "price",
        "EMA20": "ema20",
        "EMA50": "ema50",
        "EMA200": "ema200",
        "Grade": "grade",
        "RR1": "rr1",
        "Relative_Volume": "relative_volume",
        "Relative Volume": "relative_volume",
        "Stop": "stop",
    }

    normalized = normalized.rename(columns=rename_map)

    # Keep the user-facing order intuitive: rank first, symbol second, then the rest.
    for key in ["rank", "symbol"]:
        if key not in normalized.columns:
            continue

    if "rank" in normalized.columns and "symbol" in normalized.columns:
        ordered = ["rank", "symbol"] + [
            c for c in normalized.columns if c not in {"rank", "symbol"}
        ]
        normalized = normalized[ordered]

    return normalized


@st.cache_data(ttl=60, show_spinner=False)
def load_report(path_text):
    path = Path(path_text)

    if not path.exists():
        return pd.DataFrame()

    try:
        frame = pd.read_csv(path)
        return normalize_report_frame(frame)
    except Exception:
        return pd.DataFrame()


def report_updated_at(path):
    if not path.exists():
        return "Not available"

    timestamp = datetime.fromtimestamp(
        path.stat().st_mtime,
        tz=ZoneInfo("Asia/Kolkata"),
    )

    return timestamp.strftime("%d-%b-%Y %I:%M %p IST")


def render_report(name, config):
    csv_path = config["csv"]
    markdown_path = config["markdown"]

    frame = load_report(str(csv_path))

    st.subheader(f"{name} Scanner")
    st.caption(config.get("description", ""))
    st.caption(f"Last updated: {report_updated_at(csv_path)}")

    if frame.empty:
        st.info(
            "No latest report is available yet. "
            "Run the corresponding scanner workflow first."
        )
        return

    if "symbol" in frame.columns:
        frame["Chart"] = frame["symbol"].apply(chart_link)

    candidates = len(frame)
    highest_score = (
        int(frame["score"].max())
        if "score" in frame.columns and not frame.empty
        else 0
    )

    top_symbol = (
        str(frame.iloc[0]["symbol"]) if "symbol" in frame.columns and not frame.empty else "-"
    )

    metric_one, metric_two, metric_three = st.columns(3)

    metric_one.metric("Selected candidates", candidates)
    metric_two.metric("Highest score", highest_score)
    metric_three.metric("Top-ranked symbol", top_symbol)

    columns = [
        column
        for column in [
            "symbol",
            "score",
            "price",
            "rsi",
            "relative_volume",
            "entry",
            "stop",
            "target1",
            "target2",
            "target3",
            "Chart",
        ]
        if column in frame.columns
    ]

    st.dataframe(
        frame[columns],
        hide_index=True,
        use_container_width=True,
        column_config={
            "Chart": st.column_config.LinkColumn(
                "TradingView Chart",
                display_text="Open chart",
            ),
        },
    )

    if markdown_path.exists():
        with st.expander("View full Markdown report"):
            st.markdown(
                markdown_path.read_text(encoding="utf-8")
            )


def build_active_reports():
    """Return the reports mapping the app should use.

    Preference order:
    1. If the three "LATEST" CSVs exist, use them (multi-tab mode).
    2. Else if the single `swing_scan.csv` exists, expose a single "Master" tab.
    3. Else fall back to the original mapping (so UI still shows expected tabs).
    """
    active = {}
    # Prefer explicit latest files if they exist
    for name, cfg in ORIGINAL_REPORTS.items():
        if cfg["csv"].exists() or cfg["markdown"].exists():
            active[name] = cfg

    if active:
        return active

    # Fallback: single-file output produced by the current automation
    if SINGLE_REPORT_CSV.exists() or SINGLE_REPORT_MD.exists():
        return {
            "Master": {
                "csv": SINGLE_REPORT_CSV,
                "markdown": SINGLE_REPORT_MD,
                "description": "Master swing scan output (single-file scanner).",
            }
        }

    # No files detected; return original map so UI still renders the three tabs
    return ORIGINAL_REPORTS


st.title("📈 Trading OS v12")
st.caption(
    "Latest NSE scanner reports. "
    "This dashboard refreshes after the scanner workflow commits new reports."
)

if st.button("Refresh latest reports"):
    st.cache_data.clear()
    st.rerun()

REPORTS = build_active_reports()

# Create tabs dynamically from the active reports mapping
tab_names = list(REPORTS.keys())
if not tab_names:
    tab_names = ["Reports"]

tab_objs = st.tabs(tab_names)
for name, tab in zip(tab_names, tab_objs):
    with tab:
        render_report(name, REPORTS[name])

st.divider()

st.caption(
    "Educational scanner output only. "
    "Review liquidity, price action, and risk independently before trading."
)

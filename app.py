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


REPORTS = {
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


def chart_link(symbol):
    ticker = str(symbol).replace(".NS", "").upper()

    return (
        "https://www.tradingview.com/chart/"
        f"?symbol={quote(f'NSE:{ticker}', safe='')}"
    )


@st.cache_data(ttl=60, show_spinner=False)
def load_report(path_text):
    path = Path(path_text)

    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path)
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
    st.caption(config["description"])
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
        str(frame.iloc[0]["symbol"])
        if "symbol" in frame.columns and not frame.empty
        else "-"
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


st.title("📈 Trading OS v12")
st.caption(
    "Latest NSE scanner reports. "
    "This dashboard refreshes after the scanner workflow commits new reports."
)

if st.button("Refresh latest reports"):
    st.cache_data.clear()
    st.rerun()

strict_tab, aggressive_tab, budget_tab = st.tabs(
    ["Strict", "Aggressive", "Budget"]
)

with strict_tab:
    render_report("Strict", REPORTS["Strict"])

with aggressive_tab:
    render_report("Aggressive", REPORTS["Aggressive"])

with budget_tab:
    render_report("Budget", REPORTS["Budget"])

st.divider()

st.caption(
    "Educational scanner output only. "
    "Review liquidity, price action, and risk independently before trading."
)

import os
from pathlib import Path

import pandas as pd
import streamlit as st


# ============================================================
# CONFIG
# ============================================================

REPORT_FILE = Path(
    "reports/swing_scan.csv"
)


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="Trading OS v12",
    page_icon="📊",
    layout="wide",
)


# ============================================================
# HEADER
# ============================================================

st.title(
    "📊 Trading OS v12 — Swing Trading Dashboard"
)

st.caption(
    "PRE-BREAKOUT + FRESH BREAKOUT | TOP 30"
)


# ============================================================
# LOAD DATA
# ============================================================

if not REPORT_FILE.exists():

    st.error(
        "No scan report found."
    )

    st.info(
        "Run the scanner first to create "
        "reports/swing_scan.csv"
    )

    st.stop()


df = pd.read_csv(
    REPORT_FILE
)


if df.empty:

    st.warning(
        "No qualifying swing setups in the latest scan."
    )

    st.stop()


# ============================================================
# CLEAN DATA
# ============================================================

numeric_columns = [
    "Score",
    "BreakoutPct",
    "RS20",
    "RS60",
    "StockRS",
    "RSI",
    "RVOL",
    "BaseRange",
    "Compression",
    "Extension",
    "Resistance",
    "ClosingStrength",
    "Entry",
    "SL",
    "T1",
    "T2",
    "T3",
    "T4",
    "RiskPct",
]

for column in numeric_columns:

    if column in df.columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )


# ============================================================
# COUNTS
# ============================================================

pre = df[
    df["Setup"] == "PRE-BREAKOUT"
]

fresh = df[
    df["Setup"] == "FRESH BREAKOUT"
]


top_score = (
    float(df["Score"].max())
    if not df.empty
    else 0
)


# ============================================================
# SUMMARY
# ============================================================

st.subheader(
    "Market Snapshot"
)

col1, col2, col3, col4 = st.columns(4)

with col1:

    st.metric(
        "Final Watchlist",
        len(df)
    )

with col2:

    st.metric(
        "Pre-Breakout",
        len(pre)
    )

with col3:

    st.metric(
        "Fresh Breakout",
        len(fresh)
    )

with col4:

    st.metric(
        "Top Score",
        f"{top_score:.0f}/100"
    )


# ============================================================
# MASTER RANKING
# ============================================================

st.divider()

st.subheader(
    "🏆 TOP 30 — MASTER RANKING"
)


master_columns = [
    "Rank",
    "Symbol",
    "Setup",
    "Score",
    "BreakoutPct",
    "RSI",
    "RVOL",
    "Entry",
    "SL",
    "T1",
    "T2",
    "T3",
    "T4",
]


available_master = [
    col
    for col in master_columns
    if col in df.columns
]


master_display = df[
    available_master
].copy()


st.dataframe(
    master_display,
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# PRE-BREAKOUT
# ============================================================

st.divider()

st.subheader(
    "👀 PRE-BREAKOUT"
)

if pre.empty:

    st.info(
        "No pre-breakout setups today."
    )

else:

    pre_columns = [
        "Rank",
        "Symbol",
        "Score",
        "BreakoutPct",
        "RSI",
        "RVOL",
        "Extension",
        "Entry",
        "SL",
        "T1",
        "T2",
        "T3",
        "T4",
    ]

    available_pre = [
        col
        for col in pre_columns
        if col in pre.columns
    ]

    st.dataframe(
        pre[available_pre],
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# FRESH BREAKOUT
# ============================================================

st.divider()

st.subheader(
    "🚀 FRESH BREAKOUT"
)

if fresh.empty:

    st.info(
        "No fresh-breakout setups today."
    )

else:

    fresh_columns = [
        "Rank",
        "Symbol",
        "Score",
        "BreakoutPct",
        "RSI",
        "RVOL",
        "Extension",
        "Entry",
        "SL",
        "T1",
        "T2",
        "T3",
        "T4",
    ]

    available_fresh = [
        col
        for col in fresh_columns
        if col in fresh.columns
    ]

    st.dataframe(
        fresh[available_fresh],
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# STOCK DETAILS
# ============================================================

st.divider()

st.subheader(
    "🔎 Stock Details"
)


symbols = df[
    "Symbol"
].astype(str).tolist()


selected_symbol = st.selectbox(
    "Select a stock",
    symbols
)


selected = df[
    df["Symbol"].astype(str)
    == selected_symbol
].iloc[0]


# ------------------------------------------------------------
# BASIC INFO
# ------------------------------------------------------------

info1, info2, info3, info4 = st.columns(4)

with info1:

    st.metric(
        "Setup",
        str(selected["Setup"])
    )

with info2:

    st.metric(
        "Score",
        f"{selected['Score']:.0f}/100"
    )

with info3:

    st.metric(
        "RSI",
        f"{selected['RSI']:.1f}"
    )

with info4:

    st.metric(
        "RVOL",
        f"{selected['RVOL']:.2f}"
    )


# ------------------------------------------------------------
# TECHNICAL DETAILS
# ------------------------------------------------------------

st.markdown(
    "### Technical Structure"
)


tech_columns = [
    "BreakoutPct",
    "RS20",
    "RS60",
    "StockRS",
    "BaseRange",
    "Compression",
    "Extension",
    "Resistance",
    "ClosingStrength",
]


tech_data = {}

for column in tech_columns:

    if column in selected.index:

        tech_data[column] = [
            selected[column]
        ]


if tech_data:

    tech_df = pd.DataFrame(
        tech_data
    )

    st.dataframe(
        tech_df,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# TRADE PLAN
# ============================================================

st.markdown(
    "### 🎯 Trade Plan"
)


trade_data = pd.DataFrame(
    {
        "Level": [
            "Entry",
            "Stop Loss",
            "Target 1",
            "Target 2",
            "Target 3",
            "Target 4",
        ],

        "Price": [
            selected["Entry"],
            selected["SL"],
            selected["T1"],
            selected["T2"],
            selected["T3"],
            selected["T4"],
        ],

        "Meaning": [
            "Reference entry",
            "Risk control",
            "1R",
            "2R",
            "3R",
            "4R",
        ],
    }
)


st.dataframe(
    trade_data,
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "T1 = 1R | T2 = 2R | T3 = 3R | T4 = 4R"
)

st.caption(
    "R = Entry − Stop Loss"
)

st.caption(
    "Trading OS v12 is a screening and "
    "decision-support system, not a guarantee "
    "of future price movement."
)

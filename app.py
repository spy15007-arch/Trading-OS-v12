from pathlib import Path

import pandas as pd
import streamlit as st


REPORT_FILE = Path(
    "reports/swing_scan.csv"
)


st.set_page_config(
    page_title="Trading OS v12",
    page_icon="📊",
    layout="wide",
)


st.title(
    "📊 Trading OS v12"
)

st.subheader(
    "High-Quality Swing Setups"
)

st.caption(
    "PRE-BREAKOUT + FRESH BREAKOUT | "
    "Maximum 30 — not forced to 30"
)


if not REPORT_FILE.exists():

    st.error(
        "Latest scanner report not found."
    )

    st.stop()


df = pd.read_csv(
    REPORT_FILE
)


if df.empty:

    st.warning(
        "NO HIGH-QUALITY SETUPS "
        "PASSED TODAY'S FILTER."
    )

    st.info(
        "This is intentional. "
        "The scanner does not manufacture "
        "a TOP 30 list."
    )

    st.stop()


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


pre = df[
    df["Setup"]
    == "PRE-BREAKOUT"
]

fresh = df[
    df["Setup"]
    == "FRESH BREAKOUT"
]


# ============================================================
# SUMMARY
# ============================================================

a, b, c, d = st.columns(4)

with a:

    st.metric(
        "Qualified Stocks",
        len(df)
    )

with b:

    st.metric(
        "Pre-Breakout",
        len(pre)
    )

with c:

    st.metric(
        "Fresh Breakout",
        len(fresh)
    )

with d:

    st.metric(
        "Top Score",
        f"{df['Score'].max():.0f}/100"
    )


st.divider()


# ============================================================
# MASTER
# ============================================================

st.header(
    "🏆 Master Ranking"
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

master_columns = [
    c
    for c in master_columns
    if c in df.columns
]

st.dataframe(
    df[master_columns],
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# PRE-BREAKOUT
# ============================================================

st.divider()

st.header(
    "👀 PRE-BREAKOUT"
)

if pre.empty:

    st.info(
        "No qualifying pre-breakout setup."
    )

else:

    columns = [
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

    columns = [
        c
        for c in columns
        if c in pre.columns
    ]

    st.dataframe(
        pre[columns],
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# FRESH BREAKOUT
# ============================================================

st.divider()

st.header(
    "🚀 FRESH BREAKOUT"
)

if fresh.empty:

    st.info(
        "No qualifying fresh-breakout setup."
    )

else:

    columns = [
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

    columns = [
        c
        for c in columns
        if c in fresh.columns
    ]

    st.dataframe(
        fresh[columns],
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# DETAILS
# ============================================================

st.divider()

st.header(
    "🔎 Stock Details"
)

selected_symbol = st.selectbox(
    "Select stock",
    df["Symbol"].astype(str).tolist()
)

row = df[
    df["Symbol"].astype(str)
    == selected_symbol
].iloc[0]


x1, x2, x3, x4 = st.columns(4)

with x1:

    st.metric(
        "Setup",
        row["Setup"]
    )

with x2:

    st.metric(
        "Score",
        f"{row['Score']:.0f}/100"
    )

with x3:

    st.metric(
        "RSI",
        f"{row['RSI']:.1f}"
    )

with x4:

    st.metric(
        "RVOL",
        f"{row['RVOL']:.2f}"
    )


st.markdown(
    "### Technical Structure"
)

technical = pd.DataFrame(
    {
        "Metric": [
            "Breakout %",
            "RS20",
            "RS60",
            "Stock vs NIFTY",
            "Base Range",
            "Compression",
            "Extension",
            "Resistance",
        ],

        "Value": [
            row["BreakoutPct"],
            row["RS20"],
            row["RS60"],
            row["StockRS"],
            row["BaseRange"],
            row["Compression"],
            row["Extension"],
            row["Resistance"],
        ],
    }
)

st.dataframe(
    technical,
    use_container_width=True,
    hide_index=True,
)


st.markdown(
    "### 🎯 Trade Plan"
)

trade_plan = pd.DataFrame(
    {
        "Level": [
            "Entry",
            "Stop Loss",
            "T1",
            "T2",
            "T3",
            "T4",
        ],

        "Price": [
            row["Entry"],
            row["SL"],
            row["T1"],
            row["T2"],
            row["T3"],
            row["T4"],
        ],

        "Risk Multiple": [
            "Entry",
            "Risk Control",
            "1R",
            "2R",
            "3R",
            "4R",
        ],
    }
)

st.dataframe(
    trade_plan,
    use_container_width=True,
    hide_index=True,
)


st.divider()

st.caption(
    "T1 = 1R | T2 = 2R | "
    "T3 = 3R | T4 = 4R"
)

st.caption(
    "The scanner uses a maximum of 30 "
    "stocks but does not force 30 stocks."
)

st.caption(
    "A scanner score is a ranking measure, "
    "not a prediction or guarantee."
)

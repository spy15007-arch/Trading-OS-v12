"""
Trading OS v12 Professional
Report Builder
"""

import pandas as pd

from .utils import (
    banner,
    timestamp
)


# ==========================================================
# Market Summary
# ==========================================================

def market_summary(market):

    text = ""

    text += "## Market Summary\n\n"

    text += (
        f"- NIFTY : "
        f"**{market.get('NIFTY', 'NA')}**\n"
    )

    text += (
        f"- BANKNIFTY : "
        f"**{market.get('BANKNIFTY', 'NA')}**\n"
    )

    text += (
        f"- Market Mode : "
        f"**{market.get('MODE', 'UNKNOWN')}**\n"
    )

    text += "\n---\n\n"

    return text


# ==========================================================
# Build Report
# ==========================================================

def build_report(
    report_title,
    market,
    dataframe
):

    md = ""

    md += banner(
        report_title
    )

    md += (
        f"Generated : "
        f"**{timestamp()}**\n\n"
    )

    md += market_summary(
        market
    )

    if dataframe.empty:

        md += (
            "## No qualifying "
            "stocks found.\n"
        )

        return md

    md += (
        "## Top Institutional Picks\n\n"
    )

    for _, row in dataframe.iterrows():

        md += (
            f"### {row.get('Symbol', 'UNKNOWN')} "
            f"({row.get('Grade', 'N/A')})\n\n"
        )

        fields = [
            ("Score", "Institutional Score"),
            ("Trade", "Trade Type"),
            ("Entry", "Entry"),
            ("SL", "Stop Loss"),
            ("T1", "Target 1"),
            ("T2", "Target 2"),
            ("T3", "Target 3"),
            ("RSI", "RSI"),
            ("RVOL", "Relative Volume"),
            ("Lorentz", "Lorentz Score"),
            ("EMA20", "EMA20"),
            ("EMA50", "EMA50"),
            ("EMA200", "EMA200"),
            ("VWAP", "VWAP")
        ]

        for key, label in fields:

            value = row.get(
                key,
                "N/A"
            )

            if key in [
                "Entry",
                "SL",
                "T1",
                "T2",
                "T3"
            ]:

                md += (
                    f"- {label} : "
                    f"₹{value}\n"
                )

            else:

                md += (
                    f"- {label} : "
                    f"**{value}**\n"
                )

        md += "\n---\n\n"

    return md


# ==========================================================
# Results DataFrame
# ==========================================================

def results_dataframe(results):

    if not results:

        return pd.DataFrame()

    df = pd.DataFrame(
        results
    )

    sort_columns = [
        col
        for col in [
            "Score",
            "RVOL",
            "RSI"
        ]
        if col in df.columns
    ]

    if sort_columns:

        df = df.sort_values(
            by=sort_columns,
            ascending=False
        )

    return df.reset_index(
        drop=True
    )

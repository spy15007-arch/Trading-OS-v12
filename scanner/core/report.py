"""
Trading OS v12 Professional
Report Builder
"""

import pandas as pd

from core.utils import (
    banner,
    timestamp,
)


# ==========================================================
# Market Summary
# ==========================================================

def market_summary(market):

    text = ""

    text += "## Market Summary\n\n"

    text += f"- NIFTY : **{market['NIFTY']}**\n"

    text += f"- BANKNIFTY : **{market['BANKNIFTY']}**\n"

    text += f"- Market Mode : **{market['MODE']}**\n"

    text += "\n---\n\n"

    return text


# ==========================================================
# Build Scan Report
# ==========================================================

def build_report(
    report_title,
    market,
    dataframe
):

    md = ""

    md += banner(report_title)

    md += f"Generated : **{timestamp()}**\n\n"

    md += market_summary(market)

    if dataframe.empty:

        md += "## No qualifying stocks found.\n"

        return md

    md += "## Top Institutional Picks\n\n"

    for _, row in dataframe.iterrows():

        md += f"### {row['Symbol']} ({row['Grade']})\n\n"

        md += f"- Institutional Score : **{row['Score']}**\n"

        md += f"- Trade Type : {row['Trade']}\n"

        md += f"- Entry : ₹{row['Entry']}\n"

        md += f"- Stop Loss : ₹{row['SL']}\n"

        md += f"- Target 1 : ₹{row['T1']}\n"

        md += f"- Target 2 : ₹{row['T2']}\n"

        md += f"- Target 3 : ₹{row['T3']}\n"

        md += f"- RSI : {row['RSI']}\n"

        md += f"- Relative Volume : {row['RVOL']}\n"

        md += f"- Lorentz Score : {row['Lorentz']}\n"

        md += f"- EMA20 : {row['EMA20']}\n"

        md += f"- EMA50 : {row['EMA50']}\n"

        md += f"- EMA200 : {row['EMA200']}\n"

        md += f"- VWAP : {row['VWAP']}\n"

        md += "\n---\n\n"

    return md


# ==========================================================
# Convert Results to DataFrame
# ==========================================================

def results_dataframe(results):

    if not results:

        return pd.DataFrame()

    df = pd.DataFrame(results)

    df = df.sort_values(

        by=[

            "Score",

            "RVOL",

            "RSI"

        ],

        ascending=False

    )

    df.reset_index(

        drop=True,

        inplace=True

    )

    return df

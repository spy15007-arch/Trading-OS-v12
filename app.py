"""Streamlit dashboard for the latest Trading OS v12 scan."""
import json
from pathlib import Path

import pandas as pd
import streamlit as st


REPORT_DIR = Path("reports")
REPORT_FILE = REPORT_DIR / "swing_scan.csv"
SUMMARY_FILE = REPORT_DIR / "scan_summary.json"
MAX_RESULTS = 30

st.set_page_config(page_title="Trading OS v12", page_icon="📊", layout="wide")
st.title("📊 Trading OS v12")
st.subheader("High-Quality Swing Setups")
st.caption("PRE-BREAKOUT + FRESH BREAKOUT | Maximum 30 qualified stocks; no forced list")


def load_summary():
    try:
        return json.loads(SUMMARY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def normalize_columns(frame):
    """Accept current lowercase CSV headers and older mixed-case headers."""
    frame = frame.copy()
    frame.columns = [str(column).strip().lower() for column in frame.columns]
    frame = frame.loc[:, ~frame.columns.duplicated(keep="first")].copy()
    aliases = {
        "symbol": ("symbol", "ticker"),
        "setup": ("setup", "setup_type"),
        "score": ("score", "total_score"),
        "price": ("price", "close"),
        "breakout_pct": ("breakout_pct", "breakoutdistance_pct"),
        "rsi": ("rsi",),
        "rvol": ("rvol", "relative_volume"),
        "entry": ("entry", "entry_price"),
        "stop_loss": ("stop_loss", "sl", "stop"),
        "target_1": ("target_1", "t1"),
        "target_2": ("target_2", "t2"),
        "target_3": ("target_3", "t3"),
        "target_4": ("target_4", "t4"),
        "rs20": ("rs20",),
        "rs60": ("rs60",),
        "stockrs": ("stockrs", "stock_rs"),
        "base_range": ("base_range", "baserange"),
        "compression": ("compression",),
        "extension": ("extension",),
        "resistance": ("resistance",),
        "closing_strength": ("closing_strength", "closingstrength"),
        "risk_pct": ("risk_pct", "riskpct"),
        "rank": ("rank",),
    }
    for target, choices in aliases.items():
        if target not in frame.columns:
            source = next((name for name in choices if name in frame.columns), None)
            if source:
                frame[target] = frame[source]
    for col in ("symbol", "setup", "score"):
        if col not in frame.columns:
            frame[col] = "" if col != "score" else 0
    frame["symbol"] = frame["symbol"].fillna("").astype(str).str.strip().str.upper()
    frame["setup"] = (
        frame["setup"].fillna("").astype(str).str.strip().str.upper()
        .str.replace("_", "-", regex=False)
    )
    for col in frame.columns:
        if col not in ("symbol", "setup"):
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame = frame[frame["symbol"].ne("") & frame["setup"].isin(["PRE-BREAKOUT", "FRESH BREAKOUT"])]
    frame = frame.sort_values("score", ascending=False).drop_duplicates("symbol").head(MAX_RESULTS)
    return frame.reset_index(drop=True)


summary = load_summary()
if not REPORT_FILE.exists():
    st.error("No scan report is available yet. Run the Trading OS v12 scanner first.")
    st.stop()

if not summary.get("generated_at"):
    st.warning(
        "The scan summary is missing its scan timestamp. The committed CSV may be an old report, "
        "so the dashboard is hiding it rather than presenting it as current. Run the Trading OS v12 "
        "workflow once to publish a fresh CSV, Markdown report, and summary."
    )
    st.stop()

try:
    df = normalize_columns(pd.read_csv(REPORT_FILE))
except Exception as exc:
    st.error(f"Could not read the latest scan report: {exc}")
    st.stop()

market = str(summary.get("market_sentiment", "UNKNOWN")).replace("_", " ").upper()
status = str(summary.get("status", "UNKNOWN")).upper()
generated_at = summary.get("generated_at")
if generated_at:
    try:
        stamp = pd.to_datetime(generated_at, utc=True).tz_convert("Asia/Kolkata")
        st.caption(f"Market regime: {market} | Scan status: {status} | Generated: {stamp:%d %b %Y, %I:%M %p IST}")
    except (TypeError, ValueError):
        st.caption(f"Market regime: {market} | Scan status: {status}")
else:
    st.caption(f"Market regime: {market} | Scan status: {status} | Scan timestamp unavailable")

total = summary.get("stocks_in_universe", "—")
valid = summary.get("valid_data_count", "—")
raw = summary.get("raw_setup_count", "—")
a, b, c, d = st.columns(4)
a.metric("Stocks Scanned", total)
b.metric("Valid History", valid)
c.metric("Raw Setups", raw)
d.metric("Qualified Stocks", len(df))

pre = df[df["setup"].eq("PRE-BREAKOUT")]
fresh = df[df["setup"].eq("FRESH BREAKOUT")]

st.divider()
if df.empty:
    st.warning("NO HIGH-QUALITY SETUPS PASSED TODAY'S FILTER.")
    st.info("This is intentional. The scanner will not fill the shortlist with weak stocks.")
else:
    e, f, g = st.columns(3)
    e.metric("Pre-Breakout", len(pre))
    f.metric("Fresh Breakout", len(fresh))
    g.metric("Top Score", f"{df['score'].max():.0f}/100")

    st.header("🏆 Master Ranking")
    master_columns = [
        "rank", "symbol", "setup", "score", "price", "breakout_pct", "rsi", "rvol",
        "entry", "stop_loss", "target_1", "target_2", "target_3", "target_4",
    ]
    st.dataframe(df[[col for col in master_columns if col in df.columns]],
                 use_container_width=True, hide_index=True)

    st.divider()
    st.header("👀 PRE-BREAKOUT")
    if pre.empty:
        st.info("No candidates cleared for the PRE-BREAKOUT category.")
    else:
        cols = ["rank", "symbol", "score", "breakout_pct", "rsi", "rvol", "entry",
                "stop_loss", "target_1", "target_2", "target_3", "target_4"]
        st.dataframe(pre[[col for col in cols if col in pre.columns]],
                     use_container_width=True, hide_index=True)

    st.divider()
    st.header("🚀 FRESH BREAKOUT")
    if fresh.empty:
        st.info("No candidates cleared for the FRESH BREAKOUT category.")
    else:
        cols = ["rank", "symbol", "score", "breakout_pct", "rsi", "rvol", "entry",
                "stop_loss", "target_1", "target_2", "target_3", "target_4"]
        st.dataframe(fresh[[col for col in cols if col in fresh.columns]],
                     use_container_width=True, hide_index=True)

    st.divider()
    st.header("🔎 Stock Details")
    selected_symbol = st.selectbox("Select stock", df["symbol"].tolist())
    row = df[df["symbol"].eq(selected_symbol)].iloc[0]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Setup", row.get("setup", "—"))
    m2.metric("Score", f"{row.get('score', 0):.0f}/100")
    m3.metric("RSI", f"{row.get('rsi', float('nan')):.1f}" if pd.notna(row.get("rsi")) else "—")
    m4.metric("RVOL", f"{row.get('rvol', float('nan')):.2f}" if pd.notna(row.get("rvol")) else "—")

    technical_fields = [
        ("Breakout %", "breakout_pct"), ("RS20", "rs20"), ("RS60", "rs60"),
        ("Stock vs NIFTY", "stockrs"), ("Base Range", "base_range"),
        ("Compression", "compression"), ("Extension", "extension"),
        ("Resistance", "resistance"), ("Closing Strength", "closing_strength"),
    ]
    technical = [{"Metric": label, "Value": row[field]} for label, field in technical_fields
                 if field in row.index and pd.notna(row[field])]
    if technical:
        st.markdown("### Technical Structure")
        st.dataframe(pd.DataFrame(technical), use_container_width=True, hide_index=True)

    trade_fields = [
        ("Entry", "entry", "Entry"), ("Stop Loss", "stop_loss", "Risk Control"),
        ("T1", "target_1", "1R"), ("T2", "target_2", "2R"),
        ("T3", "target_3", "3R"), ("T4", "target_4", "4R"),
    ]
    trade_plan = [{"Level": label, "Price": row[field], "Risk Multiple": multiple}
                  for label, field, multiple in trade_fields
                  if field in row.index and pd.notna(row[field])]
    if trade_plan:
        st.markdown("### 🎯 Trade Plan")
        st.dataframe(pd.DataFrame(trade_plan), use_container_width=True, hide_index=True)
        st.caption("Targets: T1=1R | T2=2R | T3=3R | T4=4R. R = Entry − Stop Loss.")

st.divider()
st.caption("The scanner has a maximum shortlist of 30 stocks but never forces 30.")
st.caption("A scanner score is a ranking measure, not a prediction or guarantee.")

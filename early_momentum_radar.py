"""Separate Early Momentum Radar for pre-breakout and first-candle candidates.

Uses yfinance daily OHLCV snapshots. It is not a guaranteed real-time broker feed;
intraday current-day values may be delayed or provisional.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

import numpy as np
import pandas as pd

from scanner.core.downloader import download_all, get_nifty500_symbols
from scanner.core.indicators import atr, ema, rsi
from telegram_push import send_telegram_message, split_telegram_message

REPORT_DIR = Path("reports")
CSV_FILE = REPORT_DIR / "early_momentum_radar.csv"
DIAGNOSTICS_FILE = REPORT_DIR / "early_momentum_diagnostics.csv"
SUMMARY_FILE = REPORT_DIR / "early_momentum_summary.json"
RADAR_DEDUPE_STATE_FILE = REPORT_DIR / "early_momentum_telegram_dedupe_state.json"
MARKDOWN_FILE = REPORT_DIR / "early_momentum_radar.md"
MAX_RESULTS = 30
MIN_WATCH_SCORE = 60
MIN_BREAKOUT_SCORE = 65
MIN_PREBREAKOUT_DISTANCE = 2.5
MAX_EARLY_WATCH_DISTANCE = 6.0
MAX_FIRST_CANDLE_BREAKOUT = 2.5
MAX_EXTENSION = 8.0
MIN_HISTORY = 220
PERFORMANCE_FILE = REPORT_DIR / "early_momentum_performance.csv"


def _radar_signature(message):
    """Ignore only radar mode and snapshot timestamp when comparing same-day reports."""
    comparable = re.sub(
        r"(?m)^Scan: .*?$",
        "Scan: <mode and timestamp omitted for duplicate check>",
        message,
    )
    return hashlib.sha256(comparable.encode("utf-8")).hexdigest()


def _radar_report_already_sent(message, state_path=RADAR_DEDUPE_STATE_FILE):
    try:
        state = json.loads(Path(state_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()
    return state.get("date_ist") == today and state.get("signature") == _radar_signature(message)


def _save_radar_report_signature(message, state_path=RADAR_DEDUPE_STATE_FILE):
    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "date_ist": datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat(),
        "signature": _radar_signature(message),
    }
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _num(value, default=0.0):
    try:
        value = float(value)
        return value if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def _clean_data(frame):
    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
        return None
    df = frame.copy()
    if isinstance(df.columns, pd.MultiIndex):
        flat = []
        for col in df.columns:
            parts = col if isinstance(col, tuple) else (col,)
            flat.append(next((str(p) for p in parts if str(p).lower() in {"open", "high", "low", "close", "volume"}), str(parts[0])))
        df.columns = flat
    rename = {c: {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}.get(str(c).strip().lower(), c) for c in df.columns}
    df = df.rename(columns=rename)
    df = df.loc[:, ~df.columns.duplicated(keep="first")]
    required = ["Open", "High", "Low", "Close", "Volume"]
    if not all(c in df.columns for c in required):
        return None
    for c in required:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=required).sort_index()
    df = df[(df["Close"] > 0) & (df["High"] > 0) & (df["Low"] > 0)]
    return df if len(df) >= MIN_HISTORY else None


def evaluate_stock(symbol, frame, benchmark=None):
    """Return (candidate, None) or (None, diagnostic_reason)."""
    df = _clean_data(frame)
    if df is None:
        return None, "INSUFFICIENT_OR_INVALID_HISTORY"
    close_s, high_s, low_s, volume_s = df["Close"], df["High"], df["Low"], df["Volume"]
    price = _num(close_s.iloc[-1])
    if price <= 0:
        return None, "INVALID_PRICE"

    e20_s, e50_s, e200_s = ema(close_s, 20), ema(close_s, 50), ema(close_s, 200)
    e20, e50, e200 = _num(e20_s.iloc[-1]), _num(e50_s.iloc[-1]), _num(e200_s.iloc[-1])
    rsi_value = _num(rsi(close_s, 14).iloc[-1], 50.0)
    extension = ((price / e20) - 1) * 100 if e20 > 0 else 999.0

    # Resistance uses the prior 20 sessions, excluding the latest candle.
    prior = df.iloc[-21:-1]
    if len(prior) < 20:
        return None, "INSUFFICIENT_RESISTANCE_HISTORY"
    resistance = _num(prior["High"].max())
    if resistance <= 0:
        return None, "INVALID_RESISTANCE"
    breakout_pct = ((price / resistance) - 1) * 100
    distance_below = ((resistance / price) - 1) * 100
    base_low = _num(prior["Low"].min())
    base_range = ((resistance - base_low) / base_low) * 100 if base_low > 0 else 999.0

    candle_high, candle_low, candle_open = _num(high_s.iloc[-1]), _num(low_s.iloc[-1]), _num(df["Open"].iloc[-1])
    candle_range = max(candle_high - candle_low, 0.0)
    close_strength = (price - candle_low) / candle_range if candle_range > 0 else 0.0
    body_ratio = abs(price - candle_open) / candle_range if candle_range > 0 else 0.0
    upper_wick_ratio = (candle_high - max(price, candle_open)) / candle_range if candle_range > 0 else 1.0
    avg_volume = _num(volume_s.iloc[-21:-1].mean())
    rvol = _num(volume_s.iloc[-1]) / avg_volume if avg_volume > 0 else 0.0

    ranges = ((high_s - low_s) / close_s.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
    range_contraction = 1.0
    if len(ranges) >= 21:
        older, recent = _num(ranges.iloc[-21:-11].mean()), _num(ranges.iloc[-11:-1].mean())
        if older > 0:
            range_contraction = recent / older

    rs20 = (price / _num(close_s.iloc[-21]) - 1) * 100 if _num(close_s.iloc[-21]) > 0 else 0.0
    rs60 = (price / _num(close_s.iloc[-61]) - 1) * 100 if _num(close_s.iloc[-61]) > 0 else 0.0
    stock_rs = 0.0
    if benchmark is not None and isinstance(benchmark, pd.DataFrame) and "Close" in benchmark.columns and len(benchmark) >= 61:
        bclose = pd.to_numeric(benchmark["Close"], errors="coerce").dropna()
        if len(bclose) >= 61 and _num(bclose.iloc[-61]) > 0:
            stock_rs = ((price / _num(close_s.iloc[-61]) - 1) - (_num(bclose.iloc[-1]) / _num(bclose.iloc[-61]) - 1)) * 100

    aligned = e20 > e50 and price > e50
    soft_trend = price > e50 and e20 >= e50 * 0.97

    # Hard anti-chase and structure guards apply to both radar categories.
    if extension > MAX_EXTENSION:
        return None, "TOO_EXTENDED_FROM_EMA20"
    if base_range > 25:
        return None, "BASE_TOO_WIDE"
    if rsi_value < 48 or rsi_value > 76:
        return None, "RSI_OUTSIDE_EARLY_MOMENTUM_RANGE"

    # Detect a first post-breakout retest: a recent close above its own prior
    # 20-session high, followed by a pullback that tests the old level and holds.
    atr_value = _num(atr(df, 14).iloc[-1])
    retest_level = 0.0
    retest_found = False
    if atr_value > 0 and len(df) >= 40:
        prior_20_high = high_s.shift(1).rolling(20, min_periods=20).max()
        for offset in range(-10, -1):
            if offset - 20 < -len(df):
                continue
            breakout_day = offset
            if _num(close_s.iloc[breakout_day]) > _num(prior_20_high.iloc[breakout_day]) and _num(volume_s.iloc[breakout_day]) >= _num(volume_s.iloc[max(0, breakout_day-20):breakout_day].mean()) * 1.15:
                level = _num(prior_20_high.iloc[breakout_day])
                if level > 0 and low_s.iloc[-1] <= level + 0.35 * atr_value and price >= level and price <= level + 1.25 * atr_value:
                    retest_level, retest_found = level, True
                    break

    if retest_found:
        if not soft_trend or rvol > 1.25 or close_strength < 0.55:
            return None, "RETEST_NOT_HOLDING_OR_PULLBACK_VOLUME_NOT_CONTRACTING"
        setup = "BREAKOUT RETEST"
        resistance = retest_level
        breakout_pct = ((price / resistance) - 1) * 100
        distance_below = 0.0
    elif 0 <= breakout_pct <= MAX_FIRST_CANDLE_BREAKOUT:
        candle_ok = close_strength >= 0.60 and body_ratio >= 0.30 and upper_wick_ratio <= 0.45
        if not soft_trend:
            return None, "TREND_NOT_READY"
        if not candle_ok:
            return None, "WEAK_BREAKOUT_CANDLE"
        if rvol < 1.0:
            return None, "VOLUME_TOO_LOW"
        if rsi_value < 52:
            return None, "MOMENTUM_NOT_READY"
        setup = "FIRST-CANDLE BREAKOUT"
    elif -MIN_PREBREAKOUT_DISTANCE <= breakout_pct < 0:
        if not soft_trend or rvol < 0.65 or base_range > 20 or stock_rs < 0:
            return None, "PREBREAKOUT_QUALITY_FILTER"
        setup = "PRE-BREAKOUT"
    elif -MAX_EARLY_WATCH_DISTANCE <= breakout_pct < -MIN_PREBREAKOUT_DISTANCE:
        if not soft_trend or rvol < 0.55 or base_range > 22:
            return None, "EARLY_WATCH_QUALITY_FILTER"
        setup = "EARLY WATCH"
    else:
        return None, "ALREADY_EXTENDED_ABOVE_RESISTANCE" if breakout_pct > MAX_FIRST_CANDLE_BREAKOUT else "NOT_NEAR_RESISTANCE"

    score = 0.0
    score += 12 if aligned else 7
    score += 8 if price > e200 else 0
    score += 5 if 0 <= extension <= 4 else (3 if extension <= 6 else 1)
    score += 5 if base_range <= 12 else (3 if base_range <= 18 else 1)
    score += 8 if rs20 >= 4 else (5 if rs20 >= 0 else 1)
    score += 8 if rs60 >= 8 else (5 if rs60 >= 0 else 1)
    score += 5 if stock_rs >= 4 else (3 if stock_rs >= 0 else 1)
    score += 4 if 54 <= rsi_value <= 68 else (2 if 50 <= rsi_value <= 72 else 0)
    if setup == "FIRST-CANDLE BREAKOUT":
        score += 12 if breakout_pct <= 1.0 else 9
        score += 8 if rvol >= 1.5 else (6 if rvol >= 1.0 else 3)
        score += 8 if close_strength >= 0.75 else (5 if close_strength >= 0.60 else 2)
        score += 7 if body_ratio >= 0.50 else (4 if body_ratio >= 0.30 else 2)
    elif setup == "BREAKOUT RETEST":
        score += 12 if close_strength >= 0.75 else 8
        score += 8 if rvol <= 0.9 else 3
        score += 7 if stock_rs >= 4 else (4 if stock_rs >= 0 else 0)
    else:
        score += 12 if distance_below <= 1.5 else (9 if distance_below <= 3.5 else 6)
        score += 8 if 0.65 <= rvol <= 1.4 else (5 if rvol < 0.65 else 3)
        score += 8 if range_contraction <= 0.85 else (5 if range_contraction <= 1.0 else 2)
        score += 7 if 52 <= rsi_value <= 66 else 4
    score = round(min(score, 100.0), 1)
    threshold = MIN_BREAKOUT_SCORE if setup in {"FIRST-CANDLE BREAKOUT", "BREAKOUT RETEST"} else MIN_WATCH_SCORE
    if score < threshold:
        return None, f"SCORE_BELOW_{threshold}"

    atr_value = _num(atr(df, 14).iloc[-1])
    recent_low = _num(low_s.tail(10).min())
    stop = max(recent_low, price - 1.5 * atr_value) if atr_value > 0 else recent_low
    if stop >= price or stop <= 0:
        stop = price * 0.97
    risk = price - stop
    risk_pct = risk / price * 100
    if risk_pct > 8:
        return None, "STOP_RISK_OVER_8_PERCENT"

    return {
        "symbol": str(symbol).replace(".NS", "").upper(), "setup": setup, "score": score,
        "price": round(price, 2), "resistance": round(resistance, 2),
        "breakout_pct": round(breakout_pct, 2), "distance_below_resistance_pct": round(distance_below, 2),
        "rsi": round(rsi_value, 1), "rvol": round(rvol, 2), "rs20": round(rs20, 2),
        "rs60": round(rs60, 2), "stock_rs": round(stock_rs, 2), "base_range_pct": round(base_range, 2),
        "range_contraction": round(range_contraction, 2), "extension_pct": round(extension, 2),
        "closing_strength": round(close_strength, 2), "body_ratio": round(body_ratio, 2),
        "upper_wick_ratio": round(upper_wick_ratio, 2), "entry_reference": round(price, 2),
        "stop_reference": round(stop, 2), "risk_pct": round(risk_pct, 2),
        "target_1_reference": round(price + risk, 2), "target_2_reference": round(price + 2*risk, 2),
        "target_3_reference": round(price + 3*risk, 2), "target_4_reference": round(price + 4*risk, 2),
        "room_to_52w_high_pct": round(max(0.0, (_num(high_s.tail(252).max()) / price - 1) * 100), 2),
        "has_25pct_room_to_52w_high": bool(_num(high_s.tail(252).max()) >= price * 1.25),
        "data_date": str(df.index[-1])[:10],
    }, None


def build_message(results, summary):
    lines = [
        "🛰️ EARLY MOMENTUM RADAR — TRADING OS v12",
        f"Scan: {summary.get('scan_mode', 'MANUAL')} | Snapshot: {summary.get('generated_at_ist', 'unknown IST')}",
        f"Universe: {summary.get('stocks_in_universe', 0)} | Valid histories: {summary.get('valid_data_count', 0)}",
        f"Candidates: {len(results)} | BREAKOUT: {sum(r['setup']=='FIRST-CANDLE BREAKOUT' for r in results)} | PRE: {sum(r['setup']=='PRE-BREAKOUT' for r in results)} | WATCH: {sum(r['setup']=='EARLY WATCH' for r in results)} | RETEST: {sum(r['setup']=='BREAKOUT RETEST' for r in results)}",
        "Daily-bar snapshot may be delayed/provisional; verify live price and volume.",
        "Reference levels, not automatic buy instructions. No-trade is valid.",
        "━━━━━━━━━━━━━━━━━━━━",
    ]
    if not results:
        lines.append("No early-momentum candidates met the radar rules today.")
    category_order = ["FIRST-CANDLE BREAKOUT", "PRE-BREAKOUT", "EARLY WATCH", "BREAKOUT RETEST"]
    category_titles = {
        "FIRST-CANDLE BREAKOUT": "⚡ FIRST-CANDLE BREAKOUT",
        "PRE-BREAKOUT": "🚀 PRE-BREAKOUT",
        "EARLY WATCH": "👀 EARLY WATCH",
        "BREAKOUT RETEST": "🔄 BREAKOUT RETEST",
    }
    for category in category_order:
        group = [r for r in results if r["setup"] == category]
        if not group:
            continue
        lines += ["", f"<b>{category_titles[category]} ({len(group)})</b>", "━━━━━━━━━━━━━━━━━━━━"]
        for row in group:
            room = row.get("room_to_52w_high_pct", 0)
            room_tag = "25% ROOM* " if row.get("has_25pct_room_to_52w_high") else ""
            lines += [
                f"<b>{row['symbol']}</b> | Score {row['score']:.1f} | {room_tag}52W-high room {room:.1f}%",
                f"Price ₹{row['price']:.2f} | Level ₹{row['resistance']:.2f} | Distance {row['breakout_pct']:+.2f}%",
                f"RSI {row['rsi']:.1f} | RVOL {row['rvol']:.2f} | RS vs Nifty {row['stock_rs']:+.2f}%",
                f"Extension {row['extension_pct']:.2f}% | Base {row['base_range_pct']:.1f}% | Risk ref {row['risk_pct']:.2f}%",
                f"Entry ref ₹{row['entry_reference']:.2f} | SL ref ₹{row['stop_reference']:.2f}",
                f"T1 ₹{row['target_1_reference']:.2f} | T2 ₹{row['target_2_reference']:.2f} | T3 ₹{row['target_3_reference']:.2f} | T4 ₹{row['target_4_reference']:.2f}",
                "━━━━━━━━━━━━━━━━━━━━",
            ]
    lines += ["*25% room is only distance to the prior 52-week high, not a forecast or probability.", "Trade management concept: at +25%, consider partial profit booking; trail the balance below the higher of a structure-based swing low or a ratcheting 2.5×ATR stop. Never lower a protective stop."]
    return "\n".join(lines)


def update_performance_tracker(candidates, frames, scan_date):
    """Track each signal cohort from its first appearance; daily bars update MFE/MAE."""
    columns = [
        "symbol", "signal_date", "setup", "entry_price", "latest_close",
        "max_favourable_pct", "max_adverse_pct", "hit_5pct", "hit_10pct",
        "hit_15pct", "hit_20pct", "hit_25pct", "last_updated",
    ]
    if PERFORMANCE_FILE.exists():
        try:
            tracker = pd.read_csv(PERFORMANCE_FILE)
        except Exception:
            tracker = pd.DataFrame(columns=columns)
    else:
        tracker = pd.DataFrame(columns=columns)
    for row in candidates:
        key = (row["symbol"], scan_date)
        if tracker.empty or not ((tracker["symbol"] == key[0]) & (tracker["signal_date"].astype(str) == key[1])).any():
            tracker.loc[len(tracker)] = {
                "symbol": key[0], "signal_date": key[1], "setup": row["setup"],
                "entry_price": row["price"], "latest_close": row["price"],
                "max_favourable_pct": 0.0, "max_adverse_pct": 0.0,
                "hit_5pct": "", "hit_10pct": "", "hit_15pct": "",
                "hit_20pct": "", "hit_25pct": "", "last_updated": scan_date,
            }
    for idx, trade in tracker.iterrows():
        frame = frames.get(f"{trade['symbol']}.NS")
        if frame is None:
            frame = frames.get(trade["symbol"])
        clean = _clean_data(frame)
        if clean is None:
            continue
        entry_date = str(trade["signal_date"])[:10]
        bars = clean.loc[[str(value)[:10] >= entry_date for value in clean.index]]
        if bars.empty:
            continue
        entry = _num(trade["entry_price"])
        if entry <= 0:
            continue
        mfe = max(0.0, (_num(bars["High"].max()) / entry - 1) * 100)
        mae = min(0.0, (_num(bars["Low"].min()) / entry - 1) * 100)
        tracker.at[idx, "latest_close"] = round(_num(bars["Close"].iloc[-1]), 2)
        tracker.at[idx, "max_favourable_pct"] = round(max(_num(trade["max_favourable_pct"]), mfe), 2)
        tracker.at[idx, "max_adverse_pct"] = round(min(_num(trade["max_adverse_pct"]), mae), 2)
        for milestone in (5, 10, 15, 20, 25):
            col = f"hit_{milestone}pct"
            if pd.isna(trade.get(col)) or str(trade.get(col, "")).strip() in {"", "nan"}:
                hit = bars.index[(bars["High"] / entry - 1) * 100 >= milestone]
                if len(hit):
                    tracker.at[idx, col] = str(hit[0])[:10]
        tracker.at[idx, "last_updated"] = scan_date
    if not tracker.empty:
        tracker = tracker.sort_values(["signal_date", "symbol"], ascending=[False, True])
    tracker.to_csv(PERFORMANCE_FILE, index=False)


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    mode = os.getenv("RADAR_MODE", "MANUAL").strip().upper()
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    print(f"EARLY MOMENTUM RADAR | mode={mode} | runner time={now.isoformat()}")
    symbols = get_nifty500_symbols()
    frames = download_all(symbols, period="1y", interval="1d", chunk=10)
    benchmark = download_all(["^NSEI"], period="2y", interval="1d", chunk=1).get("^NSEI")
    candidates, diagnostics, valid_count = [], [], 0
    for symbol in symbols:
        frame = frames.get(symbol)
        if frame is None:
            diagnostics.append({"symbol": symbol.replace(".NS", ""), "status": "NO_DATA", "reason": "DOWNLOAD_MISSING"})
            continue
        if _clean_data(frame) is None:
            diagnostics.append({"symbol": symbol.replace(".NS", ""), "status": "INVALID", "reason": "INSUFFICIENT_OR_INVALID_HISTORY"})
            continue
        valid_count += 1
        candidate, reason = evaluate_stock(symbol, frame, benchmark)
        if candidate:
            candidates.append(candidate)
            diagnostics.append({"symbol": candidate["symbol"], "status": "CANDIDATE", "reason": candidate["setup"], "score": candidate["score"]})
        else:
            diagnostics.append({"symbol": symbol.replace(".NS", ""), "status": "FILTERED", "reason": reason})
    category_priority = {"FIRST-CANDLE BREAKOUT": 0, "PRE-BREAKOUT": 1, "EARLY WATCH": 2, "BREAKOUT RETEST": 3}
    candidates.sort(key=lambda row: (category_priority.get(row["setup"], 9), -row["score"], -row["stock_rs"], row["risk_pct"]))
    candidates = candidates[:MAX_RESULTS]
    scan_date = now.strftime("%Y-%m-%d")
    update_performance_tracker(candidates, frames, scan_date)
    pd.DataFrame(candidates).to_csv(CSV_FILE, index=False)
    pd.DataFrame(diagnostics).to_csv(DIAGNOSTICS_FILE, index=False)
    summary = {
        "scan_mode": mode, "generated_at_ist": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "stocks_in_universe": len(symbols), "valid_data_count": valid_count,
        "candidate_count": len(candidates),
        "early_watch_count": sum(r["setup"] == "EARLY WATCH" for r in candidates),
        "pre_breakout_count": sum(r["setup"] == "PRE-BREAKOUT" for r in candidates),
        "first_candle_count": sum(r["setup"] == "FIRST-CANDLE BREAKOUT" for r in candidates),
        "breakout_retest_count": sum(r["setup"] == "BREAKOUT RETEST" for r in candidates),
        "diagnostic_count": len(diagnostics),
        "data_source": "yfinance daily OHLCV; not a guaranteed real-time broker feed",
    }
    SUMMARY_FILE.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    report = [
        "# Early Momentum Radar — Trading OS v12", "",
        f"- **Mode:** {mode}", f"- **Generated:** {summary['generated_at_ist']}",
        f"- **Universe / valid histories:** {len(symbols)} / {valid_count}",
        f"- **Candidates:** {len(candidates)} (FIRST-CANDLE {summary['first_candle_count']}; PRE-BREAKOUT {summary['pre_breakout_count']}; EARLY WATCH {summary['early_watch_count']}; RETEST {summary['breakout_retest_count']})",
        "- **Data note:** yfinance daily OHLCV is not a guaranteed real-time broker feed; intraday snapshots may be delayed or provisional.",
        "- **Anti-chase:** candidates above +2.5% from 20-day resistance or >8% above EMA20 are excluded.", "",
    ]
    if not candidates:
        report.append("No candidates qualified. No-trade is valid.")
    for i, row in enumerate(candidates, 1):
        report += [
            f"## {i}. {row['symbol']} — {row['setup']} (score {row['score']})",
            f"- Price ₹{row['price']:.2f}; resistance ₹{row['resistance']:.2f}; breakout distance {row['breakout_pct']:+.2f}%",
            f"- RSI {row['rsi']:.1f}; RVOL {row['rvol']:.2f}; RS vs Nifty {row['stock_rs']:+.2f}%; extension {row['extension_pct']:.2f}%; 52W-high room {row['room_to_52w_high_pct']:.1f}%",
            f"- Reference entry ₹{row['entry_reference']:.2f}; reference stop ₹{row['stop_reference']:.2f}; risk {row['risk_pct']:.2f}%",
            f"- 25% potential screen: {'YES' if row['has_25pct_room_to_52w_high'] else 'NOT CONFIRMED'} (historical 52-week high distance; not a forecast)", "",
        ]
    MARKDOWN_FILE.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Radar complete: {len(symbols)} scanned; {valid_count} valid; {len(candidates)} candidates.")
    full_message = build_message(candidates, summary)
    if _radar_report_already_sent(full_message):
        print("Radar: identical report already sent today; skipping duplicate Telegram notification.")
        return
    message_chunks = split_telegram_message(full_message, max_length=3800)
    sent_all = True
    for i, chunk in enumerate(message_chunks, 1):
        if len(message_chunks) > 1:
            chunk = f"🛰️ EARLY MOMENTUM RADAR ({i}/{len(message_chunks)})\n" + chunk
        if not send_telegram_message(chunk):
            sent_all = False
            break
    if sent_all:
        _save_radar_report_signature(full_message)
        print(f"Early Momentum Radar Telegram report sent successfully ({len(message_chunks)} message(s)).")
    else:
        print("Early Momentum Radar Telegram delivery failed.")
        if os.getenv("GITHUB_ACTIONS", "").lower() == "true":
            raise RuntimeError("Early Momentum Radar Telegram delivery failed.")


if __name__ == "__main__":
    main()

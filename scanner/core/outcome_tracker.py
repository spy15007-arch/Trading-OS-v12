"""Persistent, conservative outcome tracking for qualified scanner signals."""
from pathlib import Path

import pandas as pd

TRACKER_COLUMNS = [
    "signal_date", "last_update_date", "symbol", "setup", "score",
    "entry", "stop_loss", "risk", "target_1", "target_2", "target_3", "target_4",
    "last_close", "max_high_since_signal", "min_low_since_signal",
    "sessions_tracked", "t1_hit_date", "t2_hit_date", "t3_hit_date", "t4_hit_date",
    "stop_hit_date", "first_event", "first_event_date", "status",
]
TERMINAL_STATUSES = {"STOP_LOSS", "STOP_AFTER_TARGET", "TARGET_4", "TIMEOUT_20_SESSIONS"}
MAX_TRACKING_SESSIONS = 20


def _date(value):
    try:
        stamp = pd.Timestamp(value)
        if pd.isna(stamp):
            return ""
        return stamp.date().isoformat()
    except (TypeError, ValueError):
        return ""


def _number(value, default=0.0):
    try:
        result = float(value)
        return result if pd.notna(result) else default
    except (TypeError, ValueError):
        return default


def _truthy_date(value):
    return isinstance(value, str) and bool(value.strip())


def _blank_record():
    return {column: "" for column in TRACKER_COLUMNS}


def _ensure_schema(frame):
    for column in TRACKER_COLUMNS:
        if column not in frame.columns:
            frame[column] = ""
    return frame[TRACKER_COLUMNS].copy()


def _update_record(record, history):
    signal_date = _date(record.get("signal_date"))
    if not signal_date or history is None or history.empty:
        return record

    frame = history.copy()
    frame = frame.sort_index()
    last_update = _date(record.get("last_update_date")) or signal_date
    if str(record.get("status", "ACTIVE")).upper() in TERMINAL_STATUSES:
        return record
    frame = frame.loc[[_date(idx) > last_update for idx in frame.index]]
    if frame.empty:
        return record

    entry = _number(record.get("entry"))
    stop = _number(record.get("stop_loss"))
    targets = [_number(record.get(f"target_{n}")) for n in range(1, 5)]
    if entry <= 0 or stop <= 0 or any(target <= entry for target in targets):
        return record

    max_high = _number(record.get("max_high_since_signal"), entry)
    min_low = _number(record.get("min_low_since_signal"), entry)
    sessions = int(_number(record.get("sessions_tracked"), 0))
    terminal = str(record.get("status", "ACTIVE")).upper() in TERMINAL_STATUSES

    for idx, bar in frame.iterrows():
        if terminal:
            break
        bar_date = _date(idx)
        high = _number(bar.get("High"))
        low = _number(bar.get("Low"))
        close = _number(bar.get("Close"))
        if not bar_date or high <= 0 or low <= 0 or close <= 0:
            continue

        sessions += 1
        max_high = max(max_high, high)
        min_low = min(min_low, low)
        record["last_update_date"] = bar_date
        record["last_close"] = round(close, 2)

        stop_touched = low <= stop
        target_touched = [high >= target for target in targets]
        already_hit_target = any(_truthy_date(record.get(f"t{n}_hit_date")) for n in range(1, 5))

        if stop_touched and any(target_touched) and not already_hit_target:
            record["stop_hit_date"] = record.get("stop_hit_date") or bar_date
            record["first_event"] = record.get("first_event") or "STOP_FIRST_AMBIGUOUS_BAR"
            record["first_event_date"] = record.get("first_event_date") or bar_date
            record["status"] = "STOP_LOSS"
            terminal = True
            continue

        if stop_touched:
            record["stop_hit_date"] = record.get("stop_hit_date") or bar_date
            if not _truthy_date(record.get("first_event")):
                record["first_event"] = "STOP_LOSS"
                record["first_event_date"] = bar_date
            record["status"] = "STOP_AFTER_TARGET" if already_hit_target else "STOP_LOSS"
            terminal = True
            continue

        for n, touched in enumerate(target_touched, start=1):
            field = f"t{n}_hit_date"
            if touched and not _truthy_date(record.get(field)):
                record[field] = bar_date
                if not _truthy_date(record.get("first_event")):
                    record["first_event"] = f"T{n}"
                    record["first_event_date"] = bar_date

        if target_touched[3]:
            record["status"] = "TARGET_4"
            terminal = True
        elif sessions >= MAX_TRACKING_SESSIONS:
            record["status"] = "TIMEOUT_20_SESSIONS"
            terminal = True
        else:
            record["status"] = "ACTIVE"

    record["max_high_since_signal"] = round(max_high, 2)
    record["min_low_since_signal"] = round(min_low, 2)
    record["sessions_tracked"] = sessions
    if not str(record.get("status", "")).strip():
        record["status"] = "ACTIVE"
    return record


def update_trade_outcomes(results, histories, output_path="reports/trade_outcomes.csv"):
    """Update existing signals and append newly qualified signals, without duplicates.

    histories maps stock symbols to normalized OHLCV DataFrames with Open/High/Low/Close/Volume.
    Only completed daily bars after the signal date are counted as follow-up sessions.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        try:
            old = pd.read_csv(path, dtype=str).fillna("")
        except (OSError, pd.errors.ParserError, UnicodeDecodeError):
            old = pd.DataFrame(columns=TRACKER_COLUMNS)
    else:
        old = pd.DataFrame(columns=TRACKER_COLUMNS)
    old = _ensure_schema(old)

    # Rebuild an indexed working set; signal date + symbol + setup is the unique key.
    records = {}
    for item in old.to_dict("records"):
        key = (str(item.get("signal_date", "")), str(item.get("symbol", "")).upper(),
               str(item.get("setup", "")).upper())
        if all(key):
            records[key] = item

    active_keys = {
        (str(item.get("symbol", "")).upper(), str(item.get("setup", "")).upper())
        for item in records.values()
        if str(item.get("status", "ACTIVE")).upper() not in TERMINAL_STATUSES
    }
    for result in results:
        symbol = str(result.get("symbol", "")).strip().upper().replace(".NS", "")
        setup = str(result.get("setup", "")).strip().upper().replace("_", "-")
        history = histories.get(symbol)
        if not symbol or not setup or history is None or history.empty:
            continue
        signal_date = _date(history.index[-1])
        if not signal_date:
            continue
        key = (signal_date, symbol, setup)
        if key not in records and (symbol, setup) not in active_keys:
            record = _blank_record()
            record.update({
                "signal_date": signal_date,
                "last_update_date": signal_date,
                "symbol": symbol,
                "setup": setup,
                "score": _number(result.get("score")),
                "entry": _number(result.get("entry")),
                "stop_loss": _number(result.get("stop_loss")),
                "risk": _number(result.get("entry")) - _number(result.get("stop_loss")),
                "target_1": _number(result.get("target_1")),
                "target_2": _number(result.get("target_2")),
                "target_3": _number(result.get("target_3")),
                "target_4": _number(result.get("target_4")),
                "last_close": _number(history["Close"].iloc[-1]),
                "max_high_since_signal": _number(history["High"].iloc[-1]),
                "min_low_since_signal": _number(history["Low"].iloc[-1]),
                "sessions_tracked": 0,
                "first_event": "",
                "first_event_date": "",
                "status": "ACTIVE",
            })
            records[key] = record
            active_keys.add((symbol, setup))

    # Update all records from bars after their signal date, including if a run was missed.
    for key, record in list(records.items()):
        symbol = str(record.get("symbol", "")).upper()
        history = histories.get(symbol)
        if history is not None:
            records[key] = _update_record(record, history)

    output = pd.DataFrame(records.values(), columns=TRACKER_COLUMNS)
    if not output.empty:
        output["score"] = pd.to_numeric(output["score"], errors="coerce").fillna(0)
        output = output.sort_values(["signal_date", "score"], ascending=[False, False])
    output.to_csv(path, index=False)
    print(f"Trade outcome tracker saved: {path} ({len(output)} signals)")
    return output

import numpy as np
import pandas as pd

from .indicators import ema, rsi, atr, relative_volume, closing_strength


MIN_BARS = 220

RESISTANCE_LOOKBACK = 20
BASE_LOOKBACK = 20

MAX_PRE_GAP = 5.0
MAX_FRESH_GAP = 6.0
MAX_EXTENSION = 12.0

MIN_PRE_RSI = 52.0
MIN_FRESH_RSI = 55.0

MIN_PRE_RVOL = 0.70
MIN_FRESH_RVOL = 1.30


def _prepare_dataframe(df):
    """
    Clean and standardise OHLCV dataframe.
    """

    if df is None or df.empty:
        return None

    data = df.copy()

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = [
            col[0] if isinstance(col, tuple) else col
            for col in data.columns
        ]

    rename_map = {}

    for col in data.columns:
        lower = str(col).lower()

        if lower == "open":
            rename_map[col] = "Open"
        elif lower == "high":
            rename_map[col] = "High"
        elif lower == "low":
            rename_map[col] = "Low"
        elif lower == "close":
            rename_map[col] = "Close"
        elif lower == "volume":
            rename_map[col] = "Volume"

    data = data.rename(columns=rename_map)

    required = ["Open", "High", "Low", "Close", "Volume"]

    if not all(col in data.columns for col in required):
        return None

    data = data[required].copy()

    for col in required:
        data[col] = pd.to_numeric(data[col], errors="coerce")

    data = data.dropna()

    if len(data) < MIN_BARS:
        return None

    return data


def _relative_strength(data):
    """
    Stock performance versus its own past performance.
    """

    close = data["Close"]

    rs20 = ((close.iloc[-1] / close.iloc[-21]) - 1) * 100
    rs60 = ((close.iloc[-1] / close.iloc[-61]) - 1) * 100

    return float(rs20), float(rs60)


def _stock_rs(data, benchmark):
    """
    Relative strength versus NIFTY.
    """

    try:
        stock_close = float(data["Close"].iloc[-1])
        stock_60 = float(data["Close"].iloc[-61])

        bench_close = float(benchmark["Close"].iloc[-1])
        bench_60 = float(benchmark["Close"].iloc[-61])

        stock_return = stock_close / stock_60 - 1
        bench_return = bench_close / bench_60 - 1

        return float((stock_return - bench_return) * 100)

    except Exception:
        return 0.0


def _base_metrics(data):
    """
    Measures consolidation quality.

    A good pre-breakout stock should:
    - have a reasonably tight base
    - show some volatility contraction
    - remain close to resistance
    """

    recent = data.tail(BASE_LOOKBACK)

    high = float(recent["High"].max())
    low = float(recent["Low"].min())

    if low <= 0:
        return 999.0, 999.0

    base_range = ((high - low) / low) * 100

    first_half = data["Close"].tail(BASE_LOOKBACK).head(BASE_LOOKBACK // 2)
    second_half = data["Close"].tail(BASE_LOOKBACK).tail(BASE_LOOKBACK // 2)

    first_vol = first_half.std()
    second_vol = second_half.std()

    if first_vol > 0:
        compression = 1 - (second_vol / first_vol)
    else:
        compression = 0

    compression_pct = float(compression * 100)

    return float(base_range), compression_pct


def _breakout_metrics(data):
    """
    Resistance is based on the previous 20 sessions,
    excluding today's candle.
    """

    if len(data) < RESISTANCE_LOOKBACK + 1:
        return None

    previous = data.iloc[:-1].tail(RESISTANCE_LOOKBACK)

    resistance = float(previous["High"].max())
    close = float(data["Close"].iloc[-1])

    if resistance <= 0:
        return None

    breakout_pct = ((close / resistance) - 1) * 100

    return resistance, breakout_pct


def _trend_metrics(data):
    close = data["Close"]

    e20 = float(ema(close, 20).iloc[-1])
    e50 = float(ema(close, 50).iloc[-1])
    e200 = float(ema(close, 200).iloc[-1])

    price = float(close.iloc[-1])

    extension = ((price / e20) - 1) * 100

    aligned = (
        e20 > e50
        and e50 > e200
        and price > e20
    )

    return {
        "ema20": e20,
        "ema50": e50,
        "ema200": e200,
        "extension": float(extension),
        "aligned": bool(aligned),
    }


def _momentum_metrics(data):
    close = data["Close"]

    rsi_value = float(rsi(close, 14).iloc[-1])

    return {
        "rsi": rsi_value,
    }


def _volume_metrics(data):
    try:
        rvol = float(relative_volume(data, 20))
    except Exception:
        rvol = 0.0

    avg_volume = float(
        data["Volume"].tail(20).mean()
    )

    current_volume = float(
        data["Volume"].iloc[-1]
    )

    return {
        "rvol": rvol,
        "avg_volume": avg_volume,
        "current_volume": current_volume,
    }


def _candle_metrics(data):
    strength = closing_strength(data)

    return {
        "closing_strength": float(strength),
    }


def _score_trend(metrics):
    score = 0

    if metrics["aligned"]:
        score += 14

    extension = metrics["extension"]

    if 0 <= extension <= 5:
        score += 6
    elif 5 < extension <= 10:
        score += 4
    elif 10 < extension <= 12:
        score += 2

    return min(score, 20)


def _score_relative_strength(rs20, rs60, stock_rs):
    score = 0

    if rs20 >= 3:
        score += 5
    elif rs20 >= 0:
        score += 3

    if rs60 >= 8:
        score += 5
    elif rs60 >= 0:
        score += 3

    if stock_rs >= 5:
        score += 5
    elif stock_rs >= 0:
        score += 3

    return min(score, 15)


def _score_base(base_range, compression):
    score = 0

    if base_range <= 8:
        score += 10
    elif base_range <= 12:
        score += 8
    elif base_range <= 18:
        score += 5

    if compression >= 20:
        score += 10
    elif compression >= 10:
        score += 7
    elif compression >= 0:
        score += 4

    return min(score, 20)


def _score_breakout(setup, breakout_pct, closing_strength_value):
    score = 0

    if setup == "FRESH BREAKOUT":

        if 0 < breakout_pct <= 2:
            score += 10
        elif 2 < breakout_pct <= 4:
            score += 8
        elif 4 < breakout_pct <= 6:
            score += 5

        if closing_strength_value >= 0.80:
            score += 5
        elif closing_strength_value >= 0.65:
            score += 3

    else:

        distance = abs(breakout_pct)

        if distance <= 1:
            score += 15
        elif distance <= 2:
            score += 13
        elif distance <= 3:
            score += 10
        elif distance <= 5:
            score += 7

    return min(score, 15)


def _score_volume(setup, rvol):
    if setup == "FRESH BREAKOUT":

        if rvol >= 2.0:
            return 15
        elif rvol >= 1.7:
            return 13
        elif rvol >= 1.5:
            return 11
        elif rvol >= 1.3:
            return 8

    else:

        if 0.8 <= rvol <= 1.2:
            return 15
        elif rvol < 0.8:
            return 10
        elif rvol <= 1.5:
            return 8

    return 5


def _score_momentum(rsi_value):
    if 58 <= rsi_value <= 68:
        return 10

    if 55 <= rsi_value < 58:
        return 8

    if 68 < rsi_value <= 72:
        return 7

    if 52 <= rsi_value < 55:
        return 5

    return 3


def _trade_levels(data, setup):
    """
    Trade plan.

    Entry:
        Current closing price.

    Stop:
        Based on ATR and recent structure.

    Targets:
        T1 = 1R
        T2 = 2R
        T3 = 3R
        T4 = 4R
    """

    close = float(data["Close"].iloc[-1])

    atr_value = float(
        atr(data, 14).iloc[-1]
    )

    recent_low = float(
        data["Low"].tail(10).min()
    )

    if setup == "FRESH BREAKOUT":

        stop_by_atr = close - (1.5 * atr_value)

        stop = max(
            recent_low,
            stop_by_atr
        )

    else:

        stop_by_atr = close - (1.5 * atr_value)

        stop = max(
            recent_low,
            stop_by_atr
        )

    if stop >= close:
        stop = close * 0.95

    risk = close - stop

    if risk <= 0:
        risk = close * 0.05
        stop = close - risk

    t1 = close + risk
    t2 = close + (2 * risk)
    t3 = close + (3 * risk)
    t4 = close + (4 * risk)

    risk_pct = (risk / close) * 100

    return {
        "entry": round(close, 2),
        "sl": round(stop, 2),
        "t1": round(t1, 2),
        "t2": round(t2, 2),
        "t3": round(t3, 2),
        "t4": round(t4, 2),
        "risk_pct": round(risk_pct, 2),
    }


def _classify(
    breakout_pct,
    rvol,
    rsi_value,
    closing_strength_value,
    trend,
    base_range
):
    """
    Determine whether the stock is:

    PRE-BREAKOUT
    or
    FRESH BREAKOUT
    """

    if not trend["aligned"]:
        return None

    if trend["extension"] > MAX_EXTENSION:
        return None

    # -----------------------------
    # FRESH BREAKOUT
    # -----------------------------

    if (
        0 < breakout_pct <= MAX_FRESH_GAP
        and rvol >= MIN_FRESH_RVOL
        and rsi_value >= MIN_FRESH_RSI
        and closing_strength_value >= 0.60
    ):
        return "FRESH BREAKOUT"

    # -----------------------------
    # PRE-BREAKOUT
    # -----------------------------

    if (
        -MAX_PRE_GAP <= breakout_pct <= 0
        and rvol >= MIN_PRE_RVOL
        and rsi_value >= MIN_PRE_RSI
        and base_range <= 18
    ):
        return "PRE-BREAKOUT"

    return None


def score_stock(data, benchmark=None, symbol=None):
    """
    Main scoring engine.

    Returns None if the stock does not qualify.

    Final score = maximum 100.
    """

    data = _prepare_dataframe(data)

    if data is None:
        return None

    try:

        trend = _trend_metrics(data)

        momentum = _momentum_metrics(data)

        volume = _volume_metrics(data)

        candle = _candle_metrics(data)

        base_range, compression = _base_metrics(data)

        breakout = _breakout_metrics(data)

        if breakout is None:
            return None

        resistance, breakout_pct = breakout

        rs20, rs60 = _relative_strength(data)

        stock_rs = 0.0

        if benchmark is not None:
            stock_rs = _stock_rs(
                data,
                benchmark
            )

        setup = _classify(
            breakout_pct=breakout_pct,
            rvol=volume["rvol"],
            rsi_value=momentum["rsi"],
            closing_strength_value=candle["closing_strength"],
            trend=trend,
            base_range=base_range,
        )

        if setup is None:
            return None

        trend_score = _score_trend(trend)

        rs_score = _score_relative_strength(
            rs20,
            rs60,
            stock_rs
        )

        base_score = _score_base(
            base_range,
            compression
        )

        breakout_score = _score_breakout(
            setup,
            breakout_pct,
            candle["closing_strength"]
        )

        volume_score = _score_volume(
            setup,
            volume["rvol"]
        )

        momentum_score = _score_momentum(
            momentum["rsi"]
        )

        trade = _trade_levels(
            data,
            setup
        )

        risk_score = 0

        if trade["risk_pct"] <= 4:
            risk_score = 5
        elif trade["risk_pct"] <= 6:
            risk_score = 4
        elif trade["risk_pct"] <= 8:
            risk_score = 2

        raw_score = (
            trend_score
            + rs_score
            + base_score
            + breakout_score
            + volume_score
            + momentum_score
            + risk_score
        )

        # --------------------------------
        # CHASE PENALTY
        # --------------------------------

        chase_penalty = 0

        if trend["extension"] > 8:
            chase_penalty += 3

        if trend["extension"] > 10:
            chase_penalty += 3

        if setup == "FRESH BREAKOUT" and breakout_pct > 4:
            chase_penalty += 2

        score = max(
            0,
            min(
                100,
                round(raw_score - chase_penalty)
            )
        )

        return {
            "Symbol": symbol or "",
            "Setup": setup,
            "Score": score,

            "BreakoutPct": round(
                breakout_pct,
                2
            ),

            "RS20": round(
                rs20,
                2
            ),

            "RS60": round(
                rs60,
                2
            ),

            "StockRS": round(
                stock_rs,
                2
            ),

            "RSI": round(
                momentum["rsi"],
                2
            ),

            "RVOL": round(
                volume["rvol"],
                2
            ),

            "BaseRange": round(
                base_range,
                2
            ),

            "Compression": round(
                compression,
                2
            ),

            "Extension": round(
                trend["extension"],
                2
            ),

            "Resistance": round(
                resistance,
                2
            ),

            "ClosingStrength": round(
                candle["closing_strength"],
                2
            ),

            "Entry": trade["entry"],
            "SL": trade["sl"],
            "T1": trade["t1"],
            "T2": trade["t2"],
            "T3": trade["t3"],
            "T4": trade["t4"],
            "RiskPct": trade["risk_pct"],
        }

    except Exception:
        return None

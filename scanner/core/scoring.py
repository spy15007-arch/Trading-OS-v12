"""
Trading OS v12 Professional
Institutional Stock Scoring Engine
"""

import math

import numpy as np

from .indicators import (
    ema,
    rsi,
    macd,
    atr,
    vwap,
    relative_volume,
    closing_strength,
    trend_strength,
)


# ==========================================================
# Lorentzian Distance
# ==========================================================

def lorentzian_distance(
    current_rsi,
    current_rvol,
    ideal_rsi=68.0,
    ideal_rvol=2.0,
):
    """
    Measures distance from an ideal momentum profile.

    Lower score = closer to the target RSI/RVOL profile.
    """

    try:
        d1 = math.log(
            1.0 +
            abs(
                float(current_rsi) -
                ideal_rsi
            )
        )

        d2 = math.log(
            1.0 +
            abs(
                float(current_rvol) -
                ideal_rvol
            )
        )

        return round(
            d1 + d2,
            2
        )

    except Exception:
        return 999.0


# ==========================================================
# Safe Float
# ==========================================================

def _safe_float(value, default=None):

    try:

        result = float(value)

        if not np.isfinite(result):
            return default

        return result

    except Exception:

        return default


# ==========================================================
# Institutional Score Engine
# ==========================================================

def score_stock(df):

    """
    Score one OHLCV dataframe.

    Returns a dictionary containing:
        Score
        Grade
        Trade
        Entry
        SL
        T1/T2/T3
        RSI
        RVOL
        EMA20/50/200
        VWAP
        ATR
        Lorentz
    """

    # ------------------------------------------------------
    # Basic validation
    # ------------------------------------------------------

    if df is None or df.empty:
        return None

    if len(df) < 220:
        return None

    required_columns = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    for column in required_columns:

        if column not in df.columns:
            return None

    try:

        # ==================================================
        # PRICE
        # ==================================================

        close = _safe_float(
            df["Close"].iloc[-1]
        )

        if close is None:
            return None

        # ==================================================
        # MOVING AVERAGES
        # ==================================================

        ema20_series = ema(
            df["Close"],
            20
        )

        ema50_series = ema(
            df["Close"],
            50
        )

        ema200_series = ema(
            df["Close"],
            200
        )

        ema20 = _safe_float(
            ema20_series.iloc[-1]
        )

        ema50 = _safe_float(
            ema50_series.iloc[-1]
        )

        ema200 = _safe_float(
            ema200_series.iloc[-1]
        )

        if (
            ema20 is None or
            ema50 is None or
            ema200 is None
        ):
            return None

        # ==================================================
        # RSI
        # ==================================================

        rsi_series = rsi(
            df["Close"]
        )

        rsi_now = _safe_float(
            rsi_series.iloc[-1]
        )

        if rsi_now is None:
            return None

        # ==================================================
        # MACD
        # ==================================================

        macd_line, signal_line, histogram = macd(
            df["Close"]
        )

        macd_now = _safe_float(
            macd_line.iloc[-1]
        )

        signal_now = _safe_float(
            signal_line.iloc[-1]
        )

        hist_now = _safe_float(
            histogram.iloc[-1]
        )

        if (
            macd_now is None or
            signal_now is None or
            hist_now is None
        ):
            return None

        # ==================================================
        # ATR
        # ==================================================

        atr_series = atr(
            df
        )

        atr_now = _safe_float(
            atr_series.iloc[-1]
        )

        if (
            atr_now is None or
            atr_now <= 0
        ):
            return None

        # ==================================================
        # VWAP
        # ==================================================

        vwap_series = vwap(
            df
        )

        vwap_now = _safe_float(
            vwap_series.iloc[-1]
        )

        if vwap_now is None:
            return None

        # ==================================================
        # RELATIVE VOLUME
        # ==================================================

        rel_vol = _safe_float(
            relative_volume(df)
        )

        if rel_vol is None:
            return None

        # ==================================================
        # CLOSING STRENGTH
        # ==================================================

        candle_strength = _safe_float(
            closing_strength(df),
            0.0
        )

        if candle_strength is None:
            candle_strength = 0.0

        # ==================================================
        # TREND STRENGTH
        # ==================================================

        trend = int(
            trend_strength(df)
        )

        # ==================================================
        # START SCORE
        # ==================================================

        score = 0

        # ==================================================
        # PRIMARY TREND
        # ==================================================

        if close > ema20:
            score += 2

        if ema20 > ema50:
            score += 2

        if ema50 > ema200:
            score += 3

        # ==================================================
        # RSI
        # ==================================================

        if 60 <= rsi_now <= 78:

            score += 2

        elif 55 <= rsi_now < 60:

            score += 1

        elif rsi_now > 82:

            score -= 3

        # ==================================================
        # MACD
        # ==================================================

        if macd_now > signal_now:
            score += 2

        if hist_now > 0:
            score += 1

        # ==================================================
        # VWAP
        # ==================================================

        if close > vwap_now:
            score += 2

        # ==================================================
        # RELATIVE VOLUME
        # ==================================================

        if rel_vol >= 2.0:

            score += 3

        elif rel_vol >= 1.5:

            score += 2

        elif rel_vol >= 1.2:

            score += 1

        # ==================================================
        # CANDLE QUALITY
        # ==================================================

        if candle_strength >= 0.80:

            score += 2

        elif candle_strength >= 0.65:

            score += 1

        # ==================================================
        # TREND BONUS
        # ==================================================

        score += trend

        # ==================================================
        # LORENTZIAN MOMENTUM MODEL
        # ==================================================

        lorentz = lorentzian_distance(
            rsi_now,
            rel_vol
        )

        if lorentz < 0.50:

            score += 2

        elif lorentz < 1.00:

            score += 1

        elif lorentz > 2.50:

            score -= 2

        # ==================================================
        # QUALITY GRADE
        # ==================================================

        if score >= 18:

            grade = "A+"

        elif score >= 15:

            grade = "A"

        elif score >= 12:

            grade = "B"

        else:

            grade = "C"

        # ==================================================
        # TRADE TYPE
        # ==================================================

        if (
            rel_vol >= 1.80 and
            candle_strength >= 0.75
        ):

            trade = "⚡ Intraday"

        elif (
            rel_vol >= 1.30 and
            candle_strength >= 0.70
        ):

            trade = "🌙 BTST"

        else:

            trade = "📈 Swing"

        # ==================================================
        # ATR-BASED TRADE PLAN
        # ==================================================

        entry = round(
            close,
            2
        )

        sl = round(
            close -
            (1.5 * atr_now),
            2
        )

        t1 = round(
            close +
            (1.5 * atr_now),
            2
        )

        t2 = round(
            close +
            (3.0 * atr_now),
            2
        )

        t3 = round(
            close +
            (4.5 * atr_now),
            2
        )

        # ==================================================
        # INSTITUTIONAL FILTER
        # ==================================================

        if close < ema200:
            return None

        if score < 12:
            return None

        # ==================================================
        # RESULT
        # ==================================================

        return {

            "Entry": entry,

            "Score": int(score),

            "Grade": grade,

            "Trade": trade,

            "RSI": round(
                rsi_now,
                1
            ),

            "RVOL": round(
                rel_vol,
                2
            ),

            "EMA20": round(
                ema20,
                2
            ),

            "EMA50": round(
                ema50,
                2
            ),

            "EMA200": round(
                ema200,
                2
            ),

            "VWAP": round(
                vwap_now,
                2
            ),

            "ATR": round(
                atr_now,
                2
            ),

            "Lorentz": lorentz,

            "SL": sl,

            "T1": t1,

            "T2": t2,

            "T3": t3,
        }

    except Exception:

        return None

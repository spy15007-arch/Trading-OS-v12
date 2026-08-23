"""
Trading OS v12 Professional
Institutional Scoring Engine
"""

import math

import pandas as pd

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
    ideal_rsi=68,
    ideal_rvol=2.0
):

    d1 = math.log(
        1 +
        abs(
            current_rsi -
            ideal_rsi
        )
    )

    d2 = math.log(
        1 +
        abs(
            current_rvol -
            ideal_rvol
        )
    )

    return round(
        d1 + d2,
        2
    )


# ==========================================================
# Institutional Score
# ==========================================================

def score_stock(df):

    if df is None:
        return None

    if len(df) < 220:
        return None

    try:

        close_series = df["Close"]

        close = float(
            close_series.iloc[-1]
        )

        ema20 = float(
            ema(
                close_series,
                20
            ).iloc[-1]
        )

        ema50 = float(
            ema(
                close_series,
                50
            ).iloc[-1]
        )

        ema200 = float(
            ema(
                close_series,
                200
            ).iloc[-1]
        )

        rsi_now = float(
            rsi(
                close_series
            ).iloc[-1]
        )

        macd_line, signal_line, hist = (
            macd(
                close_series
            )
        )

        atr_now = float(
            atr(df).iloc[-1]
        )

        vwap_now = float(
            vwap(df).iloc[-1]
        )

        rel_vol = float(
            relative_volume(df)
        )

        candle_strength = (
            closing_strength(df)
        )

        trend = (
            trend_strength(df)
        )

        values = [
            close,
            ema20,
            ema50,
            ema200,
            rsi_now,
            atr_now,
            vwap_now,
            rel_vol
        ]

        if any(
            pd.isna(x)
            for x in values
        ):

            return None

        score = 0

        # --------------------------------------------------
        # PRIMARY TREND
        # --------------------------------------------------

        if close > ema20:
            score += 2

        if ema20 > ema50:
            score += 2

        if ema50 > ema200:
            score += 3

        # --------------------------------------------------
        # RSI
        # --------------------------------------------------

        if 60 <= rsi_now <= 78:

            score += 2

        elif 55 <= rsi_now < 60:

            score += 1

        elif rsi_now > 82:

            score -= 3

        # --------------------------------------------------
        # MACD
        # --------------------------------------------------

        if (
            macd_line.iloc[-1] >
            signal_line.iloc[-1]
        ):

            score += 2

        if hist.iloc[-1] > 0:

            score += 1

        # --------------------------------------------------
        # VWAP
        # --------------------------------------------------

        if close > vwap_now:

            score += 2

        # --------------------------------------------------
        # RELATIVE VOLUME
        # --------------------------------------------------

        if rel_vol >= 2:

            score += 3

        elif rel_vol >= 1.5:

            score += 2

        elif rel_vol >= 1.2:

            score += 1

        # --------------------------------------------------
        # CANDLE QUALITY
        # --------------------------------------------------

        if candle_strength > 0.80:

            score += 2

        elif candle_strength > 0.65:

            score += 1

        # --------------------------------------------------
        # TREND BONUS
        # --------------------------------------------------

        score += trend

        # --------------------------------------------------
        # LORENTZIAN
        # --------------------------------------------------

        lorentz = (
            lorentzian_distance(
                rsi_now,
                rel_vol
            )
        )

        if lorentz < 0.50:

            score += 2

        elif lorentz < 1.00:

            score += 1

        elif lorentz > 2.50:

            score -= 2

        # --------------------------------------------------
        # GRADE
        # --------------------------------------------------

        if score >= 18:

            grade = "A+"

        elif score >= 15:

            grade = "A"

        elif score >= 12:

            grade = "B"

        else:

            grade = "C"

        # --------------------------------------------------
        # TRADE TYPE
        # --------------------------------------------------

        if (
            rel_vol >= 1.80 and
            candle_strength >= 0.75
        ):

            trade = "⚡ Intraday"

        elif (
            candle_strength >= 0.70 and
            rel_vol >= 1.30
        ):

            trade = "🌙 BTST"

        else:

            trade = "📈 Swing"

        # --------------------------------------------------
        # TRADE LEVELS
        # --------------------------------------------------

        entry = round(
            close,
            2
        )

        sl = round(
            close -
            1.5 * atr_now,
            2
        )

        t1 = round(
            close +
            1.5 * atr_now,
            2
        )

        t2 = round(
            close +
            3.0 * atr_now,
            2
        )

        t3 = round(
            close +
            4.5 * atr_now,
            2
        )

        # --------------------------------------------------
        # INSTITUTIONAL FILTER
        # --------------------------------------------------

        if close < ema200:

            return None

        if score < 12:

            return None

        return {

            "Entry": entry,

            "Score": score,

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

            "T3": t3

        }

    except Exception:

        return None

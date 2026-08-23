"""
Trading OS v12 Professional
Market Regime Engine
"""

import logging

import pandas as pd

from .downloader import download_index
from .indicators import (
    ema,
    rsi,
)


logger = logging.getLogger(
    "TradingOS"
)


# ==========================================================
# CONFIGURATION
# ==========================================================

INDEX_PERIOD = "2y"
INDEX_INTERVAL = "1d"

MIN_BARS = 220


# ==========================================================
# NORMALISE INDEX DATA
# ==========================================================

def _prepare_index(df):

    if df is None or df.empty:

        return None

    try:

        if isinstance(
            df.columns,
            pd.MultiIndex
        ):

            df.columns = (
                df.columns
                .get_level_values(0)
            )

        required = [
            "Close"
        ]

        for column in required:

            if column not in df.columns:

                return None

        df = df.dropna(
            subset=["Close"]
        )

        if len(df) < MIN_BARS:

            return None

        return df

    except Exception as e:

        logger.warning(
            f"Index preparation failed: "
            f"{e}"
        )

        return None


# ==========================================================
# ANALYSE INDEX
# ==========================================================

def analyse(df):

    df = _prepare_index(
        df
    )

    if df is None:

        return None

    try:

        close_series = (
            df["Close"]
        )

        close = float(
            close_series.iloc[-1]
        )

        ema20_series = ema(
            close_series,
            20
        )

        ema50_series = ema(
            close_series,
            50
        )

        ema200_series = ema(
            close_series,
            200
        )

        rsi_series = rsi(
            close_series
        )

        ema20 = float(
            ema20_series.iloc[-1]
        )

        ema50 = float(
            ema50_series.iloc[-1]
        )

        ema200 = float(
            ema200_series.iloc[-1]
        )

        rsi_now = float(
            rsi_series.iloc[-1]
        )

        if pd.isna(
            rsi_now
        ):

            return None

        # --------------------------------------------------
        # Market trend score
        # --------------------------------------------------

        score = 0

        if close > ema20:

            score += 1

        if ema20 > ema50:

            score += 1

        if ema50 > ema200:

            score += 2

        if rsi_now > 60:

            score += 1

        return {

            "close": round(
                close,
                2
            ),

            "ema20": round(
                ema20,
                2
            ),

            "ema50": round(
                ema50,
                2
            ),

            "ema200": round(
                ema200,
                2
            ),

            "rsi": round(
                rsi_now,
                1
            ),

            "score": score

        }

    except Exception as e:

        logger.warning(
            f"Index analysis failed: "
            f"{e}"
        )

        return None


# ==========================================================
# MARKET STATUS
# ==========================================================

def get_market_status():

    logger.info(
        "Loading Market Regime..."
    )

    # ------------------------------------------------------
    # IMPORTANT:
    # Only downloader.download_index()
    # is used.
    #
    # This eliminates the previous
    # download_index(period=...) conflict.
    # ------------------------------------------------------

    nifty_df = download_index(
        "^NSEI",
        period=INDEX_PERIOD,
        interval=INDEX_INTERVAL
    )

    bank_df = download_index(
        "^NSEBANK",
        period=INDEX_PERIOD,
        interval=INDEX_INTERVAL
    )

    nifty = analyse(
        nifty_df
    )

    bank = analyse(
        bank_df
    )

    # ------------------------------------------------------
    # Missing market data
    # ------------------------------------------------------

    if (
        nifty is None or
        bank is None
    ):

        logger.warning(
            "Market regime unavailable."
        )

        return {

            "MODE": "UNKNOWN",

            "NIFTY": "NA",

            "BANKNIFTY": "NA",

            "NIFTY_RSI": "NA",

            "BANK_RSI": "NA",

            "NIFTY_SCORE": 0,

            "BANK_SCORE": 0,

            "TOTAL_SCORE": 0

        }

    # ------------------------------------------------------
    # Combined score
    # ------------------------------------------------------

    total = (
        nifty["score"] +
        bank["score"]
    )

    # ------------------------------------------------------
    # Regime
    # ------------------------------------------------------

    if total >= 8:

        mode = "🟢 BULLISH"

    elif total >= 5:

        mode = "🟡 NEUTRAL"

    else:

        mode = "🔴 DEFENSIVE"

    logger.info(
        f"Market Mode: {mode}"
    )

    return {

        "MODE": mode,

        "NIFTY": nifty["close"],

        "BANKNIFTY": bank["close"],

        "NIFTY_RSI": nifty["rsi"],

        "BANK_RSI": bank["rsi"],

        "NIFTY_SCORE": nifty["score"],

        "BANK_SCORE": bank["score"],

        "TOTAL_SCORE": total

    }

"""
Trading OS v12 Professional
Market Regime Engine

Determines the broad market regime from:
    NIFTY 50
    BANK NIFTY

Regimes:
    🟢 BULLISH
    🟡 NEUTRAL
    🔴 DEFENSIVE
    ⚪ UNKNOWN
"""

from .downloader import download_index
from .indicators import ema, rsi


# ==========================================================
# CONFIGURATION
# ==========================================================

INDEX_PERIOD = "2y"

INDEX_INTERVAL = "1d"

MIN_BARS = 220


# ==========================================================
# Safe Number
# ==========================================================

def _safe_float(value, default=None):

    try:

        result = float(value)

        if result != result:
            return default

        return result

    except Exception:

        return default


# ==========================================================
# Analyse One Index
# ==========================================================

def analyse(df):

    if df is None or df.empty:
        return None

    if len(df) < MIN_BARS:
        return None

    required = [
        "Close"
    ]

    for column in required:

        if column not in df.columns:
            return None

    try:

        close_series = df[
            "Close"
        ]

        # ==================================================
        # Current Close
        # ==================================================

        close = _safe_float(
            close_series.iloc[-1]
        )

        if close is None:
            return None

        # ==================================================
        # EMA
        # ==================================================

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
            close_series,
            14
        )

        rsi_now = _safe_float(
            rsi_series.iloc[-1]
        )

        if rsi_now is None:
            return None

        # ==================================================
        # Market Trend Score
        #
        # Maximum = 5
        #
        # Price > EMA20     +1
        # EMA20 > EMA50     +1
        # EMA50 > EMA200    +2
        # RSI > 60          +1
        # ==================================================

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

            "score": int(score),
        }

    except Exception as e:

        print(
            f"Index analysis error: {e}"
        )

        return None


# ==========================================================
# Market Status
# ==========================================================

def get_market_status():

    # ------------------------------------------------------
    # NIFTY
    # ------------------------------------------------------

    nifty_df = download_index(
        "^NSEI",
        period=INDEX_PERIOD,
        interval=INDEX_INTERVAL
    )

    nifty = analyse(
        nifty_df
    )

    # ------------------------------------------------------
    # BANK NIFTY
    # ------------------------------------------------------

    bank_df = download_index(
        "^NSEBANK",
        period=INDEX_PERIOD,
        interval=INDEX_INTERVAL
    )

    bank = analyse(
        bank_df
    )

    # ------------------------------------------------------
    # Data Failure
    # ------------------------------------------------------

    if nifty is None or bank is None:

        return {

            "MODE": "⚪ UNKNOWN",

            "NIFTY": "NA",

            "BANKNIFTY": "NA",

            "NIFTY_RSI": "NA",

            "BANK_RSI": "NA",

            "NIFTY_SCORE": 0,

            "BANK_SCORE": 0,

            "TOTAL_SCORE": 0,
        }

    # ======================================================
    # Combined Score
    # ======================================================

    total = (
        nifty["score"] +
        bank["score"]
    )

    # ======================================================
    # Market Regime
    #
    # 8-10 = Bullish
    # 5-7  = Neutral
    # 0-4  = Defensive
    # ======================================================

    if total >= 8:

        mode = "🟢 BULLISH"

    elif total >= 5:

        mode = "🟡 NEUTRAL"

    else:

        mode = "🔴 DEFENSIVE"

    return {

        "MODE": mode,

        "NIFTY": nifty["close"],

        "BANKNIFTY": bank["close"],

        "NIFTY_RSI": nifty["rsi"],

        "BANK_RSI": bank["rsi"],

        "NIFTY_SCORE": nifty["score"],

        "BANK_SCORE": bank["score"],

        "TOTAL_SCORE": total,
    }

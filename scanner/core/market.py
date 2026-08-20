"""
Trading OS v12 Professional
Market Regime Engine

Purpose:
    Determine the overall market regime using
    NIFTY 50 and BANK NIFTY.

Regime:
    🟢 BULLISH
    🟡 NEUTRAL
    🔴 DEFENSIVE
"""

import yfinance as yf

from core.indicators import (
    ema,
    rsi,
)


# ==========================================================
# CONFIGURATION
# ==========================================================

INDEX_PERIOD = "2y"
INDEX_INTERVAL = "1d"
MIN_BARS = 220


# ==========================================================
# Download Index Data
# ==========================================================

def download_index(symbol):

    try:

        df = yf.download(
            symbol,
            period=INDEX_PERIOD,
            interval=INDEX_INTERVAL,
            progress=False,
            auto_adjust=True,
            threads=False,
        )

        if df is None or df.empty:
            return None

        # Handle Yahoo Finance MultiIndex data
        if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:

            try:
                df = df.xs(symbol, axis=1, level=1)
            except Exception:

                try:
                    df.columns = df.columns.get_level_values(0)
                except Exception:
                    pass

        df = df.dropna()

        if len(df) < MIN_BARS:
            return None

        return df

    except Exception as e:

        print(f"Market data error for {symbol}: {e}")

        return None


# ==========================================================
# Analyse Index
# ==========================================================

def analyse(df):

    if df is None or len(df) < MIN_BARS:
        return None

    try:

        close_series = df["Close"]

        close = float(close_series.iloc[-1])

        ema20_series = ema(close_series, 20)
        ema50_series = ema(close_series, 50)
        ema200_series = ema(close_series, 200)
        rsi_series = rsi(close_series)

        ema20 = float(ema20_series.iloc[-1])
        ema50 = float(ema50_series.iloc[-1])
        ema200 = float(ema200_series.iloc[-1])
        rsi_now = float(rsi_series.iloc[-1])

        # --------------------------------------------------
        # Trend Score
        # --------------------------------------------------

        score = 0

        # Price above EMA20
        if close > ema20:
            score += 1

        # EMA20 above EMA50
        if ema20 > ema50:
            score += 1

        # EMA50 above EMA200
        if ema50 > ema200:
            score += 2

        # RSI strength
        if rsi_now > 60:
            score += 1

        return {

            "close": round(close, 2),

            "ema20": round(ema20, 2),

            "ema50": round(ema50, 2),

            "ema200": round(ema200, 2),

            "rsi": round(rsi_now, 1),

            "score": score,

        }

    except Exception as e:

        print(f"Index analysis error: {e}")

        return None


# ==========================================================
# Market Status
# ==========================================================

def get_market_status():

    nifty = analyse(
        download_index("^NSEI")
    )

    bank = analyse(
        download_index("^NSEBANK")
    )

    # ------------------------------------------------------
    # Data unavailable
    # ------------------------------------------------------

    if nifty is None or bank is None:

        return {

            "MODE": "UNKNOWN",

            "NIFTY": "NA",

            "BANKNIFTY": "NA",

            "NIFTY_RSI": "NA",

            "BANK_RSI": "NA",

            "TOTAL_SCORE": 0,

        }

    # ------------------------------------------------------
    # Combined Market Score
    #
    # Maximum:
    # NIFTY     = 5
    # BANKNIFTY = 5
    # TOTAL     = 10
    # ------------------------------------------------------

    total = nifty["score"] + bank["score"]

    # ------------------------------------------------------
    # Market Regime
    # ------------------------------------------------------

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

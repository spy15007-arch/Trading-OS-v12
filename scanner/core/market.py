"""
Trading OS v12 Professional
Market Regime Engine
"""

from .downloader import download_index
from .indicators import ema, rsi


INDEX_PERIOD = "2y"
INDEX_INTERVAL = "1d"
MIN_BARS = 220


# ==========================================================
# Analyse Index
# ==========================================================

def analyse(df):

    if df is None or len(df) < MIN_BARS:
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
            "close": round(close, 2),
            "ema20": round(ema20, 2),
            "ema50": round(ema50, 2),
            "ema200": round(ema200, 2),
            "rsi": round(rsi_now, 1),
            "score": score
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

    nifty = analyse(
        download_index(
            "^NSEI",
            INDEX_PERIOD,
            INDEX_INTERVAL
        )
    )

    bank = analyse(
        download_index(
            "^NSEBANK",
            INDEX_PERIOD,
            INDEX_INTERVAL
        )
    )

    if nifty is None or bank is None:

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

    total = (
        nifty["score"] +
        bank["score"]
    )

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
        "TOTAL_SCORE": total
    }

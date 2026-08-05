"""
Trading OS v12 Professional
Market Regime Engine
"""

import yfinance as yf

from core.indicators import (
    ema,
    rsi,
)


# ==========================================================
# Download Index
# ==========================================================

def download_index(symbol):

    try:

        df = yf.download(
            symbol,
            period="6mo",
            interval="1d",
            progress=False,
            auto_adjust=True,
            threads=False
        )

        return df.dropna()

    except:

        return None


# ==========================================================
# Analyse Index
# ==========================================================

def analyse(df):

    if df is None or len(df) < 220:

        return None

    close = float(df.Close.iloc[-1])

    ema20 = float(ema(df.Close, 20).iloc[-1])

    ema50 = float(ema(df.Close, 50).iloc[-1])

    ema200 = float(ema(df.Close, 200).iloc[-1])

    rsi_now = float(rsi(df.Close).iloc[-1])

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

    if nifty is None or bank is None:

        return {

            "MODE": "UNKNOWN",

            "NIFTY": "NA",

            "BANKNIFTY": "NA"

        }

    total = nifty["score"] + bank["score"]

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

        "TOTAL_SCORE": total

    }

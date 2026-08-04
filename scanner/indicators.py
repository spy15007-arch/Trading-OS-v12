import pandas as pd
import numpy as np


# ==========================================================
# Exponential Moving Average
# ==========================================================

def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


# ==========================================================
# RSI
# ==========================================================

def rsi(series, period=14):

    delta = series.diff()

    gain = delta.clip(lower=0)

    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()

    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    return 100 - (100 / (1 + rs))


# ==========================================================
# MACD
# ==========================================================

def macd(series,
         fast=12,
         slow=26,
         signal=9):

    ema_fast = ema(series, fast)

    ema_slow = ema(series, slow)

    macd_line = ema_fast - ema_slow

    signal_line = macd_line.ewm(
        span=signal,
        adjust=False
    ).mean()

    hist = macd_line - signal_line

    return macd_line, signal_line, hist


# ==========================================================
# ATR
# ==========================================================

def atr(df, period=14):

    high_low = df.High - df.Low

    high_close = (df.High - df.Close.shift()).abs()

    low_close = (df.Low - df.Close.shift()).abs()

    tr = pd.concat(
        [
            high_low,
            high_close,
            low_close
        ],
        axis=1
    ).max(axis=1)

    return tr.ewm(
        alpha=1/period,
        adjust=False
    ).mean()


# ==========================================================
# VWAP
# ==========================================================

def vwap(df):

    typical = (
        df.High +
        df.Low +
        df.Close
    ) / 3

    pv = typical * df.Volume

    return pv.cumsum() / df.Volume.cumsum()


# ==========================================================
# Relative Volume
# ==========================================================

def relative_volume(df, period=20):

    avg = df.Volume.rolling(period).mean()

    return df.Volume.iloc[-1] / avg.iloc[-1]


# ==========================================================
# Closing Strength
# ==========================================================

def closing_strength(df):

    high = float(df.High.iloc[-1])

    low = float(df.Low.iloc[-1])

    close = float(df.Close.iloc[-1])

    rng = high - low

    if rng <= 0:
        return 0

    return round((close - low) / rng, 2)


# ==========================================================
# Trend Strength
# ==========================================================

def trend_strength(df):

    e20 = ema(df.Close,20).iloc[-1]

    e50 = ema(df.Close,50).iloc[-1]

    e200 = ema(df.Close,200).iloc[-1]

    score = 0

    if e20 > e50:
        score += 1

    if e50 > e200:
        score += 1

    if df.Close.iloc[-1] > e20:
        score += 1

    return score


# ==========================================================
# Parkinson Volatility
# ==========================================================

def parkinson_volatility(df):

    hl = np.log(df.High / df.Low)

    sigma = np.sqrt(
        (
            hl ** 2
        ).mean()
        /
        (
            4 * np.log(2)
        )
    )

    return sigma * np.sqrt(252)


# ==========================================================
# Historical Volatility
# ==========================================================

def historical_volatility(df):

    ret = np.log(
        df.Close /
        df.Close.shift()
    )

    return ret.std() * np.sqrt(252)

"""
Trading OS v12 Professional
Technical Indicators
"""

import numpy as np
import pandas as pd


# ==========================================================
# Helper
# ==========================================================

def _series(value):

    """
    Convert a pandas object to a clean Series.
    Handles Yahoo Finance MultiIndex columns safely.
    """

    if isinstance(value, pd.DataFrame):

        if value.shape[1] == 1:
            value = value.iloc[:, 0]
        else:
            value = value.squeeze()

    return pd.to_numeric(value, errors="coerce")


# ==========================================================
# EMA
# ==========================================================

def ema(series, period):

    series = _series(series)

    return series.ewm(
        span=period,
        adjust=False
    ).mean()


# ==========================================================
# RSI
# ==========================================================

def rsi(series, period=14):

    series = _series(series)

    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / period,
        adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        adjust=False
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    result = 100 - (
        100 / (1 + rs)
    )

    return result.fillna(50)


# ==========================================================
# MACD
# ==========================================================

def macd(
    series,
    fast=12,
    slow=26,
    signal=9
):

    series = _series(series)

    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)

    macd_line = ema_fast - ema_slow

    signal_line = macd_line.ewm(
        span=signal,
        adjust=False
    ).mean()

    histogram = (
        macd_line -
        signal_line
    )

    return (
        macd_line,
        signal_line,
        histogram
    )


# ==========================================================
# ATR
# ==========================================================

def atr(df, period=14):

    high = _series(df["High"])
    low = _series(df["Low"])
    close = _series(df["Close"])

    high_low = high - low

    high_close = (
        high -
        close.shift()
    ).abs()

    low_close = (
        low -
        close.shift()
    ).abs()

    tr = pd.concat(
        [
            high_low,
            high_close,
            low_close
        ],
        axis=1
    ).max(axis=1)

    return tr.ewm(
        alpha=1 / period,
        adjust=False
    ).mean()


# ==========================================================
# VWAP
# ==========================================================

def vwap(df):

    high = _series(df["High"])
    low = _series(df["Low"])
    close = _series(df["Close"])
    volume = _series(df["Volume"])

    typical = (
        high +
        low +
        close
    ) / 3

    pv = typical * volume

    cumulative_volume = volume.cumsum()

    return (
        pv.cumsum() /
        cumulative_volume.replace(0, np.nan)
    )


# ==========================================================
# Relative Volume
# ==========================================================

def relative_volume(
    df,
    period=20
):

    volume = _series(df["Volume"])

    average = volume.rolling(
        period
    ).mean()

    if average.empty:
        return 0.0

    current = float(
        volume.iloc[-1]
    )

    avg = float(
        average.iloc[-1]
    )

    if not np.isfinite(avg) or avg <= 0:
        return 0.0

    return current / avg


# ==========================================================
# Closing Strength
# ==========================================================

def closing_strength(df):

    high = float(
        _series(df["High"]).iloc[-1]
    )

    low = float(
        _series(df["Low"]).iloc[-1]
    )

    close = float(
        _series(df["Close"]).iloc[-1]
    )

    candle_range = high - low

    if candle_range <= 0:
        return 0.0

    return round(
        (close - low) / candle_range,
        2
    )


# ==========================================================
# Trend Strength
# ==========================================================

def trend_strength(df):

    close = _series(df["Close"])

    e20 = ema(close, 20).iloc[-1]
    e50 = ema(close, 50).iloc[-1]
    e200 = ema(close, 200).iloc[-1]

    current = close.iloc[-1]

    score = 0

    if e20 > e50:
        score += 1

    if e50 > e200:
        score += 1

    if current > e20:
        score += 1

    return score


# ==========================================================
# Parkinson Volatility
# ==========================================================

def parkinson_volatility(df):

    high = _series(df["High"])
    low = _series(df["Low"])

    hl = np.log(
        high / low
    )

    sigma = np.sqrt(
        (
            hl ** 2
        ).mean()
        /
        (
            4 * np.log(2)
        )
    )

    return float(
        sigma * np.sqrt(252)
    )


# ==========================================================
# Historical Volatility
# ==========================================================

def historical_volatility(df):

    close = _series(df["Close"])

    returns = np.log(
        close /
        close.shift()
    )

    return float(
        returns.std() *
        np.sqrt(252)
    )

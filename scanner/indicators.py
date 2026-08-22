"""
Trading OS v12 Professional
Technical Indicators Engine

This module provides all technical indicators used by
the institutional scoring and scanner engines.
"""

import numpy as np
import pandas as pd


# ==========================================================
# INTERNAL HELPERS
# ==========================================================

def _to_series(value):
    """
    Convert pandas Series/DataFrame input into a clean Series.

    Yahoo Finance can sometimes return DataFrames or MultiIndex
    structures. This helper keeps downstream indicator code
    consistent.
    """

    if isinstance(value, pd.DataFrame):

        if value.shape[1] == 1:
            value = value.iloc[:, 0]

        else:
            value = value.squeeze()

            if isinstance(value, pd.DataFrame):
                value = value.iloc[:, 0]

    return pd.to_numeric(
        value,
        errors="coerce"
    )


def _clean_frame(df):
    """
    Normalise an OHLCV dataframe.
    """

    if df is None or df.empty:
        return pd.DataFrame()

    data = df.copy()

    # Handle Yahoo Finance MultiIndex columns.
    if isinstance(
        data.columns,
        pd.MultiIndex
    ):

        flattened = []

        for column in data.columns:

            if isinstance(
                column,
                tuple
            ):

                flattened.append(
                    str(column[0])
                )

            else:

                flattened.append(
                    str(column)
                )

        data.columns = flattened

    data.columns = [
        str(column).strip()
        for column in data.columns
    ]

    return data


# ==========================================================
# EXPONENTIAL MOVING AVERAGE
# ==========================================================

def ema(
    series,
    period
):

    series = _to_series(
        series
    )

    return series.ewm(
        span=period,
        adjust=False,
        min_periods=period
    ).mean()


# ==========================================================
# SIMPLE MOVING AVERAGE
# ==========================================================

def sma(
    series,
    period
):

    series = _to_series(
        series
    )

    return series.rolling(
        window=period,
        min_periods=period
    ).mean()


# ==========================================================
# RSI
# ==========================================================

def rsi(
    series,
    period=14
):

    series = _to_series(
        series
    )

    delta = series.diff()

    gain = delta.clip(
        lower=0
    )

    loss = -delta.clip(
        upper=0
    )

    avg_gain = gain.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period
    ).mean()

    rs = (
        avg_gain /
        avg_loss.replace(
            0,
            np.nan
        )
    )

    result = (
        100 -
        (
            100 /
            (1 + rs)
        )
    )

    return result.fillna(
        50.0
    )


# ==========================================================
# MACD
# ==========================================================

def macd(
    series,
    fast=12,
    slow=26,
    signal=9
):

    series = _to_series(
        series
    )

    fast_ema = ema(
        series,
        fast
    )

    slow_ema = ema(
        series,
        slow
    )

    macd_line = (
        fast_ema -
        slow_ema
    )

    signal_line = (
        macd_line
        .ewm(
            span=signal,
            adjust=False,
            min_periods=signal
        )
        .mean()
    )

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

def atr(
    df,
    period=14
):

    data = _clean_frame(
        df
    )

    if data.empty:
        return pd.Series(
            dtype=float
        )

    high = _to_series(
        data["High"]
    )

    low = _to_series(
        data["Low"]
    )

    close = _to_series(
        data["Close"]
    )

    previous_close = (
        close.shift(1)
    )

    high_low = (
        high -
        low
    )

    high_close = (
        high -
        previous_close
    ).abs()

    low_close = (
        low -
        previous_close
    ).abs()

    true_range = pd.concat(
        [
            high_low,
            high_close,
            low_close
        ],
        axis=1
    ).max(
        axis=1
    )

    return true_range.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period
    ).mean()


# ==========================================================
# VWAP
# ==========================================================

def vwap(df):

    data = _clean_frame(
        df
    )

    if data.empty:
        return pd.Series(
            dtype=float
        )

    high = _to_series(
        data["High"]
    )

    low = _to_series(
        data["Low"]
    )

    close = _to_series(
        data["Close"]
    )

    volume = _to_series(
        data["Volume"]
    )

    typical_price = (
        high +
        low +
        close
    ) / 3.0

    price_volume = (
        typical_price *
        volume
    )

    cumulative_volume = (
        volume.cumsum()
    )

    result = (
        price_volume.cumsum() /
        cumulative_volume.replace(
            0,
            np.nan
        )
    )

    return result


# ==========================================================
# RELATIVE VOLUME
# ==========================================================

def relative_volume(
    df,
    period=20
):

    data = _clean_frame(
        df
    )

    if data.empty:
        return 0.0

    volume = _to_series(
        data["Volume"]
    )

    if len(volume) < period:
        return 0.0

    current_volume = float(
        volume.iloc[-1]
    )

    average_volume = float(
        volume
        .rolling(
            period
        )
        .mean()
        .iloc[-1]
    )

    if (
        not np.isfinite(
            average_volume
        )
        or
        average_volume <= 0
    ):

        return 0.0

    return (
        current_volume /
        average_volume
    )


# ==========================================================
# CLOSING STRENGTH
# ==========================================================

def closing_strength(
    df
):

    data = _clean_frame(
        df
    )

    if data.empty:
        return 0.0

    high = float(
        _to_series(
            data["High"]
        ).iloc[-1]
    )

    low = float(
        _to_series(
            data["Low"]
        ).iloc[-1]
    )

    close = float(
        _to_series(
            data["Close"]
        ).iloc[-1]
    )

    candle_range = (
        high -
        low
    )

    if candle_range <= 0:
        return 0.0

    return round(
        (
            close -
            low
        ) /
        candle_range,
        4
    )


# ==========================================================
# TREND STRENGTH
# ==========================================================

def trend_strength(
    df
):

    data = _clean_frame(
        df
    )

    if data.empty:
        return 0

    close = _to_series(
        data["Close"]
    )

    if len(close) < 200:
        return 0

    ema20 = ema(
        close,
        20
    ).iloc[-1]

    ema50 = ema(
        close,
        50
    ).iloc[-1]

    ema200 = ema(
        close,
        200
    ).iloc[-1]

    current_close = (
        close.iloc[-1]
    )

    score = 0

    if ema20 > ema50:
        score += 1

    if ema50 > ema200:
        score += 1

    if current_close > ema20:
        score += 1

    return score


# ==========================================================
# PARKINSON VOLATILITY
# ==========================================================

def parkinson_volatility(
    df
):

    data = _clean_frame(
        df
    )

    if data.empty:
        return 0.0

    high = _to_series(
        data["High"]
    )

    low = _to_series(
        data["Low"]
    )

    valid = (
        (high > 0) &
        (low > 0)
    )

    if not valid.any():
        return 0.0

    hl = np.log(
        high[valid] /
        low[valid]
    )

    value = np.sqrt(
        (
            hl ** 2
        ).mean()
        /
        (
            4 *
            np.log(2)
        )
    )

    return float(
        value *
        np.sqrt(252)
    )


# ==========================================================
# HISTORICAL VOLATILITY
# ==========================================================

def historical_volatility(
    df
):

    data = _clean_frame(
        df
    )

    if data.empty:
        return 0.0

    close = _to_series(
        data["Close"]
    )

    returns = np.log(
        close /
        close.shift(1)
    )

    value = (
        returns
        .dropna()
        .std()
    )

    if not np.isfinite(
        value
    ):

        return 0.0

    return float(
        value *
        np.sqrt(252)
    )


# ==========================================================
# 52-WEEK HIGH
# ==========================================================

def highest_52_week(
    df
):

    data = _clean_frame(
        df
    )

    if data.empty:
        return 0.0

    high = _to_series(
        data["High"]
    )

    if high.empty:
        return 0.0

    return float(
        high.tail(
            252
        ).max()
    )


# ==========================================================
# 52-WEEK LOW
# ==========================================================

def lowest_52_week(
    df
):

    data = _clean_frame(
        df
    )

    if data.empty:
        return 0.0

    low = _to_series(
        data["Low"]
    )

    if low.empty:
        return 0.0

    return float(
        low.tail(
            252
        ).min()
    )


# ==========================================================
# PERCENT FROM 52-WEEK HIGH
# ==========================================================

def percent_from_52_week_high(
    df
):

    data = _clean_frame(
        df
    )

    if data.empty:
        return 0.0

    close = float(
        _to_series(
            data["Close"]
        ).iloc[-1]
    )

    high_52 = highest_52_week(
        data
    )

    if high_52 <= 0:
        return 0.0

    return round(
        (
            close /
            high_52 -
            1
        ) *
        100,
        2
    )

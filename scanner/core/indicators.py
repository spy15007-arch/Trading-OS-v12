import numpy as np
import pandas as pd


def _series(x):
    if isinstance(x, pd.DataFrame):
        if x.shape[1] != 1:
            raise ValueError("expected a single series")
        x = x.iloc[:, 0]
    return pd.to_numeric(x, errors="coerce")


def ema(series, period):
    return _series(series).ewm(span=period, adjust=False, min_periods=period).mean()


def rsi(series, period=14):
    s = _series(series)
    delta = s.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(100).where(avg_loss.notna())


def macd(series, fast=12, slow=26, signal=9):
    s = _series(series)
    fast_line = ema(s, fast)
    slow_line = ema(s, slow)
    line = fast_line - slow_line
    signal_line = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return line, signal_line, line - signal_line


def atr(df, period=14):
    high = _series(df["High"])
    low = _series(df["Low"])
    close = _series(df["Close"])
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def vwap(df):
    high = _series(df["High"])
    low = _series(df["Low"])
    close = _series(df["Close"])
    volume = _series(df["Volume"])
    typical = (high + low + close) / 3
    return (typical * volume).cumsum() / volume.cumsum().replace(0, np.nan)


def relative_volume(df, period=20):
    volume = _series(df["Volume"])
    avg = volume.rolling(period, min_periods=period).mean()
    if avg.iloc[-1] in (0, np.nan) or pd.isna(avg.iloc[-1]):
        return np.nan
    return float(volume.iloc[-1] / avg.iloc[-1])


def closing_strength(df):
    high = float(_series(df["High"]).iloc[-1])
    low = float(_series(df["Low"]).iloc[-1])
    close = float(_series(df["Close"]).iloc[-1])
    rng = high - low
    return 0.0 if rng <= 0 else float((close - low) / rng)


def trend_strength(df):
    close = _series(df["Close"])
    e20 = ema(close, 20).iloc[-1]
    e50 = ema(close, 50).iloc[-1]
    e200 = ema(close, 200).iloc[-1]
    score = 0
    if e20 > e50:
        score += 1
    if e50 > e200:
        score += 1
    if close.iloc[-1] > e20:
        score += 1
    return score


def parkinson_volatility(df):
    high = _series(df["High"])
    low = _series(df["Low"])
    hl = np.log(high / low.replace(0, np.nan))
    sigma = np.sqrt((hl ** 2).mean() / (4 * np.log(2)))
    return float(sigma * np.sqrt(252))


def historical_volatility(df):
    close = _series(df["Close"])
    ret = np.log(close / close.shift())
    return float(ret.std() * np.sqrt(252))

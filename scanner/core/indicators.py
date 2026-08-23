"""Small, dependency-light technical indicator helpers."""
import numpy as np
import pandas as pd


def _series(value):
    if isinstance(value, pd.DataFrame):
        if value.shape[1] != 1:
            raise ValueError("Expected one price series")
        value = value.iloc[:, 0]
    return pd.to_numeric(value, errors="coerce")


def ema(series, period):
    return _series(series).ewm(span=period, adjust=False).mean()


def rsi(series, period=14):
    delta = _series(series).diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def atr(frame, period=14):
    high, low, close = (_series(frame[c]) for c in ("High", "Low", "Close"))
    true_range = pd.concat(
        (
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ),
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1 / period, adjust=False).mean()


def relative_volume(frame, period=20):
    volume = _series(frame["Volume"])
    average = volume.rolling(period).mean().iloc[-1]
    return 0.0 if pd.isna(average) or average <= 0 else float(volume.iloc[-1] / average)

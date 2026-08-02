import pandas as pd
import numpy as np
import math
from scipy.stats import norm


# ==========================================
# Exponential Moving Average
# ==========================================

def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


# ==========================================
# Relative Strength Index
# ==========================================

def rsi(series, period=14):

    delta = series.diff()

    gain = delta.where(delta > 0, 0)

    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(period).mean()

    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


# ==========================================
# MACD
# ==========================================

def macd(series):

    ema12 = ema(series, 12)

    ema26 = ema(series, 26)

    macd_line = ema12 - ema26

    signal = ema(macd_line, 9)

    return macd_line, signal


# ==========================================
# ATR
# ==========================================

def atr(df, period=14):

    hl = df["High"] - df["Low"]

    hc = abs(df["High"] - df["Close"].shift())

    lc = abs(df["Low"] - df["Close"].shift())

    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)

    return tr.ewm(alpha=1 / period).mean()

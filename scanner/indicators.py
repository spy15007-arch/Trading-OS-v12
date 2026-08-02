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
    # ==========================================
# VWAP
# ==========================================

def vwap(df):

    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3

    cum_vol = df["Volume"].cumsum()

    cum_tp_vol = (typical_price * df["Volume"]).cumsum()

    return cum_tp_vol / cum_vol


# ==========================================
# Relative Volume
# ==========================================

def relative_volume(df, period=20):

    avg_vol = df["Volume"].rolling(period).mean()

    return float(df["Volume"].iloc[-1] / avg_vol.iloc[-1])


# ==========================================
# Parkinson Volatility
# ==========================================

def parkinson_volatility(df, period=10):

    hl = np.log(df["High"] / df["Low"]) ** 2

    sigma = math.sqrt(
        (1 / (4 * math.log(2))) * hl.tail(period).mean()
    ) * math.sqrt(252)

    if np.isnan(sigma) or sigma == 0:

        ret = np.log(df["Close"] / df["Close"].shift())

        sigma = ret.tail(period).std() * math.sqrt(252)

    if np.isnan(sigma) or sigma == 0:

        sigma = 0.20

    return sigma


# ==========================================
# Lorentzian Distance
# ==========================================

def lorentzian_distance(rsi_value, rvol,
                        ideal_rsi=70,
                        ideal_rvol=2.0):

    d1 = math.log(1 + abs(rsi_value - ideal_rsi))

    d2 = math.log(1 + abs(rvol - ideal_rvol))

    return round(d1 + d2, 3)


# ==========================================
# Black Scholes
# ==========================================

def black_scholes_call(S, K, T, r, sigma):

    if T <= 0 or sigma <= 0:

        intrinsic = max(0, S - K)

        delta = 1 if S > K else 0

        return intrinsic, delta

    d1 = (
        math.log(S / K)
        + (r + 0.5 * sigma ** 2) * T
    ) / (sigma * math.sqrt(T))

    d2 = d1 - sigma * math.sqrt(T)

    premium = (
        S * norm.cdf(d1)
        - K * math.exp(-r * T) * norm.cdf(d2)
    )

    delta = norm.cdf(d1)

    return round(premium, 2), round(delta, 3)
    # ==========================================
# Option Recommendation
# ==========================================

def option_recommendation(price,
                          df,
                          dte=15):

    if price > 5000:

        step = 100

    elif price > 2000:

        step = 50

    elif price > 1000:

        step = 20

    elif price > 500:

        step = 10

    else:

        step = 5

    strike = int(round(price / step) * step)

    sigma = parkinson_volatility(df)

    premium, delta = black_scholes_call(
        price,
        strike,
        dte / 365,
        0.07,
        sigma
    )

    return {

        "Strike": strike,

        "Premium": premium,

        "Delta": delta
    }
    

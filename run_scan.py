import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import math
import time
from scipy.stats import norm
from concurrent.futures import ThreadPoolExecutor

# ==========================================
# Trading OS v12
# Institutional Strict Scanner
# ==========================================

LOOKBACK = "6mo"
INTERVAL = "1d"

EMA_FAST = 20
EMA_SLOW = 50
EMA_LONG = 200

RSI_PERIOD = 14

TOP_RESULTS = 25

MAX_THREADS = 8


# ==========================================
# Session
# ==========================================

def get_session():

    ist = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)

    if ist.hour < 12:
        return "🌅 MORNING STRICT SCAN", "Intraday"

    return "🌙 PRE-CLOSE STRICT SCAN", "BTST"


# ==========================================
# Indicators
# ==========================================

def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def rsi(close, period=14):

    delta = close.diff()

    gain = delta.clip(lower=0)

    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()

    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


def macd(close):

    e12 = ema(close, 12)

    e26 = ema(close, 26)

    m = e12 - e26

    s = m.ewm(span=9, adjust=False).mean()

    return m, s


def atr(df, period=14):

    hl = df.High - df.Low

    hc = abs(df.High - df.Close.shift())

    lc = abs(df.Low - df.Close.shift())

    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)

    return tr.ewm(alpha=1/period).mean()


# ==========================================
# VWAP
# ==========================================

def vwap(df):

    tp = (df.High + df.Low + df.Close) / 3

    return (tp * df.Volume).cumsum() / df.Volume.cumsum()


# ==========================================
# Relative Volume
# ==========================================

def relative_volume(df):

    return df.Volume.iloc[-1] / df.Volume.tail(50).mean()


# ==========================================
# Download
# ==========================================

def download(symbol):

    try:

        df = yf.download(
            symbol,
            period=LOOKBACK,
            interval=INTERVAL,
            progress=False,
            auto_adjust=True,
            threads=False
        )

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        return symbol, df.dropna()

    except:

        return symbol, pd.DataFrame()


def download_all(symbols):

    data = {}

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as ex:

        futures = [ex.submit(download, s) for s in symbols]

        for f in futures:

            s, d = f.result()

            data[s] = d

    return data

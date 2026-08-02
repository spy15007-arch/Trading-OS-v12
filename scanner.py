import math
import time
import datetime
import numpy as np
import pandas as pd
import yfinance as yf

from concurrent.futures import ThreadPoolExecutor, as_completed

from indicators import (
    ema,
    rsi,
    macd,
    atr,
    vwap,
    relative_volume
)

# ==========================================
# SETTINGS
# ==========================================

MIN_HISTORY = 220

ATR_SL = 1.5
ATR_T1 = 1.5
ATR_T2 = 3.0
ATR_T3 = 4.5

MAX_RESULTS = 25

THREADS = 10

# ==========================================
# NSE SYMBOL LIST
# ==========================================

def get_symbols():

    try:

        url = "https://archives.nseindia.com/content/fo/fo_mktlots.csv"

        df = pd.read_csv(url)

        df.columns = [c.strip() for c in df.columns]

        return sorted(
            list(
                set(
                    f"{x.strip()}.NS"
                    for x in df["SYMBOL"]
                )
            )
        )

    except:

        return [
            "RELIANCE.NS",
            "SBIN.NS",
            "ICICIBANK.NS",
            "HDFCBANK.NS",
            "INFY.NS",
            "TCS.NS"
        ]

# ==========================================
# FAST DOWNLOADER
# ==========================================

def download_symbol(symbol):

    try:

        df = yf.download(

            symbol,

            period="1y",

            interval="1d",

            progress=False,

            auto_adjust=True,

            threads=False

        )

        if len(df) < MIN_HISTORY:

            return None

        return symbol, df

    except:

        return None

# ==========================================
# MULTI THREAD DOWNLOAD
# ==========================================

def download_all(symbols):

    results = {}

    with ThreadPoolExecutor(max_workers=THREADS) as executor:

        futures = {

            executor.submit(download_symbol, s): s

            for s in symbols

        }

        for future in as_completed(futures):

            data = future.result()

            if data is None:

                continue

            symbol, df = data

            results[symbol] = df

    return results

import yfinance as yf
import pandas as pd
import time


# ==========================================================
# Download complete NSE F&O list
# ==========================================================

def get_fno_symbols():

    url = "https://archives.nseindia.com/content/fo/fo_mktlots.csv"

    try:

        df = pd.read_csv(url)

        df.columns = [c.strip() for c in df.columns]

        return sorted(
            list(
                set(
                    [
                        f"{s.strip().upper()}.NS"
                        for s in df["SYMBOL"]
                    ]
                )
            )
        )

    except:

        return [
            "RELIANCE.NS",
            "SBIN.NS",
            "HDFCBANK.NS",
            "ICICIBANK.NS",
            "INFY.NS",
            "TCS.NS"
        ]


# ==========================================================
# Download NSE500
# ==========================================================

def get_nse500():

    url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"

    try:

        df = pd.read_csv(url)

        return [
            s.strip().upper()+".NS"
            for s in df["Symbol"]
        ]

    except:

        return get_fno_symbols()


# ==========================================================
# Batch Downloader
# ==========================================================

def download_all(
        tickers,
        period="6mo",
        interval="1d",
        chunk=75):

    database = {}

    total = len(tickers)

    for start in range(0,total,chunk):

        batch = tickers[start:start+chunk]

        try:

            data = yf.download(
                tickers=batch,
                period=period,
                interval=interval,
                group_by="ticker",
                auto_adjust=True,
                threads=True,
                progress=False,
                prepost=False
            )

            if len(batch)==1:

                database[batch[0]] = data.dropna()

            else:

                for ticker in batch:

                    try:

                        df = data[ticker].dropna()

                        if len(df)>50:

                            database[ticker]=df

                    except:
                        pass

        except:
            pass

        time.sleep(0.10)

    return database


# ==========================================================
# Download Index
# ==========================================================

def download_index(symbol):

    try:

        df = yf.download(
            symbol,
            period="3mo",
            interval="1d",
            progress=False,
            auto_adjust=True
        )

        return df.dropna()

    except:

        return pd.DataFrame()


# ==========================================================
# Download One Stock
# ==========================================================

def download_stock(symbol):

    try:

        df = yf.download(
            symbol,
            period="6mo",
            interval="1d",
            progress=False,
            auto_adjust=True
        )

        return df.dropna()

    except:

        return pd.DataFrame()


# ==========================================================
# Download Watchlist
# ==========================================================

def download_watchlist(watchlist):

    return download_all(
        watchlist,
        period="6mo",
        interval="1d",
        chunk=25
    )

"""
Trading OS v12 Professional
Market Data Downloader
"""

import time

import pandas as pd
import yfinance as yf


# ==========================================================
# Clean Yahoo Data
# ==========================================================

def clean_dataframe(df, symbol=None):

    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    # Yahoo may return MultiIndex columns
    if isinstance(df.columns, pd.MultiIndex):

        # If symbol is present, extract it
        if symbol is not None:

            try:

                if symbol in df.columns.get_level_values(-1):

                    df = df.xs(
                        symbol,
                        axis=1,
                        level=-1
                    )

                elif symbol in df.columns.get_level_values(0):

                    df = df.xs(
                        symbol,
                        axis=1,
                        level=0
                    )

            except Exception:
                pass

        # If still MultiIndex, flatten it
        if isinstance(df.columns, pd.MultiIndex):

            df.columns = [
                str(col[0])
                for col in df.columns
            ]

    df.columns = [
        str(col).strip()
        for col in df.columns
    ]

    required = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume"
    ]

    missing = [
        col
        for col in required
        if col not in df.columns
    ]

    if missing:
        return pd.DataFrame()

    df = df[
        required
    ].copy()

    for col in required:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    return df.dropna()


# ==========================================================
# NSE F&O Universe
# ==========================================================

def get_fno_symbols():

    url = (
        "https://archives.nseindia.com/"
        "content/fo/fo_mktlots.csv"
    )

    try:

        df = pd.read_csv(url)

        df.columns = [
            str(c).strip()
            for c in df.columns
        ]

        if "SYMBOL" not in df.columns:
            raise ValueError(
                "SYMBOL column not found"
            )

        symbols = []

        for symbol in df["SYMBOL"]:

            symbol = str(
                symbol
            ).strip().upper()

            if symbol:
                symbols.append(
                    f"{symbol}.NS"
                )

        return sorted(
            list(set(symbols))
        )

    except Exception as e:

        print(
            f"F&O universe download failed: {e}"
        )

        # Safe fallback
        return [
            "RELIANCE.NS",
            "SBIN.NS",
            "HDFCBANK.NS",
            "ICICIBANK.NS",
            "INFY.NS",
            "TCS.NS"
        ]


# ==========================================================
# NSE 500
# ==========================================================

def get_nse750():

    url = (
        "https://archives.nseindia.com/"
        "content/indices/ind_nifty500list.csv"
    )

    try:

        df = pd.read_csv(url)

        symbols = []

        for symbol in df["Symbol"]:

            symbol = str(
                symbol
            ).strip().upper()

            if symbol:
                symbols.append(
                    f"{symbol}.NS"
                )

        return symbols

    except Exception as e:

        print(
            f"NSE500 download failed: {e}"
        )

        return get_fno_symbols()


# ==========================================================
# Download One Symbol
# ==========================================================

def download_stock(
    symbol,
    period="6mo",
    interval="1d"
):

    try:

        df = yf.download(
            symbol,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=True,
            threads=False,
            prepost=False
        )

        return clean_dataframe(
            df,
            symbol
        )

    except Exception as e:

        print(
            f"Download failed {symbol}: {e}"
        )

        return pd.DataFrame()


# ==========================================================
# Batch Downloader
# ==========================================================

def download_all(
    tickers,
    period="6mo",
    interval="1d",
    chunk=50
):

    database = {}

    total = len(tickers)

    print(
        f"Downloading {total} symbols..."
    )

    for start in range(
        0,
        total,
        chunk
    ):

        batch = tickers[
            start:start + chunk
        ]

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

            # Single ticker
            if len(batch) == 1:

                cleaned = clean_dataframe(
                    data,
                    batch[0]
                )

                if len(cleaned) >= 50:
                    database[
                        batch[0]
                    ] = cleaned

            # Multiple tickers
            else:

                for ticker in batch:

                    try:

                        ticker_df = data[
                            ticker
                        ]

                        cleaned = clean_dataframe(
                            ticker_df
                        )

                        if len(cleaned) >= 50:

                            database[
                                ticker
                            ] = cleaned

                    except Exception:
                        continue

        except Exception as e:

            print(
                f"Batch download error: {e}"
            )

        time.sleep(0.20)

        completed = min(
            start + chunk,
            total
        )

        print(
            f"Progress: "
            f"{completed}/{total} | "
            f"Charts: {len(database)}"
        )

    return database


# ==========================================================
# Download Index
# ==========================================================

def download_index(
    symbol,
    period="2y",
    interval="1d"
):

    return download_stock(
        symbol,
        period,
        interval
    )


# ==========================================================
# Watchlist
# ==========================================================

def download_watchlist(
    watchlist
):

    return download_all(
        watchlist,
        period="6mo",
        interval="1d",
        chunk=25
    )

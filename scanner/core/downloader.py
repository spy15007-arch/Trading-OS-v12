"""
trading os v12 professional
broad nse universe downloader

universe:
    up to 1800 nse-listed equity stocks

purpose:
    provide a much broader stock universe for
    strict, aggressive and budget scanners
"""

import time
import requests
import pandas as pd
import yfinance as yf


# ==========================================================
# configuration
# ==========================================================

MAX_UNIVERSE = 1800

DOWNLOAD_CHUNK = 75

REQUEST_TIMEOUT = 20

MIN_HISTORY = 220


# ==========================================================
# headers
# ==========================================================

NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}


# ==========================================================
# helper
# ==========================================================

def clean_symbol(symbol):

    if symbol is None:
        return None

    symbol = str(symbol).strip().upper()

    if not symbol:
        return None

    # remove obvious invalid characters
    if any(
        x in symbol
        for x in [
            " ",
            "/",
            "\\",
            "&",
            "#",
            "%",
            "(",
            ")",
        ]
    ):
        return None

    return symbol


# ==========================================================
# get broad nse universe
# ==========================================================

def get_broad_nse_universe():

    """
    downloads the broad nse equity universe.

    returns up to 1800 usable NSE symbols.

    yfinance format:
        SYMBOL.NS
    """

    urls = [

        # NSE equity master
        "https://archives.nseindia.com/content/equities/EQUITY_L.csv",

        # fallback
        "https://archives.nseindia.com/content/equities/EQUITY_L.csv",

    ]

    symbols = []

    for url in urls:

        try:

            print(
                "Downloading NSE equity universe..."
            )

            response = requests.get(
                url,
                headers=NSE_HEADERS,
                timeout=REQUEST_TIMEOUT
            )

            response.raise_for_status()

            from io import StringIO

            df = pd.read_csv(
                StringIO(
                    response.text
                )
            )

            df.columns = [
                str(c).strip().upper()
                for c in df.columns
            ]

            # --------------------------------------------------
            # find symbol column
            # --------------------------------------------------

            symbol_column = None

            for column in [
                "SYMBOL",
                "SYMBOLS",
            ]:

                if column in df.columns:

                    symbol_column = column
                    break

            if symbol_column is None:
                continue

            for value in df[
                symbol_column
            ].tolist():

                symbol = clean_symbol(
                    value
                )

                if symbol:

                    symbols.append(
                        symbol + ".NS"
                    )

            if symbols:
                break

        except Exception as e:

            print(
                f"NSE universe download failed: {e}"
            )

            continue

    # ======================================================
    # fallback universe
    # ======================================================

    if not symbols:

        print(
            "Using fallback NSE universe."
        )

        symbols = [
            "RELIANCE.NS",
            "HDFCBANK.NS",
            "ICICIBANK.NS",
            "SBIN.NS",
            "INFY.NS",
            "TCS.NS",
            "BHARTIARTL.NS",
            "ITC.NS",
            "LT.NS",
            "AXISBANK.NS",
            "KOTAKBANK.NS",
            "HINDUNILVR.NS",
            "MARUTI.NS",
            "M&M.NS",
            "SUNPHARMA.NS",
            "TITAN.NS",
            "BAJFINANCE.NS",
            "ADANIENT.NS",
            "ADANIPORTS.NS",
            "NTPC.NS",
            "POWERGRID.NS",
            "TATASTEEL.NS",
            "JSWSTEEL.NS",
            "BEL.NS",
            "HAL.NS",
        ]

    # ======================================================
    # remove duplicates
    # ======================================================

    symbols = sorted(
        list(
            set(symbols)
        )
    )

    # ======================================================
    # limit to 1800
    # ======================================================

    symbols = symbols[
        :MAX_UNIVERSE
    ]

    print(
        f"broad nse universe: "
        f"{len(symbols)} symbols"
    )

    return symbols


# ==========================================================
# compatibility function
# ==========================================================

def get_nse500():

    """
    kept for compatibility with the budget scanner.

    IMPORTANT:
    this now returns the broad 1800-stock universe.
    """

    return get_broad_nse_universe()


# ==========================================================
# f&o universe
# ==========================================================

def get_fno_symbols():

    """
    attempts to obtain the NSE F&O universe.

    if NSE blocks the request, automatically falls back
    to the broad 1800-stock universe.
    """

    url = (
        "https://archives.nseindia.com/"
        "content/fo/fo_mktlots.csv"
    )

    try:

        print(
            "Downloading NSE F&O universe..."
        )

        response = requests.get(
            url,
            headers=NSE_HEADERS,
            timeout=REQUEST_TIMEOUT
        )

        response.raise_for_status()

        from io import StringIO

        df = pd.read_csv(
            StringIO(
                response.text
            )
        )

        df.columns = [
            str(c).strip().upper()
            for c in df.columns
        ]

        if "SYMBOL" not in df.columns:
            raise ValueError(
                "SYMBOL column missing"
            )

        symbols = []

        for value in df["SYMBOL"]:

            symbol = clean_symbol(
                value
            )

            if symbol:

                symbols.append(
                    symbol + ".NS"
                )

        symbols = sorted(
            list(
                set(symbols)
            )
        )

        if len(symbols) < 50:

            raise ValueError(
                "F&O universe unexpectedly small"
            )

        print(
            f"F&O universe: "
            f"{len(symbols)} symbols"
        )

        return symbols

    except Exception as e:

        print(
            "F&O universe download failed: "
            f"{e}"
        )

        print(
            "Falling back to broad "
            "1800-stock universe."
        )

        return get_broad_nse_universe()


# ==========================================================
# batch downloader
# ==========================================================

def download_all(
    tickers,
    period="6mo",
    interval="1d",
    chunk=DOWNLOAD_CHUNK
):

    database = {}

    total = len(tickers)

    print(
        f"Downloading {total} symbols..."
    )

    processed = 0

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

                prepost=False,

            )

            # ==================================================
            # single ticker
            # ==================================================

            if len(batch) == 1:

                ticker = batch[0]

                try:

                    df = data.dropna()

                    if len(df) >= 50:

                        database[
                            ticker
                        ] = normalize_dataframe(
                            df
                        )

                except Exception:
                    pass

            # ==================================================
            # multiple tickers
            # ==================================================

            else:

                for ticker in batch:

                    try:

                        df = data[
                            ticker
                        ].dropna()

                        if len(df) >= 50:

                            database[
                                ticker
                            ] = normalize_dataframe(
                                df
                            )

                    except Exception:

                        continue

        except Exception as e:

            print(
                f"batch download error: {e}"
            )

        processed += len(batch)

        print(
            f"Progress: "
            f"{processed}/{total} | "
            f"Charts: {len(database)}"
        )

        # avoid hammering yahoo
        time.sleep(0.20)

    return database


# ==========================================================
# normalize dataframe
# ==========================================================

def normalize_dataframe(df):

    """
    ensures yfinance output has simple columns:
        open
        high
        low
        close
        volume
    """

    if df is None or df.empty:
        return df

    # handle multi-index columns
    if hasattr(
        df.columns,
        "nlevels"
    ):

        if df.columns.nlevels > 1:

            try:

                df.columns = (
                    df.columns
                    .get_level_values(0)
                )

            except Exception:
                pass

    df.columns = [
        str(column).strip().title()
        for column in df.columns
    ]

    required = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    for column in required:

        if column not in df.columns:

            return pd.DataFrame()

    return df.dropna(
        subset=[
            "Close"
        ]
    )


# ==========================================================
# download index
# ==========================================================

def download_index(symbol):

    try:

        df = yf.download(

            symbol,

            period="2y",

            interval="1d",

            progress=False,

            auto_adjust=True,

            threads=False,

        )

        if df is None or df.empty:

            return pd.DataFrame()

        return normalize_dataframe(
            df
        )

    except Exception as e:

        print(
            f"Index download error "
            f"{symbol}: {e}"
        )

        return pd.DataFrame()


# ==========================================================
# download one stock
# ==========================================================

def download_stock(symbol):

    try:

        df = yf.download(

            symbol,

            period="2y",

            interval="1d",

            progress=False,

            auto_adjust=True,

            threads=False,

        )

        if df is None or df.empty:

            return pd.DataFrame()

        df = normalize_dataframe(
            df
        )

        if len(df) < MIN_HISTORY:

            return pd.DataFrame()

        return df

    except Exception as e:

        print(
            f"Stock download error "
            f"{symbol}: {e}"
        )

        return pd.DataFrame()


# ==========================================================
# watchlist
# ==========================================================

def download_watchlist(
    watchlist
):

    return download_all(

        watchlist,

        period="2y",

        interval="1d",

        chunk=25

    )

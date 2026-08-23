"""
Trading OS v12 Professional
Market Data Downloader

Responsibilities
----------------
1. Build a reliable NSE F&O universe.
2. Use multiple NSE sources with fallbacks.
3. Fall back to NIFTY 500 if NSE F&O is temporarily unavailable.
4. Download historical Yahoo Finance data.
5. Handle Yahoo Finance MultiIndex columns.
6. Reject unusable datasets.
7. Provide progress information.

The scanner should NEVER silently reduce the universe
to six hard-coded stocks unless every universe source fails.
"""

import io
import time
import logging

import pandas as pd
import requests
import yfinance as yf


# ==========================================================
# CONFIGURATION
# ==========================================================

NSE_TIMEOUT = 20

DOWNLOAD_CHUNK = 50

MIN_BARS = 220

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/131.0 Safari/537.36"
)

logger = logging.getLogger("TradingOS")


# ==========================================================
# NSE SESSION
# ==========================================================

def _nse_session():

    session = requests.Session()

    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/",
            "Connection": "keep-alive",
        }
    )

    return session


# ==========================================================
# CLEAN SYMBOL
# ==========================================================

def _clean_symbol(symbol):

    if symbol is None:
        return None

    symbol = str(symbol).strip().upper()

    if not symbol:
        return None

    # Remove Yahoo suffix if already present
    symbol = symbol.replace(".NS", "")

    # Remove accidental spaces
    symbol = symbol.replace(" ", "")

    return symbol


# ==========================================================
# CONVERT TO YAHOO SYMBOL
# ==========================================================

def _yahoo_symbol(symbol):

    symbol = _clean_symbol(symbol)

    if not symbol:
        return None

    # Yahoo uses hyphens for some NSE symbols
    symbol = symbol.replace("&", "-")

    return f"{symbol}.NS"


# ==========================================================
# EXTRACT SYMBOL COLUMN
# ==========================================================

def _find_symbol_column(df):

    if df is None or df.empty:
        return None

    candidates = [
        "SYMBOL",
        "Symbol",
        "symbol",
        "UNDERLYING",
        "Underlying",
        "underlying",
        "Underlying Symbol",
        "UNDERLYING_SYMBOL",
    ]

    for column in candidates:

        if column in df.columns:
            return column

    # Case-insensitive search
    for column in df.columns:

        normalized = (
            str(column)
            .strip()
            .upper()
            .replace(" ", "_")
        )

        if normalized in {
            "SYMBOL",
            "UNDERLYING",
            "UNDERLYING_SYMBOL",
        }:

            return column

    return None


# ==========================================================
# PARSE NSE CSV
# ==========================================================

def _parse_nse_csv(content):

    if not content:
        return []

    try:

        df = pd.read_csv(
            io.BytesIO(content),
            low_memory=False
        )

        column = _find_symbol_column(df)

        if column is None:
            return []

        symbols = []

        for value in df[column].tolist():

            symbol = _clean_symbol(value)

            if symbol:
                symbols.append(symbol)

        return sorted(set(symbols))

    except Exception as exc:

        logger.warning(
            f"NSE CSV parsing failed: {exc}"
        )

        return []


# ==========================================================
# SOURCE 1
# NSE LIST OF UNDERLYINGS
# ==========================================================

def _get_nse_underlyings():

    url = (
        "https://www.nseindia.com/"
        "api/equity-stockIndices"
        "?index=NIFTY%20500"
    )

    try:

        session = _nse_session()

        # Establish NSE session first
        session.get(
            "https://www.nseindia.com/",
            timeout=NSE_TIMEOUT
        )

        response = session.get(
            url,
            timeout=NSE_TIMEOUT
        )

        if response.status_code != 200:
            return []

        payload = response.json()

        data = payload.get("data", [])

        symbols = []

        for item in data:

            symbol = _clean_symbol(
                item.get("symbol")
            )

            if symbol:
                symbols.append(symbol)

        return sorted(set(symbols))

    except Exception as exc:

        logger.warning(
            f"NSE API universe failed: {exc}"
        )

        return []


# ==========================================================
# SOURCE 2
# NSE F&O CONTRACT FILE
# ==========================================================

def _get_nse_fo_contracts():

    urls = [

        # Current NSE contract information
        (
            "https://archives.nseindia.com/"
            "content/fo/NSE_FO_contract_"
        ),

        # Legacy market-lot file
        (
            "https://archives.nseindia.com/"
            "content/fo/fo_mktlots.csv"
        ),
    ]

    # ------------------------------------------------------
    # Legacy CSV
    # ------------------------------------------------------

    try:

        session = _nse_session()

        response = session.get(
            urls[1],
            timeout=NSE_TIMEOUT
        )

        if response.status_code == 200:

            symbols = _parse_nse_csv(
                response.content
            )

            if len(symbols) > 50:

                logger.info(
                    f"NSE F&O CSV returned "
                    f"{len(symbols)} symbols."
                )

                return symbols

    except Exception as exc:

        logger.warning(
            f"NSE F&O CSV failed: {exc}"
        )

    return []


# ==========================================================
# SOURCE 3
# NIFTY 500
# ==========================================================

def _get_nifty500():

    urls = [

        (
            "https://archives.nseindia.com/"
            "content/indices/ind_nifty500list.csv"
        ),

        (
            "https://www.niftyindices.com/"
            "IndexConstituent/ind_nifty500list.csv"
        ),
    ]

    for url in urls:

        try:

            session = _nse_session()

            response = session.get(
                url,
                timeout=NSE_TIMEOUT
            )

            if response.status_code != 200:
                continue

            symbols = _parse_nse_csv(
                response.content
            )

            if len(symbols) > 100:

                logger.info(
                    f"NIFTY 500 returned "
                    f"{len(symbols)} symbols."
                )

                return symbols

        except Exception as exc:

            logger.warning(
                f"NIFTY 500 source failed: {exc}"
            )

    return []


# ==========================================================
# SOURCE 4
# BROAD FALLBACK UNIVERSE
# ==========================================================

def _fallback_universe():

    return [

        "ABB",
        "ADANIENSOL",
        "ADANIENT",
        "ADANIGREEN",
        "ADANIPORTS",
        "AMBUJACEM",
        "APOLLOHOSP",
        "ASIANPAINT",
        "AXISBANK",
        "BAJAJ-AUTO",
        "BAJAJFINSV",
        "BAJFINANCE",
        "BANKBARODA",
        "BEL",
        "BHARTIARTL",
        "BHEL",
        "BPCL",
        "BRITANNIA",
        "CANBK",
        "CHOLAFIN",
        "CIPLA",
        "COALINDIA",
        "COFORGE",
        "COLPAL",
        "CONCOR",
        "CUMMINSIND",
        "DABUR",
        "DIVISLAB",
        "DLF",
        "DMART",
        "DRREDDY",
        "EICHERMOT",
        "ETERNAL",
        "EXIDEIND",
        "FEDERALBNK",
        "GAIL",
        "GODREJCP",
        "GODREJPROP",
        "GRASIM",
        "HAL",
        "HAVELLS",
        "HCLTECH",
        "HDFCBANK",
        "HDFCLIFE",
        "HEROMOTOCO",
        "HINDALCO",
        "HINDPETRO",
        "HINDUNILVR",
        "ICICIBANK",
        "ICICIGI",
        "ICICIPRULI",
        "IDEA",
        "INDHOTEL",
        "INDIAMART",
        "INDIGO",
        "INDUSINDBK",
        "INFY",
        "IOC",
        "IRCTC",
        "ITC",
        "JINDALSTEL",
        "JSWENERGY",
        "JSWSTEEL",
        "JUBLFOOD",
        "KOTAKBANK",
        "LICHSGFIN",
        "LICI",
        "LT",
        "LTIM",
        "LUPIN",
        "M&M",
        "MANAPPURAM",
        "MARICO",
        "MARUTI",
        "MAXHEALTH",
        "MCX",
        "MGL",
        "MOTHERSON",
        "MPHASIS",
        "MRF",
        "MUTHOOTFIN",
        "NATIONALUM",
        "NAUKRI",
        "NESTLEIND",
        "NMDC",
        "NTPC",
        "OBEROIRLTY",
        "OFSS",
        "ONGC",
        "PAGEIND",
        "PEL",
        "PERSISTENT",
        "PETRONET",
        "PFC",
        "PIDILITIND",
        "PIIND",
        "PNB",
        "POLYCAB",
        "POWERGRID",
        "POWERINDIA",
        "PVRINOX",
        "RAMCOCEM",
        "RECLTD",
        "RELIANCE",
        "SAIL",
        "SBICARD",
        "SBILIFE",
        "SBIN",
        "SHREECEM",
        "SHRIRAMFIN",
        "SIEMENS",
        "SRF",
        "SUNPHARMA",
        "SUPREMEIND",
        "TATACHEM",
        "TATACONSUM",
        "TATAELXSI",
        "TATAMOTORS",
        "TATAPOWER",
        "TATASTEEL",
        "TCS",
        "TECHM",
        "TIINDIA",
        "TORNTPHARM",
        "TRENT",
        "TVSMOTOR",
        "UBL",
        "ULTRACEMCO",
        "UNIONBANK",
        "UPL",
        "VEDL",
        "VOLTAS",
        "WIPRO",
        "YESBANK",
        "ZOMATO",
    ]

# ==========================================================
# PUBLIC F&O UNIVERSE
# ==========================================================

def get_fno_symbols():

    logger.info(
        "Building NSE F&O universe..."
    )

    # ------------------------------------------------------
    # Attempt 1: NSE F&O CSV
    # ------------------------------------------------------

    symbols = _get_nse_fo_contracts()

    if len(symbols) >= 50:

        yahoo_symbols = sorted(
            set(
                _yahoo_symbol(s)
                for s in symbols
                if _yahoo_symbol(s)
            )
        )

        logger.info(
            f"F&O universe loaded: "
            f"{len(yahoo_symbols)} symbols"
        )

        return yahoo_symbols

    # ------------------------------------------------------
    # Attempt 2: NIFTY 500
    #
    # This is deliberately broad rather than six stocks.
    # ------------------------------------------------------

    logger.warning(
        "NSE F&O universe unavailable."
    )

    logger.warning(
        "Using NIFTY 500 fallback universe."
    )

    symbols = _get_nifty500()

    if len(symbols) >= 100:

        yahoo_symbols = sorted(
            set(
                _yahoo_symbol(s)
                for s in symbols
                if _yahoo_symbol(s)
            )
        )

        logger.info(
            f"NIFTY 500 fallback loaded: "
            f"{len(yahoo_symbols)} symbols"
        )

        return yahoo_symbols

    # ------------------------------------------------------
    # Attempt 3: Broad hard-coded universe
    # ------------------------------------------------------

    logger.warning(
        "NIFTY 500 unavailable."
    )

    symbols = _fallback_universe()

    yahoo_symbols = sorted(
        set(
            _yahoo_symbol(s)
            for s in symbols
            if _yahoo_symbol(s)
        )
    )

    logger.warning(
        f"Using emergency universe: "
        f"{len(yahoo_symbols)} symbols"
    )

    return yahoo_symbols


# ==========================================================
# GET NIFTY 500
# ==========================================================

def get_nse500():

    symbols = _get_nifty500()

    if len(symbols) < 100:

        logger.warning(
            "NIFTY 500 download unavailable. "
            "Using broad fallback."
        )

        symbols = _fallback_universe()

    return sorted(
        set(
            _yahoo_symbol(s)
            for s in symbols
            if _yahoo_symbol(s)
        )
    )


# ==========================================================
# NORMALIZE YAHOO DATAFRAME
# ==========================================================

def _normalize_dataframe(
    df,
    ticker=None
):

    if df is None or df.empty:
        return pd.DataFrame()

    try:

        # --------------------------------------------------
        # Yahoo Finance MultiIndex
        # --------------------------------------------------

        if isinstance(df.columns, pd.MultiIndex):

            # Case:
            # Price -> Ticker

            if ticker is not None:

                try:

                    if ticker in df.columns.get_level_values(
                        -1
                    ):

                        df = df.xs(
                            ticker,
                            axis=1,
                            level=-1
                        )

                except Exception:
                    pass

            # If still MultiIndex, flatten it
            if isinstance(
                df.columns,
                pd.MultiIndex
            ):

                df.columns = [
                    str(col[0])
                    for col in df.columns
                ]

        # --------------------------------------------------
        # Standardize column names
        # --------------------------------------------------

        rename = {}

        for column in df.columns:

            name = str(column).strip().lower()

            if name == "open":
                rename[column] = "Open"

            elif name == "high":
                rename[column] = "High"

            elif name == "low":
                rename[column] = "Low"

            elif name == "close":
                rename[column] = "Close"

            elif name == "adj close":
                rename[column] = "Adj Close"

            elif name == "volume":
                rename[column] = "Volume"

        df = df.rename(
            columns=rename
        )

        required = [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]

        if not all(
            column in df.columns
            for column in required
        ):

            return pd.DataFrame()

        df = df[
            required
        ].copy()

        # --------------------------------------------------
        # Numeric conversion
        # --------------------------------------------------

        for column in required:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

        df = df.dropna()

        # --------------------------------------------------
        # Remove invalid zero volume rows
        # --------------------------------------------------

        df = df[
            df["Volume"] > 0
        ]

        return df

    except Exception as exc:

        logger.warning(
            f"Dataframe normalization failed: "
            f"{exc}"
        )

        return pd.DataFrame()


# ==========================================================
# DOWNLOAD ONE STOCK
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

            prepost=False,

        )

        df = _normalize_dataframe(
            df,
            ticker=symbol
        )

        if len(df) < MIN_BARS:

            return pd.DataFrame()

        return df

    except Exception as exc:

        logger.warning(
            f"{symbol}: download failed: {exc}"
        )

        return pd.DataFrame()


# ==========================================================
# BATCH DOWNLOAD
# ==========================================================

def download_all(
    tickers,
    period="6mo",
    interval="1d",
    chunk=DOWNLOAD_CHUNK
):

    database = {}

    tickers = list(
        dict.fromkeys(tickers)
    )

    total = len(tickers)

    logger.info(
        f"Downloading {total} symbols..."
    )

    downloaded = 0

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

            # --------------------------------------------------
            # Single ticker
            # --------------------------------------------------

            if len(batch) == 1:

                ticker = batch[0]

                df = _normalize_dataframe(
                    data,
                    ticker=ticker
                )

                if len(df) >= MIN_BARS:

                    database[ticker] = df

                    downloaded += 1

            # --------------------------------------------------
            # Multiple tickers
            # --------------------------------------------------

            else:

                for ticker in batch:

                    try:

                        if isinstance(
                            data.columns,
                            pd.MultiIndex
                        ):

                            # Most common Yahoo layout
                            try:

                                df = data[
                                    ticker
                                ].copy()

                            except Exception:

                                try:

                                    df = data.xs(
                                        ticker,
                                        axis=1,
                                        level=1
                                    ).copy()

                                except Exception:

                                    df = pd.DataFrame()

                        else:

                            df = data.copy()

                        df = _normalize_dataframe(
                            df,
                            ticker=ticker
                        )

                        if len(df) >= MIN_BARS:

                            database[
                                ticker
                            ] = df

                            downloaded += 1

                    except Exception:
                        continue

        except Exception as exc:

            logger.warning(
                f"Batch download failed "
                f"({start + 1}-{min(start + chunk, total)}): "
                f"{exc}"
            )

            # --------------------------------------------------
            # Individual retry
            # --------------------------------------------------

            logger.info(
                "Retrying failed batch individually..."
            )

            for ticker in batch:

                df = download_stock(
                    ticker,
                    period=period,
                    interval=interval
                )

                if not df.empty:

                    database[ticker] = df

                    downloaded += 1

                time.sleep(0.05)

        logger.info(
            f"Progress: "
            f"{min(start + chunk, total)}/{total} "
            f"| Charts: {len(database)}"
        )

        time.sleep(0.10)

    logger.info(
        f"Download complete: "
        f"{len(database)} usable charts"
    )

    return database


# ==========================================================
# DOWNLOAD INDEX
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

            prepost=False,

        )

        return _normalize_dataframe(
            df,
            ticker=symbol
        )

    except Exception as exc:

        logger.warning(
            f"Index download failed "
            f"{symbol}: {exc}"
        )

        return pd.DataFrame()


# ==========================================================
# WATCHLIST
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

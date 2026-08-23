"""
Trading OS v12 Professional
Market Data Downloader

Responsibilities:
    - NSE equity universe
    - 1800-stock scanning universe
    - Yahoo Finance historical data
    - NIFTY / BANK NIFTY index data
"""

import time
import logging

import pandas as pd
import yfinance as yf


logger = logging.getLogger(
    "TradingOS"
)


# ==========================================================
# CONFIGURATION
# ==========================================================

DEFAULT_PERIOD = "6mo"
DEFAULT_INTERVAL = "1d"

INDEX_PERIOD = "2y"
INDEX_INTERVAL = "1d"

DOWNLOAD_CHUNK = 75


# ==========================================================
# CLEAN YAHOO DATA
# ==========================================================

def clean_dataframe(
    df,
    symbol=None
):

    if df is None or df.empty:

        return pd.DataFrame()

    try:

        # --------------------------------------------------
        # Flatten Yahoo MultiIndex
        # --------------------------------------------------

        if isinstance(
            df.columns,
            pd.MultiIndex
        ):

            # Case: ticker is level 1
            if (
                symbol is not None and
                symbol in df.columns
                    .get_level_values(-1)
            ):

                try:

                    df = df.xs(
                        symbol,
                        axis=1,
                        level=-1
                    )

                except Exception:
                    pass

            # Still MultiIndex
            if isinstance(
                df.columns,
                pd.MultiIndex
            ):

                df.columns = (
                    df.columns
                    .get_level_values(0)
                )

        # --------------------------------------------------
        # Standardise columns
        # --------------------------------------------------

        df.columns = [
            str(c).strip()
            for c in df.columns
        ]

        required = [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume"
        ]

        missing = [
            c
            for c in required
            if c not in df.columns
        ]

        if missing:

            return pd.DataFrame()

        df = df[
            required
        ].copy()

        df = df.apply(
            pd.to_numeric,
            errors="coerce"
        )

        df = df.dropna()

        return df

    except Exception:

        return pd.DataFrame()


# ==========================================================
# DOWNLOAD INDEX
# ==========================================================

def download_index(
    symbol,
    period=INDEX_PERIOD,
    interval=INDEX_INTERVAL
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

        df = clean_dataframe(
            df,
            symbol
        )

        return df

    except Exception as e:

        logger.warning(
            f"Index download failed "
            f"for {symbol}: {e}"
        )

        return pd.DataFrame()


# ==========================================================
# DOWNLOAD ONE STOCK
# ==========================================================

def download_stock(
    symbol,
    period=DEFAULT_PERIOD,
    interval=DEFAULT_INTERVAL
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

        logger.warning(
            f"{symbol}: {e}"
        )

        return pd.DataFrame()


# ==========================================================
# NSE EQUITY UNIVERSE
# ==========================================================

def get_nse_equity_universe():

    logger.info(
        "Downloading NSE equity universe..."
    )

    urls = [

        (
            "https://archives.nseindia.com/"
            "content/equities/"
            "EQUITY_L.csv"
        ),

        (
            "https://archives.nseindia.com/"
            "content/equities/"
            "EQ_ISINCODE_2026.csv"
        )
    ]

    for url in urls:

        try:

            df = pd.read_csv(
                url,
                timeout=30
            )

            df.columns = [
                str(c).strip().upper()
                for c in df.columns
            ]

            symbol_column = None

            for candidate in [
                "SYMBOL",
                "SYMBOLS",
                "TICKER"
            ]:

                if candidate in df.columns:

                    symbol_column = candidate
                    break

            if symbol_column is None:

                continue

            symbols = []

            for symbol in df[
                symbol_column
            ].dropna():

                symbol = str(
                    symbol
                ).strip().upper()

                if not symbol:
                    continue

                if (
                    symbol.startswith(
                        "20"
                    )
                ):
                    continue

                symbols.append(
                    f"{symbol}.NS"
                )

            symbols = sorted(
                list(
                    set(symbols)
                )
            )

            if len(symbols) >= 500:

                logger.info(
                    f"NSE universe: "
                    f"{len(symbols)} symbols"
                )

                return symbols

        except Exception as e:

            logger.warning(
                f"NSE universe source "
                f"failed: {e}"
            )

    return []


# ==========================================================
# 1800-STOCK UNIVERSE
# ==========================================================

def get_broad_universe(
    limit=1800
):

    symbols = (
        get_nse_equity_universe()
    )

    if not symbols:

        logger.warning(
            "NSE equity universe unavailable."
        )

        return []

    # Remove common non-trading / ETF-like
    # symbols where possible.

    blacklist = {

        "NIFTYBEES.NS",
        "BANKBEES.NS",
        "JUNIORBEES.NS",
        "GOLDBEES.NS",
        "LIQUIDBEES.NS",
        "ITBEES.NS",
        "PHARMABEES.NS",
        "CPSEETF.NS",
        "MON100.NS",
        "SETFNIF50.NS",

    }

    symbols = [
        s
        for s in symbols
        if s not in blacklist
    ]

    # Deterministic universe.
    # This keeps the scanner at the
    # requested 1800-stock level.

    symbols = symbols[
        :limit
    ]

    logger.info(
        f"Broad NSE universe: "
        f"{len(symbols)} symbols"
    )

    return symbols


# ==========================================================
# NSE 500
# ==========================================================

def get_nse500():

    url = (
        "https://archives.nseindia.com/"
        "content/indices/"
        "ind_nifty500list.csv"
    )

    try:

        df = pd.read_csv(
            url
        )

        df.columns = [
            str(c).strip()
            for c in df.columns
        ]

        symbols = [

            f"{str(s).strip().upper()}.NS"

            for s in df["Symbol"].dropna()

        ]

        return sorted(
            list(
                set(symbols)
            )
        )

    except Exception as e:

        logger.warning(
            f"NIFTY 500 download failed: "
            f"{e}"
        )

        return get_broad_universe(
            500
        )


# ==========================================================
# F&O UNIVERSE
# ==========================================================

def get_fno_symbols():

    url = (
        "https://archives.nseindia.com/"
        "content/fo/"
        "fo_mktlots.csv"
    )

    try:

        df = pd.read_csv(
            url
        )

        df.columns = [
            str(c).strip().upper()
            for c in df.columns
        ]

        if "SYMBOL" not in df.columns:

            raise ValueError(
                "SYMBOL column not found"
            )

        symbols = [

            f"{str(s).strip().upper()}.NS"

            for s in df[
                "SYMBOL"
            ].dropna()

        ]

        return sorted(
            list(
                set(symbols)
            )
        )

    except Exception as e:

        logger.warning(
            "F&O universe download failed: "
            f"{e}"
        )

        return []


# ==========================================================
# BATCH DOWNLOADER
# ==========================================================

def download_all(
    tickers,
    period=DEFAULT_PERIOD,
    interval=DEFAULT_INTERVAL,
    chunk=DOWNLOAD_CHUNK
):

    database = {}

    tickers = list(
        dict.fromkeys(
            tickers
        )
    )

    total = len(
        tickers
    )

    logger.info(
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

            # --------------------------------------------------
            # Single ticker
            # --------------------------------------------------

            if len(batch) == 1:

                ticker = batch[0]

                df = clean_dataframe(
                    data,
                    ticker
                )

                if len(df) >= 50:

                    database[
                        ticker
                    ] = df

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

                            if ticker not in (
                                data.columns
                                .get_level_values(0)
                            ):

                                if ticker not in (
                                    data.columns
                                    .get_level_values(1)
                                ):

                                    continue

                            try:

                                df = data[
                                    ticker
                                ]

                            except Exception:

                                df = data.xs(
                                    ticker,
                                    axis=1,
                                    level=1
                                )

                        else:

                            df = data

                        df = clean_dataframe(
                            df,
                            ticker
                        )

                        if len(df) >= 50:

                            database[
                                ticker
                            ] = df

                    except Exception:

                        continue

        except Exception as e:

            logger.warning(
                f"Batch download failed "
                f"{start + 1}-"
                f"{min(start + chunk, total)}: "
                f"{e}"
            )

        completed = min(
            start + chunk,
            total
        )

        logger.info(
            f"Progress: "
            f"{completed}/{total} | "
            f"Charts: {len(database)}"
        )

        time.sleep(
            0.10
        )

    return database


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

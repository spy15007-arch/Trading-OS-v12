"""NSE universe and robust Yahoo Finance download functions."""
import logging
import time

import pandas as pd
import yfinance as yf


logger = logging.getLogger("TradingOS")

DEFAULT_PERIOD = "6mo"
DEFAULT_INTERVAL = "1d"

INDEX_PERIOD = "2y"
INDEX_INTERVAL = "1d"

MIN_STOCK_BARS = 110
DOWNLOAD_CHUNK = 75

_BLACKLIST = {
    "NIFTYBEES.NS",
    "BANKBEES.NS",
    "GOLDBEES.NS",
    "LIQUIDBEES.NS",
    "JUNIORBEES.NS",
    "MON100.NS",
}

_FALLBACK = (
    "RELIANCE TCS HDFCBANK ICICIBANK INFY ITC SBIN BHARTIARTL LT "
    "AXISBANK KOTAKBANK HINDUNILVR BAJFINANCE MARUTI SUNPHARMA "
    "TATAMOTORS TATASTEEL M&M NTPC POWERGRID"
).split()


def normalise_symbol(symbol):
    if symbol is None:
        return None

    value = str(symbol).strip().upper()

    if value.endswith(".NS"):
        value = value[:-3]

    if not value or value in {"SYMBOL", "NAN", "NONE", "NULL", "N/A"}:
        return None

    return value + ".NS"


def clean_dataframe(frame, symbol=None):
    """Return numeric OHLCV data from either Yahoo column arrangement."""
    if frame is None or frame.empty:
        return pd.DataFrame()

    data = frame.copy()

    try:
        if isinstance(data.columns, pd.MultiIndex):
            for level in range(data.columns.nlevels):
                if symbol in data.columns.get_level_values(level):
                    data = data.xs(symbol, axis=1, level=level)
                    break

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        data.columns = [str(column).strip().title() for column in data.columns]

        required = ["Open", "High", "Low", "Close"]

        if any(column not in data.columns for column in required):
            return pd.DataFrame()

        if "Volume" not in data.columns:
            data["Volume"] = 0

        data = data[required + ["Volume"]]
        data = data.apply(pd.to_numeric, errors="coerce").dropna()

        return data[~data.index.duplicated(keep="last")].sort_index()

    except Exception:
        return pd.DataFrame()


def _download(symbols, period, interval, group_by="ticker"):
    return yf.download(
        symbols,
        period=period,
        interval=interval,
        group_by=group_by,
        auto_adjust=True,
        progress=False,
        threads=True,
        prepost=False,
    )


def download_index(symbol, period=INDEX_PERIOD, interval=INDEX_INTERVAL):
    """Download index data; accepts period to avoid the former mismatch."""
    try:
        return clean_dataframe(
            _download(symbol, period, interval),
            symbol,
        )

    except Exception as exc:
        logger.warning("Index download failed for %s: %s", symbol, exc)
        return pd.DataFrame()


def download_stock(symbol, period=DEFAULT_PERIOD, interval=DEFAULT_INTERVAL):
    ticker = normalise_symbol(symbol)

    if not ticker:
        return pd.DataFrame()

    try:
        return clean_dataframe(
            _download(ticker, period, interval),
            ticker,
        )

    except Exception as exc:
        logger.warning("Download failed for %s: %s", ticker, exc)
        return pd.DataFrame()


def get_broad_universe(limit=1800):
    """Get listed NSE equities, capped at the requested broad universe."""
    urls = [
        "https://archives.nseindia.com/content/equities/EQUITY_L.csv",
        "https://archives.nseindia.com/content/indices/ind_nifty500list.csv",
    ]

    symbols = []

    for url in urls:
        try:
            frame = pd.read_csv(url)

            column = next(
                (
                    column
                    for column in frame.columns
                    if str(column).strip().upper() == "SYMBOL"
                ),
                None,
            )

            if column:
                symbols = [normalise_symbol(value) for value in frame[column].tolist()]
                symbols = sorted(
                    {
                        value
                        for value in symbols
                        if value and value not in _BLACKLIST
                    }
                )

                if len(symbols) >= 500:
                    break

        except Exception as exc:
            logger.warning("Universe source unavailable: %s", exc)

    if not symbols:
        logger.warning(
            "Using small built-in fallback universe; NSE list was unavailable."
        )
        symbols = [normalise_symbol(symbol) for symbol in _FALLBACK]

    return symbols[:int(limit)]


def get_nse_universe(limit=1800):
    return get_broad_universe(limit)


def get_nse500():
    return get_broad_universe(500)


def get_fno_symbols():
    """Legacy compatibility alias; v12 scanners use the broad universe."""
    return get_broad_universe(1800)


def _extract_batch(raw, ticker):
    if not isinstance(raw.columns, pd.MultiIndex):
        return raw

    for level in range(raw.columns.nlevels):
        if ticker in raw.columns.get_level_values(level):
            return raw.xs(ticker, axis=1, level=level)

    return pd.DataFrame()


def download_all(
    tickers,
    period=DEFAULT_PERIOD,
    interval=DEFAULT_INTERVAL,
    chunk=DOWNLOAD_CHUNK,
):
    symbols = list(
        dict.fromkeys(
            symbol
            for symbol in (normalise_symbol(ticker) for ticker in tickers)
            if symbol
        )
    )

    database = {}
    total = len(symbols)

    logger.info(
        "Downloading %d NSE symbols (%s, %s).",
        total,
        period,
        interval,
    )

    for start in range(0, total, int(chunk)):
        batch = symbols[start:start + int(chunk)]

        try:
            raw = _download(batch, period, interval)

            for ticker in batch:
                frame = clean_dataframe(
                    _extract_batch(raw, ticker),
                    ticker,
                )

                if len(frame) >= MIN_STOCK_BARS:
                    database[ticker] = frame

        except Exception as exc:
            logger.warning(
                "Batch %d-%d failed: %s",
                start + 1,
                start + len(batch),
                exc,
            )

            for ticker in batch:
                frame = download_stock(ticker, period, interval)

                if len(frame) >= MIN_STOCK_BARS:
                    database[ticker] = frame

        logger.info(
            "Downloaded %d/%d; usable charts: %d",
            min(start + len(batch), total),
            total,
            len(database),
        )

        time.sleep(0.1)

    return database

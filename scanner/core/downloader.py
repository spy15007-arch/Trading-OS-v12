"""Reliable, rate-limit-aware Yahoo Finance downloader for Trading OS v12."""

from __future__ import annotations

import io
import time
from typing import Dict, Iterable, Optional

import pandas as pd
import requests
import yfinance as yf

NIFTY50_URL = "https://www.niftyindices.com/IndexConstituent/ind_nifty50list.csv"
NIFTY_NEXT50_URL = "https://www.niftyindices.com/IndexConstituent/ind_niftynext50list.csv"

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/126.0 Safari/537.36"
    ),
    "Accept": "text/csv,text/plain,*/*",
    "Referer": "https://www.niftyindices.com/",
}

OHLCV = ("Open", "High", "Low", "Close", "Volume")


def _clean_symbol(value) -> Optional[str]:
    symbol = str(value).strip().upper()

    if not symbol or symbol in {"NAN", "NONE", "NULL"}:
        return None

    return symbol.removesuffix(".NS")


def _read_constituents(url: str) -> list[str]:
    response = requests.get(
        url,
        headers=HTTP_HEADERS,
        timeout=25,
    )
    response.raise_for_status()

    if not response.content:
        raise RuntimeError(f"Empty response from {url}")

    frame = pd.read_csv(io.BytesIO(response.content))

    symbol_col = next(
        (
            column
            for column in frame.columns
            if str(column).strip().upper() == "SYMBOL"
        ),
        None,
    )

    if symbol_col is None:
        raise RuntimeError(f"SYMBOL column missing from {url}")

    symbols = [_clean_symbol(value) for value in frame[symbol_col].tolist()]

    return list(
        dict.fromkeys(
            f"{symbol}.NS"
            for symbol in symbols
            if symbol
        )
    )


def get_nifty50_next50_symbols() -> list[str]:
    """Return the official Nifty 50 + Nifty Next 50 universe.

    Fails closed if either constituent file cannot be loaded. It does not
    silently substitute a partial or broad NSE universe.
    """
    print("Loading official Nifty 50 and Nifty Next 50 constituents...")

    nifty50 = _read_constituents(NIFTY50_URL)
    next50 = _read_constituents(NIFTY_NEXT50_URL)

    if not 45 <= len(nifty50) <= 55:
        raise RuntimeError(
            f"Unexpected Nifty 50 constituent count: {len(nifty50)}"
        )

    if not 45 <= len(next50) <= 55:
        raise RuntimeError(
            f"Unexpected Nifty Next 50 constituent count: {len(next50)}"
        )

    symbols = list(dict.fromkeys(nifty50 + next50))

    if not 90 <= len(symbols) <= 110:
        raise RuntimeError(
            f"Unexpected combined universe count: {len(symbols)}"
        )

    print(
        f"Universe loaded: {len(nifty50)} Nifty 50 + "
        f"{len(next50)} Next 50; {len(symbols)} unique symbols"
    )

    return symbols


def get_nse_equity_symbols(limit: int = 1800) -> list[str]:
    """Compatibility alias; returns the Nifty 100 universe for this project."""
    symbols = get_nifty50_next50_symbols()
    return symbols[:limit] if limit else symbols


def get_fno_symbols() -> list[str]:
    return get_nifty50_next50_symbols()


def get_nse500() -> list[str]:
    """Compatibility function; Trading OS v12 uses the Nifty 100 universe."""
    return get_nifty50_next50_symbols()


def _normalise_yf(
    frame: pd.DataFrame,
    ticker: Optional[str] = None,
) -> pd.DataFrame:
    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
        return pd.DataFrame()

    df = frame.copy()

    if isinstance(df.columns, pd.MultiIndex):
        # yfinance may return (Ticker, Price) or (Price, Ticker).
        if ticker:
            ticker_variants = {
                ticker,
                ticker.upper(),
                ticker.replace(".NS", ""),
                ticker.replace(".NS", "").upper(),
            }

            for level in range(df.columns.nlevels):
                values = {
                    str(value)
                    for value in df.columns.get_level_values(level)
                }

                match = next(
                    (value for value in ticker_variants if value in values),
                    None,
                )

                if match is not None:
                    try:
                        df = df.xs(
                            match,
                            axis=1,
                            level=level,
                            drop_level=True,
                        )
                        break
                    except (KeyError, ValueError, TypeError):
                        pass

        if isinstance(df.columns, pd.MultiIndex):
            flattened = []
            known = {field.lower(): field for field in OHLCV}

            for column in df.columns:
                parts = [
                    str(part).strip()
                    for part in (
                        column if isinstance(column, tuple) else (column,)
                    )
                ]

                field = next(
                    (
                        known[part.lower()]
                        for part in parts
                        if part.lower() in known
                    ),
                    parts[0],
                )

                flattened.append(field)

            df.columns = flattened

    rename = {}
    known = {field.lower(): field for field in OHLCV}

    for column in df.columns:
        name = str(column).strip()

        if name.lower() in known:
            rename[column] = known[name.lower()]

    df = df.rename(columns=rename)
    df = df.loc[:, ~df.columns.duplicated(keep="first")]

    if not all(column in df.columns for column in OHLCV):
        return pd.DataFrame()

    df = df.loc[:, list(OHLCV)].copy()

    for column in OHLCV:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df.dropna(
        subset=["Open", "High", "Low", "Close", "Volume"]
    )

    return df.sort_index() if not df.empty else pd.DataFrame()


def _download_batch(
    batch: list[str],
    period: str,
    interval: str,
) -> dict[str, pd.DataFrame]:
    """Download a small batch, retrying transient errors."""
    last_error = None

    for attempt in range(3):
        try:
            raw = yf.download(
                tickers=batch,
                period=period,
                interval=interval,
                group_by="ticker",
                auto_adjust=True,
                threads=False,
                progress=False,
                prepost=False,
                timeout=30,
            )

            output: dict[str, pd.DataFrame] = {}

            for ticker in batch:
                frame = None

                if isinstance(raw, pd.DataFrame):
                    if isinstance(raw.columns, pd.MultiIndex):
                        for level in range(raw.columns.nlevels):
                            values = {
                                str(value)
                                for value in raw.columns.get_level_values(level)
                            }

                            if ticker in values:
                                try:
                                    frame = raw.xs(
                                        ticker,
                                        axis=1,
                                        level=level,
                                        drop_level=True,
                                    )
                                    break
                                except Exception:
                                    pass

                    elif len(batch) == 1:
                        frame = raw

                normalized = _normalise_yf(frame, ticker)

                if len(normalized) >= 220:
                    output[ticker] = normalized

            return output

        except Exception as exc:
            last_error = exc
            message = str(exc).lower()

            if "rate" in message or "429" in message or "too many" in message:
                wait = 5 * (2 ** attempt)
            else:
                wait = 2 * (attempt + 1)

            print(
                f"Download attempt {attempt + 1}/3 failed "
                f"for batch of {len(batch)}: {exc}"
            )

            if attempt < 2:
                time.sleep(wait)

    print(f"Batch abandoned after retries: {last_error}")
    return {}


def download_all(
    tickers: Iterable[str],
    period: str = "1y",
    interval: str = "1d",
    chunk: int = 10,
) -> Dict[str, pd.DataFrame]:
    """Download symbols in serial batches to reduce Yahoo Finance throttling."""
    cleaned = list(
        dict.fromkeys(
            str(ticker).strip()
            for ticker in (tickers or [])
            if str(ticker).strip()
        )
    )

    if not cleaned:
        print("No tickers supplied for download.")
        return {}

    chunk = max(1, min(int(chunk or 10), 15))
    results: Dict[str, pd.DataFrame] = {}

    print(
        f"Downloading {len(cleaned)} symbols "
        f"in serial batches of up to {chunk}..."
    )

    for start in range(0, len(cleaned), chunk):
        batch = cleaned[start:start + chunk]
        batch_data = _download_batch(batch, period, interval)
        results.update(batch_data)

        print(
            f"Progress: {min(start + len(batch), len(cleaned))}/"
            f"{len(cleaned)} | Valid charts: {len(results)}"
        )

        if start + chunk < len(cleaned):
            time.sleep(2.0)

    return results


def download_stock(
    symbol: str,
    period: str = "1y",
    interval: str = "1d",
) -> pd.DataFrame:
    symbol = str(symbol).strip()

    if not symbol:
        return pd.DataFrame()

    try:
        raw = yf.download(
            symbol,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=True,
            threads=False,
            timeout=30,
        )

        df = _normalise_yf(raw, symbol)

        if len(df) >= 1:
            return df

    except Exception as exc:
        print(f"Single-symbol download failed for {symbol}: {exc}")

    return pd.DataFrame()


def download_index(
    symbol: str,
    period: str = "2y",
    interval: str = "1d",
) -> pd.DataFrame:
    return download_stock(symbol, period=period, interval=interval)


def download_watchlist(
    watchlist: Iterable[str],
) -> dict[str, pd.DataFrame]:
    return download_all(
        watchlist,
        period="1y",
        interval="1d",
        chunk=10,
    )

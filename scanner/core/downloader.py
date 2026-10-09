"""Reliable, rate-limit-aware market data downloader for Trading OS v12."""
from __future__ import annotations

import io
import time
from typing import Dict, Iterable, Optional

import pandas as pd
import requests
import yfinance as yf

NIFTY50_URL = "https://www.niftyindices.com/IndexConstituent/ind_nifty50list.csv"
NIFTY_NEXT50_URL = "https://www.niftyindices.com/IndexConstituent/ind_niftynext50list.csv"
NIFTY_MIDCAP150_URL = "https://www.niftyindices.com/IndexConstituent/ind_niftymidcap150list.csv"
NIFTY_SMALLCAP250_URL = "https://www.niftyindices.com/IndexConstituent/ind_niftysmallcap250list.csv"

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
    """Compatibility function: official Nifty 50 + Nifty Next 50."""
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

    combined = list(dict.fromkeys(nifty50 + next50))

    if not 90 <= len(combined) <= 110:
        raise RuntimeError(
            f"Unexpected combined Nifty 100 count: {len(combined)}"
        )

    print(f"Nifty 100 universe loaded: {len(combined)} unique symbols")
    return combined


def get_nifty500_symbols() -> list[str]:
    """Official Nifty 50 + Next 50 + Midcap 150 + Smallcap 250 universe."""
    groups = [
        ("Nifty 50", NIFTY50_URL, 45, 55),
        ("Nifty Next 50", NIFTY_NEXT50_URL, 45, 55),
        ("Nifty Midcap 150", NIFTY_MIDCAP150_URL, 140, 160),
        ("Nifty Smallcap 250", NIFTY_SMALLCAP250_URL, 240, 260),
    ]

    combined: list[str] = []
    summary = []

    for name, url, minimum, maximum in groups:
        symbols = _read_constituents(url)

        if not minimum <= len(symbols) <= maximum:
            raise RuntimeError(
                f"Unexpected {name} constituent count: {len(symbols)}"
            )

        summary.append(f"{name}={len(symbols)}")
        combined.extend(symbols)

    unique = list(dict.fromkeys(combined))

    if not 480 <= len(unique) <= 520:
        raise RuntimeError(
            f"Unexpected combined Nifty 500 count: {len(unique)}"
        )

    print(
        "Nifty 500 universe loaded: "
        + ", ".join(summary)
        + f"; {len(unique)} unique symbols"
    )

    return unique


def get_nse_equity_symbols(limit: int = 1800) -> list[str]:
    """Compatibility function; returns the expanded Nifty 500 universe."""
    symbols = get_nifty500_symbols()
    return symbols[:limit] if limit else symbols


def get_fno_symbols() -> list[str]:
    """Compatibility function for older scanner modules."""
    return get_nifty500_symbols()


def get_nse500() -> list[str]:
    """Compatibility function for older scanner modules."""
    return get_nifty500_symbols()


def _normalise_yf(
    frame: pd.DataFrame,
    ticker: Optional[str] = None,
) -> pd.DataFrame:
    if (
        frame is None
        or not isinstance(frame, pd.DataFrame)
        or frame.empty
    ):
        return pd.DataFrame()

    df = frame.copy()

    if isinstance(df.columns, pd.MultiIndex):
        if ticker:
            variants = {
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
                    (value for value in variants if value in values),
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
            known = {field.lower(): field for field in OHLCV}
            flattened = []

            for column in df.columns:
                parts = column if isinstance(column, tuple) else (column,)
                match = next(
                    (
                        known[str(part).lower()]
                        for part in parts
                        if str(part).lower() in known
                    ),
                    None,
                )
                flattened.append(
                    match or str(parts[0])
                )

            df.columns = flattened

    known = {field.lower(): field for field in OHLCV}

    df = df.rename(
        columns={
            column: known[str(column).strip().lower()]
            for column in df.columns
            if str(column).strip().lower() in known
        }
    )

    df = df.loc[:, ~df.columns.duplicated(keep="first")]

    if not all(column in df.columns for column in OHLCV):
        return pd.DataFrame()

    df = df.loc[:, list(OHLCV)].copy()

    for column in OHLCV:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df.dropna(subset=list(OHLCV))

    return df.sort_index() if not df.empty else pd.DataFrame()


def _download_batch(
    batch: list[str],
    period: str,
    interval: str,
) -> dict[str, pd.DataFrame]:
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

            output = {}

            for ticker in batch:
                frame = None

                if isinstance(raw, pd.DataFrame):
                    if isinstance(raw.columns, pd.MultiIndex):
                        for level in range(raw.columns.nlevels):
                            if ticker in {
                                str(value)
                                for value in raw.columns.get_level_values(level)
                            }:
                                try:
                                    frame = raw.xs(
                                        ticker,
                                        axis=1,
                                        level=level,
                                        drop_level=True,
                                    )
                                    break
                                except (
                                    KeyError,
                                    ValueError,
                                    TypeError,
                                ):
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

            wait = (
                5 * (2 ** attempt)
                if (
                    "rate" in message
                    or "429" in message
                    or "too many" in message
                )
                else 2 * (attempt + 1)
            )

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
        results.update(_download_batch(batch, period, interval))

        print(
            f"Progress: {min(start + len(batch), len(cleaned))}"
            f"/{len(cleaned)} | Valid charts: {len(results)}"
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
    return download_stock(
        symbol,
        period=period,
        interval=interval,
    )


def download_watchlist(
    watchlist: Iterable[str],
) -> dict[str, pd.DataFrame]:
    return download_all(
        watchlist,
        period="1y",
        interval="1d",
        chunk=10,
    )

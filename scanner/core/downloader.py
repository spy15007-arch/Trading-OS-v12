import io
import time

import pandas as pd
import requests
import yfinance as yf

BROAD_UNIVERSE_URLS = [
    "https://archives.nseindia.com/content/equities/EQUITY_L.csv",
    "https://archives.nseindia.com/content/equities/EQUITY_L_N.csv",
]

FALLBACK_SYMBOLS = [
    "RELIANCE", "HDFCBANK", "ICICIBANK", "SBIN", "INFY", "TCS",
    "LT", "AXISBANK", "KOTAKBANK", "BHARTIARTL", "ITC", "MARUTI",
    "SUNPHARMA", "TITAN", "M&M", "HINDUNILVR", "BAJFINANCE", "DIXON",
    "POLYCAB", "TRENT", "CGPOWER", "PERSISTENT", "KEI", "BSE",
]


def _clean_symbol(symbol):
    s = str(symbol).strip().upper()
    return s if s and s not in {"NAN", "NONE"} else None


def _normalize_yf(df, ticker=None):
    if df is None:
        return pd.DataFrame()

    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    if isinstance(df.columns, pd.MultiIndex):
        if ticker:
            for level in range(df.columns.nlevels):
                vals = [str(x) for x in df.columns.get_level_values(level)]
                if ticker in vals:
                    try:
                        df = df.xs(ticker, axis=1, level=level, drop_level=True)
                        break
                    except Exception:
                        pass

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [str(c[0]) for c in df.columns]

    if df.empty:
        return pd.DataFrame()

    rename = {str(c).strip().title(): str(c).strip().title() for c in df.columns}
    df = df.rename(columns=rename)

    needed = ["Open", "High", "Low", "Close", "Volume"]
    if not all(c in df.columns for c in needed):
        return pd.DataFrame()

    normalized = df[needed].apply(pd.to_numeric, errors="coerce").dropna()
    return normalized if not normalized.empty else pd.DataFrame()


def get_nse_equity_symbols(limit=1800):
    print("Downloading NSE equity universe...")
    for url in BROAD_UNIVERSE_URLS:
        try:
            response = requests.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            if not response.content:
                continue

            df = pd.read_csv(io.BytesIO(response.content))
            if df.empty:
                continue

            column = next((c for c in df.columns if str(c).strip().upper() == "SYMBOL"), None)
            if not column:
                continue

            symbols = []
            for symbol in df[column].tolist():
                cleaned = _clean_symbol(symbol)
                if cleaned:
                    symbols.append(f"{cleaned}.NS")

            symbols = list(dict.fromkeys(symbols))
            if len(symbols) >= 500:
                symbols = symbols[:limit]
                print(f"broad nse universe: {len(symbols)} symbols")
                return symbols

        except Exception as exc:
            print(f"universe source failed: {exc}")

    fallback_symbols = [f"{symbol}.NS" for symbol in FALLBACK_SYMBOLS]
    fallback_symbols = fallback_symbols[:limit]
    print(f"using fallback universe: {len(fallback_symbols)} symbols")
    return fallback_symbols


def get_fno_symbols():
    return get_nse_equity_symbols(1800)


def get_nse500():
    return get_nse_equity_symbols(500)


def download_all(tickers, period="1y", interval="1d", chunk=75):
    tickers = [str(t).strip() for t in (tickers or []) if str(t).strip()]
    database = {}
    total = len(tickers)

    if total == 0:
        print("No tickers supplied for download.")
        return database

    print(f"Downloading {total} symbols...")

    for start in range(0, total, chunk):
        batch = tickers[start:start + chunk]

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

            if isinstance(data, dict):
                mapping = data
            elif isinstance(data, pd.DataFrame):
                mapping = {}
                for ticker in batch:
                    try:
                        mapping[ticker] = data[ticker]
                    except Exception:
                        pass
            else:
                mapping = {}

            for ticker in batch:
                try:
                    frame = mapping.get(ticker)
                    if frame is None and isinstance(data, pd.DataFrame):
                        frame = data[ticker]
                    df = _normalize_yf(frame, ticker)
                    if len(df) >= 220:
                        database[ticker] = df
                except Exception:
                    continue

        except Exception as exc:
            print(f"download batch failed: {exc}")

        print(f"Progress: {min(start + len(batch), total)}/{total} | Charts: {len(database)}")
        time.sleep(0.05)

    return database


def download_stock(symbol, period="1y", interval="1d"):
    symbol = str(symbol).strip()
    if not symbol:
        return pd.DataFrame()

    try:
        data = yf.download(
            symbol,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=True,
            threads=False,
        )
        return _normalize_yf(data, symbol)
    except Exception:
        return pd.DataFrame()


def download_index(symbol, period="2y", interval="1d"):
    return download_stock(symbol, period=period, interval=interval)


def download_watchlist(watchlist):
    return download_all(watchlist, period="1y", interval="1d", chunk=50)

import io
import time
import requests
import pandas as pd
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
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        # yfinance can return (Price, Ticker) or (Ticker, Price).
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
    rename = {str(c).strip().title(): str(c).strip().title() for c in df.columns}
    df = df.rename(columns=rename)
    needed = ["Open", "High", "Low", "Close", "Volume"]
    if not all(c in df.columns for c in needed):
        return pd.DataFrame()
    return df[needed].apply(pd.to_numeric, errors="coerce").dropna()


def get_nse_equity_symbols(limit=1800):
    print("Downloading NSE equity universe...")
    for url in BROAD_UNIVERSE_URLS:
        try:
            r = requests.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            df = pd.read_csv(io.BytesIO(r.content))
            col = next((c for c in df.columns if str(c).strip().upper() == "SYMBOL"), None)
            if col:
                symbols = []
                for s in df[col].tolist():
                    s = _clean_symbol(s)
                    if s:
                        symbols.append(f"{s}.NS")
                symbols = list(dict.fromkeys(symbols))
                if len(symbols) >= 500:
                    symbols = symbols[:limit]
                    print(f"broad nse universe: {len(symbols)} symbols")
                    return symbols
        except Exception as e:
            print(f"universe source failed: {e}")
    symbols = [f"{s}.NS" for s in FALLBACK_SYMBOLS]
    print(f"using fallback universe: {len(symbols)} symbols")
    return symbols


def get_fno_symbols():
    # Kept for compatibility with older runners.
    return get_nse_equity_symbols(1800)


def get_nse500():
    return get_nse_equity_symbols(500)


def download_all(tickers, period="1y", interval="1d", chunk=75):
    database = {}
    total = len(tickers)
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
            if len(batch) == 1:
                df = _normalize_yf(data, batch[0])
                if len(df) >= 220:
                    database[batch[0]] = df
            else:
                for ticker in batch:
                    try:
                        df = _normalize_yf(data[ticker], ticker)
                        if len(df) >= 220:
                            database[ticker] = df
                    except Exception:
                        continue
        except Exception as e:
            print(f"download batch failed: {e}")
        print(f"Progress: {min(start + len(batch), total)}/{total} | Charts: {len(database)}")
        time.sleep(0.05)
    return database


def download_stock(symbol, period="1y", interval="1d"):
    try:
        data = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=True, threads=False)
        return _normalize_yf(data, symbol)
    except Exception:
        return pd.DataFrame()


def download_index(symbol, period="2y", interval="1d"):
    return download_stock(symbol, period=period, interval=interval)


def download_watchlist(watchlist):
    return download_all(watchlist, period="1y", interval="1d", chunk=50)

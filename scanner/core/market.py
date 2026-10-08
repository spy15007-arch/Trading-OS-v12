import pandas as pd

from .downloader import download_index


def _normalise_index_data(data):
    """
    Normalise index OHLCV data returned by yfinance/downloader.
    """

    if data is None or data.empty:
        return None

    df = data.copy()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            col[0] if isinstance(col, tuple) else col
            for col in df.columns
        ]

    rename_map = {}

    for col in df.columns:

        name = str(col).lower()

        if name == "open":
            rename_map[col] = "Open"

        elif name == "high":
            rename_map[col] = "High"

        elif name == "low":
            rename_map[col] = "Low"

        elif name == "close":
            rename_map[col] = "Close"

        elif name == "volume":
            rename_map[col] = "Volume"

    df = df.rename(
        columns=rename_map
    )

    if "Close" not in df.columns:
        return None

    df["Close"] = pd.to_numeric(
        df["Close"],
        errors="coerce"
    )

    df = df.dropna(
        subset=["Close"]
    )

    return df


def get_market_regime():
    """
    Determine broad NIFTY market regime.

    Returns:
        BULLISH
        NEUTRAL
        BEARISH
        UNKNOWN

    This function deliberately uses the canonical
    download_index() from scanner/core/downloader.py.
    """

    try:

        data = download_index(
            "^NSEI",
            period="2y",
            interval="1d",
        )

        data = _normalise_index_data(
            data
        )

        if data is None:
            return "UNKNOWN"

        if len(data) < 220:
            return "UNKNOWN"

        close = data["Close"]

        ema20 = (
            close
            .ewm(
                span=20,
                adjust=False
            )
            .mean()
            .iloc[-1]
        )

        ema50 = (
            close
            .ewm(
                span=50,
                adjust=False
            )
            .mean()
            .iloc[-1]
        )

        ema200 = (
            close
            .ewm(
                span=200,
                adjust=False
            )
            .mean()
            .iloc[-1]
        )

        current = float(
            close.iloc[-1]
        )

        bullish_conditions = 0

        if current > ema20:
            bullish_conditions += 1

        if ema20 > ema50:
            bullish_conditions += 1

        if ema50 > ema200:
            bullish_conditions += 1

        if current > ema200:
            bullish_conditions += 1

        # Strong bullish structure
        if bullish_conditions >= 4:
            return "BULLISH"

        # Reasonably constructive
        if bullish_conditions >= 3:
            return "BULLISH"

        # Mixed market
        if bullish_conditions >= 2:
            return "NEUTRAL"

        # Weak market
        return "BEARISH"

    except Exception as exc:

        print(
            f"Market regime calculation failed: {exc}"
        )

        return "UNKNOWN"

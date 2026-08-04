"""
core/market.py

Market regime detection for Trading OS v12
"""

import yfinance as yf
import pandas as pd


def ema(series, length):
    return series.ewm(span=length, adjust=False).mean()


def get_index_data(symbol):
    """
    Download last 6 months of index data.
    """
    try:
        df = yf.download(
            symbol,
            period="6mo",
            interval="1d",
            progress=False,
            auto_adjust=True,
        )

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        return df.dropna()

    except Exception:
        return pd.DataFrame()


def trend_from_df(df):

    if df.empty or len(df) < 200:
        return "UNKNOWN"

    close = float(df.Close.iloc[-1])

    ema20 = ema(df.Close, 20).iloc[-1]
    ema50 = ema(df.Close, 50).iloc[-1]
    ema200 = ema(df.Close, 200).iloc[-1]

    if close > ema20 > ema50 > ema200:
        return "BULLISH"

    if close < ema20 < ema50 < ema200:
        return "BEARISH"

    return "SIDEWAYS"


def get_market_status():
    """
    Returns overall market regime.
    """

    nifty = get_index_data("^NSEI")
    bank = get_index_data("^NSEBANK")

    nifty_trend = trend_from_df(nifty)
    bank_trend = trend_from_df(bank)

    if nifty_trend == "BULLISH" and bank_trend == "BULLISH":
        mode = "AGGRESSIVE"

    elif nifty_trend == "BEARISH" and bank_trend == "BEARISH":
        mode = "DEFENSIVE"

    else:
        mode = "NEUTRAL"

    return {
        "NIFTY": nifty_trend,
        "BANKNIFTY": bank_trend,
        "MODE": mode,
    }


if __name__ == "__main__":

    market = get_market_status()

    print("\n===== MARKET STATUS =====")
    print(f"NIFTY      : {market['NIFTY']}")
    print(f"BANKNIFTY  : {market['BANKNIFTY']}")
    print(f"MODE        : {market['MODE']}")

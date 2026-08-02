import yfinance as yf
import pandas as pd
import time


# ==========================================
# Download Market Data
# ==========================================

def download_all(tickers,
                 period="6mo",
                 interval="1d",
                 chunk_size=100):

    market_data = {}

    for i in range(0, len(tickers), chunk_size):

        chunk = tickers[i:i + chunk_size]

        try:

            data = yf.download(
                tickers=chunk,
                period=period,
                interval=interval,
                group_by="ticker",
                auto_adjust=False,
                progress=False,
                threads=True
            )

            if len(chunk) == 1:

                market_data[chunk[0]] = data.dropna()

            else:

                for ticker in chunk:

                    try:

                        df = data[ticker].dropna()

                        if len(df) > 50:

                            market_data[ticker] = df

                    except:

                        pass

        except:

            pass

        time.sleep(0.05)

    return market_data


# ==========================================
# Remove Weak Stocks
# ==========================================

def clean_market_data(data_dict):

    cleaned = {}

    for symbol, df in data_dict.items():

        try:

            if len(df) < 220:

                continue

            if df["Volume"].rolling(20).mean().iloc[-1] < 100000:

                continue

            cleaned[symbol] = df

        except:

            pass

    return cleaned

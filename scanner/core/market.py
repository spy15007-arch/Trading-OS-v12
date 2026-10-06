import pandas as pd
from .downloader import download_index
from .indicators import ema, rsi

MIN_BARS = 220


def analyse(df):
    if df is None or len(df) < MIN_BARS:
        return None
    close = pd.to_numeric(df["Close"], errors="coerce").dropna()
    e20 = float(ema(close, 20).iloc[-1])
    e50 = float(ema(close, 50).iloc[-1])
    e200 = float(ema(close, 200).iloc[-1])
    r = float(rsi(close).iloc[-1])
    score = int(close.iloc[-1] > e20) + int(e20 > e50) + 2 * int(e50 > e200) + int(r > 60)
    return {"close": round(float(close.iloc[-1]), 2), "ema20": round(e20, 2), "ema50": round(e50, 2), "ema200": round(e200, 2), "rsi": round(r, 1), "score": score}


def get_market_status():
    nifty = analyse(download_index("^NSEI", period="2y"))
    bank = analyse(download_index("^NSEBANK", period="2y"))
    if nifty is None and bank is None:
        return {"MODE": "UNKNOWN", "NIFTY": "NA", "BANKNIFTY": "NA", "NIFTY_RSI": "NA", "BANK_RSI": "NA", "TOTAL_SCORE": 0}
    ns = nifty["score"] if nifty else 0
    bs = bank["score"] if bank else 0
    total = ns + bs
    mode = "BULLISH" if total >= 8 else "NEUTRAL" if total >= 5 else "DEFENSIVE"
    return {
        "MODE": mode,
        "NIFTY": nifty["close"] if nifty else "NA",
        "BANKNIFTY": bank["close"] if bank else "NA",
        "NIFTY_RSI": nifty["rsi"] if nifty else "NA",
        "BANK_RSI": bank["rsi"] if bank else "NA",
        "NIFTY_SCORE": ns,
        "BANK_SCORE": bs,
        "TOTAL_SCORE": total,
    }

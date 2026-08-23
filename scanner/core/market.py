"""Market regime detection based on NIFTY 50."""
from .downloader import download_index
from .indicators import ema, rsi


def get_market_regime(symbol="^NSEI", period="2y"):
    data = download_index(symbol, period=period)

    if len(data) < 60:
        return {
            "regime": "NEUTRAL",
            "symbol": symbol,
            "reason": "index data unavailable",
        }

    close = data["Close"]

    last = float(close.iloc[-1])
    ema20 = float(ema(close, 20).iloc[-1])
    ema50 = float(ema(close, 50).iloc[-1])
    rsi_value = float(rsi(close).iloc[-1])

    if last > ema20 > ema50 and rsi_value >= 52:
        regime = "BULLISH"
    elif last < ema20 < ema50 and rsi_value <= 48:
        regime = "DEFENSIVE"
    else:
        regime = "NEUTRAL"

    return {
        "regime": regime,
        "symbol": symbol,
        "close": round(last, 2),
        "rsi": round(rsi_value, 1),
        "ema20": round(ema20, 2),
        "ema50": round(ema50, 2),
    }

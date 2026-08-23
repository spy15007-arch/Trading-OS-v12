"""Momentum scoring and scan-profile qualification."""
from .indicators import ema, rsi, relative_volume
from .risk import trade_levels


PROFILES = {
    "strict": {
        "minimum": 75,
        "rsi_low": 55,
        "rsi_high": 72,
        "min_rvol": 1.10,
    },
    "aggressive": {
        "minimum": 60,
        "rsi_low": 50,
        "rsi_high": 78,
        "min_rvol": 0.85,
    },
    "budget": {
        "minimum": 65,
        "rsi_low": 52,
        "rsi_high": 75,
        "min_rvol": 0.90,
        "max_price": 500,
    },
}


def score_stock(symbol, frame, profile="strict", regime="NEUTRAL"):
    if profile not in PROFILES or len(frame) < 60:
        return None

    close = frame["Close"]

    price = float(close.iloc[-1])
    ema20 = float(ema(close, 20).iloc[-1])
    ema50 = float(ema(close, 50).iloc[-1])

    rsi_value = float(rsi(close).iloc[-1])
    rvol = relative_volume(frame)

    high20 = float(frame["High"].rolling(20).max().iloc[-1])

    score = 0

    score += 25 if price > ema20 > ema50 else 0
    score += 20 if ema20 > ema50 else 0
    score += 20 if rsi_value >= 55 else 10 if rsi_value >= 50 else 0
    score += 20 if rvol >= 1.2 else 10 if rvol >= 0.9 else 0
    score += 15 if price >= high20 * 0.97 else 0

    if regime == "BULLISH":
        score += 5

    if regime == "DEFENSIVE":
        score -= 10

    config = PROFILES[profile]

    qualified = (
        score >= config["minimum"]
        and config["rsi_low"] <= rsi_value <= config["rsi_high"]
        and rvol >= config["min_rvol"]
    )

    if "max_price" in config:
        qualified = qualified and price <= config["max_price"]

    result = {
        "symbol": symbol.replace(".NS", ""),
        "score": int(score),
        "price": round(price, 2),
        "rsi": round(rsi_value, 1),
        "relative_volume": round(rvol, 2),
        "near_20d_high_pct": round(price / high20 * 100, 1),
        "qualified": qualified,
        "profile": profile,
    }

    result.update(trade_levels(frame, price))

    return result


def scan(database, profile="strict", regime="NEUTRAL"):
    results = [
        score_stock(symbol, frame, profile, regime)
        for symbol, frame in database.items()
    ]

    return sorted(
        (
            result
            for result in results
            if result and result["qualified"]
        ),
        key=lambda result: result["score"],
        reverse=True,
    )

"""Trade levels derived from ATR; educational output, not investment advice."""
from .indicators import atr


def trade_levels(frame, entry=None, stop_atr=1.5, target_atr=3.0):
    price = float(entry if entry is not None else frame["Close"].iloc[-1])
    atr_value = float(atr(frame).iloc[-1])

    if atr_value <= 0:
        return {}

    stop = price - stop_atr * atr_value
    target = price + target_atr * atr_value

    return {
        "entry": round(price, 2),
        "stop": round(stop, 2),
        "target": round(target, 2),
        "atr": round(atr_value, 2),
        "reward_risk": round(
            (target - price) / (price - stop),
            2,
        ),
    }

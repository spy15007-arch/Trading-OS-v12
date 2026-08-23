"""Trade levels derived from ATR; educational output, not investment advice."""
from .indicators import atr


def trade_levels(frame, entry=None, stop_atr=1.5):
    price = float(entry if entry is not None else frame["Close"].iloc[-1])
    atr_value = float(atr(frame).iloc[-1])

    if atr_value <= 0:
        return {}

    stop = price - stop_atr * atr_value
    risk_per_share = price - stop

    target1 = price + risk_per_share
    target2 = price + (risk_per_share * 1.5)
    target3 = price + (risk_per_share * 2.0)

    return {
        "entry": round(price, 2),
        "stop": round(stop, 2),
        "atr": round(atr_value, 2),
        "target1": round(target1, 2),
        "target2": round(target2, 2),
        "target3": round(target3, 2),
        "reward_risk_t3": 2.0,
    }

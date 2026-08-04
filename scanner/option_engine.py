import math
import numpy as np
from scipy.stats import norm


# ==========================================================
# Black Scholes Call Price
# ==========================================================

def black_scholes_call(
    spot,
    strike,
    t,
    rate,
    sigma
):

    if sigma <= 0:
        sigma = 0.20

    if t <= 0:
        t = 1 / 365

    d1 = (
        math.log(spot / strike)
        +
        (rate + sigma**2 / 2) * t
    ) / (sigma * math.sqrt(t))

    d2 = d1 - sigma * math.sqrt(t)

    premium = (
        spot * norm.cdf(d1)
        -
        strike * math.exp(-rate * t) * norm.cdf(d2)
    )

    delta = norm.cdf(d1)

    return round(premium,2), round(delta,2)


# ==========================================================
# Historical Volatility
# ==========================================================

def estimate_iv(df):

    returns = np.log(
        df.Close /
        df.Close.shift()
    )

    iv = returns.std() * np.sqrt(252)

    if np.isnan(iv):

        iv = 0.20

    if iv < 0.10:

        iv = 0.10

    if iv > 0.80:

        iv = 0.80

    return float(iv)


# ==========================================================
# Strike Interval
# ==========================================================

def strike_step(price):

    if price >= 5000:
        return 100

    if price >= 2000:
        return 50

    if price >= 1000:
        return 20

    if price >= 500:
        return 10

    return 5


# ==========================================================
# ATM Strike
# ==========================================================

def atm_strike(price):

    step = strike_step(price)

    return int(round(price / step) * step)


# ==========================================================
# Option Recommendation
# ==========================================================

def option_trade(
    df,
    bullish=True,
    dte=15
):

    spot = float(df.Close.iloc[-1])

    strike = atm_strike(spot)

    iv = estimate_iv(df)

    premium, delta = black_scholes_call(
        spot,
        strike,
        dte / 365,
        0.07,
        iv
    )

    if bullish:

        option = f"{strike} CE"

    else:

        option = f"{strike} PE"

    sl = round(
        premium * 0.75,
        2
    )

    t1 = round(
        premium * 1.30,
        2
    )

    t2 = round(
        premium * 1.60,
        2
    )

    t3 = round(
        premium * 2.00,
        2
    )

    return {

        "Option": option,

        "Premium": premium,

        "Delta": delta,

        "IV": round(iv,2),

        "OSL": sl,

        "OT1": t1,

        "OT2": t2,

        "OT3": t3

    }

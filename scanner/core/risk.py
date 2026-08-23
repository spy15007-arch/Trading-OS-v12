"""
Trading OS v12 Professional
Risk Management Engine
"""

from dataclasses import dataclass


# ==========================================================
# RISK MODEL
# ==========================================================

@dataclass
class RiskModel:

    capital: float = 100000.0

    risk_percent: float = 2.0


# ==========================================================
# RISK AMOUNT
# ==========================================================

def risk_amount(
    model: RiskModel
):

    return (
        model.capital *
        model.risk_percent /
        100
    )


# ==========================================================
# POSITION SIZE
# ==========================================================

def position_size(
    entry,
    stoploss,
    model: RiskModel
):

    risk = risk_amount(
        model
    )

    per_share = abs(
        entry -
        stoploss
    )

    if per_share <= 0:

        return 0

    quantity = int(
        risk /
        per_share
    )

    return max(
        quantity,
        0
    )


# ==========================================================
# CAPITAL REQUIRED
# ==========================================================

def capital_required(
    entry,
    quantity
):

    return round(
        entry *
        quantity,
        2
    )


# ==========================================================
# RISK / REWARD
# ==========================================================

def risk_reward(
    entry,
    stoploss,
    target
):

    risk = abs(
        entry -
        stoploss
    )

    reward = abs(
        target -
        entry
    )

    if risk <= 0:

        return 0

    return round(
        reward /
        risk,
        2
    )


# ==========================================================
# TRADE PLAN
# ==========================================================

def build_trade_plan(
    entry,
    sl,
    t1,
    model=None
):

    if model is None:

        model = RiskModel()

    quantity = position_size(
        entry,
        sl,
        model
    )

    capital = capital_required(
        entry,
        quantity
    )

    rr = risk_reward(
        entry,
        sl,
        t1
    )

    return {

        "Quantity": quantity,

        "Capital": capital,

        "RiskAmount": round(
            risk_amount(model),
            2
        ),

        "RR": rr

    }

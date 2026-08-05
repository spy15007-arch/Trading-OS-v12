"""
Trading OS v12 Professional
Risk Management Engine
"""

from dataclasses import dataclass


# ==========================================================
# Risk Model
# ==========================================================

@dataclass
class RiskModel:

    capital: float = 100000

    risk_percent: float = 2.0


# ==========================================================
# Risk Amount
# ==========================================================

def risk_amount(model: RiskModel):

    return model.capital * model.risk_percent / 100


# ==========================================================
# Position Size
# ==========================================================

def position_size(
    entry,
    stoploss,
    model: RiskModel
):

    risk = risk_amount(model)

    per_share = abs(entry - stoploss)

    if per_share <= 0:

        return 0

    qty = int(risk / per_share)

    return max(qty, 0)


# ==========================================================
# Capital Required
# ==========================================================

def capital_required(
    entry,
    quantity
):

    return round(entry * quantity, 2)


# ==========================================================
# Risk Reward
# ==========================================================

def risk_reward(
    entry,
    stoploss,
    target
):

    risk = abs(entry - stoploss)

    reward = abs(target - entry)

    if risk <= 0:

        return 0

    return round(reward / risk, 2)


# ==========================================================
# Trade Plan
# ==========================================================

def build_trade_plan(
    entry,
    sl,
    t1,
    model=None
):

    if model is None:

        model = RiskModel()

    qty = position_size(

        entry,

        sl,

        model

    )

    capital = capital_required(

        entry,

        qty

    )

    rr = risk_reward(

        entry,

        sl,

        t1

    )

    return {

        "Quantity": qty,

        "Capital": capital,

        "RiskAmount": round(

            risk_amount(model),

            2

        ),

        "RR": rr

    }

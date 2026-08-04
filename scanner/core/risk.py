"""
core/risk.py

Risk Management Engine
Trading OS v12 Professional
"""

from dataclasses import dataclass
import math


@dataclass
class RiskConfig:
    capital: float = 100000.0
    risk_percent: float = 1.0
    brokerage_per_trade: float = 0.0
    slippage_percent: float = 0.05


class RiskEngine:

    def __init__(self, config: RiskConfig):
        self.config = config

    @property
    def max_risk_amount(self):
        return self.config.capital * self.config.risk_percent / 100.0

    def position_size(self, entry, stoploss):

        risk_per_share = abs(entry - stoploss)

        if risk_per_share <= 0:
            return 0

        qty = math.floor(self.max_risk_amount / risk_per_share)

        return max(qty, 0)

    def expected_profit(self, entry, target, qty):

        return round((target - entry) * qty, 2)

    def expected_loss(self, entry, stoploss, qty):

        return round((entry - stoploss) * qty, 2)

    def risk_reward(self, entry, stoploss, target):

        risk = abs(entry - stoploss)

        reward = abs(target - entry)

        if risk == 0:
            return 0

        return round(reward / risk, 2)

    def trade_summary(
        self,
        entry,
        stoploss,
        target
    ):

        qty = self.position_size(entry, stoploss)

        rr = self.risk_reward(
            entry,
            stoploss,
            target
        )

        profit = self.expected_profit(
            entry,
            target,
            qty
        )

        loss = self.expected_loss(
            entry,
            stoploss,
            qty
        )

        return {

            "Capital": self.config.capital,

            "RiskPercent": self.config.risk_percent,

            "MaxRisk": round(
                self.max_risk_amount,
                2
            ),

            "Quantity": qty,

            "Entry": round(entry,2),

            "StopLoss": round(stoploss,2),

            "Target": round(target,2),

            "RiskReward": rr,

            "ExpectedProfit": profit,

            "ExpectedLoss": loss

        }


def default_risk_engine():

    cfg = RiskConfig()

    return RiskEngine(cfg)


if __name__ == "__main__":

    engine = default_risk_engine()

    trade = engine.trade_summary(

        entry=520.50,

        stoploss=505.20,

        target=551.00

    )

    print("\n===== RISK SUMMARY =====")

    for k, v in trade.items():

        print(f"{k:20}: {v}")

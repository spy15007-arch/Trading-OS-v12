"""Optional options helper. This scanner does not fetch option-chain data."""


def option_bias(regime, score):
    if regime == "BULLISH" and score >= 75:
        return (
            "Bullish bias; consider only defined-risk strategies "
            "after independent review."
        )

    return "No options bias generated."

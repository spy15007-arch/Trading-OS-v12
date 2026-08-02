from scanner.indicators import (
    ema,
    rsi,
    macd,
    atr,
    vwap,
    relative_volume,
    lorentzian_distance,
    option_recommendation
)


# ==========================================
# Institutional AI Score Engine
# ==========================================

def score_stock(df):

    if len(df) < 220:
        return None

    close = float(df.Close.iloc[-1])

    ema20 = ema(df.Close,20).iloc[-1]
    ema50 = ema(df.Close,50).iloc[-1]
    ema200 = ema(df.Close,200).iloc[-1]

    vwap_now = vwap(df).iloc[-1]

    rsi_now = rsi(df.Close).iloc[-1]

    macd_line, signal_line = macd(df.Close)

    atr_now = atr(df).iloc[-1]

    rvol = relative_volume(df)

    score = 0


    # Trend

    if close > ema20:
        score += 2

    if ema20 > ema50:
        score += 2

    if ema50 > ema200:
        score += 3


    # Momentum

    if 60 <= rsi_now <= 78:
        score += 2

    if macd_line.iloc[-1] > signal_line.iloc[-1]:
        score += 2


    # Institutional Buying

    if close > vwap_now:
        score += 2

    if rvol >= 2:
        score += 3

    elif rvol >= 1.3:
        score += 2


    # Candle Strength

    position = (
        close - df.Low.iloc[-1]
    ) / (
        df.High.iloc[-1] -
        df.Low.iloc[-1] +
        0.01
    )

    if position > 0.75:
        score += 2


    # Lorentzian AI Filter

    distance = lorentzian_distance(
        rsi_now,
        rvol
    )

    if distance < 0.6:
        score += 1

    elif distance > 1.5:
        score -= 1


    # Avoid Exhaustion

    if rsi_now > 80:
        score -= 3


    option = option_recommendation(close, df)


    return {

        "Entry": round(close,2),

        "Score": score,

        "RSI": round(rsi_now,1),

        "RVOL": round(rvol,2),

        "EMA20": round(ema20,2),

        "EMA50": round(ema50,2),

        "EMA200": round(ema200,2),

        "SL": round(close-1.5*atr_now,2),

        "T1": round(close+1.5*atr_now,2),

        "T2": round(close+3*atr_now,2),

        "T3": round(close+4.5*atr_now,2),

        "Strike": option["Strike"],

        "Premium": option["Premium"],

        "Delta": option["Delta"]

    }

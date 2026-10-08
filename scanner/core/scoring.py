import numpy as np
import pandas as pd

from .indicators import (
    ema,
    rsi,
    atr,
    relative_volume,
    closing_strength,
)


MIN_BARS = 220

RESISTANCE_LOOKBACK = 20
BASE_LOOKBACK = 20

MAX_PRE_GAP = 4.0
MAX_FRESH_GAP = 5.0

MAX_EXTENSION = 10.0

MIN_PRE_RSI = 55.0
MIN_FRESH_RSI = 58.0

MIN_PRE_RVOL = 0.65
MIN_FRESH_RVOL = 1.40


def _prepare_dataframe(df):

    if df is None or df.empty:
        return None

    data = df.copy()

    if isinstance(data.columns, pd.MultiIndex):

        data.columns = [
            col[0] if isinstance(col, tuple) else col
            for col in data.columns
        ]

    rename_map = {}

    for col in data.columns:

        name = str(col).lower()

        if name == "open":
            rename_map[col] = "Open"

        elif name == "high":
            rename_map[col] = "High"

        elif name == "low":
            rename_map[col] = "Low"

        elif name == "close":
            rename_map[col] = "Close"

        elif name == "volume":
            rename_map[col] = "Volume"

    data = data.rename(
        columns=rename_map
    )

    required = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    if not all(
        column in data.columns
        for column in required
    ):
        return None

    data = data[
        required
    ].copy()

    for column in required:

        data[column] = pd.to_numeric(
            data[column],
            errors="coerce"
        )

    data = data.dropna()

    if len(data) < MIN_BARS:
        return None

    return data


def _relative_strength(data):

    close = data["Close"]

    rs20 = (
        close.iloc[-1]
        / close.iloc[-21]
        - 1
    ) * 100

    rs60 = (
        close.iloc[-1]
        / close.iloc[-61]
        - 1
    ) * 100

    return (
        float(rs20),
        float(rs60),
    )


def _stock_rs(data, benchmark):

    try:

        stock_now = float(
            data["Close"].iloc[-1]
        )

        stock_old = float(
            data["Close"].iloc[-61]
        )

        bench_now = float(
            benchmark["Close"].iloc[-1]
        )

        bench_old = float(
            benchmark["Close"].iloc[-61]
        )

        stock_return = (
            stock_now / stock_old
            - 1
        )

        benchmark_return = (
            bench_now / bench_old
            - 1
        )

        return float(
            (
                stock_return
                - benchmark_return
            ) * 100
        )

    except Exception:

        return 0.0


def _base_metrics(data):

    recent = data.tail(
        BASE_LOOKBACK
    )

    high = float(
        recent["High"].max()
    )

    low = float(
        recent["Low"].min()
    )

    if low <= 0:
        return (
            999.0,
            0.0,
        )

    base_range = (
        (high - low)
        / low
    ) * 100

    first_half = (
        data["Close"]
        .tail(BASE_LOOKBACK)
        .head(BASE_LOOKBACK // 2)
    )

    second_half = (
        data["Close"]
        .tail(BASE_LOOKBACK)
        .tail(BASE_LOOKBACK // 2)
    )

    first_vol = float(
        first_half.std()
    )

    second_vol = float(
        second_half.std()
    )

    if first_vol > 0:

        compression = (
            1
            - (
                second_vol
                / first_vol
            )
        ) * 100

    else:

        compression = 0.0

    return (
        float(base_range),
        float(compression),
    )


def _breakout_metrics(data):

    if len(data) < (
        RESISTANCE_LOOKBACK + 1
    ):
        return None

    previous = (
        data.iloc[:-1]
        .tail(RESISTANCE_LOOKBACK)
    )

    resistance = float(
        previous["High"].max()
    )

    close = float(
        data["Close"].iloc[-1]
    )

    if resistance <= 0:
        return None

    breakout_pct = (
        (
            close / resistance
        ) - 1
    ) * 100

    return (
        resistance,
        breakout_pct,
    )


def _trend_metrics(data):

    close = data["Close"]

    e20 = float(
        ema(
            close,
            20
        ).iloc[-1]
    )

    e50 = float(
        ema(
            close,
            50
        ).iloc[-1]
    )

    e200 = float(
        ema(
            close,
            200
        ).iloc[-1]
    )

    price = float(
        close.iloc[-1]
    )

    extension = (
        (price / e20)
        - 1
    ) * 100

    aligned = (
        e20 > e50
        and e50 > e200
        and price > e20
    )

    return {
        "ema20": e20,
        "ema50": e50,
        "ema200": e200,
        "extension": float(extension),
        "aligned": aligned,
    }


def _momentum_metrics(data):

    value = float(
        rsi(
            data["Close"],
            14
        ).iloc[-1]
    )

    return {
        "rsi": value,
    }


def _volume_metrics(data):

    try:

        rvol = float(
            relative_volume(
                data,
                20
            )
        )

    except Exception:

        rvol = 0.0

    return {
        "rvol": rvol,
    }


def _candle_metrics(data):

    return {
        "closing_strength": float(
            closing_strength(data)
        )
    }


def _classify(
    breakout_pct,
    rvol,
    rsi_value,
    closing_strength_value,
    trend,
    base_range,
    compression,
):

    if not trend["aligned"]:
        return None

    if trend["extension"] > MAX_EXTENSION:
        return None

    # --------------------------------------------------------
    # FRESH BREAKOUT
    # --------------------------------------------------------

    if (
        0 < breakout_pct <= MAX_FRESH_GAP
        and rvol >= MIN_FRESH_RVOL
        and rsi_value >= MIN_FRESH_RSI
        and closing_strength_value >= 0.65
        and compression >= -5
    ):

        return "FRESH BREAKOUT"

    # --------------------------------------------------------
    # PRE-BREAKOUT
    # --------------------------------------------------------

    if (
        -MAX_PRE_GAP
        <= breakout_pct
        <= 0
        and rvol >= MIN_PRE_RVOL
        and rsi_value >= MIN_PRE_RSI
        and base_range <= 15
        and compression >= 5
    ):

        return "PRE-BREAKOUT"

    return None


def _score_trend(metrics):

    score = 0

    if metrics["aligned"]:
        score += 14

    extension = metrics["extension"]

    if 0 <= extension <= 4:
        score += 6

    elif extension <= 7:
        score += 4

    elif extension <= 10:
        score += 2

    return min(
        score,
        20
    )


def _score_relative_strength(
    rs20,
    rs60,
    stock_rs,
):

    score = 0

    if rs20 >= 5:
        score += 5

    elif rs20 >= 2:
        score += 4

    elif rs20 >= 0:
        score += 2

    if rs60 >= 12:
        score += 5

    elif rs60 >= 7:
        score += 4

    elif rs60 >= 3:
        score += 2

    if stock_rs >= 8:
        score += 5

    elif stock_rs >= 4:
        score += 4

    elif stock_rs >= 0:
        score += 2

    return min(
        score,
        15
    )


def _score_base(
    base_range,
    compression,
):

    score = 0

    if base_range <= 7:
        score += 10

    elif base_range <= 10:
        score += 8

    elif base_range <= 15:
        score += 5

    if compression >= 25:
        score += 10

    elif compression >= 15:
        score += 8

    elif compression >= 5:
        score += 5

    return min(
        score,
        20
    )


def _score_breakout(
    setup,
    breakout_pct,
    closing_strength_value,
):

    score = 0

    if setup == "FRESH BREAKOUT":

        if breakout_pct <= 1.5:
            score += 10

        elif breakout_pct <= 3:
            score += 8

        elif breakout_pct <= 5:
            score += 5

        if closing_strength_value >= 0.85:
            score += 5

        elif closing_strength_value >= 0.75:
            score += 4

        elif closing_strength_value >= 0.65:
            score += 2

    else:

        distance = abs(
            breakout_pct
        )

        if distance <= 1:
            score += 15

        elif distance <= 2:
            score += 12

        elif distance <= 3:
            score += 9

        elif distance <= 4:
            score += 6

    return min(
        score,
        15
    )


def _score_volume(
    setup,
    rvol,
):

    if setup == "FRESH BREAKOUT":

        if rvol >= 2.5:
            return 15

        if rvol >= 2.0:
            return 13

        if rvol >= 1.7:
            return 11

        if rvol >= 1.4:
            return 8

    else:

        if 0.70 <= rvol <= 1.15:
            return 15

        if rvol <= 1.30:
            return 12

        if rvol <= 1.60:
            return 7

    return 4


def _score_momentum(
    rsi_value
):

    if 60 <= rsi_value <= 68:
        return 10

    if 57 <= rsi_value < 60:
        return 8

    if 68 < rsi_value <= 72:
        return 7

    if 55 <= rsi_value < 57:
        return 5

    return 2


def _trade_levels(data):

    close = float(
        data["Close"].iloc[-1]
    )

    atr_value = float(
        atr(
            data,
            14
        ).iloc[-1]
    )

    recent_low = float(
        data["Low"]
        .tail(10)
        .min()
    )

    stop_by_atr = (
        close
        - 1.5 * atr_value
    )

    stop = max(
        recent_low,
        stop_by_atr
    )

    if stop >= close:

        stop = (
            close * 0.95
        )

    risk = close - stop

    if risk <= 0:

        risk = (
            close * 0.05
        )

        stop = (
            close - risk
        )

    return {
        "entry": round(
            close,
            2
        ),

        "sl": round(
            stop,
            2
        ),

        "t1": round(
            close + risk,
            2
        ),

        "t2": round(
            close + 2 * risk,
            2
        ),

        "t3": round(
            close + 3 * risk,
            2
        ),

        "t4": round(
            close + 4 * risk,
            2
        ),

        "risk_pct": round(
            (risk / close) * 100,
            2
        ),
    }


def score_stock(
    data,
    benchmark=None,
    symbol=None,
):

    data = _prepare_dataframe(
        data
    )

    if data is None:
        return None

    try:

        trend = _trend_metrics(
            data
        )

        momentum = _momentum_metrics(
            data
        )

        volume = _volume_metrics(
            data
        )

        candle = _candle_metrics(
            data
        )

        base_range, compression = (
            _base_metrics(data)
        )

        breakout = _breakout_metrics(
            data
        )

        if breakout is None:
            return None

        resistance, breakout_pct = (
            breakout
        )

        rs20, rs60 = (
            _relative_strength(data)
        )

        stock_rs = 0.0

        if benchmark is not None:

            stock_rs = _stock_rs(
                data,
                benchmark
            )

        setup = _classify(
            breakout_pct,
            volume["rvol"],
            momentum["rsi"],
            candle["closing_strength"],
            trend,
            base_range,
            compression,
        )

        if setup is None:
            return None

        trend_score = _score_trend(
            trend
        )

        rs_score = _score_relative_strength(
            rs20,
            rs60,
            stock_rs,
        )

        base_score = _score_base(
            base_range,
            compression,
        )

        breakout_score = _score_breakout(
            setup,
            breakout_pct,
            candle["closing_strength"],
        )

        volume_score = _score_volume(
            setup,
            volume["rvol"],
        )

        momentum_score = _score_momentum(
            momentum["rsi"]
        )

        trade = _trade_levels(
            data
        )

        risk_score = 0

        if trade["risk_pct"] <= 4:
            risk_score = 5

        elif trade["risk_pct"] <= 6:
            risk_score = 3

        elif trade["risk_pct"] <= 8:
            risk_score = 1

        raw_score = (
            trend_score
            + rs_score
            + base_score
            + breakout_score
            + volume_score
            + momentum_score
            + risk_score
        )

        # ----------------------------------------------------
        # CHASE PENALTY
        # ----------------------------------------------------

        penalty = 0

        if trend["extension"] > 7:
            penalty += 3

        if trend["extension"] > 9:
            penalty += 4

        if (
            setup == "FRESH BREAKOUT"
            and breakout_pct > 4
        ):
            penalty += 3

        score = max(
            0,
            min(
                100,
                round(
                    raw_score
                    - penalty
                ),
            ),
        )

        return {
            "Symbol": symbol or "",
            "Setup": setup,
            "Score": score,

            "BreakoutPct": round(
                breakout_pct,
                2
            ),

            "RS20": round(
                rs20,
                2
            ),

            "RS60": round(
                rs60,
                2
            ),

            "StockRS": round(
                stock_rs,
                2
            ),

            "RSI": round(
                momentum["rsi"],
                2
            ),

            "RVOL": round(
                volume["rvol"],
                2
            ),

            "BaseRange": round(
                base_range,
                2
            ),

            "Compression": round(
                compression,
                2
            ),

            "Extension": round(
                trend["extension"],
                2
            ),

            "Resistance": round(
                resistance,
                2
            ),

            "ClosingStrength": round(
                candle["closing_strength"],
                2
            ),

            "Entry": trade["entry"],
            "SL": trade["sl"],
            "T1": trade["t1"],
            "T2": trade["t2"],
            "T3": trade["t3"],
            "T4": trade["t4"],
            "RiskPct": trade["risk_pct"],
        }

    except Exception:

        return None

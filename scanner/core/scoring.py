"""
Trading OS v12 - Master Swing Scoring Engine

The scanner is deliberately focused on only two setups:

1. PRE-BREAKOUT
   - Strong trend
   - Tight / controlled base
   - Close to prior resistance
   - Not excessively extended

2. FRESH BREAKOUT
   - Actual resistance breakout
   - Volume confirmation
   - Strong closing price
   - Momentum confirmation
   - Limited extension / chase risk

Final score:
    0 - 100

The engine also calculates:
    RS20
    RS60
    RSI
    RVOL
    BreakoutPct
    BaseRangePct
    Entry
    SL
    T1
    T2

No stock is classified simply as "BREAKOUT".
"""


import numpy as np
import pandas as pd

from .indicators import (
    ema,
    rsi,
    macd,
    atr,
    relative_volume,
    closing_strength,
)


# ============================================================
# CONFIGURATION
# ============================================================

MIN_BARS = 220

EMA_FAST = 20
EMA_MID = 50
EMA_SLOW = 200

RSI_PERIOD = 14

RESISTANCE_LOOKBACK = 20

BASE_LOOKBACK = 20

MAX_PRE_BREAKOUT_GAP = 5.0

MAX_FRESH_BREAKOUT_GAP = 6.0

MAX_EXTENSION_FROM_EMA20 = 12.0

MIN_PRE_RSI = 52.0

MIN_FRESH_RSI = 55.0

MIN_PRE_RVOL = 0.70

MIN_FRESH_RVOL = 1.30


# ============================================================
# SAFE NUMBER
# ============================================================

def _num(value, default=np.nan):

    try:

        value = float(value)

        if np.isfinite(value):
            return value

    except (
        TypeError,
        ValueError,
    ):
        pass

    return default


# ============================================================
# DATA PREPARATION
# ============================================================

def _prepare_dataframe(df):

    if df is None:
        return None

    if df.empty:
        return None

    data = df.copy()

    # --------------------------------------------------------
    # Flatten possible MultiIndex columns from yfinance.
    # --------------------------------------------------------

    if isinstance(
        data.columns,
        pd.MultiIndex,
    ):

        data.columns = [
            str(col[0])
            for col in data.columns
        ]

    # --------------------------------------------------------
    # Standardise column names.
    # --------------------------------------------------------

    rename_map = {}

    for column in data.columns:

        name = str(column).strip()

        lower = name.lower()

        if lower == "open":
            rename_map[column] = "Open"

        elif lower == "high":
            rename_map[column] = "High"

        elif lower == "low":
            rename_map[column] = "Low"

        elif lower == "close":
            rename_map[column] = "Close"

        elif lower == "volume":
            rename_map[column] = "Volume"

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

    for column in required:

        if column not in data.columns:
            return None

    data = data[
        required
    ].copy()

    for column in required:

        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        )

    data = data.dropna(
        subset=[
            "High",
            "Low",
            "Close",
        ]
    )

    data = data[
        data["Close"] > 0
    ]

    data = data[
        data["High"] >= data["Low"]
    ]

    if len(data) < MIN_BARS:
        return None

    return data


# ============================================================
# RELATIVE STRENGTH
# ============================================================

def _relative_return(
    series,
    periods,
):

    if len(series) <= periods:
        return np.nan

    start = _num(
        series.iloc[-periods - 1]
    )

    end = _num(
        series.iloc[-1]
    )

    if not np.isfinite(start):
        return np.nan

    if start <= 0:
        return np.nan

    return (
        (end / start) - 1.0
    ) * 100.0


def _relative_strength(
    stock_df,
    benchmark_df,
):

    stock_rs20 = _relative_return(
        stock_df["Close"],
        20,
    )

    stock_rs60 = _relative_return(
        stock_df["Close"],
        60,
    )

    if (
        benchmark_df is None
        or benchmark_df.empty
    ):

        return (
            stock_rs20,
            stock_rs60,
            stock_rs20,
            stock_rs60,
        )

    benchmark = _prepare_dataframe(
        benchmark_df
    )

    if benchmark is None:

        return (
            stock_rs20,
            stock_rs60,
            stock_rs20,
            stock_rs60,
        )

    bench_rs20 = _relative_return(
        benchmark["Close"],
        20,
    )

    bench_rs60 = _relative_return(
        benchmark["Close"],
        60,
    )

    if np.isfinite(
        stock_rs20
    ) and np.isfinite(
        bench_rs20
    ):

        relative_rs20 = (
            stock_rs20
            - bench_rs20
        )

    else:

        relative_rs20 = stock_rs20

    if np.isfinite(
        stock_rs60
    ) and np.isfinite(
        bench_rs60
    ):

        relative_rs60 = (
            stock_rs60
            - bench_rs60
        )

    else:

        relative_rs60 = stock_rs60

    return (
        stock_rs20,
        stock_rs60,
        relative_rs20,
        relative_rs60,
    )


# ============================================================
# BASE QUALITY
# ============================================================

def _base_metrics(df):

    recent = df.tail(
        BASE_LOOKBACK
    )

    if len(recent) < 15:
        return {
            "BaseRangePct": np.nan,
            "Compression": 0.0,
        }

    high = _num(
        recent["High"].max()
    )

    low = _num(
        recent["Low"].min()
    )

    close = _num(
        df["Close"].iloc[-1]
    )

    if (
        not np.isfinite(high)
        or not np.isfinite(low)
        or low <= 0
    ):

        return {
            "BaseRangePct": np.nan,
            "Compression": 0.0,
        }

    base_range = (
        (high - low)
        / low
    ) * 100.0

    # --------------------------------------------------------
    # Compare first half and second half of the base.
    # A narrower second half = better compression.
    # --------------------------------------------------------

    half = len(recent) // 2

    first = recent.iloc[
        :half
    ]

    second = recent.iloc[
        half:
    ]

    first_range = (
        (
            first["High"].max()
            - first["Low"].min()
        )
        / max(
            first["Low"].min(),
            0.01,
        )
    ) * 100.0

    second_range = (
        (
            second["High"].max()
            - second["Low"].min()
        )
        / max(
            second["Low"].min(),
            0.01,
        )
    ) * 100.0

    if first_range > 0:

        compression = (
            1.0
            - (
                second_range
                / first_range
            )
        ) * 100.0

    else:

        compression = 0.0

    compression = max(
        0.0,
        min(
            100.0,
            compression,
        ),
    )

    return {
        "BaseRangePct": base_range,
        "Compression": compression,
    }


# ============================================================
# BREAKOUT METRICS
# ============================================================

def _breakout_metrics(df):

    close = _num(
        df["Close"].iloc[-1]
    )

    # IMPORTANT:
    # Exclude today's candle.
    # This prevents today's close from becoming
    # today's own resistance.

    prior = df.iloc[
        :-1
    ]

    if len(prior) < RESISTANCE_LOOKBACK:
        return None

    resistance_window = prior.tail(
        RESISTANCE_LOOKBACK
    )

    resistance = _num(
        resistance_window["High"].max()
    )

    if (
        not np.isfinite(resistance)
        or resistance <= 0
    ):

        return None

    breakout_pct = (
        (
            close
            / resistance
        ) - 1.0
    ) * 100.0

    return {
        "Resistance": resistance,
        "BreakoutPct": breakout_pct,
    }


# ============================================================
# TREND
# ============================================================

def _trend_metrics(df):

    close = df["Close"]

    e20 = ema(
        close,
        EMA_FAST,
    )

    e50 = ema(
        close,
        EMA_MID,
    )

    e200 = ema(
        close,
        EMA_SLOW,
    )

    close_now = _num(
        close.iloc[-1]
    )

    ema20 = _num(
        e20.iloc[-1]
    )

    ema50 = _num(
        e50.iloc[-1]
    )

    ema200 = _num(
        e200.iloc[-1]
    )

    if not all(
        np.isfinite(x)
        for x in [
            close_now,
            ema20,
            ema50,
            ema200,
        ]
    ):

        return None

    extension = (
        (
            close_now
            / ema20
        ) - 1.0
    ) * 100.0

    return {
        "EMA20": ema20,
        "EMA50": ema50,
        "EMA200": ema200,
        "ExtensionPct": extension,
        "Trend20Above50": ema20 > ema50,
        "Trend50Above200": ema50 > ema200,
        "CloseAbove20": close_now > ema20,
    }


# ============================================================
# MOMENTUM
# ============================================================

def _momentum_metrics(df):

    close = df["Close"]

    rsi_series = rsi(
        close,
        RSI_PERIOD,
    )

    rsi_now = _num(
        rsi_series.iloc[-1]
    )

    macd_line, signal, hist = macd(
        close
    )

    macd_hist = _num(
        hist.iloc[-1]
    )

    previous_hist = _num(
        hist.iloc[-2]
    )

    return {
        "RSI": rsi_now,
        "MACDHist": macd_hist,
        "MACDImproving": (
            np.isfinite(
                macd_hist
            )
            and np.isfinite(
                previous_hist
            )
            and macd_hist
            >= previous_hist
        ),
    }


# ============================================================
# VOLUME
# ============================================================

def _volume_metrics(df):

    volume = df["Volume"]

    rvol = _num(
        relative_volume(
            df,
            20,
        )
    )

    avg_volume = _num(
        volume.tail(20).mean()
    )

    current_volume = _num(
        volume.iloc[-1]
    )

    if (
        not np.isfinite(avg_volume)
        or avg_volume <= 0
    ):

        avg_volume = np.nan

    return {
        "RVOL": rvol,
        "AvgVolume20": avg_volume,
        "CurrentVolume": current_volume,
    }


# ============================================================
# CANDLE STRENGTH
# ============================================================

def _candle_metrics(df):

    strength = _num(
        closing_strength(df)
    )

    open_price = _num(
        df["Open"].iloc[-1]
    )

    close = _num(
        df["Close"].iloc[-1]
    )

    high = _num(
        df["High"].iloc[-1]
    )

    low = _num(
        df["Low"].iloc[-1]
    )

    day_return = np.nan

    if (
        np.isfinite(open_price)
        and open_price > 0
    ):

        day_return = (
            (
                close
                / open_price
            ) - 1.0
        ) * 100.0

    return {
        "ClosingStrength": strength,
        "DayReturnPct": day_return,
        "High": high,
        "Low": low,
        "Close": close,
    }


# ============================================================
# SETUP CLASSIFICATION
# ============================================================

def _classify_setup(
    trend,
    momentum,
    volume,
    breakout,
    base,
    candle,
):

    if (
        trend is None
        or momentum is None
        or volume is None
        or breakout is None
        or base is None
        or candle is None
    ):

        return None

    gap = _num(
        breakout["BreakoutPct"]
    )

    rsi_now = _num(
        momentum["RSI"]
    )

    rvol = _num(
        volume["RVOL"]
    )

    extension = _num(
        trend["ExtensionPct"]
    )

    close_strength = _num(
        candle["ClosingStrength"]
    )

    base_range = _num(
        base["BaseRangePct"]
    )

    # --------------------------------------------------------
    # FRESH BREAKOUT
    #
    # Price has actually cleared prior resistance.
    # --------------------------------------------------------

    fresh = (
        gap > 0.0
        and gap <= MAX_FRESH_BREAKOUT_GAP
        and rvol >= MIN_FRESH_RVOL
        and rsi_now >= MIN_FRESH_RSI
        and close_strength >= 0.60
        and trend["Trend20Above50"]
        and trend["Trend50Above200"]
        and trend["CloseAbove20"]
        and extension <= MAX_EXTENSION_FROM_EMA20
    )

    if fresh:

        return "FRESH BREAKOUT"

    # --------------------------------------------------------
    # PRE-BREAKOUT
    #
    # Price is still below resistance but within 5%.
    # We deliberately do NOT accept stocks that are
    # already extended far above EMA20.
    # --------------------------------------------------------

    pre = (
        gap <= 0.0
        and gap >= -MAX_PRE_BREAKOUT_GAP
        and rsi_now >= MIN_PRE_RSI
        and rvol >= MIN_PRE_RVOL
        and trend["Trend20Above50"]
        and trend["Trend50Above200"]
        and trend["CloseAbove20"]
        and extension <= MAX_EXTENSION_FROM_EMA20
        and base_range <= 18.0
    )

    if pre:

        return "PRE-BREAKOUT"

    return None


# ============================================================
# SCORE
# ============================================================

def _score_setup(
    setup,
    trend,
    momentum,
    volume,
    breakout,
    base,
    candle,
    relative_rs20,
    relative_rs60,
):

    score = 0.0

    # ========================================================
    # 1. TREND QUALITY — 20 POINTS
    # ========================================================

    if trend["Trend20Above50"]:
        score += 7

    if trend["Trend50Above200"]:
        score += 7

    if trend["CloseAbove20"]:
        score += 6

    # ========================================================
    # 2. RELATIVE STRENGTH — 15 POINTS
    # ========================================================

    rs60 = _num(
        relative_rs60,
        0.0,
    )

    rs20 = _num(
        relative_rs20,
        0.0,
    )

    if rs60 >= 20:
        score += 8

    elif rs60 >= 10:
        score += 6

    elif rs60 >= 5:
        score += 4

    elif rs60 >= 0:
        score += 2

    if rs20 >= 10:
        score += 7

    elif rs20 >= 5:
        score += 5

    elif rs20 >= 0:
        score += 3

    # ========================================================
    # 3. BASE QUALITY — 20 POINTS
    # ========================================================

    base_range = _num(
        base["BaseRangePct"],
        20,
    )

    compression = _num(
        base["Compression"],
        0,
    )

    if base_range <= 8:
        score += 12

    elif base_range <= 10:
        score += 10

    elif base_range <= 13:
        score += 8

    elif base_range <= 18:
        score += 5

    if compression >= 30:
        score += 8

    elif compression >= 15:
        score += 6

    elif compression >= 0:
        score += 3

    # ========================================================
    # 4. BREAKOUT QUALITY / PROXIMITY — 15 POINTS
    # ========================================================

    gap = _num(
        breakout["BreakoutPct"],
        -10,
    )

    if setup == "FRESH BREAKOUT":

        if 0 <= gap <= 2:
            score += 15

        elif gap <= 4:
            score += 13

        elif gap <= 6:
            score += 10

    else:

        distance = abs(gap)

        if distance <= 1:
            score += 15

        elif distance <= 2:
            score += 13

        elif distance <= 3:
            score += 11

        elif distance <= 5:
            score += 8

    # ========================================================
    # 5. VOLUME — 15 POINTS
    # ========================================================

    rvol = _num(
        volume["RVOL"],
        0,
    )

    if rvol >= 3:
        score += 15

    elif rvol >= 2:
        score += 13

    elif rvol >= 1.5:
        score += 10

    elif rvol >= 1.2:
        score += 7

    elif rvol >= 1:
        score += 4

    # ========================================================
    # 6. MOMENTUM — 10 POINTS
    # ========================================================

    rsi_now = _num(
        momentum["RSI"],
        50,
    )

    if 60 <= rsi_now <= 72:
        score += 8

    elif 55 <= rsi_now < 60:
        score += 6

    elif 72 < rsi_now <= 78:
        score += 5

    elif rsi_now >= 50:
        score += 3

    if momentum["MACDImproving"]:
        score += 2

    # ========================================================
    # 7. RISK / ENTRY QUALITY — 5 POINTS
    # ========================================================

    extension = _num(
        trend["ExtensionPct"],
        99,
    )

    if extension <= 5:
        score += 5

    elif extension <= 8:
        score += 4

    elif extension <= 12:
        score += 2

    # ========================================================
    # CHASE PENALTY
    # ========================================================

    # Strong stocks are useful.
    # Buying a stock after it has already run too far is not.

    if extension > 10:
        score -= 5

    if setup == "FRESH BREAKOUT":

        if gap > 5:
            score -= 5

    score = max(
        0,
        min(
            100,
            round(score),
        ),
    )

    return int(score)


# ============================================================
# TRADE LEVELS
# ============================================================

def _trade_levels(
    df,
    setup,
    resistance,
    atr_value,
):

    close = _num(
        df["Close"].iloc[-1]
    )

    low20 = _num(
        df["Low"].tail(20).min()
    )

    ema20 = _num(
        ema(
            df["Close"],
            20,
        ).iloc[-1]
    )

    atr_now = _num(
        atr_value
    )

    if not np.isfinite(
        atr_now
    ) or atr_now <= 0:

        atr_now = close * 0.03

    # --------------------------------------------------------
    # Entry
    # --------------------------------------------------------

    if setup == "FRESH BREAKOUT":

        entry = close

    else:

        # Pre-breakout entry is slightly above resistance,
        # representing confirmation rather than anticipation.
        entry = resistance * 1.005

    # --------------------------------------------------------
    # Stop
    # --------------------------------------------------------

    swing_stop = (
        low20
        if np.isfinite(low20)
        else ema20
    )

    atr_stop = (
        entry
        - 1.5 * atr_now
    )

    if setup == "FRESH BREAKOUT":

        stop = max(
            swing_stop,
            atr_stop,
        )

    else:

        stop = max(
            swing_stop,
            entry - 1.5 * atr_now,
        )

    # Ensure stop remains below entry.

    if stop >= entry:

        stop = (
            entry
            - 1.5 * atr_now
        )

    risk = (
        entry
        - stop
    )

    # Safety fallback.

    if risk <= 0:

        risk = entry * 0.03

        stop = (
            entry
            - risk
        )

    t1 = (
        entry
        + 2.0 * risk
    )

    t2 = (
        entry
        + 3.0 * risk
    )

    return {
        "Entry": round(
            entry,
            2,
        ),
        "SL": round(
            stop,
            2,
        ),
        "T1": round(
            t1,
            2,
        ),
        "T2": round(
            t2,
            2,
        ),
        "RiskPct": round(
            (
                risk
                / entry
            ) * 100,
            2,
        ),
    }


# ============================================================
# MAIN SCORING FUNCTION
# ============================================================

def score_stock(
    df,
    benchmark_df=None,
):

    data = _prepare_dataframe(
        df
    )

    if data is None:
        return None

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    trend = _trend_metrics(
        data
    )

    if trend is None:
        return None

    momentum = _momentum_metrics(
        data
    )

    volume = _volume_metrics(
        data
    )

    candle = _candle_metrics(
        data
    )

    breakout = _breakout_metrics(
        data
    )

    if breakout is None:
        return None

    base = _base_metrics(
        data
    )

    (
        stock_rs20,
        stock_rs60,
        relative_rs20,
        relative_rs60,
    ) = _relative_strength(
        data,
        benchmark_df,
    )

    # --------------------------------------------------------
    # Setup classification
    # --------------------------------------------------------

    setup = _classify_setup(
        trend,
        momentum,
        volume,
        breakout,
        base,
        candle,
    )

    if setup is None:
        return None

    # --------------------------------------------------------
    # Score
    # --------------------------------------------------------

    score = _score_setup(
        setup=setup,
        trend=trend,
        momentum=momentum,
        volume=volume,
        breakout=breakout,
        base=base,
        candle=candle,
        relative_rs20=relative_rs20,
        relative_rs60=relative_rs60,
    )

    # --------------------------------------------------------
    # Trade levels
    # --------------------------------------------------------

    atr_series = atr(
        data,
        14,
    )

    atr_now = _num(
        atr_series.iloc[-1]
    )

    levels = _trade_levels(
        data,
        setup,
        breakout["Resistance"],
        atr_now,
    )

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    result = {
        "Setup": setup,
        "Score": score,

        "BreakoutPct": round(
            _num(
                breakout["BreakoutPct"],
                0,
            ),
            2,
        ),

        "RS20": round(
            _num(
                relative_rs20,
                0,
            ),
            2,
        ),

        "RS60": round(
            _num(
                relative_rs60,
                0,
            ),
            2,
        ),

        "StockRS20": round(
            _num(
                stock_rs20,
                0,
            ),
            2,
        ),

        "StockRS60": round(
            _num(
                stock_rs60,
                0,
            ),
            2,
        ),

        "RSI": round(
            _num(
                momentum["RSI"],
                50,
            ),
            1,
        ),

        "RVOL": round(
            _num(
                volume["RVOL"],
                0,
            ),
            2,
        ),

        "BaseRangePct": round(
            _num(
                base["BaseRangePct"],
                0,
            ),
            2,
        ),

        "Compression": round(
            _num(
                base["Compression"],
                0,
            ),
            2,
        ),

        "ExtensionPct": round(
            _num(
                trend["ExtensionPct"],
                0,
            ),
            2,
        ),

        "Resistance": round(
            _num(
                breakout["Resistance"],
                0,
            ),
            2,
        ),

        "ClosingStrength": round(
            _num(
                candle["ClosingStrength"],
                0,
            ),
            2,
        ),

        "Entry": levels["Entry"],
        "SL": levels["SL"],
        "T1": levels["T1"],
        "T2": levels["T2"],
        "RiskPct": levels["RiskPct"],
    }

    return result

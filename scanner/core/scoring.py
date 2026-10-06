import numpy as np
import pandas as pd
from .indicators import ema, rsi, atr, relative_volume, closing_strength


def _clip(x, lo=0, hi=100):
    return max(lo, min(hi, float(x)))


def _safe(x, default=0.0):
    return default if pd.isna(x) or not np.isfinite(x) else float(x)


def _base_metrics(df):
    close = pd.to_numeric(df["Close"], errors="coerce")
    high = pd.to_numeric(df["High"], errors="coerce")
    low = pd.to_numeric(df["Low"], errors="coerce")
    volume = pd.to_numeric(df["Volume"], errors="coerce")
    e20 = ema(close, 20)
    e50 = ema(close, 50)
    e200 = ema(close, 200)
    atr14 = atr(df, 14)
    r = rsi(close, 14)
    avg20 = volume.rolling(20).mean()
    resistance20 = high.shift(1).rolling(20).max()
    resistance30 = high.shift(1).rolling(30).max()
    resistance55 = high.shift(1).rolling(55).max()
    range20 = (high.rolling(20).max() - low.rolling(20).min()) / low.rolling(20).min()
    range10 = (high.rolling(10).max() - low.rolling(10).min()) / low.rolling(10).min()
    vol_ratio = volume / avg20
    return locals()


def score_stock(df, benchmark_df=None):
    if df is None or len(df) < 220:
        return None
    try:
        m = _base_metrics(df)
        close = m["close"]; high = m["high"]; low = m["low"]; volume = m["volume"]
        e20 = m["e20"]; e50 = m["e50"]; e200 = m["e200"]; atr14 = m["atr14"]; r = m["r"]
        avg20 = m["avg20"]; res20 = m["resistance20"]; res30 = m["resistance30"]; res55 = m["resistance55"]
        range20 = m["range20"]; range10 = m["range10"]; vr = m["vol_ratio"]

        c = float(close.iloc[-1]); a = _safe(atr14.iloc[-1]); rr = _safe(r.iloc[-1]); rv = _safe(vr.iloc[-1])
        r20 = _safe(res20.iloc[-1]); r30 = _safe(res30.iloc[-1]); r55 = _safe(res55.iloc[-1])
        dist20 = (c / r20 - 1) * 100 if r20 else 999
        dist30 = (c / r30 - 1) * 100 if r30 else 999
        dist55 = (c / r55 - 1) * 100 if r55 else 999
        close_strength = _safe((c - float(low.iloc[-1])) / max(float(high.iloc[-1] - low.iloc[-1]), 1e-9))
        trend = c > e20.iloc[-1] > e50.iloc[-1] > e200.iloc[-1]
        trend_partial = c > e20.iloc[-1] and e20.iloc[-1] > e50.iloc[-1]
        ret20 = c / float(close.iloc[-21]) - 1 if len(close) > 21 else 0
        ret60 = c / float(close.iloc[-61]) - 1 if len(close) > 61 else 0

        if benchmark_df is not None and len(benchmark_df) >= 61:
            bc = pd.to_numeric(benchmark_df["Close"], errors="coerce").dropna()
            bench20 = float(bc.iloc[-1] / bc.iloc[-21] - 1)
            bench60 = float(bc.iloc[-1] / bc.iloc[-61] - 1)
            rs20 = ret20 - bench20
            rs60 = ret60 - bench60
        else:
            rs20 = ret20
            rs60 = ret60

        # A fresh breakout is allowed only if it is recent and not already extended.
        breakout = c > r20 * 1.002 and c <= r20 * 1.06 and rv >= 1.35 and rr >= 55 and trend_partial
        fresh_breakout = False
        for i in range(max(1, len(close) - 3), len(close)):
            prior_res = float(high.iloc[:i].tail(20).max())
            if float(close.iloc[i]) > prior_res * 1.002 and float(close.iloc[i]) <= prior_res * 1.08:
                fresh_breakout = True
                break
        breakout = breakout or fresh_breakout

        # Pre-breakout: tight base, close near resistance, but not already broken too far.
        tight_base = _safe(range20.iloc[-1], 1) <= 0.18 and _safe(range10.iloc[-1], 1) <= 0.12
        volume_contracting = _safe(volume.iloc[-1] / max(avg20.iloc[-1], 1)) <= 1.35
        near_resistance = -3.0 <= dist20 <= 1.5
        pre_breakout = tight_base and near_resistance and trend and rr >= 52 and rs60 > 0 and volume_contracting

        if not breakout and not pre_breakout:
            return None

        setup = "BREAKOUT" if breakout else "PRE-BREAKOUT"
        score = 0.0

        # Trend quality: 20 points
        score += 8 if trend else 5 if trend_partial else 0
        score += 4 if c > e200.iloc[-1] else 0
        score += 4 if e50.iloc[-1] > e200.iloc[-1] else 0
        score += 4 if e20.iloc[-1] > e50.iloc[-1] else 0

        # Relative strength: 15
        score += _clip(7.5 + rs20 * 80, 0, 10)
        score += _clip(5 + rs60 * 30, 0, 5)

        # Base / setup quality: 20
        if setup == "PRE-BREAKOUT":
            score += _clip(12 - _safe(range20.iloc[-1]) * 40, 0, 12)
            score += 5 if tight_base else 0
            score += _clip(3 - abs(dist20) * 1.2, 0, 3)
        else:
            score += 10
            score += _clip(7 - max(dist20, 0) * 1.2, 0, 7)
            score += 3 if rv >= 2 else 2 if rv >= 1.5 else 0

        # Volume: 15
        score += _clip((rv - 0.8) * 7, 0, 10)
        score += 5 if close_strength >= 0.75 else 3 if close_strength >= 0.60 else 0

        # Momentum: 10
        score += 5 if 58 <= rr <= 72 else 3 if 52 <= rr < 58 else 1 if rr < 78 else 0
        score += 5 if ret20 > 0.08 else 4 if ret20 > 0.04 else 2 if ret20 > 0 else 0

        # Risk/reward: 5. Prefer manageable ATR and room to resistance/target.
        atr_pct = a / c * 100 if c else 99
        score += 5 if 2 <= atr_pct <= 6 else 3 if atr_pct <= 8 else 1

        # Chase penalty. This is deliberately strong.
        extension = (c / float(e20.iloc[-1]) - 1) * 100
        if extension > 10:
            score -= min(15, (extension - 10) * 1.5)
        elif extension > 7:
            score -= (extension - 7) * 1.0
        if rr > 78:
            score -= 6

        score = int(round(_clip(score, 0, 100)))
        if score < 60:
            return None

        entry = c
        sl = c - max(1.5 * a, c * 0.03)
        t1 = c + 1.5 * a
        t2 = c + 3.0 * a
        t3 = c + 4.5 * a
        risk = c - sl
        rr1 = (t1 - c) / risk if risk else 0

        return {
            "Entry": round(entry, 2), "Score": score, "Setup": setup,
            "RSI": round(rr, 1), "RVOL": round(rv, 2),
            "RS20": round(rs20 * 100, 2), "RS60": round(rs60 * 100, 2),
            "BreakoutPct": round(dist20, 2), "BaseRangePct": round(_safe(range20.iloc[-1]) * 100, 2),
            "ExtensionPct": round(extension, 2), "Grade": "A+" if score >= 90 else "A" if score >= 80 else "B+" if score >= 70 else "B",
            "Trade": "SWING", "SL": round(sl, 2), "T1": round(t1, 2), "T2": round(t2, 2), "T3": round(t3, 2),
            "RR1": round(rr1, 2), "EMA20": round(float(e20.iloc[-1]), 2), "EMA50": round(float(e50.iloc[-1]), 2),
            "EMA200": round(float(e200.iloc[-1]), 2), "ATR": round(a, 2),
        }
    except Exception:
        return None

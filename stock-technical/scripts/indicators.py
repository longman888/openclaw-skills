#!/usr/bin/env python3
"""
Technical Indicators — Pure Python implementation.
All indicators are vectorized (operate on arrays) for efficiency.

Usage:
    from indicators import SMA, EMA, MACD, KDJ, RSI, BollingerBands, ATR, OBV
"""

import math
from typing import List

# ─── Core Indicators ───────────────────────────────────────────────────────────

def SMA(close: List[float], period: int) -> List[float]:
    """Simple Moving Average."""
    if len(close) < period:
        return []
    result = []
    for i in range(period - 1, len(close)):
        result.append(sum(close[i - period + 1:i + 1]) / period)
    return result


def EMA(close: List[float], period: int) -> List[float]:
    """Exponential Moving Average."""
    if len(close) < period:
        return []
    alpha = 2 / (period + 1)
    result = [sum(close[:period]) / period]
    for price in close[period:]:
        ema = alpha * price + (1 - alpha) * result[-1]
        result.append(ema)
    return result


def MACD(
    close: List[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> dict:
    """
    MACD (Moving Average Convergence Divergence).
    Returns DIF, DEA (Signal), Histogram, and crossover signal.
    """
    if len(close) < slow_period + signal_period:
        return {"macd": 0, "signal": 0, "histogram": 0, "crossover": None,
                "dif": [], "dea": [], "histogram_series": []}

    ema_fast = EMA(close, fast_period)
    ema_slow = EMA(close, slow_period)

    # DIF = EMA_fast - EMA_slow
    dif = [f - s for f, s in zip(ema_fast, ema_slow)]

    # DEA (Signal) = EMA(DIF, signal_period)
    # Align: DIF starts from slow_period-1
    dif_aligned = [0] * (slow_period - 1) + dif
    dea = EMA(dif_aligned, signal_period)

    # MACD Histogram = (DIF - DEA) * 2
    # Align dea to dif length
    offset = len(dif) - len(dea)
    histogram = []
    for i, d in enumerate(dif):
        j = i - offset
        if j >= 0 and j < len(dea):
            histogram.append((d - dea[j]) * 2)
        else:
            histogram.append(0)

    # Crossover detection
    crossover = None
    if len(histogram) >= 2:
        if histogram[-2] <= 0 and histogram[-1] > 0:
            crossover = "golden"
        elif histogram[-2] >= 0 and histogram[-1] < 0:
            crossover = "death"

    # Latest values (from aligned index)
    latest_dif = dif[-1] if dif else 0
    latest_dea = dea[-1] if dea else 0
    latest_hist = histogram[-1] if histogram else 0

    return {
        "macd": round(latest_dif, 4),
        "signal": round(latest_dea, 4),
        "histogram": round(latest_hist, 4),
        "crossover": crossover,
        "dif": dif,
        "dea": dea,
        "histogram_series": histogram
    }


def KDJ(
    high: List[float],
    low: List[float],
    close: List[float],
    period: int = 9,
    k_period: int = 3,
    d_period: int = 3
) -> dict:
    """
    KDJ Indicator (Stochastic).
    Returns K, D, J values and overbought/oversold signal.
    """
    if len(close) < period:
        return {"k": 50, "d": 50, "j": 50, "crossover": None}

    rsv = []
    for i in range(period - 1, len(close)):
        h = max(high[i - period + 1:i + 1])
        l = min(low[i - period + 1:i + 1])
        c = close[i]
        if h == l:
            rsv.append(50)
        else:
            rsv.append((c - l) / (h - l) * 100)

    # K = SMA(RSV, k_period), D = SMA(K, d_period)
    k_vals = [50.0]
    for r in rsv[:k_period]:
        k_vals.append((k_vals[-1] * (k_period - 1) + r) / k_period)

    d_vals = [50.0]
    for k in k_vals[k_period:]:
        d_vals.append((d_vals[-1] * (d_period - 1) + k) / d_period)

    # J = 3*K - 2*D
    j_vals = [3 * k - 2 * d for k, d in zip(k_vals, d_vals)]

    latest_k = k_vals[-1] if k_vals else 50
    latest_d = d_vals[-1] if d_vals else 50
    latest_j = j_vals[-1] if j_vals else 50

    # Crossover
    crossover = None
    if len(k_vals) >= 2 and len(d_vals) >= 2:
        if k_vals[-2] <= d_vals[-2] and k_vals[-1] > d_vals[-1]:
            crossover = "golden"
        elif k_vals[-2] >= d_vals[-2] and k_vals[-1] < d_vals[-1]:
            crossover = "death"

    return {
        "k": round(latest_k, 2),
        "d": round(latest_d, 2),
        "j": round(latest_j, 2),
        "crossover": crossover,
        "overbought": latest_k > 80 or latest_j > 100,
        "oversold": latest_k < 20 or latest_j < 0
    }


def RSI(close: List[float], period: int = 14) -> dict:
    """Relative Strength Index."""
    if len(close) < period + 1:
        return {"rsi": 50, "signal": "neutral"}

    changes = [close[i] - close[i - 1] for i in range(1, len(close))]
    gains = [max(c, 0) for c in changes]
    losses = [abs(min(c, 0)) for c in changes]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    rsi_values = []
    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi_values.append(100)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100 - 100 / (1 + rs))

    latest_rsi = rsi_values[-1] if rsi_values else 50
    signal = "overbought" if latest_rsi > 70 else "oversold" if latest_rsi < 30 else "neutral"

    return {"rsi": round(latest_rsi, 2), "signal": signal, "series": rsi_values}


def BollingerBands(close: List[float], period: int = 20, std_dev: float = 2) -> dict:
    """Bollinger Bands."""
    if len(close) < period:
        return {"upper": 0, "middle": 0, "lower": 0, "bandwidth": 0, "position": 0.5}

    sma_vals = SMA(close, period)
    if not sma_vals:
        return {"upper": 0, "middle": 0, "lower": 0, "bandwidth": 0, "position": 0.5}

    middle = sma_vals[-1]
    std = math.sqrt(sum((c - middle) ** 2 for c in close[-period:]) / period)
    upper = middle + std_dev * std
    lower = middle - std_dev * std

    # Bandwidth = (Upper - Lower) / Middle
    bandwidth = (upper - lower) / middle if middle else 0

    # Position = (Price - Lower) / (Upper - Lower)
    latest = close[-1]
    if upper != lower:
        position = (latest - lower) / (upper - lower)
    else:
        position = 0.5

    return {
        "upper": round(upper, 2),
        "middle": round(middle, 2),
        "lower": round(lower, 2),
        "bandwidth": round(bandwidth, 4),
        "position": round(position, 2),
        "squeeze": bandwidth < 0.1  # Bandwidth below average
    }


def ATR(high: List[float], low: List[float], close: List[float], period: int = 14) -> dict:
    """Average True Range."""
    if len(close) < period + 1:
        return {"atr": 0, "atr_pct": 0}

    trs = []
    for i in range(1, len(close)):
        h = high[i]
        l = low[i]
        pc = close[i - 1]
        tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)

    atr_vals = SMA(trs, period)
    latest_atr = atr_vals[-1] if atr_vals else trs[-1]
    latest_close = close[-1]
    atr_pct = (latest_atr / latest_close * 100) if latest_close else 0

    return {"atr": round(latest_atr, 4), "atr_pct": round(atr_pct, 2)}


def OBV(close: List[float], volume: List[int]) -> dict:
    """On-Balance Volume."""
    if len(close) != len(volume) or len(close) < 2:
        return {"obv": 0, "trend": "neutral"}

    obv = [0]
    for i in range(1, len(close)):
        if close[i] > close[i - 1]:
            obv.append(obv[-1] + volume[i])
        elif close[i] < close[i - 1]:
            obv.append(obv[-1] - volume[i])
        else:
            obv.append(obv[-1])

    latest_obv = obv[-1]
    trend = "increasing" if obv[-1] > obv[-2] else "decreasing" if obv[-1] < obv[-2] else "neutral"

    return {"obv": latest_obv, "trend": trend}


# ─── Multi-Indicator Analysis ──────────────────────────────────────────────────

def full_analysis(
    close: List[float],
    high: List[float],
    low: List[float],
    volume: List[int]
) -> dict:
    """Run all indicators on price data."""
    result = {}

    if len(close) >= 20:
        result["ma"] = {
            "ma5": round(SMA(close, 5)[-1], 2) if len(close) >= 5 else None,
            "ma10": round(SMA(close, 10)[-1], 2) if len(close) >= 10 else None,
            "ma20": round(SMA(close, 20)[-1], 2) if len(close) >= 20 else None,
            "ma60": round(SMA(close, 60)[-1], 2) if len(close) >= 60 else None,
        }
        result["bb"] = BollingerBands(close)
        result["atr"] = ATR(high, low, close)

    if len(close) >= 26:
        result["macd"] = MACD(close)

    if len(close) >= 14:
        result["rsi"] = RSI(close)

    if len(high) >= 9 and len(low) >= 9:
        result["kdj"] = KDJ(high, low, close)

    if len(volume) == len(close) and len(close) >= 2:
        result["obv"] = OBV(close, volume)

    return result


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse, json

    parser = argparse.ArgumentParser(description="Technical Indicators")
    sub = parser.add_subparsers(dest="cmd")

    p_calc = sub.add_parser("calc", help="Calculate indicators")
    p_calc.add_argument("--close", required=True, help="Comma-separated close prices")
    p_calc.add_argument("--high", default="", help="Comma-separated high prices")
    p_calc.add_argument("--low", default="", help="Comma-separated low prices")
    p_calc.add_argument("--volume", default="", help="Comma-separated volume")
    p_calc.add_argument("--indicators", default="all", help="Indicators to calculate")

    args = parser.parse_args()

    close = [float(x) for x in args.close.split(",")]
    high = [float(x) for x in args.high.split(",")] if args.high else close[:]
    low = [float(x) for x in args.low.split(",")] if args.low else close[:]
    volume = [int(x) for x in args.volume.split(",")] if args.volume else [1000000] * len(close)

    if args.indicators == "all":
        result = full_analysis(close, high, low, volume)
    else:
        result = {}
        for ind in args.indicators.split(","):
            ind = ind.strip()
            if ind == "sma":
                result["sma20"] = SMA(close, 20)[-1] if len(close) >= 20 else None
            elif ind == "ema":
                result["ema20"] = EMA(close, 20)[-1] if len(close) >= 20 else None
            elif ind == "macd":
                result["macd"] = MACD(close)
            elif ind == "rsi":
                result["rsi"] = RSI(close)
            elif ind == "kdj":
                result["kdj"] = KDJ(high, low, close)
            elif ind == "bb":
                result["bb"] = BollingerBands(close)
            elif ind == "atr":
                result["atr"] = ATR(high, low, close)

    print(json.dumps(result, indent=2, ensure_ascii=False))

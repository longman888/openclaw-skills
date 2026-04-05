#!/usr/bin/env python3
"""
Signal Generator — generates buy/sell/hold signals from technical analysis.
Supports: trend_following, mean_reversion, breakout, multi_factor.
"""

import math
import logging
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("signal-generator")


# ─── Signal Model ─────────────────────────────────────────────────────────────

@dataclass
class Signal:
    symbol: str
    signal: str           # STRONG_BUY / BUY / HOLD / SELL / STRONG_SELL
    confidence: float     # 0.0 - 1.0
    entry: float
    stop_loss: float
    target: float
    position_size: float  # 0.0 - 1.0
    risk_reward: float
    reason: str
    indicators: dict
    timestamp: str
    strategy: str

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol, "signal": self.signal,
            "confidence": self.confidence, "entry": self.entry,
            "stop_loss": self.stop_loss, "target": self.target,
            "position_size": self.position_size, "risk_reward": self.risk_reward,
            "reason": self.reason, "indicators": self.indicators,
            "timestamp": self.timestamp, "strategy": self.strategy
        }


# ─── Indicator Scoring ────────────────────────────────────────────────────────

def score_indicators(ind: dict) -> tuple[int, list[str]]:
    """
    Score indicators. Returns (score, signals).
    Positive = bullish, Negative = bearish.
    """
    score = 0
    signals = []

    # MA scoring
    ma = ind.get("ma", {})
    if all(v is not None for v in ma.values()):
        if ma["ma5"] > ma["ma10"] > ma["ma20"] > ma["ma60"]:
            score += 2
            signals.append("MA多头排列")
        elif ma["ma5"] < ma["ma10"] < ma["ma20"] < ma["ma60"]:
            score -= 2
            signals.append("MA空头排列")
        elif ma["ma5"] > ma["ma20"]:
            score += 1
            signals.append("MA短期多头")
        elif ma["ma5"] < ma["ma20"]:
            score -= 1
            signals.append("MA短期空头")

    # MACD scoring
    macd = ind.get("macd", {})
    if macd.get("crossover") == "golden":
        score += 2
        signals.append("MACD金叉")
    elif macd.get("crossover") == "death":
        score -= 2
        signals.append("MACD死叉")
    if macd.get("histogram", 0) > 0:
        score += 1
        signals.append("MACD柱正值")
    elif macd.get("histogram", 0) < 0:
        score -= 1
        signals.append("MACD柱负值")

    # RSI scoring
    rsi = ind.get("rsi", {})
    rsi_val = rsi.get("rsi", 50)
    if rsi_val > 70:
        score -= 1
        signals.append("RSI超买")
    elif rsi_val < 30:
        score += 1
        signals.append("RSI超卖")
    elif 50 < rsi_val < 70:
        score += 1
        signals.append("RSI偏强")
    elif 30 < rsi_val < 50:
        score -= 1
        signals.append("RSI偏弱")

    # KDJ scoring
    kdj = ind.get("kdj", {})
    if kdj.get("crossover") == "golden":
        score += 1
        signals.append("KDJ金叉")
    elif kdj.get("crossover") == "death":
        score -= 1
        signals.append("KDJ死叉")
    if kdj.get("overbought"):
        score -= 1
        signals.append("KDJ超买")
    elif kdj.get("oversold"):
        score += 1
        signals.append("KDJ超卖")

    # Bollinger Bands
    bb = ind.get("bb", {})
    if bb.get("position", 0.5) > 0.8:
        score -= 1
        signals.append("BB价格靠近上轨")
    elif bb.get("position", 0.5) < 0.2:
        score += 1
        signals.append("BB价格靠近下轨")

    return score, signals


# ─── Signal Generation ─────────────────────────────────────────────────────

def generate_signal(
    symbol: str,
    current_price: float,
    indicators: dict,
    strategy: str = "multi_factor"
) -> Optional[Signal]:
    """Generate trading signal from indicators."""
    score, signals = score_indicators(indicators)
    atr = indicators.get("atr", {})
    return _build_signal(symbol, current_price, indicators, score, signals, atr, strategy)


def _build_signal(symbol, price, ind, score, signals, atr, strategy) -> Signal:
    """Build a Signal object from score and indicators."""
    # Determine signal level
    if score >= 3:
        signal_str = "STRONG_BUY"
        confidence = min(0.5 + score * 0.1, 0.95)
    elif score == 2:
        signal_str = "BUY"
        confidence = 0.70
    elif score == 1:
        signal_str = "HOLD"
        confidence = 0.50
    elif score == 0:
        signal_str = "HOLD"
        confidence = 0.50
    elif score == -1:
        signal_str = "SELL"
        confidence = 0.65
    else:
        signal_str = "STRONG_SELL"
        confidence = min(0.5 + abs(score) * 0.1, 0.95)

    # Stop loss: ATR-based
    atr_val = atr.get("atr", price * 0.02) if isinstance(atr, dict) and atr.get("atr") else price * 0.02
    if signal_str in ("STRONG_BUY", "BUY"):
        stop_loss = round(price - 2 * atr_val, 2)
        target = round(price + 4 * atr_val, 2)
        position_size = min(confidence * 0.3, 0.30)
    elif signal_str == "HOLD":
        stop_loss = round(price - 3 * atr_val, 2)
        target = round(price + 3 * atr_val, 2)
        position_size = min(confidence * 0.10, 0.10)
    else:
        stop_loss = round(price + 1 * atr_val, 2)
        target = round(price - 3 * atr_val, 2)
        position_size = 0.0

    risk = price - stop_loss
    risk_reward = round((target - price) / risk, 2) if risk > 0 else 0.0

    reason = " + ".join(signals) if signals else "No strong signal"

    return Signal(
        symbol=symbol,
        signal=signal_str,
        confidence=round(confidence, 3),
        entry=round(price, 2),
        stop_loss=stop_loss,
        target=target,
        position_size=round(position_size, 4),
        risk_reward=risk_reward,
        reason=reason[:200],
        indicators={k: str(v) if not isinstance(v, dict) else v for k, v in ind.items()},
        timestamp=datetime.now().isoformat(),
        strategy=strategy
    )


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse, json

    parser = argparse.ArgumentParser(description="Signal Generator")
    sub = parser.add_subparsers(dest="cmd")

    p_calc = sub.add_parser("calc", help="Calculate signal from indicators")
    p_calc.add_argument("--symbol", default="TEST")
    p_calc.add_argument("--price", type=float, default=100.0)
    p_calc.add_argument("--strategy", default="multi_factor")

    args = parser.parse_args()

    if args.cmd == "calc":
        # Mock indicators for testing
        import random
        random.seed(42)
        prices = [100 + random.gauss(0, 2) for _ in range(60)]
        high = [p + abs(random.gauss(0, 1)) for p in prices]
        low = [p - abs(random.gauss(0, 1)) for p in prices]
        volume = [int(random.uniform(1e6, 5e6)) for _ in range(60)]

        from indicators import SMA, EMA, MACD, RSI, KDJ, BollingerBands, ATR, OBV

        ind = {
            "ma": {
                "ma5": round(SMA(prices, 5)[-1], 2),
                "ma10": round(SMA(prices, 10)[-1], 2),
                "ma20": round(SMA(prices, 20)[-1], 2),
                "ma60": round(SMA(prices, 60)[-1], 2) if len(prices) >= 60 else None,
            },
            "macd": MACD(prices),
            "rsi": RSI(prices, 14),
            "kdj": KDJ(high, low, prices, 9),
            "bb": BollingerBands(prices, 20, 2),
            "atr": ATR(high, low, prices, 14),
        }

        sig = generate_signal(args.symbol, args.price, ind, args.strategy)
        if sig:
            print(json.dumps(sig.to_dict(), indent=2, ensure_ascii=False))
        else:
            print("Error: signal is None")

    else:
        parser.print_help()

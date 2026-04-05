#!/usr/bin/env python3
"""
Condition Evaluator
Evaluates condition-based triggers (price, volume, news, signals).

Supports:
- price_above / price_below
- price_change_pct
- volume_spike
- news_keywords
- signal_detected
- portfolio_threshold
"""

import re
import logging
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

# ─── Logging ────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("condition-evaluator")


# ─── Data Sources ─────────────────────────────────────────────────────────────

@dataclass
class MarketData:
    symbol: str
    current_price: float
    prev_close: float
    change_pct: float
    volume: int
    avg_volume_20d: int
    timestamp: str


def fetch_realtime_quote(symbol: str) -> Optional[MarketData]:
    """
    Fetch real-time quote from Yahoo Finance.
    In production, use yfinance library.
    """
    try:
        import subprocess
        result = subprocess.run(
            ["python3", "-c", f"""
import yfinance as yf
t = yf.Ticker('{symbol}')
d = t.fast_info
print(d.last_price, d.previous_close, d.volume or 0)
"""],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split()
            if len(parts) >= 3:
                price = float(parts[0])
                prev = float(parts[1])
                vol = int(parts[2])
                return MarketData(
                    symbol=symbol,
                    current_price=price,
                    prev_close=prev,
                    change_pct=(price - prev) / prev * 100 if prev else 0,
                    volume=vol,
                    avg_volume_20d=vol,  # simplified
                    timestamp=datetime.now().isoformat()
                )
    except Exception as e:
        log.warning(f"Failed to fetch quote for {symbol}: {e}")
    return None


# ─── Condition Evaluators ─────────────────────────────────────────────────────

class ConditionEvaluator:

    def __init__(self):
        self.cache: dict[str, tuple[datetime, MarketData]] = {}

    def get_cached_quote(self, symbol: str, max_age_seconds: int = 60) -> Optional[MarketData]:
        """Get quote with 60-second cache."""
        if symbol in self.cache:
            cached_time, data = self.cache[symbol]
            age = (datetime.now() - cached_time).total_seconds()
            if age < max_age_seconds:
                return data
        data = fetch_realtime_quote(symbol)
        if data:
            self.cache[symbol] = (datetime.now(), data)
        return data

    def evaluate(self, condition_type: str, **kwargs) -> tuple[bool, str]:
        """
        Evaluate a condition. Returns (triggered, reason).
        """
        if condition_type == "price_above":
            return self.price_above(
                kwargs["symbol"], kwargs["threshold"]
            )
        elif condition_type == "price_below":
            return self.price_below(
                kwargs["symbol"], kwargs["threshold"]
            )
        elif condition_type == "price_change_pct":
            return self.price_change_pct(
                kwargs["symbol"], kwargs["threshold"]
            )
        elif condition_type == "volume_spike":
            return self.volume_spike(
                kwargs["symbol"], kwargs["threshold"]
            )
        elif condition_type == "news_keywords":
            return self.news_keywords(
                kwargs["keywords"], kwargs.get("symbol", "")
            )
        elif condition_type == "signal_detected":
            return self.signal_detected(
                kwargs["symbol"], kwargs["condition"]
            )
        elif condition_type == "portfolio_threshold":
            return self.portfolio_threshold(
                kwargs["metric"], kwargs["threshold"]
            )
        else:
            return False, f"Unknown condition type: {condition_type}"

    def price_above(self, symbol: str, threshold: float) -> tuple[bool, str]:
        data = self.get_cached_quote(symbol)
        if not data:
            return False, f"No data for {symbol}"
        triggered = data.current_price >= threshold
        reason = f"{symbol}: {data.current_price:.2f} {'>=' if triggered else '<'} {threshold:.2f}"
        return triggered, reason

    def price_below(self, symbol: str, threshold: float) -> tuple[bool, str]:
        data = self.get_cached_quote(symbol)
        if not data:
            return False, f"No data for {symbol}"
        triggered = data.current_price <= threshold
        reason = f"{symbol}: {data.current_price:.2f} {'<=' if triggered else '>'} {threshold:.2f}"
        return triggered, reason

    def price_change_pct(self, symbol: str, threshold_pct: float) -> tuple[bool, str]:
        data = self.get_cached_quote(symbol)
        if not data:
            return False, f"No data for {symbol}"
        triggered = abs(data.change_pct) >= abs(threshold_pct)
        reason = f"{symbol}: change={data.change_pct:+.2f}%, threshold={threshold_pct:+.2f}%"
        return triggered, reason

    def volume_spike(self, symbol: str, multiplier: float = 3.0) -> tuple[bool, str]:
        data = self.get_cached_quote(symbol)
        if not data:
            return False, f"No data for {symbol}"
        if data.avg_volume_20d == 0:
            return False, f"No volume data for {symbol}"
        ratio = data.volume / data.avg_volume_20d
        triggered = ratio >= multiplier
        reason = f"{symbol}: vol={data.volume:,}, avg={data.avg_volume_20d:,}, ratio={ratio:.1f}x"
        return triggered, reason

    def news_keywords(self, keywords: str, symbol: str = "") -> tuple[bool, str]:
        """
        Check for news containing keywords.
        In production, scrape news from financial news sites.
        """
        # Placeholder: always returns False (no live news feed)
        log.info(f"News keywords check: {keywords} (symbol={symbol})")
        return False, "News check not implemented (needs news feed API)"

    def signal_detected(self, symbol: str, condition: str) -> tuple[bool, str]:
        """
        Check if a trading signal is detected.
        Conditions: macd_golden_cross, macd_death_cross,
        rsi_oversold, rsi_overbought, boll_break_upper, boll_break_lower
        """
        # Placeholder: would need indicator calculation
        log.info(f"Signal check: {symbol} / {condition}")
        return False, f"Signal '{condition}' check not implemented (needs indicator engine)"

    def portfolio_threshold(self, metric: str, threshold: float) -> tuple[bool, str]:
        """
        Check if a portfolio metric exceeds threshold.
        Metrics: total_value, daily_pnl, daily_pnl_pct, var_95, max_drawdown
        """
        # Placeholder: would read from portfolio state file
        log.info(f"Portfolio threshold check: {metric} > {threshold}")
        return False, f"Portfolio metric '{metric}' check not implemented (needs portfolio state)"


# ─── Trigger Evaluation Loop ─────────────────────────────────────────────────

def evaluate_pending_triggers(store, max_age_seconds: int = 60) -> list[tuple[str, str]]:
    """
    Evaluate all pending condition-based triggers.
    Returns list of (trigger_id, reason) for triggered triggers.
    """
    from trigger_manager import TriggerStore
    store = TriggerStore()
    evaluator = ConditionEvaluator()
    triggered = []

    triggers = store.list(include_disabled=False)
    for t in triggers:
        if t.type == "cron":
            continue  # handled by cron scheduler

        if t.type in ("price_above", "price_below", "price_change_pct"):
            data = evaluator.get_cached_quote(t.symbol, max_age_seconds)
            if not data:
                continue
            ok, reason = evaluator.evaluate(t.type, symbol=t.symbol, threshold=t.threshold)
            if ok:
                triggered.append((t.id, reason))
                log.info(f"Triggered: {t.name} — {reason}")

        elif t.type in ("news_keywords", "signal_detected", "portfolio_threshold"):
            ok, reason = evaluator.evaluate(t.type, symbol=t.symbol,
                                           threshold=t.threshold, keywords=t.keywords,
                                           condition=t.condition, metric=t.condition)
            if ok:
                triggered.append((t.id, reason))
                log.info(f"Triggered: {t.name} — {reason}")

    return triggered


# ─── CLI Entry Point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Condition Evaluator")
    sub = parser.add_subparsers(dest="cmd")

    p_eval = sub.add_parser("eval", help="Evaluate a condition")
    p_eval.add_argument("type")  # price_above, price_below, etc.
    p_eval.add_argument("--symbol", default="")
    p_eval.add_argument("--threshold", type=float, default=0.0)
    p_eval.add_argument("--keywords", default="")
    p_eval.add_argument("--condition", default="")

    p_quote = sub.add_parser("quote", help="Fetch a quote")
    p_quote.add_argument("symbol")

    args = parser.parse_args()
    evaluator = ConditionEvaluator()

    if args.cmd == "quote":
        data = fetch_realtime_quote(args.symbol)
        if data:
            print(f"{data.symbol}: ${data.current_price:.2f} ({data.change_pct:+.2f}%)")
            print(f"  Volume: {data.volume:,} | Avg: {data.avg_volume_20d:,}")
        else:
            print(f"No data for {args.symbol}")

    elif args.cmd == "eval":
        ok, reason = evaluator.evaluate(args.type, symbol=args.symbol,
                                       threshold=args.threshold,
                                       keywords=args.keywords,
                                       condition=args.condition)
        print(f"{'✅ TRIGGERED' if ok else '❌ Not triggered'}: {reason}")

    else:
        parser.print_help()

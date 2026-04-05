#!/usr/bin/env python3
"""
Risk Metrics — VaR, Sharpe Ratio, Max Drawdown, Beta calculations.
"""

import math
import logging
from dataclasses import dataclass
from typing import List, Optional

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("risk-metrics")


def returns(prices: List[float]) -> List[float]:
    """Calculate period-over-period returns."""
    return [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]


def historical_var(returns: List[float], confidence: float = 0.95) -> float:
    """Historical VaR: the quantile of returns at confidence level."""
    if not returns:
        return 0.0
    sorted_ret = sorted(returns)
    idx = int((1 - confidence) * len(sorted_ret))
    idx = min(idx, len(sorted_ret) - 1)
    return sorted_ret[max(0, idx)]


def cvar(returns: List[float], confidence: float = 0.95) -> float:
    """CVaR (Expected Shortfall): average of returns beyond VaR."""
    if not returns:
        return 0.0
    var = historical_var(returns, confidence)
    tail = [r for r in returns if r <= var]
    return sum(tail) / len(tail) if tail else var


def sharpe_ratio(returns: List[float], risk_free: float = 0.03, periods_per_year: int = 252) -> float:
    """Annualized Sharpe Ratio."""
    if not returns or len(returns) < 2:
        return 0.0
    mean_ret = sum(returns) / len(returns)
    std_ret = math.sqrt(sum((r - mean_ret) ** 2 for r in returns) / (len(returns) - 1))
    if std_ret == 0:
        return 0.0
    excess = mean_ret - risk_free / periods_per_year
    return (excess / std_ret) * math.sqrt(periods_per_year)


def max_drawdown(equity_curve: List[float]) -> dict:
    """Maximum drawdown from peak."""
    if not equity_curve:
        return {"max_drawdown": 0.0, "peak_date": None, "trough_date": None}
    peak = equity_curve[0]
    max_dd = 0.0
    peak_idx = 0
    trough_idx = 0
    current_peak = equity_curve[0]
    for i, val in enumerate(equity_curve):
        if val > current_peak:
            current_peak = val
            peak_idx = i
        dd = (val - current_peak) / current_peak if current_peak else 0
        if dd < max_dd:
            max_dd = dd
            trough_idx = i
    return {"max_drawdown": round(max_dd, 4), "peak_idx": peak_idx, "trough_idx": trough_idx}


def beta_stock(stock_returns: List[float], benchmark_returns: List[float]) -> float:
    """Calculate beta: covariance(stock, benchmark) / variance(benchmark)."""
    if len(stock_returns) != len(benchmark_returns) or len(stock_returns) < 2:
        return 1.0
    n = len(stock_returns)
    mean_s = sum(stock_returns) / n
    mean_b = sum(benchmark_returns) / n
    cov = sum((stock_returns[i] - mean_s) * (benchmark_returns[i] - mean_b) for i in range(n)) / n
    var_b = sum((b - mean_b) ** 2 for b in benchmark_returns) / n
    if var_b == 0 or abs(var_b) < 1e-10:
        # Benchmark has near-zero variance — return 0 (no market exposure)
        return 0.0
    beta = cov / var_b
    # Clamp to reasonable range
    return max(0.0, min(beta, 5.0))


def risk_grade(var_95: float, max_dd: float, sharpe: float) -> str:
    """Assign risk grade A/B/C/D based on metrics."""
    if var_95 > -0.03 or abs(max_dd) > 0.20 or sharpe < 0.5:
        return "D"
    if var_95 > -0.02 or abs(max_dd) > 0.10 or sharpe < 1.0:
        return "C"
    if var_95 > -0.01 or abs(max_dd) > 0.05 or sharpe < 2.0:
        return "B"
    return "A"


if __name__ == "__main__":
    import argparse, json, sys
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")
    p = sub.add_parser("var", help="Calculate VaR")
    p.add_argument("--returns", required=True, help="Comma-separated returns")
    p.add_argument("--confidence", type=float, default=0.95)
    args = parser.parse_args()
    rets = [float(x) for x in args.returns.split(",")]
    result = {"var": historical_var(rets, args.confidence), "cvar": cvar(rets, args.confidence)}
    print(json.dumps(result))

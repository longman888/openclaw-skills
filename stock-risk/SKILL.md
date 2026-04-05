---
name: stock-risk
description: |
  Risk management skill — calculates VaR, monitors positions, checks stop-loss, manages exposure.
  Triggers when: (1) checking portfolio risk before trading;
  (2) validating if a trade exceeds position limits;
  (3) monitoring drawdown and VaR metrics;
  (4) generating risk reports.
  Provides: VaR calculation, position limit checks, stop-loss monitoring, risk alerts.
---

# Risk Management

## Core Risk Metrics

### PortfolioVaR(returns, confidence=0.95, method="historical")

计算投资组合VaR（Value at Risk）。

```python
var = PortfolioVaR(returns, confidence=0.95, method="historical")
# {
#   "var_95": -0.023,       # 95% VaR: 1天最多损失2.3%
#   "var_99": -0.038,       # 99% VaR: 1天最多损失3.8%
#   "cvar_95": -0.031,      # CVaR (Expected Shortfall)
#   "confidence": 0.95,
#   "method": "historical",
#   "period": "1d"
# }
```

**方法：**
- `historical`: 历史模拟法（基于真实收益率分布）
- `variance_covariance`: 方差-协方差法（假设正态分布）
- `monte_carlo`: 蒙特卡洛模拟

### MaxDrawdown(equity_curve) → float

```python
mdd = MaxDrawdown(equity_curve)
# {"max_drawdown": -0.128, "peak_date": "2025-06-15", "trough_date": "2025-09-20"}
```

### SharpeRatio(returns, risk_free=0.03) → float

```python
sr = SharpeRatio(returns, risk_free=0.03)
# {"sharpe_ratio": 1.45, "annualized_return": 0.183, "annualized_vol": 0.105}
```

### BetaStock(returns, benchmark_returns) → float

```python
beta = BetaStock(stock_returns, benchmark_returns)
# {"beta": 1.23, "correlation": 0.78}
```

## Position Limits

### check_position_limits(positions, new_trade)

检查新增交易是否超过仓位限制。

```python
result = check_position_limits(positions, new_trade)
# {
#   "passed": True,
#   "violations": [],
#   "current_positions": {
#     "AAPL": {"value": 195000, "pct": 0.195, "limit": 0.20},
#     "TSLA": {"value": 98000, "pct": 0.098, "limit": 0.15}
#   }
# }
```

**默认仓位限制：**

| 限制类型 | 默认值 | 说明 |
|---------|--------|------|
| 单股最大仓位 | 20% | 任何单只股票不超过组合20% |
| 行业集中度 | 30% | 单一行业不超过30% |
| 总仓位 | 90% | 最高90%，保留现金 |
| 日内交易 | 50% | 单日交易额不超过组合50% |

### Position Warnings

```python
WARNINGS = {
    "yellow": {   # 预警
        "single_stock_pct": 0.18,    # 单股 > 18%
        "sector_pct": 0.25,          # 行业 > 25%
        "total_pct": 0.85,           # 总仓位 > 85%
        "daily_var_pct": 0.02,       # 日VaR > 2%
    },
    "red": {      # 红色警告
        "single_stock_pct": 0.20,    # 单股 >= 20%
        "sector_pct": 0.30,          # 行业 >= 30%
        "total_pct": 0.90,           # 总仓位 >= 90%
        "daily_var_pct": 0.03,       # 日VaR > 3%
    }
}
```

## Stop-Loss Monitoring

### check_stop_loss(positions, prices) → list[Alert]

检查持仓是否触发止损。

```python
alerts = check_stop_loss(positions, prices)
# [
#   {
#     "symbol": "AAPL",
#     "current_price": 178.50,
#     "stop_loss": 180.00,
#     "loss_pct": -0.058,
#     "action": "SELL",       # 建议操作
#     "urgency": "HIGH"       # "HIGH" | "MEDIUM" | "LOW"
#   }
# ]
```

**止损类型：**

| 类型 | 规则 | 触发条件 |
|------|------|---------|
| 固定止损 | 买入价 - 5% | 价格跌破买入价5% |
| 跟踪止损 | 最高价 - 3% | 从最高点回落3% |
| 时间止损 | 持有30天 | 持有超过30天未盈利 |
| 资金止损 | 组合-5% | 单次交易亏损超过组合1% |

## Risk Report

### generate_risk_report(portfolio, benchmark_returns)

生成完整风险报告。

```python
report = generate_risk_report(portfolio, benchmark_returns)
# {
#   "timestamp": "2026-04-02T09:30:00",
#   "portfolio_value": 1000000,
#   "daily_var": {"var_95": -0.023, "var_99": -0.038},
#   "weekly_var": {"var_95": -0.045, "var_99": -0.072},
#   "max_drawdown": -0.128,
#   "sharpe_ratio": 1.45,
#   "beta": 1.12,
#   "positions": [...],
#   "warnings": [],
#   "stop_loss_alerts": [],
#   "risk_grade": "B",   # "A"(safe) / "B"(moderate) / "C"(risky) / "D"(dangerous)
#   "summary": "组合风险可控，日VaR约2.3%，最大回撤历史约12.8%"
# }
```

## Risk Grade

| Grade | 日VaR | 最大回撤 | Sharpe | 操作建议 |
|-------|-------|---------|--------|---------|
| A | <1% | <5% | >2.0 | 正常操作 |
| B | 1-2% | 5-10% | 1.0-2.0 | 控制仓位 |
| C | 2-3% | 10-20% | 0.5-1.0 | 减仓观望 |
| D | >3% | >20% | <0.5 | 清仓 |

## Scripts

- `scripts/risk_metrics.py` — VaR, Sharpe, drawdown calculations
- `scripts/position_checker.py` — Position limit validation
- `scripts/stop_loss_monitor.py` — Stop-loss monitoring engine
- `scripts/risk_report.py` — Full risk report generator

## References

- `references/risk-formulas.md` — Mathematical formulas for risk metrics
- `references/risk-limits.md` — Default risk parameters

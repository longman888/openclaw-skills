---
name: stock-strategy
description: |
  Trading strategy skill — generates buy/sell/hold signals, position sizing, entry/exit rules.
  Triggers when: (1) user asks for trading recommendations;
  (2) generating actionable signals from technical analysis;
  (3) portfolio rebalancing decisions;
  (4) backtesting strategy signals.
  Provides: signal generation, position sizing, risk-adjusted recommendations.
---

# Trading Strategy

## Signal Generation

### generate_signal(symbol, strategy="multi_factor")

从技术指标和形态生成交易信号。

```python
signal = generate_signal("AAPL", strategy="trend_following")
# {
#   "symbol": "AAPL",
#   "signal": "BUY",
#   "confidence": 0.75,
#   "entry": 189.50,
#   "stop_loss": 180.00,
#   "target": 205.00,
#   "position_size": 0.20,  # 20% of portfolio
#   "risk_reward": 2.65,
#   "reason": "MACD golden cross + RSI 突破60",
#   "indicators": {
#     "MA": "bullish",
#     "MACD": "golden_cross",
#     "RSI": 62.5,
#     "KDJ": "normal"
#   },
#   "timestamp": "2026-04-02T09:30:00"
# }
```

**Signal levels:** `STRONG_BUY` / `BUY` / `HOLD` / `SELL` / `STRONG_SELL`

### Signal Confidence

| Confidence | 含义 | 操作 |
|-----------|------|------|
| ≥ 0.8 | 强烈信号 | 可重仓 |
| 0.6–0.8 | 确认信号 | 正常仓位 |
| 0.4–0.6 | 中性信号 | 轻仓或观望 |
| < 0.4 | 弱信号 | 不操作 |

## Strategy Types

### 1. trend_following — 趋势跟踪

基于均线和MACD的趋势跟踪策略。

**规则：**
- 买入：5日均线 > 10日均线 > 20日均线，且MACD > 0
- 卖出：均线空头排列，或MACD死叉

### 2. mean_reversion — 均值回归

基于RSI和布林带的均值回归策略。

**规则：**
- 买入：RSI < 30 或 价格触及布林带下轨
- 卖出：RSI > 70 或 价格触及布林带上轨

### 3. breakout — 突破策略

基于价格突破阻力位/支撑位。

**规则：**
- 买入：价格突破20日高点 + 成交量放大 > 1.5×
- 卖出：价格跌破10日低点

### 4. multi_factor — 多因子综合

综合技术指标、趋势、动量多因子打分。

**打分规则：**
- MA多头排列：+1分
- MACD金叉：+1分
- RSI > 60：+1分
- KDJ超买：-1分
- 成交量放大：+1分

**信号：**
- 3分以上：STRONG_BUY
- 2分：BUY
- 0-1分：HOLD
- -1分：SELL
- -2分以下：STRONG_SELL

## Position Sizing

### calculate_position(signal, portfolio_value, risk_tolerance=0.02)

根据信号置信度和风险承受能力计算仓位。

```python
pos = calculate_position(signal, portfolio_value=1000000, risk_tolerance=0.02)
# {
#   "shares": 105,
#   "amount": 19897.50,    # 买入金额
#   "position_pct": 0.0199,  # 2%
#   "risk_amount": 997.50,  # 风险金额
#   "stop_loss_pct": 0.05   # 5%止损
# }
```

**Kelly Criterion（凯利公式）：**
```
f = (bp - q) / b
其中：b = 赔率（盈亏比），p = 胜率，q = 1-p
```

## Entry/Exit Rules

### Entry Rules

1. **分批建仓：** 首次买入30%，回调确认后再买40%，突破加仓30%
2. **成本价入场：** 信号触发后，在信号价格±1%内入场
3. **时间过滤：** 盘前15分钟和收盘前30分钟不建仓

### Exit Rules

```python
EXIT_RULES = {
    "stop_loss": {
        "default": -0.05,     # 5% 固定止损
        "trailing": 0.03,     # 跟踪止损：最高点回落3%卖出
        "time_based": 30,     # 持有超过30天强制止损
    },
    "take_profit": {
        "target_1": 0.10,    # 第一止盈：+10%卖出一半
        "target_2": 0.20,    # 第二止盈：+20%全部卖出
        "trailing": 0.05,    # 跟踪止盈：最高点回落5%全部卖出
    }
}
```

## Strategy Backtest

### backtest(strategy, symbol, start_date, end_date)

回测策略表现。

```python
bt = backtest("trend_following", "AAPL", "2025-01-01", "2026-04-01")
# {
#   "strategy": "trend_following",
#   "symbol": "AAPL",
#   "period": "2025-01-01 to 2026-04-01",
#   "total_return": 0.245,
#   "annualized_return": 0.183,
#   "max_drawdown": -0.128,
#   "win_rate": 0.62,
#   "sharpe_ratio": 1.45,
#   "trade_count": 18,
#   "avg_holding_days": 12.5
# }
```

## Portfolio Strategy

### generate_portfolio_signals(watchlist: list[str])

对自选股列表批量生成信号。

```python
signals = generate_portfolio_signals(["AAPL", "TSLA", "腾讯控股", "茅台"])
# {
#   "timestamp": "2026-04-02T09:30:00",
#   "signals": [
#     {"symbol": "AAPL", "signal": "BUY", "confidence": 0.72},
#     {"symbol": "TSLA", "signal": "HOLD", "confidence": 0.45},
#     {"symbol": "腾讯控股", "signal": "STRONG_BUY", "confidence": 0.85},
#     {"symbol": "茅台", "signal": "BUY", "confidence": 0.68}
#   ],
#   "action": "加仓腾讯控股，首选茅台"
# }
```

## Scripts

- `scripts/signal_generator.py` — Signal generation engine
- `scripts/position_sizer.py` — Position sizing calculator
- `scripts/backtester.py` — Backtesting engine
- `scripts/portfolio_screener.py` — Watchlist screener

## References

- `references/strategies.md` — Detailed strategy rules and parameters

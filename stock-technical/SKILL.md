---
name: stock-technical
description: |
  Technical analysis skill — calculates indicators, identifies patterns, generates analysis reports.
  Triggers when: (1) user asks to calculate technical indicators for a stock;
  (2) analyzing chart patterns or trend direction;
  (3) generating trading signals from indicators;
  (4) comparing indicators across multiple stocks.
  Supports: MA, MACD, KDJ, RSI, Bollinger Bands, ATR, OBV, and candlestick patterns.
---

# Technical Analysis

## Indicator Functions

### SMA(close, period) — 简单移动平均

```python
sma_20 = SMA(close_prices, 20)
sma_60 = SMA(close_prices, 60)
```

### EMA(close, period) — 指数移动平均

```python
ema_12 = EMA(close_prices, 12)
ema_26 = EMA(close_prices, 26)
```

### MACD(close, fast=12, slow=26, signal=9)

```python
macd = MACD(close)
# {
#   "macd": 1.45,        # DIF line
#   "signal": 1.12,      # DEA line
#   "histogram": 0.33,   # MACD柱
#   "crossover": "golden"  # "golden" | "death" | None
# }
```

**Signal:** `golden_cross` (DIF crosses above signal) / `death_cross` (DIF crosses below signal)

### KDJ(high, low, close, period=9, k=3, d=3)

```python
kdj = KDJ(high, low, close)
# {
#   "k": 72.5,
#   "d": 68.3,
#   "j": 81.0,
#   "crossover": "overbought"  # "overbought" | "oversold" | None
# }
```

- KDJ > 80: 超买区域
- KDJ < 20: 超卖区域

### RSI(close, period=14)

```python
rsi = RSI(close, 14)
# {
#   "rsi": 58.3,
#   "signal": "neutral"  # "overbought" (>70) | "oversold" (<30) | "neutral"
# }
```

### BollingerBands(close, period=20, std_dev=2)

```python
bb = BollingerBands(close)
# {
#   "upper": 195.5,
#   "middle": 190.0,
#   "lower": 184.5,
#   "bandwidth": 5.79,
#   "position": 0.65,    # 0=lower, 1=upper
#   "squeeze": False      # True if bandwidth < 6-month avg
# }
```

### ATR(high, low, close, period=14)

```python
atr = ATR(high, low, close, 14)
# {"atr": 3.45, "atr_pct": 1.82}  # ATR and ATR as % of price
```

### OBV(close, volume)

```python
obv = OBV(close, volume)
# {"obv": 1523400000, "trend": "increasing"}
```

## Candlestick Patterns

### identify_patterns(ohlc_list) → list[Pattern]

```python
patterns = identify_patterns(ohlc_list)
# [
#   {"name": "Morning Star", "signal": "bullish", "confidence": 0.78},
#   {"name": "Doji", "signal": "neutral", "confidence": 0.65},
#   ...
# ]
```

**常用形态：**

| 形态 | 信号 | 描述 |
|------|------|------|
| Morning Star | 🔴 看涨 | 三日形态，确认底部 |
| Evening Star | 🔴 看跌 | 三日形态，确认顶部 |
| Doji | ⚪ 中性 | 十字星，犹豫信号 |
| Hammer | 🔴 看涨 | 锤子线，底部反转 |
| Engulfing Bullish | 🔴 看涨 | 吞噬形态，向上反转 |
| Engulfing Bearish | 🔴 看跌 | 吞噬形态，向下反转 |
| Head Shoulders | 🔴 看跌 | 头肩顶，趋势反转 |
| Double Bottom | 🔴 看涨 | 双底，W形态 |

## Analysis Report

### generate_analysis(symbol, period="1d")

综合技术分析报告。

```python
report = generate_analysis("AAPL", period="1d")
# {
#   "symbol": "AAPL",
#   "timestamp": "2026-04-02T09:30:00",
#   "trend": "上升趋势",
#   "signals": {
#     "MA": "看多",       # 5>10>20 多头排列
#     "MACD": "中性",     # DIF > 0 但背离
#     "KDJ": "超买",      # KDJ > 80
#     "RSI": "中性",      # RSI = 58
#     "Bollinger": "中性"  # 价格在中轨附近
#   },
#   "overall": "持有",
#   "support": [185.0, 182.5],
#   "resistance": [195.0, 200.0],
#   "stop_loss": 180.0,
#   "target": 205.0
# }
```

## Scripts

- `scripts/indicators.py` — All indicator calculations
- `scripts/patterns.py` — Candlestick pattern recognition
- `scripts/analyzer.py` — Full analysis report generator

## References

- `references/indicators.md` — Detailed indicator formulas
- `references/patterns.md` — Pattern recognition guide

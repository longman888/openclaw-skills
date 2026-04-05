---
name: trading-tools
description: |
  量化交易工具集 — 参考 BeeQuant 设计的策略模板和指标工具。
  包含：技术指标、择时信号、择币筛选、网格策略、AI策略接口。
---

# trading-tools — 量化交易工具集

> 参考 [BeeQuant](https://www.beequant.io/create-strategy) 设计的策略模板

## 工具分类

### 📊 技术指标工具

| 工具 | 描述 | BeeQuant对应 |
|------|------|-------------|
| `ma` | 移动平均线 | 单均线策略 |
| `rsi` | 相对强弱指数 | RSI趋势追踪 |
| `bollinger` | 布林带 | BB+KDJ策略 |
| `atr` | 平均真实波幅 | SuperTrend/海龟 |
| `donchian` | 唐奇安通道 | 海龟策略 |
| `adx` | 平均趋向指数 | ADX趋势过滤 |
| `kdj` | KDJ指标 | KDJ+RSI |
| `ema` | 指数移动平均 | EMA三线 |
| `ichimoku` | 一目均衡表 | 云图五线 |
| `obv` | 能量潮 | 多空力量 |
| `volume_profile` | 成交量分析 | 成交量突破 |

### 🎯 择时信号工具

| 工具 | 策略 | 难度 |
|------|------|------|
| `ma_crossover` | 均线金叉/死叉 | 入门 |
| `rsi_extreme` | RSI超买超卖 | 入门 |
| `donchian_breakout` | 唐奇安通道突破 | 进阶 |
| `supertrend` | ATR+ADX趋势系统 | 进阶 |
| `bollinger_squeeze` | 布林带收口突破 | 进阶 |
| `dual_thrust` | Dual Thrust突破 | 进阶 |
| `ichimoku_signal` | 云图五线信号 | 专业 |
| `candlestick_pattern` | K线形态识别 | 进阶 |
| `ema_triple_reversal` | EMA三线反转 | 入门 |
| `zscore_momentum` | Z-score统计动量 | 专业 |

### 🪙 择币筛选工具

| 工具 | 描述 | 难度 |
|------|------|------|
| `momentum_rank` | 动量排名选币 | 入门 |
| `volume_breakout` | 成交量突破选币 | 进阶 |
| `smart_beta` | Smart Beta因子选币 | 进阶 |
| `multi_factor` | 多因子截面选币 | 专业 |
| `long_short_neutral` | 多空中性对冲 | 专业 |
| `onchain_metrics` | 链上指标筛选 | 专业 |

### 📈 策略执行工具

| 工具 | 描述 | 难度 |
|------|------|------|
| `grid_trade` | 网格交易 | 进阶 |
| `trend_grid` | 趋势追踪网格 | 专业 |
| `trailing_stop` | 移动止损 | 入门 |

### 🤖 AI策略接口

| 工具 | 描述 | 难度 |
|------|------|------|
| `lstm_timing` | LSTM择时模型 | 专业 |
| `lightgbm_timing` | LightGBM择时 | 专业 |
| `transformer_alpha` | Transformer多因子 | 专业 |

---

## 快速使用

```python
from skills.trading_tools import (
    # 指标
    calculate_ma, calculate_rsi, calculate_bollinger, calculate_atr,
    calculate_adx, calculate_kdj, calculate_donchian,
    # 信号
    ma_crossover_signal, rsi_extreme_signal, donchian_breakout_signal,
    supertrend_signal, bollinger_squeeze_signal,
    # 选币
    momentum_rank, volume_breakout, multi_factor_select,
    # 策略
    GridTrader, TrendGridTrader
)

# 计算均线
ma20 = calculate_ma(prices, period=20)
ma100 = calculate_ma(prices, period=100)

# 均线金叉信号
signal = ma_crossover_signal(prices, fast=10, slow=100)

# RSI超买超卖
rsi_signal = rsi_extreme_signal(prices, period=14, oversold=30, overbought=70)

# 唐奇安通道突破
breakout = donchian_breakout_signal(highs, lows, closes, period=20)

# 超级趋势
supertrend_signal = supertrend_signal(highs, lows, closes, period=10, multiplier=3)

# 动量排名选币
top_coins = momentum_rank(price_data_dict, period=20, top_n=5)

# 网格交易
grid = GridTrader(upper=40000, lower=30000, layers=10)
```

---

## 指标计算 API

### MA - 移动平均线

```python
def calculate_ma(prices: list[float], period: int) -> list[float]:
    """计算简单移动平均线"""
    # SMA = Sum(price, period) / period
    return ma_values
```

### RSI - 相对强弱指数

```python
def calculate_rsi(prices: list[float], period: int = 14) -> list[float]:
    """计算RSI指标
    RSI = 100 - (100 / (1 + RS))
    RS = Avg(Gain) / Avg(Loss)
    """
    return rsi_values
```

### Bollinger Bands - 布林带

```python
def calculate_bollinger(prices: list[float], period: int = 20, std_dev: float = 2.0):
    """计算布林带
    Middle = MA(20)
    Upper = Middle + 2*STD
    Lower = Middle - 2*STD
    """
    return {"upper": upper, "middle": middle, "lower": lower, "bandwidth": bw}
```

### ATR - 平均真实波幅

```python
def calculate_atr(highs, lows, closes, period: int = 14) -> list[float]:
    """计算ATR
    TR = max(H-L, |H-PC|, |L-PC|)
    ATR = SMA(TR, period)
    """
    return atr_values
```

### ADX - 平均趋向指数

```python
def calculate_adx(highs, lows, closes, period: int = 14) -> dict:
    """计算ADX
    +DI = 上行方向指标
    -DI = 下行方向指标
    ADX = 趋向指数
    """
    return {"adx": adx_values, "plus_di": plus_di, "minus_di": minus_di}
```

### KDJ 指标

```python
def calculate_kdj(highs, lows, closes, period: int = 9) -> dict:
    """计算KDJ
    RSV = (C-LowN)/(HighN-LowN) * 100
    K = 2/3*K(-1) + 1/3*RSV
    D = 2/3*D(-1) + 1/3*K
    J = 3*K - 2*D
    """
    return {"k": k_values, "d": d_values, "j": j_values}
```

### Donchian Channel - 唐奇安通道

```python
def calculate_donchian(highs, lows, period: int = 20) -> dict:
    """计算唐奇安通道
    Upper = Highest(High, period)
    Lower = Lowest(Low, period)
    Middle = (Upper + Lower) / 2
    """
    return {"upper": upper, "middle": middle, "lower": lower}
```

### SuperTrend

```python
def supertrend_signal(highs, lows, closes, period: int = 10, multiplier: float = 3.0) -> dict:
    """计算SuperTrend信号
    ATR通道 = Close ± multiplier * ATR
    趋势向上 = Close > 上轨
    趋势向下 = Close < 下轨
    """
    return {
        "trend": trend_list,  # 1=上涨, -1=下跌
        "supertrend": st_values,
        "signal": signals  # 1=买入, -1=卖出, 0=持有
    }
```

---

## 择时信号 API

### 均线金叉/死叉

```python
def ma_crossover_signal(prices: list[float], fast: int = 10, slow: int = 100) -> dict:
    """均线金叉死叉信号
    金叉: fast上穿slow → 买入
    死叉: fast下穿slow → 卖出
    """
    return {
        "fast_ma": fast_ma,
        "slow_ma": slow_ma,
        "signal": signal,  # 1/0/-1
        "crossover": crossover_type  # "golden"/"death"/None
    }
```

### RSI 超买超卖

```python
def rsi_extreme_signal(prices: list[float], period: int = 14,
                       oversold: float = 30, overbought: float = 70) -> dict:
    """RSI超买超卖信号
    RSI < oversold → 买入(超卖反弹)
    RSI > overbought → 卖出(超买回调)
    """
    return {
        "rsi": rsi_values,
        "signal": signal,
        "extreme": extreme_type  # "oversold"/"overbought"/None
    }
```

### 唐奇安通道突破

```python
def donchian_breakout_signal(highs, lows, closes, period: int = 20) -> dict:
    """唐奇安通道突破
    突破上轨 → 买入
    跌破下轨 → 卖出
    """
    return {
        "upper": upper,
        "lower": lower,
        "breakout": breakout_type,  # "upper"/"lower"/None
        "signal": signal
    }
```

---

## 择币筛选 API

### 动量排名

```python
def momentum_rank(price_data: dict[str, list[float]], period: int = 20, top_n: int = 5) -> list[dict]:
    """动量排名选币
    Momentum = (Current Price - Price N days ago) / Price N days ago
    返回Top N强势币种
    """
    return [
        {"symbol": "BTC", "momentum": 0.15, "rank": 1},
        {"symbol": "ETH", "momentum": 0.12, "rank": 2},
        ...
    ]
```

### 成交量突破选币

```python
def volume_breakout(candles: dict[str, dict], threshold: float = 2.0) -> list[dict]:
    """成交量突破选币
    量比 = 今日成交量 / N日平均成交量
    量比 > threshold → 突破
    """
    return [
        {"symbol": "BTC", "volume_ratio": 2.5, "trend": "up"},
        ...
    ]
```

### 多因子选币

```python
def multi_factor_select(
    price_data: dict,
    volume_data: dict,
    onchain_data: dict = None,
    factors: list[str] = ["momentum", "volume", "volatility"],
    top_n: int = 10
) -> list[dict]:
    """多因子截面选币
    factors: momentum/volume/volatility/oi/funding_rate
    """
    return [
        {"symbol": "BTC", "composite_score": 0.85, "rank": 1, "factors": {...}},
        ...
    ]
```

---

## 策略执行 API

### 网格交易

```python
class GridTrader:
    def __init__(self, upper: float, lower: float, layers: int = 10,
                 initial_ratio: float = 0.1, leverage: float = 1.0):
        """
        震荡网格策略
        upper/lower: 价格区间
        layers: 网格层数
        initial_ratio: 初始仓位比例
        leverage: 杠杆倍数
        """
        
    def get_grid_levels(self) -> list[float]:
        """获取网格价格水平"""
        
    def signal(self, current_price: float) -> dict:
        """生成交易信号
        Returns: {"action": "buy"/"sell"/"hold", "level": price, "quantity": amount}
        """

# 使用示例
grid = GridTrader(upper=40000, lower=30000, layers=10, leverage=2.0)
for price in price_series:
    sig = grid.signal(price)
    if sig["action"] != "hold":
        execute_trade(sig)
```

### 趋势追踪网格

```python
class TrendGridTrader(GridTrader):
    def __init__(self, upper, lower, layers, ma_period: int = 50, trailing_pct: float = 0.02):
        """
        趋势追踪网格
        在网格基础上增加:
        - MA趋势过滤
        - 移动止损
        """
        
    def signal(self, current_price: float, ma_value: float) -> dict:
        """考虑趋势的信号"""
```

### 移动止损

```python
def trailing_stop(entry_price: float, current_price: float,
                  highest_price: float, trailing_pct: float = 0.05) -> dict:
    """移动止损
    止损价 = 最高价 * (1 - trailing_pct)
    """
    stop_price = highest_price * (1 - trailing_pct)
    return {
        "stop_price": stop_price,
        "should_stop": current_price < stop_price,
        "profit_pct": (current_price - entry_price) / entry_price * 100
    }
```

---

## AI策略接口

### LSTM 择时

```python
class LSTMTiming:
    def __init__(self, lookback: int = 60, features: int = 32):
        """LSTM择时模型
        输入: N个时间步的特征
        输出: 上涨/下跌概率
        """
        
    def predict(self, features: list[list[float]]) -> dict:
        """预测
        Returns: {"prob_up": 0.7, "prob_down": 0.3, "signal": "long"}
        """
        
    def train(self, X, y, epochs: int = 100):
        """训练模型"""
```

### LightGBM 择时

```python
class LightGBMTiming:
    def __init__(self, num_trees: int = 100):
        """LightGBM择时模型"""
        
    def predict(self, features: dict) -> dict:
        """预测
        Returns: {"signal": 1/0/-1, "importance": {...}}
        """
```

---

## 策略模板

### 入门: 单均线策略

```python
def ma_strategy(prices: list[float], ma_period: int = 100,
                take_profit: float = 0.10, stop_loss: float = 0.10) -> dict:
    """
    单均线策略
    - 收盘价站上MA100 → 做多
    - 跌破MA100 → 平仓
    - 止盈 +10%, 止损 -10%
    """
    ma = calculate_ma(prices, ma_period)
    signals = []
    
    for i in range(len(prices)):
        if prices[i] > ma[i] and prices[i-1] <= ma[i-1]:
            signals.append({"action": "buy", "price": prices[i]})
        elif prices[i] < ma[i] and prices[i-1] >= ma[i-1]:
            signals.append({"action": "sell", "price": prices[i]})
        else:
            signals.append({"action": "hold", "price": prices[i]})
    
    return {"signals": signals, "ma": ma}
```

### 进阶: RSI趋势追踪

```python
def rsi_trend_strategy(prices: list[float], rsi_period: int = 14,
                       oversold: float = 30, overbought: float = 70) -> dict:
    """
    RSI趋势追踪
    - RSI < 30 → 超卖，做多
    - RSI > 70 → 超买，做空
    - RSI回归50 → 平仓
    """
    rsi = calculate_rsi(prices, rsi_period)
    signals = []
    
    position = 0  # 0=空仓, 1=多头, -1=空头
    
    for i in range(len(prices)):
        if position == 0:
            if rsi[i] < oversold:
                signals.append({"action": "buy", "price": prices[i], "rsi": rsi[i]})
                position = 1
            elif rsi[i] > overbought:
                signals.append({"action": "sell", "price": prices[i], "rsi": rsi[i]})
                position = -1
            else:
                signals.append({"action": "hold", "price": prices[i], "rsi": rsi[i]})
        elif position == 1 and rsi[i] > 50:
            signals.append({"action": "sell", "price": prices[i], "rsi": rsi[i]})
            position = 0
        elif position == -1 and rsi[i] < 50:
            signals.append({"action": "buy", "price": prices[i], "rsi": rsi[i]})
            position = 0
        else:
            signals.append({"action": "hold", "price": prices[i], "rsi": rsi[i]})
    
    return {"signals": signals, "rsi": rsi}
```

### 进阶: 海龟策略

```python
def turtle_strategy(highs, lows, closes, entry_period: int = 20,
                    exit_period: int = 10, position_pct: float = 0.9) -> dict:
    """
    海龟策略
    - 突破20日高点 → 做多
    - 跌破20日低点 → 平多
    - 仓位 90%
    """
    donchian_entry = calculate_donchian(highs, lows, entry_period)
    donchian_exit = calculate_donchian(highs, lows, exit_period)
    
    signals = []
    position = 0
    entry_price = 0
    
    for i in range(len(closes)):
        if position == 0:
            if highs[i] > donchian_entry["upper"][i]:
                signals.append({"action": "buy", "price": closes[i], "type": "entry"})
                position = 1
                entry_price = closes[i]
            else:
                signals.append({"action": "hold"})
        elif position == 1:
            if lows[i] < donchian_exit["lower"][i]:
                signals.append({"action": "sell", "price": closes[i], "type": "exit"})
                position = 0
            else:
                signals.append({"action": "hold"})
    
    return {"signals": signals, "entry_channel": donchian_entry, "exit_channel": donchian_exit}
```

---

## 参考

- BeeQuant策略模板: https://www.beequant.io/create-strategy
- 本地指标实现: `trading_tools/indicators.py`

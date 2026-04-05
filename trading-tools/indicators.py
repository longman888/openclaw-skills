"""
trading-tools — 技术指标和策略实现
参考 BeeQuant 设计的指标和策略模板
"""

import numpy as np
from typing import Optional

# ============================================================================
# 基础指标
# ============================================================================

def calculate_ma(prices: list[float], period: int) -> list[float]:
    """计算简单移动平均线 SMA"""
    if len(prices) < period:
        return [None] * len(prices)
    
    result = []
    for i in range(len(prices)):
        if i < period - 1:
            result.append(None)
        else:
            ma = sum(prices[i - period + 1:i + 1]) / period
            result.append(round(ma, 4))
    return result


def calculate_ema(prices: list[float], period: int) -> list[float]:
    """计算指数移动平均线 EMA"""
    if len(prices) < period:
        return [None] * len(prices)
    
    multiplier = 2 / (period + 1)
    result = [None] * (period - 1)
    
    # 第一个 EMA = SMA
    first_ema = sum(prices[:period]) / period
    result.append(round(first_ema, 4))
    
    for i in range(period, len(prices)):
        ema = (prices[i] - result[-1]) * multiplier + result[-1]
        result.append(round(ema, 4))
    
    return result


def calculate_rsi(prices: list[float], period: int = 14) -> list[float]:
    """计算 RSI 相对强弱指数"""
    if len(prices) < period + 1:
        return [None] * len(prices)
    
    result = [None] * period
    
    # 计算变化
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    
    # 分离涨跌
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    
    # 初始平均
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    # 第一个 RSI
    rs = avg_gain / avg_loss if avg_loss != 0 else 100
    result.append(round(100 - (100 / (1 + rs)), 4))
    
    # 后续 RSI (平滑)
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rs = avg_gain / avg_loss if avg_loss != 0 else 100
        result.append(round(100 - (100 / (1 + rs)), 4))
    
    return result


def calculate_bollinger(prices: list[float], period: int = 20, std_dev: float = 2.0) -> dict:
    """计算布林带"""
    if len(prices) < period:
        return {"upper": [None]*len(prices), "middle": [None]*len(prices), 
                "lower": [None]*len(prices), "bandwidth": [None]*len(prices)}
    
    middle = calculate_ma(prices, period)
    upper = []
    lower = []
    bandwidth = []
    
    for i in range(len(prices)):
        if i < period - 1:
            upper.append(None)
            lower.append(None)
            bandwidth.append(None)
        else:
            slice_prices = prices[i - period + 1:i + 1]
            std = np.std(slice_prices)
            u = middle[i] + std_dev * std
            l = middle[i] - std_dev * std
            bw = (u - l) / middle[i] if middle[i] else None
            upper.append(round(u, 4))
            lower.append(round(l, 4))
            bandwidth.append(round(bw, 6) if bw else None)
    
    return {"upper": upper, "middle": middle, "lower": lower, "bandwidth": bandwidth}


def calculate_atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> list[float]:
    """计算 ATR 平均真实波幅"""
    if len(highs) < period + 1:
        return [None] * len(highs)
    
    tr = []
    for i in range(1, len(highs)):
        h_l = highs[i] - lows[i]
        h_c = abs(highs[i] - closes[i-1])
        l_c = abs(lows[i] - closes[i-1])
        tr.append(max(h_l, h_c, l_c))
    
    atr = [None]
    for i in range(14, len(tr)):
        if i == 14:
            avg = sum(tr[:period]) / period
        else:
            avg = (atr[-1] * (period - 1) + tr[i]) / period
        atr.append(round(avg, 4))
    
    # Pad to match length
    while len(atr) < len(highs):
        atr.insert(0, None)
    
    return atr


def calculate_donchian(highs: list[float], lows: list[float], period: int = 20) -> dict:
    """计算唐奇安通道"""
    upper = []
    middle = []
    lower = []
    
    for i in range(len(highs)):
        if i < period - 1:
            upper.append(None)
            middle.append(None)
            lower.append(None)
        else:
            window_high = max(highs[i - period + 1:i + 1])
            window_low = min(lows[i - period + 1:i + 1])
            upper.append(round(window_high, 4))
            lower.append(round(window_low, 4))
            middle.append(round((window_high + window_low) / 2, 4))
    
    return {"upper": upper, "middle": middle, "lower": lower}


def calculate_adx(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> dict:
    """计算 ADX 平均趋向指数"""
    if len(highs) < period + 1:
        return {"adx": [None]*len(highs), "plus_di": [None]*len(highs), "minus_di": [None]*len(highs)}
    
    plus_dm = []
    minus_dm = []
    tr = []
    
    for i in range(1, len(highs)):
        h_diff = highs[i] - highs[i-1]
        l_diff = lows[i-1] - lows[i]
        
        if h_diff > l_diff and h_diff > 0:
            plus_dm.append(h_diff)
        else:
            plus_dm.append(0)
        
        if l_diff > h_diff and l_diff > 0:
            minus_dm.append(l_diff)
        else:
            minus_dm.append(0)
        
        tr.append(max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1])))
    
    # Smooth
    period_list = range(period)
    plus_di = [None] * period
    minus_di = [None] * period
    adx = [None] * period
    
    sum_tr = sum(tr[:period])
    sum_plus = sum(plus_dm[:period])
    sum_minus = sum(minus_dm[:period])
    
    prev_adx = 0
    
    for i in range(period, len(tr)):
        sum_tr = sum_tr - sum_tr / period + tr[i]
        sum_plus = sum_plus - sum_plus / period + plus_dm[i]
        sum_minus = sum_minus - sum_minus / period + minus_dm[i]
        
        p_di = 100 * sum_plus / sum_tr if sum_tr != 0 else 0
        m_di = 100 * sum_minus / sum_tr if sum_tr != 0 else 0
        
        plus_di.append(round(p_di, 4))
        minus_di.append(round(m_di, 4))
        
        dx = 100 * abs(p_di - m_di) / (p_di + m_di) if (p_di + m_di) != 0 else 0
        adx.append(round((prev_adx * (period - 1) + dx) / period, 4))
        prev_adx = adx[-1]
    
    # Pad to match
    while len(adx) < len(highs):
        adx.insert(0, None)
        plus_di.insert(0, None)
        minus_di.insert(0, None)
    
    return {"adx": adx, "plus_di": plus_di, "minus_di": minus_di}


def calculate_kdj(highs: list[float], lows: list[float], closes: list[float], 
                  n: int = 9, m1: int = 3, m2: int = 3) -> dict:
    """计算 KDJ 随机指标"""
    if len(highs) < n:
        return {"k": [None]*len(highs), "d": [None]*len(highs), "j": [None]*len(highs)}
    
    k = [50.0] * n
    d = [50.0] * n
    
    for i in range(n, len(closes)):
        window_high = max(highs[i - n + 1:i + 1])
        window_low = min(lows[i - n + 1:i + 1])
        
        if window_high == window_low:
            rsv = 50
        else:
            rsv = (closes[i] - window_low) / (window_high - window_low) * 100
        
        k.append((2/3) * k[-1] + (1/3) * rsv)
        d.append((2/3) * d[-1] + (1/3) * k[-1])
    
    j = [3*k[i] - 2*d[i] for i in range(len(k))]
    
    # Pad to match
    k = [None] * n + k[n:]
    d = [None] * n + d[n:]
    j = [None] * n + j[n:]
    
    return {"k": [round(v, 4) if v else None for v in k], 
            "d": [round(v, 4) if v else None for v in d], 
            "j": [round(v, 4) if v else None for v in j]}


def calculate_obv(prices: list[float], volumes: list[float]) -> list[float]:
    """计算 OBV 能量潮"""
    if len(prices) < 2:
        return [0] * len(prices)
    
    obv = [0]
    for i in range(1, len(prices)):
        if prices[i] > prices[i-1]:
            obv.append(obv[-1] + volumes[i])
        elif prices[i] < prices[i-1]:
            obv.append(obv[-1] - volumes[i])
        else:
            obv.append(obv[-1])
    
    return [round(v, 2) for v in obv]


def calculate_macd(prices: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    """计算 MACD"""
    ema_fast = calculate_ema(prices, fast)
    ema_slow = calculate_ema(prices, slow)
    
    dif = []
    for i in range(len(prices)):
        if ema_fast[i] is None or ema_slow[i] is None:
            dif.append(None)
        else:
            dif.append(round(ema_fast[i] - ema_slow[i], 4))
    
    dea = calculate_ema([d if d else 0 for d in dif], signal)
    
    macd = []
    for i in range(len(dif)):
        if dif[i] is None or dea[i] is None:
            macd.append(None)
        else:
            macd.append(round(2 * (dif[i] - dea[i]), 4))
    
    return {"dif": dif, "dea": dea, "macd": macd}


# ============================================================================
# 信号生成
# ============================================================================

def ma_crossover_signal(prices: list[float], fast: int = 10, slow: int = 100) -> dict:
    """均线金叉死叉信号"""
    fast_ma = calculate_ma(prices, fast)
    slow_ma = calculate_ma(prices, slow)
    
    signals = []
    crossovers = []
    
    for i in range(len(prices)):
        if i < slow - 1 or fast_ma[i] is None or slow_ma[i] is None:
            signals.append(0)
            crossovers.append(None)
        else:
            # 金叉
            if fast_ma[i] > slow_ma[i] and fast_ma[i-1] <= slow_ma[i-1]:
                signals.append(1)
                crossovers.append("golden")
            # 死叉
            elif fast_ma[i] < slow_ma[i] and fast_ma[i-1] >= slow_ma[i-1]:
                signals.append(-1)
                crossovers.append("death")
            else:
                signals.append(0)
                crossovers.append(None)
    
    return {
        "fast_ma": fast_ma,
        "slow_ma": slow_ma,
        "signal": signals,
        "crossover": crossovers
    }


def rsi_extreme_signal(prices: list[float], period: int = 14,
                      oversold: float = 30, overbought: float = 70) -> dict:
    """RSI 超买超卖信号"""
    rsi = calculate_rsi(prices, period)
    
    signals = []
    extremes = []
    
    for i in range(len(prices)):
        if rsi[i] is None:
            signals.append(0)
            extremes.append(None)
        elif rsi[i] < oversold:
            signals.append(1)  # 买入
            extremes.append("oversold")
        elif rsi[i] > overbought:
            signals.append(-1)  # 卖出
            extremes.append("overbought")
        else:
            signals.append(0)
            extremes.append(None)
    
    return {
        "rsi": rsi,
        "signal": signals,
        "extreme": extremes
    }


def donchian_breakout_signal(highs: list[float], lows: list[float], closes: list[float], 
                            period: int = 20) -> dict:
    """唐奇安通道突破信号"""
    channel = calculate_donchian(highs, lows, period)
    
    signals = []
    breakouts = []
    
    for i in range(len(closes)):
        if i < period or channel["upper"][i] is None:
            signals.append(0)
            breakouts.append(None)
        else:
            # 突破上轨
            if highs[i] > channel["upper"][i] and highs[i-1] <= channel["upper"][i-1]:
                signals.append(1)
                breakouts.append("upper")
            # 跌破下轨
            elif lows[i] < channel["lower"][i] and lows[i-1] >= channel["lower"][i-1]:
                signals.append(-1)
                breakouts.append("lower")
            else:
                signals.append(0)
                breakouts.append(None)
    
    return {
        "upper": channel["upper"],
        "lower": channel["lower"],
        "signal": signals,
        "breakout": breakouts
    }


def supertrend_signal(highs: list[float], lows: list[float], closes: list[float],
                     period: int = 10, multiplier: float = 3.0) -> dict:
    """超级趋势信号"""
    atr = calculate_atr(highs, lows, closes, period)
    
    upper_band = []
    lower_band = []
    supertrend = []
    trend = []
    
    for i in range(len(closes)):
        if atr[i] is None:
            upper_band.append(None)
            lower_band.append(None)
            supertrend.append(None)
            trend.append(0)
        else:
            hl2 = (highs[i] + lows[i]) / 2
            upper = hl2 + multiplier * atr[i]
            lower = hl2 - multiplier * atr[i]
            
            # 趋势判断
            if i == 0 or trend[-1] == 0:
                current_trend = 1 if closes[i] >= hl2 else -1
            else:
                if closes[i] > upper_band[-1]:
                    current_trend = 1
                elif closes[i] < lower_band[-1]:
                    current_trend = -1
                else:
                    current_trend = trend[-1]
            
            trend.append(current_trend)
            upper_band.append(round(upper, 4))
            lower_band.append(round(lower, 4))
            supertrend.append(round(upper if current_trend == -1 else lower, 4))
    
    # 信号
    signals = []
    for i in range(len(trend)):
        if i < period:
            signals.append(0)
        elif trend[i] == 1 and trend[i-1] == -1:
            signals.append(1)  # 买入
        elif trend[i] == -1 and trend[i-1] == 1:
            signals.append(-1)  # 卖出
        else:
            signals.append(0)
    
    return {
        "trend": trend,
        "supertrend": supertrend,
        "upper_band": upper_band,
        "lower_band": lower_band,
        "signal": signals
    }


def bollinger_squeeze_signal(prices: list[float], period: int = 20, std_dev: float = 2.0,
                           adx_period: int = 14, adx_threshold: float = 25) -> dict:
    """布林带收口突破信号"""
    bb = calculate_bollinger(prices, period, std_dev)
    adx_data = calculate_adx(prices, prices, prices, adx_period)
    adx = adx_data["adx"]
    
    signals = []
    squeeze = []
    
    for i in range(len(prices)):
        if bb["bandwidth"][i] is None or adx[i] is None:
            signals.append(0)
            squeeze.append(False)
        else:
            # 收口: 带宽低于历史20%分位
            is_squeeze = bb["bandwidth"][i] < np.percentile(bb["bandwidth"][:i+1], 20) if i > 10 else False
            squeeze.append(is_squeeze)
            
            # 突破确认: ADX > 阈值
            if is_squeeze and adx[i] > adx_threshold:
                if closes[i] > bb["upper"][i]:
                    signals.append(1)  # 向上突破
                elif closes[i] < bb["lower"][i]:
                    signals.append(-1)  # 向下突破
                else:
                    signals.append(0)
            else:
                signals.append(0)
    
    return {
        "bollinger": bb,
        "adx": adx,
        "signal": signals,
        "squeeze": squeeze
    }


def momentum_rank(price_data: dict[str, list[float]], period: int = 20, top_n: int = 5) -> list[dict]:
    """动量排名选币"""
    results = []
    
    for symbol, prices in price_data.items():
        if len(prices) < period + 1:
            continue
        
        current = prices[-1]
        past = prices[-period - 1]
        momentum = (current - past) / past if past != 0 else 0
        
        results.append({
            "symbol": symbol,
            "current_price": current,
            "past_price": past,
            "momentum": round(momentum, 6),
            "momentum_pct": round(momentum * 100, 2)
        })
    
    # 按动量排序
    results.sort(key=lambda x: x["momentum"], reverse=True)
    
    # 添加排名
    for i, r in enumerate(results):
        r["rank"] = i + 1
    
    return results[:top_n]


def volume_breakout(candle_data: dict[str, dict], threshold: float = 2.0, period: int = 20) -> list[dict]:
    """成交量突破选币"""
    results = []
    
    for symbol, data in candle_data.items():
        volumes = data.get("volumes", [])
        closes = data.get("closes", [])
        highs = data.get("highs", closes)
        lows = data.get("lows", closes)
        
        if len(volumes) < period + 1:
            continue
        
        # 计算量比
        avg_volume = sum(volumes[-period:]) / period
        current_volume = volumes[-1]
        volume_ratio = current_volume / avg_volume if avg_volume != 0 else 0
        
        # 判断趋势
        ma = calculate_ma(closes, period)
        trend = "up" if closes[-1] > ma[-1] else "down"
        
        # 是否突破
        is_breakout = volume_ratio > threshold
        
        results.append({
            "symbol": symbol,
            "volume_ratio": round(volume_ratio, 2),
            "current_volume": current_volume,
            "avg_volume": round(avg_volume, 2),
            "trend": trend,
            "is_breakout": is_breakout
        })
    
    # 按量比排序
    results.sort(key=lambda x: x["volume_ratio"], reverse=True)
    
    return results


# ============================================================================
# 策略执行
# ============================================================================

class GridTrader:
    """网格交易策略"""
    
    def __init__(self, upper: float, lower: float, layers: int = 10,
                 initial_ratio: float = 0.1, leverage: float = 1.0):
        self.upper = upper
        self.lower = lower
        self.layers = layers
        self.initial_ratio = initial_ratio
        self.leverage = leverage
        self.grid_prices = np.linspace(lower, upper, layers)
        self.positions = {}  # {price_level: quantity}
        
    def get_grid_levels(self) -> list[float]:
        """获取网格价格水平"""
        return self.grid_prices.tolist()
    
    def signal(self, current_price: float) -> dict:
        """生成交易信号"""
        # 找到最近的网格
        idx = np.abs(self.grid_prices - current_price).argmin()
        nearest_price = self.grid_prices[idx]
        
        action = "hold"
        quantity = 0
        level = idx
        
        # 简单策略: 价格触及网格线且无仓位则开仓
        if nearest_price not in self.positions:
            if current_price <= nearest_price * 1.001:  # 触及网格
                action = "buy"
                quantity = self.initial_ratio * self.leverage
                self.positions[nearest_price] = quantity
        else:
            # 已有仓位，检查是否需要平仓
            if current_price >= nearest_price * 1.01:  # 盈利1%
                action = "sell"
                quantity = self.positions[nearest_price]
                del self.positions[nearest_price]
        
        return {
            "action": action,
            "level_price": float(nearest_price),
            "level_index": int(idx),
            "quantity": quantity,
            "grid_levels": self.get_grid_levels(),
            "current_positions": list(self.positions.keys())
        }


class TrendGridTrader(GridTrader):
    """趋势追踪网格策略"""
    
    def __init__(self, upper: float, lower: float, layers: int = 10,
                 ma_period: int = 50, trailing_pct: float = 0.02, **kwargs):
        super().__init__(upper, lower, layers, **kwargs)
        self.ma_period = ma_period
        self.trailing_pct = trailing_pct
        self.highest_price = lower
        
    def signal(self, current_price: float, ma_value: Optional[float] = None) -> dict:
        """考虑趋势的信号"""
        # 更新最高价
        if current_price > self.highest_price:
            self.highest_price = current_price
        
        # 检查移动止损
        stop_price = self.highest_price * (1 - self.trailing_pct)
        trailing_stop_triggered = current_price < stop_price
        
        # 趋势过滤
        trend_filter = True
        if ma_value is not None:
            trend_filter = current_price > ma_value  # 只在上涨趋势中做多
        
        # 基本网格信号
        base_signal = super().signal(current_price)
        
        # 如果触发移动止损
        if trailing_stop_triggered and self.positions:
            return {
                "action": "sell",
                "reason": "trailing_stop",
                "stop_price": round(stop_price, 4),
                "highest_price": round(self.highest_price, 4),
                **base_signal
            }
        
        # 趋势过滤
        if not trend_filter:
            return {
                "action": "hold",
                "reason": "trend_filter",
                "ma_required": ma_value,
                "current_price": current_price,
                **base_signal
            }
        
        return {
            "reason": "grid",
            "trailing_stop_price": round(stop_price, 4),
            "highest_price": round(self.highest_price, 4),
            **base_signal
        }


def trailing_stop(entry_price: float, current_price: float,
                  highest_price: float, trailing_pct: float = 0.05) -> dict:
    """移动止损"""
    stop_price = highest_price * (1 - trailing_pct)
    
    return {
        "stop_price": round(stop_price, 4),
        "should_stop": current_price < stop_price,
        "profit_pct": round((current_price - entry_price) / entry_price * 100, 2),
        "highest_price": round(highest_price, 4)
    }

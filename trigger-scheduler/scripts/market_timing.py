#!/usr/bin/env python3
"""
Stock Market Timing Constants and Helpers
Pre-defined cron expressions for market events.
"""

from typing import NamedTuple
from enum import Enum


# ─── Market Timing Constants ─────────────────────────────────────────────────

class MarketTiming(NamedTuple):
    name: str
    expression: str
    description: str
    timezone: str = "Asia/Shanghai"

# A股主要时间节点
A股_MARKET_TIMING = {
    "PRE_MARKET_OPEN": MarketTiming(
        "盘前开始",
        "0 8 * * 1-5",
        "8:00 AM — 盘前准备、隔夜新闻阅读",
    ),
    "MORNING_PREP": MarketTiming(
        "早盘准备",
        "0 9 * * 1-5",
        "9:00 AM — 开盘前最后检查",
    ),
    "MARKET_OPEN": MarketTiming(
        "开盘",
        "0 9 * * 1-5",
        "9:00 AM — A股开盘",
    ),
    "MORNING_SESSION": MarketTiming(
        "早盘",
        "0 10 * * 1-5",
        "10:00 AM — 早盘第一个小时",
    ),
    "MIDDAY_CHECK": MarketTiming(
        "午盘检查",
        "0 11 * * 1-5",
        "11:00 AM — 午盘前检查",
    ),
    "LUNCH_BREAK": MarketTiming(
        "午间休市",
        "0 12 * * 1-5",
        "12:00 PM — 午间休市",
    ),
    "AFTERNOON_PREP": MarketTiming(
        "下午盘准备",
        "0 12 * * 1-5",
        "12:30 PM — 下午盘准备",
    ),
    "AFTERNOON_SESSION": MarketTiming(
        "下午盘",
        "0 13 * * 1-5",
        "1:00 PM — 下午盘开始",
    ),
    "MARKET_CLOSE": MarketTiming(
        "收盘",
        "0 15 * * 1-5",
        "3:00 PM — A股收盘",
    ),
    "POST_MARKET_1": MarketTiming(
        "盘后分析",
        "0 15 * * 1-5",
        "3:00 PM — 盘后初步分析",
    ),
    "AFTER_HOURS": MarketTiming(
        "盘后总结",
        "0 16 * * 1-5",
        "4:00 PM — 盘后总结",
    ),
    "DAY_END": MarketTiming(
        "日终",
        "0 17 * * 1-5",
        "5:00 PM — 日终处理",
    ),
}

# 美股主要时间节点（北京时间）
美股_MARKET_TIMING = {
    "PRE_MARKET": MarketTiming(
        "美股盘前",
        "0 16 * * 1-5",
        "4:00 AM 北京时间 = 盘前交易开始",
    ),
    "REGULAR_SESSION": MarketTiming(
        "美股盘中",
        "0 21 * * 1-5",
        "9:30 AM ET = 9:30 PM 北京时间（夏令时）",
    ),
    "AFTER_HOURS": MarketTiming(
        "美股盘后",
        "0 1 * * 1-5",
        "4:00 AM ET = 盘后交易",
    ),
}

# 周期性检查
PERIODIC_CHECKS = {
    "HOURLY": MarketTiming(
        "每小时检查",
        "0 * * * *",
        "每小时整点执行",
    ),
    "EVERY_30_MIN": MarketTiming(
        "每30分钟",
        "*/30 * * * *",
        "每30分钟执行",
    ),
    "EVERY_15_MIN": MarketTiming(
        "每15分钟",
        "*/15 * * * *",
        "每15分钟执行（日内交易）",
    ),
    "EVERY_5_MIN": MarketTiming(
        "每5分钟",
        "*/5 * * * *",
        "每5分钟执行（高频监控）",
    ),
}

# 每周总结
WEEKLY_REVIEW = {
    "MONDAY_PREP": MarketTiming(
        "周一准备",
        "0 8 * * 1",
        "周一开盘前 — 周回顾与本周计划",
    ),
    "FRIDAY_REVIEW": MarketTiming(
        "周五回顾",
        "0 16 * * 5",
        "周五收盘 — 本周总结",
    ),
    "WEEKLY_REBALANCE": MarketTiming(
        "每周调仓",
        "0 9 * * 1",
        "周一 — 评估是否需要调仓",
    ),
}

# 月度
MONTHLY = {
    "MONTH_START": MarketTiming(
        "月初",
        "0 9 1 * *",
        "每月1日 — 月度策略回顾",
    ),
    "MONTH_END": MarketTiming(
        "月末",
        "0 16 L * *",
        "每月最后一天 — 月度结算",
    ),
}

# ─── Market Calendars ─────────────────────────────────────────────────────────

A股_TRADING_DAYS = [1, 2, 3, 4, 5]  # Monday = 1, Sunday = 7

# 2026年A股休市日（部分）
A股_HOLIDAYS_2026 = [
    "2026-01-01",  # 元旦
    "2026-01-28",  # 春节
    "2026-01-29",
    "2026-01-30",
    "2026-01-31",
    "2026-02-01",
    "2026-02-02",
    "2026-02-03",
    "2026-04-03",  # 清明
    "2026-04-04",
    "2026-04-05",
    "2026-05-01",  # 劳动节
    "2026-05-02",
    "2026-05-03",
    "2026-06-01",  # 儿童节（不调休）
    "2026-06-20",  # 端午节
    "2026-06-21",
    "2026-06-22",
    "2026-09-28",  # 中秋
    "2026-09-29",
    "2026-09-30",
    "2026-10-01",  # 国庆
    "2026-10-02",
    "2026-10-03",
    "2026-10-04",
    "2026-10-05",
    "2026-10-06",
    "2026-10-07",
    "2026-10-08",
    "2026-10-09",
]


# ─── Condition Templates ─────────────────────────────────────────────────────

class ConditionType(str, Enum):
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    PRICE_CHANGE_PCT = "price_change_pct"
    VOLUME_SPIKE = "volume_spike"
    NEWS_KEYWORDS = "news_keywords"
    SIGNAL_DETECTED = "signal_detected"
    PORTFOLIO_THRESHOLD = "portfolio_threshold"


@dataclass
class TriggerCondition:
    type: str
    symbol: str = ""
    threshold: float = 0.0
    comparison: str = ">"  # >, <, >=, <=, ==
    keywords: list[str] = field(default_factory=list)
    lookback_period: int = 20  # for volume spike

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v}


# ─── Quick Reference ──────────────────────────────────────────────────────────

QUICK_TRIGGERS = {
    # 盘前
    "盘前准备": {
        "name": "盘前准备",
        "type": "cron",
        "schedule": "0 8 * * 1-5",
        "payload": {
            "kind": "agentTurn",
            "message": "执行盘前准备：\n1. 检查隔夜美股涨跌\n2. 查看A50期货\n3. 阅读重要财经新闻\n4. 生成今日关注股票"
        }
    },

    # 开盘
    "开盘检查": {
        "name": "开盘检查",
        "type": "cron",
        "schedule": "0 9 * * 1-5",
        "payload": {
            "kind": "agentTurn",
            "message": "执行开盘检查：\n1. 确认开盘价\n2. 检查集合竞价情况\n3. 评估开盘方向\n4. 如有异动给出预警"
        }
    },

    # 午盘
    "午盘检查": {
        "name": "午盘检查",
        "type": "cron",
        "schedule": "0 11 * * 1-5",
        "payload": {
            "kind": "agentTurn",
            "message": "执行午盘分析：\n1. 上午行情回顾\n2. 下午操作建议\n3. 重点关注股票检查"
        }
    },

    # 收盘
    "盘后总结": {
        "name": "盘后总结",
        "type": "cron",
        "schedule": "0 15 * * 1-5",
        "payload": {
            "kind": "agentTurn",
            "message": "执行盘后总结：\n1. 今日行情回顾\n2. 持仓检查\n3. 止损线检查\n4. 明日操作计划"
        }
    },

    # 周报
    "周度回顾": {
        "name": "周度回顾",
        "type": "cron",
        "schedule": "0 16 * * 5",
        "payload": {
            "kind": "agentTurn",
            "message": "执行本周回顾：\n1. 本周收益率统计\n2. 基准对比\n3. 策略执行情况\n4. 下周操作计划"
        }
    },

    # 月报
    "月度回顾": {
        "name": "月度回顾",
        "type": "cron",
        "schedule": "0 9 1 * *",
        "payload": {
            "kind": "agentTurn",
            "message": "执行月度回顾：\n1. 本月收益率\n2. 风险评估\n3. 策略有效性分析\n4. 下月调整计划"
        }
    },
}


if __name__ == "__main__":
    print("=== A股市场时间节点 ===")
    for key, t in A股_MARKET_TIMING.items():
        print(f"{t.name:20} | {t.expression:15} | {t.description}")

    print("\n=== 快速触发器模板 ===")
    for key, trig in QUICK_TRIGGERS.items():
        print(f"- {key}: {trig['type']} / {trig.get('schedule', trig.get('symbol', 'N/A'))}")

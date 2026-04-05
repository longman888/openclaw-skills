---
name: trigger-scheduler
description: |
  Cron-based task scheduling and event-driven trigger system.
  Triggers when: (1) user asks to schedule recurring tasks ("every day at 9am", "every Monday");
  (2) setting up automated workflows (pre-market prep, post-market summary);
  (3) conditional triggers (price alert, news event, signal detected).
  Based on Claude Code's AGENT_TRIGGERS architecture.
  Provides: cron expressions, event types, trigger chains, and stock market timing.
---

# Trigger Scheduler

## Core Concept

Define once, execute automatically. Triggers replace manual polling with event-driven automation.

```
Trigger = Time/Condition + Action + Payload
```

## Trigger Types

### 1. Time-Based Triggers (Cron)

Standard cron expression: `minute hour day month weekday`

| Expression | Meaning |
|------------|---------|
| `0 9 * * 1-5` | 9:00 AM every weekday (trading days) |
| `0 15 * * 1-5` | 3:00 PM every weekday (close) |
| `0 8 * * 1-5` | 8:00 AM every weekday (pre-market) |
| `30 9 * * 1-5` | 9:30 AM every weekday (market open) |
| `0 12 * * *` | Noon every day |
| `0 */2 * * *` | Every 2 hours |

### 2. Stock Market Timing Triggers

Pre-defined market timing constants:

| Name | Expression | Purpose |
|------|------------|---------|
| `PRE_MARKET` | `0 8 * * 1-5` | Pre-market preparation |
| `MARKET_OPEN` | `30 9 * * 1-5` | Market open analysis |
| `INTRADAY_CHECK` | `0 */1 * * 1-5` | Hourly check during session |
| `MARKET_CLOSE` | `0 15 * * 1-5` | Post-market summary |
| `AFTER_HOURS` | `0 16 * * 1-5` | After-hours analysis |
| `WEEKLY_SUMMARY` | `0 16 * * 5` | Friday weekly report |
| `MONTHLY_REBALANCE` | `0 9 1 * *` | Month-start rebalance |

### 3. Condition-Based Triggers

| Condition | Description | Example |
|-----------|-------------|---------|
| `price_above` | Stock price crosses above threshold | AAPL > $200 |
| `price_below` | Stock price crosses below threshold | TSLA < $150 |
| `price_change_pct` | Price change exceeds % | BTC ±5% |
| `volume_spike` | Volume exceeds N× average | Volume > 3× 20-day avg |
| `news_keywords` | News contains keywords | "FDA approval" |
| `signal_detected` | Trading signal triggered | MACD golden cross |
| `portfolio_threshold` | Portfolio metric breached | Portfolio VaR > 2% |

## Trigger Definition Schema

```json
{
  "id": "trigger_001",
  "name": "Daily Market Open Briefing",
  "type": "cron",
  "schedule": "0 8 * * 1-5",
  "timezone": "Asia/Shanghai",
  "enabled": true,
  "payload": {
    "kind": "agentTurn",
    "message": "执行盘前准备：\n1. 检查隔夜美股涨跌\n2. 获取A股期货走势\n3. 阅读最新财经新闻\n4. 生成今日重点关注股票"
  },
  "sessionTarget": "isolated",
  "delivery": {
    "mode": "announce"
  },
  "cooldownSeconds": 3600,
  "lastRun": null,
  "nextRun": "2026-04-02T08:00:00+08:00"
}
```

## Stock Market Trigger Examples

### Pre-Market Prep (Every Trading Day 8:00 AM)

```json
{
  "name": "盘前准备",
  "type": "cron",
  "schedule": "0 8 * * 1-5",
  "timezone": "Asia/Shanghai",
  "payload": {
    "kind": "agentTurn",
    "message": "执行盘前准备任务：\n1. 检查隔夜美股收盘（标普500、纳斯达克）\n2. 查看A50期货走势\n3. 阅读隔夜重要财经新闻\n4. 列出今日重点关注股票\n5. 生成操作计划摘要"
  }
}
```

### Price Alert Trigger

```json
{
  "name": "AAPL价格预警",
  "type": "price_above",
  "symbol": "AAPL",
  "threshold": 200.0,
  "payload": {
    "kind": "agentTurn",
    "message": "AAPL 价格已突破 $200！\n执行检查：\n1. 查看相关新闻\n2. 检查技术面突破有效性\n3. 评估是否触发买入条件\n4. 生成操作建议"
  }
}
```

### Weekly Portfolio Review (Every Friday 4:00 PM)

```json
{
  "name": "每周组合回顾",
  "type": "cron",
  "schedule": "0 16 * * 5",
  "payload": {
    "kind": "agentTurn",
    "message": "执行本周组合回顾：\n1. 统计本周各持仓收益率\n2. 对比基准（沪深300）表现\n3. 检查止损线是否触发\n4. 评估下周操作计划\n5. 生成周报"
  }
}
```

## Trigger Chains

Chain multiple triggers into a sequence:

```json
{
  "name": "开盘监测链",
  "triggers": [
    {
      "type": "cron",
      "schedule": "0 9 * * 1-5",
      "action": "run_payload"
    },
    {
      "type": "signal",
      "signal": "market_volatility > 0.02",
      "action": "run_payload"
    },
    {
      "type": "timeout",
      "seconds": 7200,
      "action": "run_payload"
    }
  ]
}
```

## Execution Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `isolated` | Run in separate session | Background tasks, scheduled jobs |
| `main` | Run in main session | Urgent interrupts, user present |
| `subagent` | Spawn sub-agent | Complex analysis, parallel tasks |

## Trigger Management Commands

| Action | Command |
|--------|---------|
| List triggers | `cron list` |
| Add trigger | `cron add <trigger.json>` |
| Enable | `cron enable <trigger_id>` |
| Disable | `cron disable <trigger_id>` |
| Run now | `cron run <trigger_id>` |
| View history | `cron runs <trigger_id>` |
| Remove | `cron remove <trigger_id>` |

## Anti-Spam: Cooldown

Each trigger has a `cooldownSeconds` field to prevent over-firing:

| Trigger Type | Default Cooldown |
|-------------|-----------------|
| Cron (daily) | 3600s (1 hour) |
| Cron (hourly) | 600s (10 min) |
| Price alert | 300s (5 min) |
| News alert | 600s (10 min) |
| Signal alert | 60s (1 min) |

## Scripts

- `scripts/trigger_manager.py` — CRUD operations for triggers
- `scripts/market_timing.py` — Stock market timing constants and helpers
- `scripts/condition_evaluator.py` — Condition-based trigger evaluation

## References

- `references/cron-syntax.md` — Full cron expression reference
- `references/stock-triggers.md` — Stock domain trigger templates

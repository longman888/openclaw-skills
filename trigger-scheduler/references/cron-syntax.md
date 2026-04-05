# Cron Syntax Reference

## Format

```
minute hour day month weekday
```

| Field | Allowed Values | Special Characters |
|-------|---------------|-------------------|
| minute | 0-59 | * , - / |
| hour | 0-23 | * , - / |
| day | 1-31 | * , - / |
| month | 1-12 | * , - / |
| weekday | 0-7 (0,7=Sunday) | * , - / |

## Special Characters

| Char | Meaning | Example |
|------|---------|---------|
| `*` | Any value | `* * * * *` = every minute |
| `,` | List | `0,30 * * * *` = at 0 and 30 minutes |
| `-` | Range | `9-17 * * 1-5` = 9am-5pm weekdays |
| `/` | Step | `*/15 * * * *` = every 15 minutes |

## Common Stock Market Examples

```bash
# Every trading day at specific times
0 8 * * 1-5      # 8:00 AM every weekday (pre-market)
0 9 * * 1-5      # 9:00 AM every weekday (market open)
0 15 * * 1-5     # 3:00 PM every weekday (market close)
0 16 * * 1-5     # 4:00 PM every weekday (after hours)

# Every 15 minutes during trading hours
*/15 9-15 * * 1-5  # Every 15 min from 9am-3pm weekdays

# Weekly
0 16 * * 5        # 4:00 PM every Friday (weekly review)
0 9 * * 1         # 9:00 AM every Monday (weekly plan)

# Monthly
0 9 1 * *         # 9:00 AM on 1st of every month

# Specific stock alerts
30 9 * * 1-5      # 9:30 AM (market open 30 min)
0 10 * * 1-5      # 10:00 AM (first hour check)
0 11 * * 1-5      # 11:00 AM (midday check)
0 13 * * 1-5      # 1:00 PM (afternoon session)
```

## Timezone Handling

Always specify timezone for stock market triggers:

```json
{
  "schedule": "0 9 * * 1-5",
  "timezone": "Asia/Shanghai"
}
```

## Validation

```python
from trigger_manager import parse_cron

# Validate
minutes, hours, days, months, weekdays = parse_cron("0 9 * * 1-5")

# Check if valid
minutes == [0]
hours == [9]
weekdays == [1, 2, 3, 4, 5]
```

## Stock Trigger Templates

```json
// Price alert template
{
  "name": "价格预警",
  "type": "price_above",
  "symbol": "AAPL",
  "threshold": 200.0,
  "cooldownSeconds": 300,
  "payload": {
    "kind": "agentTurn",
    "message": "AAPL 价格突破 $200，执行检查并给出建议"
  }
}

// Volume spike template
{
  "name": "成交量异动",
  "type": "volume_spike",
  "symbol": "TSLA",
  "threshold": 3.0,
  "cooldownSeconds": 600,
  "payload": {
    "kind": "agentTurn",
    "message": "TSLA 成交量异常放大，检查原因并分析"
  }
}

// News alert template
{
  "name": "新闻关键词预警",
  "type": "news_keywords",
  "keywords": "FDA,approval,drug",
  "symbol": "MRNA",
  "cooldownSeconds": 600,
  "payload": {
    "kind": "agentTurn",
    "message": "检测到MRNA相关新闻触发关键词，执行分析"
  }
}
```

---
name: stock-data
description: |
  Stock market data acquisition skill — real-time quotes, historical K-line, financial news, and fundamental data.
  Triggers when: (1) user asks to fetch stock prices, quotes, or market data;
  (2) building datasets for backtesting or analysis;
  (3) monitoring watchlist stocks;
  (4) scraping financial news.
  Supports: Yahoo Finance, Tencent Finance, Eastmoney, Tushare API.
  Provides: unified data API, caching layer, data validation.
---

# Stock Data Acquisition

## Data Sources

| Source | Coverage | Auth | Latency |
|--------|---------|------|---------|
| **Yahoo Finance** | Global (A/H/ADR) | None | ~15min delayed |
| **Tencent Finance** | A股 + 港股 | None | Real-time |
| **Eastmoney** | A股全市场 | None | Real-time |
| **Tushare** | A股 + 港股 | API Token | Historical + 实时 |

## Core Functions

### get_quote(symbol)

获取单只股票实时行情。

```python
quote = get_quote("AAPL")
# {
#   "symbol": "AAPL",
#   "name": "Apple Inc.",
#   "price": 189.45,
#   "change": -1.23,
#   "change_pct": -0.65,
#   "open": 190.50,
#   "high": 191.20,
#   "low": 188.90,
#   "prev_close": 190.68,
#   "volume": 52340000,
#   "market_cap": 2950e9,
#   "timestamp": "2026-04-02T09:15:00+08:00"
# }
```

### get_quotes(symbols: list)

批量获取多只股票行情。

```python
quotes = get_quotes(["AAPL", "TSLA", "腾讯控股"])
```

### get_kline(symbol, period="1d", count=100)

获取历史K线数据。

```python
kline = get_kline("AAPL", period="1d", count=100)
# {
#   "symbol": "AAPL",
#   "period": "1d",
#   "data": [
#     {"date": "2026-01-03", "open": 185.2, "high": 187.5, "low": 184.8, "close": 186.9, "volume": 45230000},
#     ...
#   ]
# }
```

**period 选项：** `1m` `5m` `15m` `1h` `1d` `1wk`

### get_financials(symbol)

获取财务报表数据。

```python
 financials = get_financials("AAPL")
# {
#   "symbol": "AAPL",
#   "income_statement": { ... },   # 利润表
#   "balance_sheet": { ... },       # 资产负债表
#   "cash_flow": { ... },           # 现金流量表
#   "metrics": {
#     "pe_ratio": 28.5,
#     "pb_ratio": 45.2,
#     "roe": 0.156,
#     "debt_to_equity": 1.82,
#     "revenue": 394328e6,
#     "net_income": 97015e6,
#     "eps": 6.13
#   }
# }
```

### get_news(symbol, count=10)

获取新闻列表。

```python
news = get_news("AAPL", count=10)
# [
#   {"title": "...", "source": "Reuters", "url": "...", "time": "2026-04-02T08:30:00"},
#   ...
# ]
```

## Symbol Format

| Market | Format | Example |
|--------|--------|---------|
| A股 | `600519.SH` / `000001.SZ` | 上交所茅台、深交所平安 |
| 港股 | `00700.HK` | 腾讯 |
| 美股 | `AAPL` / `TSLA` | 苹果、特斯拉 |
| H股ADR | `9988.HK` | 阿里巴巴 |

## Caching

- Real-time quote cache: 60 seconds
- K-line data cache: 5 minutes (intraday) / 1 hour (daily+)
- Financial data cache: 1 hour
- News cache: 5 minutes

## Data Validation

```python
# Price sanity check
assert quote["low"] <= quote["price"] <= quote["high"], "Price outside H/L range"

# Change consistency
expected = quote["price"] - quote["prev_close"]
assert abs(quote["change"] - expected) < 0.01, "Change mismatch"
```

## Scripts

- `scripts/data_api.py` — Unified data API (all sources)
- `scripts/cache.py` — Cache management
- `scripts/tencent_scraper.py` — Tencent Finance scraper
- `scripts/eastmoney_scraper.py` — Eastmoney scraper

## References

- `references/symbols.md` — Symbol format reference for all markets

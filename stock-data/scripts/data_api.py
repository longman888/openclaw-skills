#!/usr/bin/env python3
"""
Stock Data API — Unified interface for all data sources.
Supports: Yahoo Finance, Tencent Finance, Eastmoney.

Usage:
    from data_api import get_quote, get_kline, get_financials, get_news
"""

import re
import json
import time
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("stock-data")

# ─── Symbol Utilities ─────────────────────────────────────────────────────────

def normalize_symbol(symbol: str) -> tuple[str, str]:
    """
    Normalize symbol to (normalized, market).
    Returns (yahoo_symbol, market).
    """
    symbol = symbol.strip().upper()

    # A股沪市
    if re.match(r"^\d{6}\.SH$", symbol):
        return symbol, "SSE"
    # A股深市
    if re.match(r"^\d{6}\.SZ$", symbol):
        return symbol, "SZSE"
    # 港股
    if re.match(r"^\d{5}\.HK$", symbol):
        return symbol, "HK"
    # 美股 (already normalized)
    if re.match(r"^[A-Z]{1,5}$", symbol):
        return symbol, "US"

    # Chinese names → symbols (basic)
    NAME_MAP = {
        "腾讯控股": "00700.HK",
        "阿里巴巴": "9988.HK",
        "茅台": "600519.SH",
        "平安": "601318.SH",
        "招商银行": "600036.SH",
        "宁德时代": "300750.SZ",
    }
    if symbol in NAME_MAP:
        return NAME_MAP[symbol], "HK" if ".HK" in NAME_MAP[symbol] else "SSE"

    return symbol, "US"


def to_yahoo_symbol(symbol: str) -> str:
    """Convert to Yahoo Finance format."""
    norm, market = normalize_symbol(symbol)
    if market == "SSE":
        return norm  # e.g., 600519.SS for Shanghai
    if market == "SZSE":
        return norm  # e.g., 000001.SZ for Shenzhen
    if market == "HK":
        return norm
    return norm  # US stocks already in Yahoo format


# ─── Data Models ──────────────────────────────────────────────────────────────

@dataclass
class Quote:
    symbol: str
    name: str
    price: float
    change: float
    change_pct: float
    open: float
    high: float
    low: float
    prev_close: float
    volume: int
    market_cap: float
    timestamp: str
    source: str

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol, "name": self.name, "price": self.price,
            "change": self.change, "change_pct": self.change_pct,
            "open": self.open, "high": self.high, "low": self.low,
            "prev_close": self.prev_close, "volume": self.volume,
            "market_cap": self.market_cap, "timestamp": self.timestamp,
            "source": self.source
        }


@dataclass
class OHLC:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    adj_close: Optional[float] = None


# ─── Yahoo Finance ────────────────────────────────────────────────────────────

def fetch_yahoo_quote(symbol: str) -> Optional[Quote]:
    """Fetch quote from Yahoo Finance using yfinance."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        meta = ticker.info

        price = info.last_price or 0
        prev = info.previous_close or 0
        change = price - prev
        change_pct = (change / prev * 100) if prev else 0

        return Quote(
            symbol=symbol,
            name=meta.get("shortName", symbol),
            price=price,
            change=round(change, 2),
            change_pct=round(change_pct, 2),
            open=info.open or price,
            high=info.day_high or price,
            low=info.day_low or price,
            prev_close=prev,
            volume=int(info.last_volume or 0),
            market_cap=info.market_cap or 0,
            timestamp=datetime.now().isoformat(),
            source="yahoo"
        )
    except Exception as e:
        log.warning(f"Yahoo fetch failed for {symbol}: {e}")
        return None


def fetch_yahoo_kline(symbol: str, period: str = "1mo", count: int = 100) -> list[OHLC]:
    """Fetch historical K-line from Yahoo Finance."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, auto_adjust=False)

        if df.empty:
            return []

        # Rename columns to lowercase
        df.columns = [c.lower() for c in df.columns]
        result = []
        for _, row in df.iterrows():
            result.append(OHLC(
                date=str(row.name.date()),
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=int(row.volume),
                adj_close=float(row.get("adj close", row.close))
            ))
        return result[-count:]
    except Exception as e:
        log.warning(f"Yahoo kline failed for {symbol}: {e}")
        return []


def fetch_yahoo_financials(symbol: str) -> Optional[dict]:
    """Fetch financial statements from Yahoo Finance."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)

        # Get income statement, balance sheet, cash flow
        income = ticker.income_stmt
        balance = ticker.balance_sheet
        cashflow = ticker.cashflow
        info = ticker.info

        if income is None or income.empty:
            return None

        # Extract key metrics
        metrics = {}
        if "PE ratio" in info:
            metrics["pe_ratio"] = info.get("trailing_pe", info.get("forward_pe", 0))
        if "Price to Book" in info:
            metrics["pb_ratio"] = info.get("price_to_book", 0)
        if "Return on Equity" in info:
            metrics["roe"] = info.get("returnOnEquity", 0)
        if "Debt to Equity" in info:
            metrics["debt_to_equity"] = info.get("debtToEquity", 0)
        if "Total Revenue" in income.index:
            metrics["revenue"] = float(income.loc["Total Revenue"].iloc[-1])
        if "Net Income" in income.index:
            metrics["net_income"] = float(income.loc["Net Income"].iloc[-1])

        # EPS
        if income.index.str.contains("EPS", case=False).any():
            eps_series = income.loc[income.index.str.contains("EPS", case=False)].iloc[-1]
            metrics["eps"] = float(eps_series)

        return {
            "symbol": symbol,
            "income_statement": income.to_dict() if income is not None else {},
            "balance_sheet": balance.to_dict() if balance is not None else {},
            "cash_flow": cashflow.to_dict() if cashflow is not None else {},
            "metrics": metrics
        }
    except Exception as e:
        log.warning(f"Yahoo financials failed for {symbol}: {e}")
        return None


# ─── Tencent Finance ─────────────────────────────────────────────────────────

def fetch_tencent_quote(symbol: str) -> Optional[Quote]:
    """
    Fetch quote from Tencent Finance API.
    API: https://qt.gtimg.cn/q=<symbol>
    Symbol format: usAAPL, hk00700, sh600519, sz000001
    """
    try:
        import urllib.request
        import json

        # Convert symbol to Tencent format
        norm, market = normalize_symbol(symbol)
        if market == "US":
            tt_symbol = f"us{norm}"
        elif market == "HK":
            tt_symbol = f"hk{norm.zfill(5)}"
        elif market == "SSE":
            tt_symbol = f"sh{norm}"
        elif market == "SZSE":
            tt_symbol = f"sz{norm}"
        else:
            tt_symbol = f"us{norm}"

        url = f"https://qt.gtimg.cn/q={tt_symbol}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("gbk", errors="replace")

        # Parse response
        # Format: v_pvtestquote="data1|data2|..."
        match = re.search(r'"([^"]+)"', raw)
        if not match:
            return None

        parts = match.group(1).split("~")
        if len(parts) < 50:
            return None

        # parts[0]=symbol, parts[1]=name, parts[3]=price, parts[4]=change,
        # parts[5]=change%, parts[6]=volume, parts[32-34]=OHLC, parts[36]=prev_close
        price = float(parts[3]) if parts[3] else 0
        prev_close = float(parts[4]) if parts[4] else price
        change = price - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0
        volume = int(parts[6]) if parts[6] else 0

        return Quote(
            symbol=norm,
            name=parts[1] if parts[1] else symbol,
            price=price,
            change=round(change, 2),
            change_pct=round(change_pct, 2),
            open=float(parts[5]) if parts[5] else price,
            high=float(parts[33]) if parts[33] else price,
            low=float(parts[34]) if parts[34] else price,
            prev_close=prev_close,
            volume=volume,
            market_cap=0,
            timestamp=datetime.now().isoformat(),
            source="tencent"
        )
    except Exception as e:
        log.warning(f"Tencent fetch failed for {symbol}: {e}")
        return None


# ─── Main API ─────────────────────────────────────────────────────────────────

def get_quote(symbol: str, source: str = "auto") -> Optional[Quote]:
    """
    Get real-time quote for a symbol.
    source: "yahoo" | "tencent" | "auto"
    """
    if source == "auto":
        # Try Yahoo first, fall back to Tencent
        q = fetch_yahoo_quote(to_yahoo_symbol(symbol))
        if q:
            return q
        return fetch_tencent_quote(symbol)

    if source == "yahoo":
        return fetch_yahoo_quote(to_yahoo_symbol(symbol))
    if source == "tencent":
        return fetch_tencent_quote(symbol)
    return None


def get_quotes(symbols: list[str], source: str = "auto") -> list[Quote]:
    """Get quotes for multiple symbols."""
    results = []
    for sym in symbols:
        q = get_quote(sym, source)
        if q:
            results.append(q)
        time.sleep(0.1)  # Rate limiting
    return results


def get_kline(symbol: str, period: str = "1mo", count: int = 100, source: str = "yahoo") -> list[OHLC]:
    """
    Get historical K-line data.
    period: 1m, 5m, 15m, 1h, 1d, 1wk (Yahoo format)
    """
    if source == "yahoo":
        return fetch_yahoo_kline(to_yahoo_symbol(symbol), period, count)
    return []


def get_financials(symbol: str, source: str = "yahoo") -> Optional[dict]:
    """Get financial statements."""
    if source == "yahoo":
        return fetch_yahoo_financials(to_yahoo_symbol(symbol))
    return None


def get_news(symbol: str, count: int = 10) -> list[dict]:
    """
    Get financial news for a symbol.
    Placeholder — in production, use news API (NewsAPI, TuShare, etc.)
    """
    # Simple placeholder
    return [
        {
            "title": f"{symbol} 相关新闻（需集成新闻API）",
            "source": "system",
            "url": "",
            "time": datetime.now().isoformat()
        }
    ]


# ─── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Stock Data API")
    sub = parser.add_subparsers(dest="cmd")
    p_q = sub.add_parser("quote", help="Get quote")
    p_q.add_argument("symbol")
    p_k = sub.add_parser("kline", help="Get K-line")
    p_k.add_argument("symbol")
    p_k.add_argument("--period", default="1mo")
    p_k.add_argument("--count", type=int, default=30)
    args = parser.parse_args()

    if args.cmd == "quote":
        q = get_quote(args.symbol)
        if q:
            print(f"{q.name} ({q.symbol}): ${q.price} ({q.change:+.2f}, {q.change_pct:+.2f}%)")
            print(f"  O:{q.open} H:{q.high} L:{q.low} C:{q.prev_close}")
            print(f"  Vol: {q.volume:,} | Source: {q.source}")
        else:
            print(f"No data for {args.symbol}")

    elif args.cmd == "kline":
        klines = get_kline(args.symbol, args.period, args.count)
        print(f"K-line ({args.symbol}, {args.period}, {len(klines)} bars):")
        for k in klines[-5:]:
            print(f"  {k.date}: O={k.open:.2f} H={k.high:.2f} L={k.low:.2f} C={k.close:.2f} V={k.volume:,}")

    else:
        parser.print_help()

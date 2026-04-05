# china_data_adapter.py — A股数据适配器
"""
将必盈API / 同花顺API 适配为 TradingAgents 风格的数据接口。
数据源优先级：必盈API > 同花顺 > akshare（冷备）
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger("china_data_adapter")


# ─── 数据源配置 ────────────────────────────────────────────────────

@dataclass
class DataSourceConfig:
    biying_api_key: str = "0DBE72CF-F8CF-4F85-BAB8-2AC17E1D7E9E"
    biying_base_url: str = "https://api.biyingapi.com"
    ths_appid: str = "a6e59af717e1411cb64e511f58ecf54a"
    ths_api_key: str = "5a0bcba649a44065a075e30d73b321ef"
    ths_base_url: str = "https://api.aimiai.com"

    @classmethod
    def from_env(cls) -> "DataSourceConfig":
        """从环境变量或配置文件加载"""
        return cls(
            biying_api_key=os.environ.get("BIYING_API_KEY", cls.biying_api_key),
            biying_base_url=os.environ.get("BIYING_API_BASE", cls.biying_base_url),
            ths_appid=os.environ.get("THS_APPID", cls.ths_appid),
            ths_api_key=os.environ.get("THS_API_KEY", cls.ths_api_key),
            ths_base_url=os.environ.get("THS_API_BASE", cls.ths_base_url),
        )


# ─── A股代码标准化 ────────────────────────────────────────────────

def normalize_code(code: str) -> str:
    """
    将各种格式的A股代码标准化为6位纯数字。
    Examples:
        600519 -> 600519
        sh600519 -> 600519
        600519.SH -> 600519
        贵州茅台 -> 600519 (需要映射表，这里仅做标准化)
    """
    code = code.strip().upper()
    # 移除后缀
    for suffix in [".SH", ".SZ", ".BJ", ".SS"]:
        if code.endswith(suffix):
            code = code[:-len(suffix)]
    # 移除交易所前缀
    for prefix in ["SH", "SZ", "BJ", "SHANGHAI", "SHENZHEN"]:
        if code.startswith(prefix):
            code = code[len(prefix):]
    return code.strip().lstrip("0")


# ─── 实时行情 ──────────────────────────────────────────────────────

async def get_realtime_quote(codes: List[str]) -> Dict[str, Any]:
    """
    获取A股实时行情。
    URL格式: /hsrl/ssjy/{code}/{licence}
    对应 TradingAgents 的 get_stock_data。
    
    Returns:
        Dict[code, quote_data]
    """
    config = DataSourceConfig.from_env()
    results = {}

    for code in codes:
        code = normalize_code(code)
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                # 必盈实时行情: /hsrl/ssjy/{code}/{licence}
                resp = await client.get(
                    f"{config.biying_base_url}/hsrl/ssjy/{code}/{config.biying_api_key}",
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results[code] = _parse_biying_quote(data)
                    continue

                # 降级到同花顺
                resp = await client.get(
                    f"{config.ths_base_url}/v1/quote",
                    params={"appid": config.ths_appid, "apikey": config.ths_api_key, "code": code},
                )
                if resp.status_code == 200:
                    results[code] = _parse_ths_quote(resp.json())
        except Exception as e:
            logger.warning(f"Failed to fetch quote for {code}: {e}")

    return results


def _parse_biying_quote(data: dict) -> dict:
    """
    解析必盈实时行情。
    URL: /hsrl/ssjy/{code}/{licence}
    响应字段: t/time, p/price, pc/price_change_pct, ud/updown_abs, 
             v/volume, cje/amount, zf/zhangfu_amplitude, hs/turnover_rate,
             pe, lb/vol_ratio, h/high, l/low, o/open, pc2/prev_close
    """
    try:
        return {
            "name": data.get("nm", ""),           # name
            "code": data.get("code", ""),
            "price": float(data.get("p", 0)),      # 当前价
            "change_pct": float(data.get("pc", 0)) * 100,  # 涨跌幅（%，API返回小数）
            "change_abs": float(data.get("ud", 0)),  # 涨跌绝对值
            "volume": float(data.get("v", 0)),       # 成交量（万手）
            "amount": float(data.get("cje", 0)),    # 成交额（元）
            "high": float(data.get("h", 0)),         # 最高价
            "low": float(data.get("l", 0)),          # 最低价
            "open": float(data.get("o", 0)),         # 开盘价
            "prev_close": float(data.get("pc2", data.get("p", 0))),  # 昨收
            "turnover_rate": float(data.get("hs", 0)),  # 换手率（%）
            "volume_ratio": float(data.get("lb", 0)),  # 量比
            "pe": float(data.get("pe", 0)),          # 市盈率
            "amplitude": float(data.get("zf", 0)),    # 振幅（%）
            "pe": float(data.get("pe", 0)),           # 市盈率（实时报价中已有）
            "source": "biyingapi",
        }
    except (ValueError, TypeError) as e:
        logger.error(f"Failed to parse biying quote: {e}")
        return {}


def _parse_ths_quote(data: dict) -> dict:
    """解析同花顺实时行情"""
    try:
        q = data.get("data", {}).get("quote", {})
        return {
            "name": q.get("name", ""),
            "code": q.get("code", ""),
            "price": float(q.get("price", 0)),
            "change_pct": float(q.get("changeRate", 0)) * 100,
            "change_abs": float(q.get("change", 0)),
            "volume": int(q.get("volume", 0)),
            "amount": float(q.get("amount", 0)),
            "high": float(q.get("high", 0)),
            "low": float(q.get("low", 0)),
            "open": float(q.get("open", 0)),
            "prev_close": float(q.get("close", 0)),
            "bid1": float(q.get("bid1", 0)),
            "ask1": float(q.get("ask1", 0)),
            "bid_vol1": int(q.get("bidvol1", 0)),
            "ask_vol1": int(q.get("askvol1", 0)),
            "source": "10jqka",
        }
    except (ValueError, TypeError) as e:
        logger.error(f"Failed to parse THS quote: {e}")
        return {}


# ─── K线数据 ──────────────────────────────────────────────────────

async def get_kline(
    code: str,
    period: str = "daily",
    start_date: str = "",
    end_date: str = "",
    adjust: str = "qfq",
) -> List[Dict[str, Any]]:
    """
    获取A股K线数据。
    URL: /hszbl/fsjy/{code}/d/{KEY}（历史日线）
    响应: [{d:"2001-08-27",o,h,l,c,v,e,zf,hs,zd,zde,ud},...]
    """
    config = DataSourceConfig.from_env()
    code = normalize_code(code)

    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            # 必盈历史日线
            url = f"{config.biying_base_url}/hszbl/fsjy/{code}/d/{config.biying_api_key}"
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return _parse_biying_kline(data)
    except Exception as e:
        logger.warning(f"Failed to fetch kline for {code}: {e}")

    return []


def _parse_biying_kline(data: list) -> List[dict]:
    """
    解析必盈K线数据（历史日线格式）。
    响应为 list: [{d:"2001-08-27",o,h,l,c,v,e,zf,hs,zd,zde,ud},...]
    """
    result = []
    for row in data:
        try:
            result.append({
                "date": row.get("d", ""),
                "open": float(row.get("o", 0)),
                "high": float(row.get("h", 0)),
                "low": float(row.get("l", 0)),
                "close": float(row.get("c", 0)),
                "volume": int(float(row.get("v", 0))),      # 成交量（手）
                "amount": float(row.get("e", 0)),          # 成交额（元）
                "amplitude": float(row.get("zf", 0)),       # 振幅（%）
                "turnover_rate": float(row.get("hs", 0)),   # 换手率（%）
                "change_abs": float(row.get("zd", 0)),     # 涨跌（绝对值）
                "change_pct": float(row.get("zde", 0)),   # 涨跌幅（%）
            })
        except (ValueError, TypeError):
            pass
    return result


# ─── 财务数据 ──────────────────────────────────────────────────────

async def get_financials(code: str) -> Dict[str, Any]:
    """
    获取A股财务数据（PE、PB、ROE等）。
    对应 TradingAgents 的 get_fundamentals。
    """
    config = DataSourceConfig.from_env()
    code = normalize_code(code)

    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{config.biying_base_url}/financial/{code}",
                headers={"apikey": config.biying_api_key},
            )
            if resp.status_code == 200:
                return _parse_biying_financial(resp.json())
    except Exception as e:
        logger.warning(f"Failed to fetch financials for {code}: {e}")

    return {}


def _parse_biying_financial(data: dict) -> dict:
    """解析必盈财务数据"""
    return {
        "pe": data.get("pe", 0),
        "pb": data.get("pb", 0),
        "roe": data.get("roe", 0),
        "revenue_yoy": data.get("revenue_yoy", 0),  # 营收同比（%）
        "profit_yoy": data.get("profit_yoy", 0),    # 净利润同比（%）
        "gross_margin": data.get("gross_margin", 0),  # 毛利率（%）
        "net_margin": data.get("net_margin", 0),      # 净利率（%）
        "debt_ratio": data.get("debt_ratio", 0),      # 资产负债率（%）
        "total_revenue": data.get("total_revenue", 0),
        "total_profit": data.get("total_profit", 0),
        "business_income": data.get("business_income", 0),
        "operate_cash_flow": data.get("operate_cash_flow", 0),
        "source": "biyingapi",
    }


# ─── 新闻数据 ──────────────────────────────────────────────────────

async def get_news(code: str, limit: int = 10) -> List[Dict[str, str]]:
    """
    获取A股新闻/公告。
    对应 TradingAgents 的 get_news。
    """
    config = DataSourceConfig.from_env()
    code = normalize_code(code)

    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{config.biying_base_url}/news/{code}",
                headers={"apikey": config.biying_api_key},
                params={"limit": limit},
            )
            if resp.status_code == 200:
                data = resp.json()
                news_list = data.get("data", [])
                return [
                    {
                        "title": item.get("title", ""),
                        "pub_time": item.get("pub_time", ""),
                        "source": item.get("source", ""),
                        "summary": item.get("summary", ""),
                        "url": item.get("url", ""),
                    }
                    for item in news_list
                ]
    except Exception as e:
        logger.warning(f"Failed to fetch news for {code}: {e}")

    return []


# ─── 持仓接口 ──────────────────────────────────────────────────────

def load_portfolio() -> Dict[str, Any]:
    """从 portfolio.json 加载当前持仓"""
    portfolio_file = r"E:\.openclaw\data_bus\portfolio.json"
    if os.path.exists(portfolio_file):
        with open(portfolio_file, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    return {}


def save_portfolio(portfolio: Dict[str, Any]) -> None:
    """保存持仓到 portfolio.json"""
    portfolio_file = r"E:\.openclaw\data_bus\portfolio.json"
    os.makedirs(os.path.dirname(portfolio_file), exist_ok=True)
    with open(portfolio_file, "w", encoding="utf-8-sig") as f:
        json.dump(portfolio, f, ensure_ascii=False, indent=2)

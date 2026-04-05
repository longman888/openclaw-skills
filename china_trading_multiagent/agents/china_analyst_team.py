# china_analyst_team.py — A股分析师团队
"""
Analyst Team for A-share market.
给定股票代码，并行调用多维度分析，输出结构化分析报告。
支持 Quality Level (LOW/MEDIUM/HIGH) 和本地 LM Studio (Qwen3.5-7B) LLM 驱动。
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from skills.china_trading_multiagent.data_tools.china_data_adapter import (
    get_realtime_quote,
    get_kline,
    get_financials,
    get_news,
    normalize_code,
)
from skills.china_trading_multiagent.data_tools.sentiment_news_fetcher import (
    fetch_news_for_stock,
    brief,
)
from skills.china_trading_multiagent.data_tools.lm_client import (
    generate_fundamental_report,
    generate_debate_arguments,
    is_lm_available,
)
from skills.china_trading_multiagent.config.china_config import (
    ANALYST_SYSTEM_PROMPT,
    TECHNICAL_ANALYST_PROMPT,
    ChinaTradingConfig,
    AnalysisDepth,
)

logger = logging.getLogger("analyst_team")


@dataclass
class AnalystReport:
    """结构化分析报告"""
    code: str
    name: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # 基本面
    fundamental_score: int = 50   # 0-100
    fundamental_grade: str = "持有"
    fundamental_pros: List[str] = field(default_factory=list)
    fundamental_cons: List[str] = field(default_factory=list)
    pe: float = 0
    pb: float = 0
    roe: float = 0
    revenue_yoy: float = 0
    profit_yoy: float = 0

    # 技术面
    technical_score: int = 50
    technical_trend: str = "震荡"
    technical_indicators: Dict[str, str] = field(default_factory=dict)
    support_levels: List[float] = field(default_factory=list)
    resistance_levels: List[float] = field(default_factory=list)

    # 情绪/新闻
    news_count: int = 0
    news_sentiment: str = "中性"
    latest_news: List[Dict[str, str]] = field(default_factory=list)

    # 实时行情快照
    current_price: float = 0
    change_pct: float = 0
    volume_ratio: float = 0
    turnover_rate: float = 0


async def fetch_all_data(code: str, depth: AnalysisDepth = AnalysisDepth.MEDIUM) -> Dict[str, Any]:
    """
    并行获取所有类型数据。
    根据 analysis_depth 决定是否执行耗时的网络搜索新闻。
    """
    code = normalize_code(code)

    # 基础数据（low/medium/high 都获取）
    quote_task = get_realtime_quote([code])
    kline_task = get_kline(code, period="daily", start_date="", end_date="", adjust="qfq")

    # 财报 + 快报新闻（low 除外）
    financial_task = None
    news_task = None
    if depth != AnalysisDepth.LOW:
        financial_task = get_financials(code)
        news_task = get_news(code, limit=10)

    # Web 深度搜索新闻（medium/high）
    web_news_task = None
    if depth == AnalysisDepth.MEDIUM or depth == AnalysisDepth.HIGH:
        quote_data = await quote_task
        name = ""
        if isinstance(quote_data, dict):
            name = quote_data.get(code, {}).get("name", "")
        if name:
            web_news_task = fetch_news_for_stock(code, name, max_results=8)

    results = await asyncio.gather(
        quote_task, kline_task,
        financial_task if financial_task else asyncio.sleep(0),
        news_task if news_task else asyncio.sleep(0),
        web_news_task if web_news_task else asyncio.sleep(0),
        return_exceptions=True,
    )

    return {
        "quote": results[0].get(code, {}) if isinstance(results[0], dict) else {},
        "klines": results[1] if isinstance(results[1], list) else [],
        "financials": results[2] if isinstance(results[2], dict) else {},
        "news": results[3] if isinstance(results[3], list) else [],
        "web_sentiment": results[4] if results[4] is not None else None,
    }


def calculate_technical_indicators(klines: List[dict]) -> Dict[str, Any]:
    """根据K线数据计算技术指标。"""
    if len(klines) < 20:
        return {}

    closes = [k["close"] for k in klines]

    def sma(data, period):
        if len(data) < period:
            return None
        return sum(data[-period:]) / period

    ma5 = sma(closes, 5)
    ma10 = sma(closes, 10)
    ma20 = sma(closes, 20)
    ma60 = sma(closes, 60) if len(closes) >= 60 else None
    current = closes[-1]

    # RSI(14)
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0 for d in deltas[-14:]]
    losses = [-d if d < 0 else 0 for d in deltas[-14:]]
    avg_gain = sum(gains) / 14 if gains else 0
    avg_loss = sum(losses) / 14 if losses else 0
    rs = avg_gain / avg_loss if avg_loss > 0 else 999
    rsi = 100 - (100 / (1 + rs)) if rs < 999 else 50

    # MACD (简化)
    ema12 = sum(closes[-12:]) / 12
    ema26 = sum(closes[-26:]) / 26
    dif = ema12 - ema26

    # 布林带（20日）
    import statistics
    if len(closes) >= 20:
        ma20_arr = closes[-20:]
        std = statistics.stdev(ma20_arr)
        upper_band = ma20 + 2 * std
        lower_band = ma20 - 2 * std
    else:
        upper_band = lower_band = ma20

    return {
        "MA5": round(ma5, 2) if ma5 else None,
        "MA10": round(ma10, 2) if ma10 else None,
        "MA20": round(ma20, 2) if ma20 else None,
        "MA60": round(ma60, 2) if ma60 else None,
        "RSI14": round(rsi, 1),
        "MACD_DIF": round(dif, 3),
        "BOLL_UPPER": round(upper_band, 2),
        "BOLL_LOWER": round(lower_band, 2),
        "BOLL_POSITION": round((current - lower_band) / (upper_band - lower_band) * 100, 1)
                          if upper_band != lower_band else 50,
        "PRICE": current,
        "SUPPORT": round(lower_band, 2),
        "RESISTANCE": round(upper_band, 2),
    }


def score_fundamentals(financials: dict, quote: dict) -> tuple:
    """根据财务数据打分"""
    score = 50
    pros, cons = [], []

    pe = financials.get("pe", 0)
    pb = financials.get("pb", 0)
    roe = financials.get("roe", 0)
    rev_yoy = financials.get("revenue_yoy", 0)
    prof_yoy = financials.get("profit_yoy", 0)
    gross_margin = financials.get("gross_margin", 0)
    debt_ratio = financials.get("debt_ratio", 0)

    if 0 < pe < 20:
        score += 15; pros.append(f"PE={pe:.1f}，估值偏低")
    elif pe > 60:
        score -= 15; cons.append(f"PE={pe:.1f}，估值偏高")
    elif pe <= 0:
        cons.append("PE为负，亏损状态")

    if roe > 15:
        score += 15; pros.append(f"ROE={roe:.1f}%，盈利能力优秀")
    elif roe > 8:
        score += 5; pros.append(f"ROE={roe:.1f}%，盈利能力良好")
    elif roe < 0:
        score -= 15; cons.append(f"ROE={roe:.1f}%，亏损")

    if rev_yoy > 20:
        score += 10; pros.append(f"营收同比增长{rev_yoy:.1f}%，成长性强劲")
    elif rev_yoy < 0:
        score -= 10; cons.append(f"营收同比下滑{rev_yoy:.1f}%，业务萎缩")

    if prof_yoy > 20:
        score += 10; pros.append(f"净利润同比增长{prof_yoy:.1f}%，业绩超预期")
    elif prof_yoy < -20:
        score -= 10; cons.append(f"净利润同比下滑{prof_yoy:.1f}%，业绩变差")

    if gross_margin > 40:
        score += 5; pros.append(f"毛利率{gross_margin:.1f}%，定价能力强")
    elif gross_margin < 15:
        score -= 5; cons.append(f"毛利率{gross_margin:.1f}%，竞争激烈")

    if debt_ratio > 80:
        score -= 10; cons.append(f"资产负债率{debt_ratio:.1f}%，财务风险偏高")
    elif debt_ratio < 50:
        pros.append(f"资产负债率{debt_ratio:.1f}%，财务稳健")

    score = max(0, min(100, score))

    if score >= 80: grade = "强烈买入"
    elif score >= 65: grade = "买入"
    elif score >= 40: grade = "持有"
    elif score >= 25: grade = "卖出"
    else: grade = "强烈卖出"

    return score, grade, pros[:3], cons[:3]


def score_technical(indicators: dict, quote: dict) -> tuple:
    """根据技术指标打分"""
    score = 50
    current = indicators.get("PRICE", 0)
    ma5 = indicators.get("MA5", 0)
    ma10 = indicators.get("MA10", 0)
    ma20 = indicators.get("MA20", 0)
    ma60 = indicators.get("MA60", 0)
    rsi = indicators.get("RSI14", 50)
    boll_pos = indicators.get("BOLL_POSITION", 50)

    if not all([current, ma5, ma10, ma20]):
        return 50, "震荡"

    if current > ma5 > ma10 > ma20:
        score += 20
    elif current > ma20 and ma5 > ma10:
        score += 10
    elif current < ma20:
        score -= 15

    if rsi > 80: score -= 10
    elif rsi < 30: score += 10
    elif 40 <= rsi <= 60: score += 5

    if boll_pos > 80: score -= 10
    elif boll_pos < 20: score += 10

    if ma60 and current > ma60: score += 10
    elif ma60 and current < ma60: score -= 10

    score = max(0, min(100, score))
    if score >= 70: trend = "多头"
    elif score <= 30: trend = "空头"
    else: trend = "震荡"

    return score, trend


async def run_analyst_team(
    code: str,
    analysis_depth: AnalysisDepth = AnalysisDepth.MEDIUM,
) -> AnalystReport:
    """主函数：运行完整的A股分析师团队"""
    logger.info(f"[AnalystTeam] 开始分析 {code} (depth={analysis_depth.value})")

    # 并行获取所有数据
    data = await fetch_all_data(code, depth=analysis_depth)

    quote = data["quote"]
    klines = data["klines"]
    financials = data["financials"]
    news = data["news"]
    web_sentiment = data.get("web_sentiment")

    name = quote.get("name", "")
    if not name:
        name = _code_to_name_fallback(code)

    report = AnalystReport(code=code, name=name)

    # 行情快照
    report.current_price = quote.get("price", 0)
    report.change_pct = quote.get("change_pct", 0)
    report.volume_ratio = quote.get("volume_ratio", 0)
    report.turnover_rate = quote.get("turnover_rate", 0)

    # 基本面评分（LLM 驱动 or 规则兜底）
    merged = dict(financials) if financials else {}
    if not merged.get("pe") and quote.get("pe"):
        merged["pe"] = quote.get("pe", 0)

    if merged or quote.get("pe"):
        # LLM 驱动（LM Studio 可用时）
        lm_ok = is_lm_available() and analysis_depth != AnalysisDepth.LOW
        if lm_ok:
            logger.info("[AnalystTeam] LM Studio 可用，使用 LLM 生成基本面报告（注入K线+策略上下文）...")
            llm_result = generate_fundamental_report(
                code=code, name=name,
                price=report.current_price,
                change_pct=report.change_pct,
                pe=report.pe, pb=report.pb, roe=report.roe,
                gross_margin=0,
                rev_yoy=report.revenue_yoy, prof_yoy=report.profit_yoy,
                klines=klines,   # 注入K线，让模型知道当前行情
            )
            if llm_result:
                report.fundamental_score = int(llm_result.get("fundamental_score", report.fundamental_score))
                report.fundamental_grade = llm_result.get("grade", report.fundamental_grade)
                report.fundamental_pros = llm_result.get("pros", report.fundamental_pros)
                report.fundamental_cons = llm_result.get("cons", report.fundamental_cons)
                logger.info(f"[AnalystTeam] LLM报告: score={report.fundamental_score}, grade={report.fundamental_grade}")
            else:
                logger.warning("[AnalystTeam] LLM报告生成失败，使用规则打分兜底")
                (report.fundamental_score, report.fundamental_grade,
                 report.fundamental_pros, report.fundamental_cons) = score_fundamentals(merged or quote, quote)
        else:
            (report.fundamental_score, report.fundamental_grade,
             report.fundamental_pros, report.fundamental_cons) = score_fundamentals(merged or quote, quote)

        report.pe = merged.get("pe", quote.get("pe", 0))
        report.pb = merged.get("pb", 0)
        report.roe = merged.get("roe", 0)
        report.revenue_yoy = merged.get("revenue_yoy", 0)
        report.profit_yoy = merged.get("profit_yoy", 0)

    # 技术面评分
    if klines:
        indicators = calculate_technical_indicators(klines)
        report.technical_indicators = indicators
        report.technical_score, report.technical_trend = score_technical(indicators, quote)
        report.support_levels = [indicators.get("SUPPORT", 0)]
        report.resistance_levels = [indicators.get("RESISTANCE", 0)]

    # 新闻/情绪（Web搜索优先，关键词兜底）
    report.news_count = len(news)
    report.latest_news = news[:5] if news else []

    if web_sentiment and web_sentiment.news:
        report.news_sentiment = web_sentiment.sentiment_label
        report.news_count = len(web_sentiment.news) + len(news)
        report.latest_news = [
            {"title": n.title, "snippet": (n.snippet[:80] + "..." if len(n.snippet) > 80 else n.snippet), "url": n.url}
            for n in web_sentiment.news[:5]
        ]
    elif news:
        bullish = sum(1 for n in news if any(k in n.get("title","") for k in ["突破","涨停","大涨","买入","增持","超预期","业绩"]))
        bearish = sum(1 for n in news if any(k in n.get("title","") for k in ["下跌","减持","亏损","风险","警告","暴雷","业绩下滑"]))
        if bullish > bearish * 2:
            report.news_sentiment = "看多"
        elif bearish > bullish * 2:
            report.news_sentiment = "看空"
        else:
            report.news_sentiment = "中性"

    logger.info(f"[AnalystTeam] {code} 完成: 基本面={report.fundamental_score}, 技术={report.technical_score}, 评级={report.fundamental_grade}, 情绪={report.news_sentiment}")

    return report


def _code_to_name_fallback(code: str) -> str:
    """代码到名称的本地映射"""
    name_map = {
        "600519": "贵州茅台", "000858": "五粮液", "601318": "中国平安",
        "600036": "招商银行", "000001": "平安银行", "300750": "宁德时代",
        "688981": "中芯国际", "002475": "立讯精密", "600276": "恒瑞医药",
    }
    code = normalize_code(code)
    return name_map.get(code, code)

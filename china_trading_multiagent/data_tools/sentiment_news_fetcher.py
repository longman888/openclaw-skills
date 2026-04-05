# sentiment_news_fetcher.py — A股新闻与情绪数据获取
"""
通过 DuckDuckGo 搜索获取A股相关新闻，解析摘要用于情绪分析。
集成自 OpenHarness web_search_tool.py 的搜索思路。
"""

import re
import html
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger("sentiment_news_fetcher")

# ─── 常量 ────────────────────────────────────────────────────────

BULLISH_KEYWORDS = [
    "突破", "涨停", "大涨", "涨停板", "买入", "增持", "超预期",
    "业绩", "高增长", "订单", "合作", "新品", "获批", "净流入",
    "布局", "扩张", "亮眼", "强劲", "史上", "首次",
]

BEARISH_KEYWORDS = [
    "下跌", "跌停", "大跌", "减持", "亏损", "风险", "警告",
    "暴雷", "业绩下滑", "造假", "调查", "处罚", "净流出",
    "减持", "清仓", "踩雷", "危机", "困境", "终止",
]


@dataclass
class NewsItem:
    title: str
    url: str
    snippet: str
    pub_time: str = ""
    sentiment: str = "neutral"  # bullish / bearish / neutral
    sentiment_score: int = 50   # 0-100, >50 bullish


@dataclass
class SentimentResult:
    code: str
    name: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    news: List[NewsItem] = field(default_factory=list)
    bullish_count: int = 0
    bearish_count: int = 0
    neutral_count: int = 0
    sentiment_score: int = 50   # 0-100, >50 bullish
    sentiment_label: str = "neutral"
    summary: str = ""


# ─── 搜索 ────────────────────────────────────────────────────────

async def fetch_news_for_stock(code: str, name: str, max_results: int = 8) -> SentimentResult:
    """
    主函数：搜索股票相关新闻，返回情绪分析结果。
    优先用 DuckDuckGo（英文/国际），备选百度搜索（国内可访问）。
    """
    """
    主函数：搜索股票相关新闻，返回情绪分析结果。
    """
    import httpx

    result = SentimentResult(code=code, name=name)

    # 构造搜索 query（A股股票加关键词）
    queries = [
        f"{name} {code} 股票 最新",
        f"{name}" + " 业绩 公告",
        f"{name}" + " 涨跌 最新",
    ]

    async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
        for query in queries[:2]:  # 最多搜2次
            try:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": "Mozilla/5.0 (compatible; agent/1.0)"},
                )
                if resp.status_code == 200 and len(resp.text) > 200:
                    items = _parse_search_results(resp.text, max_results=3)
                    result.news.extend(items)
            except Exception as e:
                logger.debug(f"DuckDuckGo search failed: {e}")

        # 备选：百度搜索（国内可访问）
        if not result.news:
            for query in queries[:1]:
                try:
                    resp = await client.get(
                        "https://www.baidu.com/s",
                        params={"wd": query, "rn": 5, "ie": "utf-8"},
                        headers={"User-Agent": "Mozilla/5.0 (compatible; agent/1.0)"},
                    )
                    if resp.status_code == 200:
                        items = _parse_baidu_results(resp.text, max_results=5)
                        result.news.extend(items)
                except Exception as e:
                    logger.debug(f"Baidu search failed: {e}")

    # 去重
    seen = set()
    unique_news = []
    for item in result.news:
        if item.url not in seen:
            seen.add(item.url)
            unique_news.append(item)
    result.news = unique_news[:max_results]

    # 计算情绪
    _score_sentiment(result)

    return result


# ─── 解析 ────────────────────────────────────────────────────────

def _parse_search_results(body: str, max_results: int = 5) -> List[NewsItem]:
    """从 DuckDuckGo HTML 解析搜索结果"""
    results: List[NewsItem] = []

    # 提取标题+URL
    anchor_pattern = re.compile(
        r'<a(?P<attrs>[^>]+)>(?P<title>.*?)</a>',
        flags=re.DOTALL | re.IGNORECASE,
    )
    for match in anchor_pattern.finditer(body):
        attrs = match.group("attrs")
        class_match = re.search(r'class="(?P<class>[^"]+)"', attrs, re.IGNORECASE)
        if class_match is None:
            continue
        class_names = class_match.group("class")
        if "result__a" not in class_names and "result-link" not in class_names:
            continue
        href_match = re.search(r'href="(?P<href>[^"]+)"', attrs, re.IGNORECASE)
        if href_match is None:
            continue
        title = _clean_text(match.group("title"))
        if not title:
            continue
        url = _normalize_url(href_match.group("href"))
        if not url or len(url) < 10:
            continue
        results.append(NewsItem(title=title, url=url, snippet=""))
        if len(results) >= max_results:
            break

    # 提取 snippet
    snippet_pattern = re.compile(
        r'<(?:a|div|span)[^>]+class="[^"]*(?:result__snippet|result-snippet)[^"]*"[^>]*>'
        r'(?P<snippet>.*?)'
        r'</(?:a|div|span)>',
        flags=re.DOTALL | re.IGNORECASE,
    )
    snippets = [_clean_text(m.group("snippet")) for m in snippet_pattern.finditer(body)]

    for i, item in enumerate(results):
        if i < len(snippets):
            item.snippet = snippets[i][:200]  # 截断

    return results


def _clean_text(fragment: str) -> str:
    """清理 HTML 标签和转义字符"""
    text = re.sub(r"(?s)<[^>]+>", " ", fragment)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_url(raw_url: str) -> str:
    """规范化 DuckDuckGo 跳转 URL"""
    from urllib.parse import parse_qs, unquote, urlparse
    parsed = urlparse(raw_url)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(target) if target else raw_url
    return raw_url


def _parse_baidu_results(body: str, max_results: int = 5) -> List[NewsItem]:
    """从百度搜索结果页面解析新闻"""
    results: List[NewsItem] = []
    # 百度搜索结果: <h3 class="news-title"><a href="...">标题</a>...
    title_pattern = re.compile(
        r'<h3[^>]+class="[^"]*title[^"]*"[^>]*>.*?<a[^>]+href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>',
        flags=re.DOTALL | re.IGNORECASE,
    )
    for match in title_pattern.finditer(body):
        url = match.group("url").strip()
        title = _clean_text(match.group("title"))
        if title and url and len(url) > 10:
            results.append(NewsItem(title=title, url=url, snippet=""))
        if len(results) >= max_results:
            break
    return results


# ─── 情绪评分 ────────────────────────────────────────────────────

def _score_sentiment(result: SentimentResult) -> None:
    """
    根据新闻标题关键词和 snippet 计算情绪。
    更新 result 的 sentiment_score / sentiment_label / 各项计数。
    """
    bullish = 0
    bearish = 0

    for item in result.news:
        text = item.title + " " + item.snippet
        text_lower = text.lower()

        b_count = sum(1 for kw in BULLISH_KEYWORDS if kw in text)
        bear_count = sum(1 for kw in BEARISH_KEYWORDS if kw in text)

        if b_count > bear_count:
            item.sentiment = "bullish"
            item.sentiment_score = min(50 + b_count * 10, 95)
            bullish += 1
        elif bear_count > b_count:
            item.sentiment = "bearish"
            item.sentiment_score = max(50 - bear_count * 10, 5)
            bearish += 1
        else:
            item.sentiment = "neutral"
            item.sentiment_score = 50

    result.bullish_count = bullish
    result.bearish_count = bearish
    result.neutral_count = max(0, len(result.news) - bullish - bearish)

    total = len(result.news)
    if total == 0:
        result.sentiment_score = 50
        result.sentiment_label = "neutral"
        result.summary = "无相关新闻数据"
        return

    # 加权情绪分
    raw = sum(n.sentiment_score for n in result.news) / total
    result.sentiment_score = int(raw)

    if raw >= 60:
        result.sentiment_label = "bullish"
        result.summary = f"看多（{bullish}利好 / {bearish}利空）"
    elif raw <= 40:
        result.sentiment_label = "bearish"
        result.summary = f"看空（{bearish}利空 / {bullish}利好）"
    else:
        result.sentiment_label = "neutral"
        result.summary = f"中性（{bullish}多 / {bearish}空 / {result.neutral_count}中）"


# ─── Brief Tool（压缩长文本）─────────────────────────────────────

def brief(text: str, max_chars: int = 120) -> str:
    """
    将长文本压缩为关键句子。
    来自 OpenHarness brief_tool.py 的思路。
    """
    if not text or len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "…"

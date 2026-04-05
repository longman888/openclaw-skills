# lm_client.py — LM Studio / Qwen 本地大模型客户端
"""
通过 LM Studio 本地部署的 Qwen3.5-9B 生成分析报告。
接口兼容 OpenAI API 格式，支持 /v1/chat/completions。

重要：本地模型知识截止约2024年，最新行情（2026）必须通过Prompt注入，
模型才能基于真实数据进行分析，而非依赖训练数据"记忆"。
"""

import os
import json
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger("lm_client")


# ─── 配置 ────────────────────────────────────────────────────────

DEFAULT_BASE_URL = "http://localhost:41430/v1"   # LM Studio 服务器地址
DEFAULT_MODEL = "qwen3.5-9b"                          # Qwen3.5-9B


def get_lm_config() -> dict:
    """从环境变量读取 LM Studio 配置"""
    return {
        "base_url": os.environ.get("LM_BASE_URL", DEFAULT_BASE_URL),
        "model": os.environ.get("LM_MODEL", DEFAULT_MODEL),
        "api_key": os.environ.get("LM_API_KEY", "lm-studio"),
        "temperature": float(os.environ.get("LM_TEMPERATURE", "0.3")),
        "max_tokens": int(os.environ.get("LM_MAX_TOKENS", "1024")),
    }


# ─── 基础调用 ────────────────────────────────────────────────────

def generate(
    prompt: str,
    system: str = "",
    config: dict = None,
) -> str:
    """
    同步调用本地 LLM。
    """
    import httpx

    cfg = get_lm_config()
    if config:
        cfg.update(config)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": cfg["temperature"],
        "max_tokens": cfg["max_tokens"],
        "stream": False,
    }

    try:
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{cfg['base_url']}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {cfg['api_key']}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
            else:
                logger.error(f"LM Studio API error {resp.status_code}: {resp.text[:300]}")
                return ""
    except Exception as e:
        logger.warning(f"LM Studio request failed: {e}")
        return ""


def _extract_json(result: str) -> dict:
    """从 LLM 输出中提取 JSON"""
    import re
    try:
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", result, re.DOTALL)
        if json_match:
            text = json_match.group(1)
        else:
            start = result.find("{")
            end = result.rfind("}") + 1
            text = result[start:end] if start >= 0 else result
        return json.loads(text)
    except Exception as e:
        logger.warning(f"JSON extract failed: {e}\nRaw: {result[:200]}")
        return {}


# ─── Prompt 模板（注入实时行情 + K线 + 策略上下文）─────────────

def _build_kline_context(klines: List[dict], n: int = 30) -> str:
    """
    将最近N条K线数据格式化为易读的文本表格，注入Prompt。
    这是让模型"知道"最新行情的关键——K线数据=最新市场共识。
    """
    if not klines:
        return "（无可用K线数据）"

    recent = klines[-n:]
    lines = ["日期        开盘    最高    最低    收盘    成交量      成交额"]
    for k in recent:
        date = k.get("date", "")
        o = k.get("open", 0)
        h = k.get("high", 0)
        l = k.get("low", 0)
        c = k.get("close", 0)
        v = k.get("volume", 0)
        e = k.get("amount", 0)
        change = k.get("change_pct", 0)
        sign = "+" if change >= 0 else ""
        lines.append(f"{date}  {o:>7.2f}  {h:>7.2f}  {l:>7.2f}  {c:>7.2f}  {v:>10,}  {e:>14,.0f}  {sign}{change:.2f}%")

    # 添加最近5日均线
    closes = [k["close"] for k in recent if k.get("close")]
    if len(closes) >= 5:
        ma5 = sum(closes[-5:]) / 5
        ma10 = sum(closes[-10:]) / 10 if len(closes) >= 10 else None
        ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else None
        lines.append(f"\n均线: MA5={ma5:.2f}" + (f" MA10={ma10:.2f}" if ma10 else "") + (f" MA20={ma20:.2f}" if ma20 else ""))

    return "\n".join(lines)


def _build_strategy_context() -> str:
    """
    加载用户的选股策略文件，作为 Prompt 上下文注入。
    让模型理解用户的交易逻辑，按需调整分析侧重点。
    """
    strategy_paths = [
        r"E:\.openclaw\stock_trading\strategy_selector.py",
        r"E:\.openclaw\knowledge\stock_selection_strategy.md",
        r"E:\.openclaw\knowledge\投资框架文档.md",
    ]
    fragments = []
    for path in strategy_paths:
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                content = f.read(2000)  # 只取前2000字避免过长
            if content.strip():
                fragments.append(f"=== {path} ===\n{content.strip()}")
        except Exception:
            pass

    if fragments:
        return "\n\n".join(fragments)
    return "（无可用策略文件，使用默认分析逻辑）"


# ─── 结构化调用：基本面报告 ────────────────────────────────────

LLM_ANALYST_SYSTEM = """你是一位专业的A股基本面分析师，服务于机构级量化交易系统。
你的知识截止到约2024年，因此**必须严格依赖用户提供的最新行情数据**进行分析，
不能依赖模型"记忆"中的任何价格或事件信息。

分析原则：
1. 一切判断基于用户提供的数据，没有数据则如实标注"数据缺失"
2. 估值要与当前股价对比，不使用历史知识
3. 结合K线趋势判断当前位置高低
4. 风险点要具体，联系当前行情描述"""


def generate_fundamental_report(
    code: str,
    name: str,
    price: float,
    change_pct: float,
    pe: float = 0,
    pb: float = 0,
    roe: float = 0,
    gross_margin: float = 0,
    rev_yoy: float = 0,
    prof_yoy: float = 0,
    debt_ratio: float = 0,
    klines: List[dict] = None,
) -> dict:
    """
    用 LLM 生成基本面分析报告。

    关键改进：Prompt 注入实时行情 + 最近K线，让模型知道当前是2026年。
    """
    kline_text = _build_kline_context(klines or [], n=30)
    strategy_text = _build_strategy_context()

    prompt = f"""请分析以下股票，基于提供的实时数据（而非模型记忆）给出判断。

## 股票信息
名称：{name}（代码：{code}）

## 当前行情（实时数据，2026年）
当前价：¥{price:.2f}
涨跌幅：{change_pct:+.2f}%
市盈率PE：{pe:.2f}（0或负值表示亏损或无数据）
市净率PB：{pb:.2f}
净资产收益率ROE：{roe:.2f}%
毛利率：{gross_margin:.2f}%
营收增速：{rev_yoy:+.2f}%
净利润增速：{prof_yoy:+.2f}%
资产负债率：{debt_ratio:.2f}%

## 最近30个交易日K线（数据来源：必盈API）
{kline_text}

## 用户选股策略参考
{strategy_text}

请输出以下JSON（严格只包含JSON，不要其他内容）：
{{
  "fundamental_score": 0-100整数,
  "grade": "强烈买入"或"买入"或"持有"或"卖出"或"强烈卖出",
  "pros": ["亮点1", "亮点2", "亮点3"],
  "cons": ["风险1", "风险2", "风险3"],
  "summary": "80字以内的综合摘要，基于当前实时数据"
}}"""

    result = generate(prompt, system=LLM_ANALYST_SYSTEM, config={"temperature": 0.2, "max_tokens": 1200})
    if not result:
        return {}

    parsed = _extract_json(result)
    required = ["fundamental_score", "grade", "pros", "cons"]
    if all(k in parsed for k in required):
        logger.info(f"[LM] Generated fundamental report for {code}: score={parsed['fundamental_score']}")
        return parsed
    logger.warning(f"[LM] Incomplete LLM output: {result[:200]}")
    return {}


# ─── 结构化调用：多空辩论论点 ────────────────────────────────

LLM_DEBATE_SYSTEM = """你是一位专业的A股多空辩论研究员。你需要从多方和空方两个角度给出最有说服力的论点。
**必须严格依赖用户提供的实时行情数据**，不能使用模型记忆中关于该股票的知识。"""


def generate_debate_arguments(
    code: str,
    name: str,
    price: float,
    fund_score: int,
    grade: str,
    tech_score: int,
    trend: str,
    sentiment: str,
    klines: List[dict] = None,
) -> dict:
    """
    用 LLM 生成多空辩论论点。
    注入K线数据和当前价格，让模型基于真实数据推理。
    """
    kline_text = _build_kline_context(klines or [], n=20)
    strategy_text = _build_strategy_context()

    prompt = f"""请对{name}（{code}）进行多空辩论，基于以下实时数据（2026年）进行推理。

## 当前行情
当前价：¥{price:.2f}
技术面评分：{tech_score}/100，趋势：{trend}
基本面评分：{fund_score}/100，评级：{grade}
市场情绪：{sentiment}

## 最近20个交易日K线
{kline_text}

## 用户选股策略参考
{strategy_text}

请输出JSON（严格只包含JSON）：
{{
  "bull_arguments": ["看多论点1（60字以内）", "看多论点2", "看多论点3"],
  "bear_arguments": ["看空论点1（60字以内）", "看空论点2", "看空论点3"],
  "target_price": 目标价（数字，如无法估算则填null）,
  "stop_loss": 止损价（数字，如无法估算则填null）,
  "reasoning": "裁判判定理由（40字以内，基于数据而非记忆）"
}}"""

    result = generate(prompt, system=LLM_DEBATE_SYSTEM, config={"temperature": 0.4, "max_tokens": 1200})
    if not result:
        return {}

    parsed = _extract_json(result)
    required = ["bull_arguments", "bear_arguments"]
    if all(k in parsed for k in required):
        logger.info(f"[LM] Generated debate arguments for {code}")
        return parsed
    logger.warning(f"[LM] Incomplete debate output: {result[:200]}")
    return {}


# ─── 通用分析调用（适合快速研判）─────────────────────────────

def generate_analysis(
    code: str,
    name: str,
    price: float,
    klines: List[dict],
    fundamentals: dict,
    sentiment: str,
    depth: str = "medium",
) -> str:
    """
    通用分析调用，适合 medium 深度。
    返回一段完整的文字分析（供直接展示给用户）。
    """
    kline_text = _build_kline_context(klines, n=30)
    strategy_text = _build_strategy_context()

    prompt = f"""作为A股分析师，请对{name}（{code}）进行综合分析。
**一切判断必须基于以下实时数据**，不要使用模型记忆中关于该股的信息。

## 实时行情（2026年）
当前价：¥{price:.2f}

## 财务数据
PE={fundamentals.get('pe', 'N/A')}  PB={fundamentals.get('pb', 'N/A')}  ROE={fundamentals.get('roe', 'N/A')}%
营收增速={fundamentals.get('revenue_yoy', 'N/A')}%  净利润增速={fundamentals.get('profit_yoy', 'N/A')}%
资产负债率={fundamentals.get('debt_ratio', 'N/A')}%

## 技术面（最近30日K线）
{kline_text}

## 市场情绪
{sentiment}

## 用户选股策略
{strategy_text}

请输出一段200-400字的投资分析，要求：
1. 结合K线判断当前位置（高/低/中部）
2. 结合基本面给出估值判断
3. 给出明确的投资建议（买入/持有/卖出）
4. 识别最大风险和最大机会"""

    return generate(prompt, system="你是一位专业、客观的A股分析师。", config={"temperature": 0.3, "max_tokens": 2000})


# ─── 健康检查 ──────────────────────────────────────────────────

def is_lm_available() -> bool:
    """检查 LM Studio 是否正在运行"""
    try:
        import httpx
        cfg = get_lm_config()
        with httpx.Client(timeout=5.0) as client:
            # 去掉 /v1 后缀，用 /models 端点检测
            base = cfg["base_url"].replace("/v1", "")
            r = client.get(f"{base}/models")
            return r.status_code == 200
    except Exception as e:
        logger.debug(f"LM Studio health check failed: {e}")
        return False

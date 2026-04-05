# bull_bear_debate.py — 多空辩论引擎
"""
Bull vs Bear Debate Engine.
多空研究员对分析师报告进行正反两面辩论，投资裁判综合判定。
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


# ─── Brief 压缩工具（来自 OpenHarness brief_tool.py）────────────────
def _brief(text: str, max_chars: int = 150) -> str:
    """将长论点压缩为关键句子，保留核心逻辑。"""
    if not text or len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."

logger = logging.getLogger("bull_bear_debate")


class JudgeDecision(Enum):
    BULL = "BULL"      # 看多
    BEAR = "BEAR"      # 看空
    NEUTRAL = "NEUTRAL"  # 中性/观望


@dataclass
class DebateRound:
    round_num: int
    bull_argument: str
    bull_confidence: int  # 0-100
    bear_argument: str
    bear_confidence: int  # 0-100


@dataclass
class DebateResult:
    code: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    debate_rounds: List[DebateRound] = field(default_factory=list)
    final_decision: str = "NEUTRAL"  # BULL / BEAR / NEUTRAL
    bull_score: float = 0
    bear_score: float = 0
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    reasoning: str = ""
    conviction: int = 50  # 决策置信度 0-100


def run_bull_bear_debate(
    report,  # AnalystReport
    max_rounds: int = 2,
    current_price: float = 0,
) -> DebateResult:
    """
    运行多空辩论。
    给定分析师报告，多空研究员各执己见，通过辩论达成裁判判定。

    Args:
        report: AnalystReport from china_analyst_team
        max_rounds: 辩论轮数
        current_price: 当前股价（用于计算目标价）
    """
    result = DebateResult(code=report.code)

    logger.info(f"[BullBear] {report.code} 开始多空辩论，共 {max_rounds} 轮")

    # ─── 多头论点生成（基于分析师报告）─────────────────────────────
    bull_arguments = _generate_bull_arguments(report)
    bear_arguments = _generate_bear_arguments(report)

    # ─── 辩论轮次模拟 ────────────────────────────────────────────
    for round_num in range(1, max_rounds + 1):
        bull_conf = _calculate_confidence(bull_arguments[round_num - 1], is_bull=True, report=report)
        bear_conf = _calculate_confidence(bear_arguments[round_num - 1], is_bull=False, report=report)

        round_result = DebateRound(
            round_num=round_num,
            bull_argument=_brief(bull_arguments[round_num - 1], max_chars=150),
            bull_confidence=bull_conf,
            bear_argument=_brief(bear_arguments[round_num - 1], max_chars=150),
            bear_confidence=bear_conf,
        )
        result.debate_rounds.append(round_result)

        # 更新累计分数
        result.bull_score += bull_conf
        result.bear_score += bear_conf

        logger.info(f"[BullBear] Round {round_num}: Bull={bull_conf}, Bear={bear_conf}")

    # ─── 裁判判定 ────────────────────────────────────────────────
    avg_bull = result.bull_score / max_rounds
    avg_bear = result.bear_score / max_rounds
    score_diff = avg_bull - avg_bear

    if score_diff > 15 and avg_bull > 60:
        result.final_decision = JudgeDecision.BULL.value
        result.reasoning = f"多头优势明显（差距{score_diff:.0f}分），{report.name}具备上涨逻辑"
        result.conviction = min(int(avg_bull), 90)
    elif score_diff < -15 and avg_bear > 60:
        result.final_decision = JudgeDecision.BEAR.value
        result.reasoning = f"空头占优（差距{abs(score_diff):.0f}分），{report.name}下行风险较大"
        result.conviction = min(int(avg_bear), 90)
    else:
        result.final_decision = JudgeDecision.NEUTRAL.value
        result.reasoning = f"多空分歧较大（差{abs(score_diff):.0f}分），建议观望等待更多信息"
        result.conviction = max(50 - int(abs(score_diff)), 20)

    # ─── 目标价与止损价 ─────────────────────────────────────────
    if current_price > 0:
        if result.final_decision == JudgeDecision.BULL.value:
            # 上涨空间 15-30%，止损 7%
            result.target_price = round(current_price * (1 + result.conviction / 200), 2)
            result.stop_loss = round(current_price * 0.93, 2)
        elif result.final_decision == JudgeDecision.BEAR.value:
            # 下跌空间 10-20%
            result.target_price = round(current_price * (1 - result.conviction / 300), 2)
            result.stop_loss = round(current_price * 1.07, 2)
        else:
            result.target_price = round(current_price * 1.05, 2)
            result.stop_loss = round(current_price * 0.95, 2)

    logger.info(
        f"[BullBear] {report.code} 裁判判定: {result.final_decision} "
        f"(信心{result.conviction}%) 目标:{result.target_price} 止损:{result.stop_loss}"
    )

    return result


# ─── 论点生成函数 ──────────────────────────────────────────────────

def _generate_bull_arguments(report) -> List[str]:
    """生成多头论点"""
    args = []
    confs = []

    # 论点1：估值+基本面
    if report.fundamental_score >= 65:
        args.append(
            f"{report.name}基本面优秀（评分{report.fundamental_score}），"
            f"PE={report.pe:.1f}，ROE={report.roe:.1f}%，净利润增长{report.profit_yoy:.1f}%。"
            f"机构评级一致看多，当前估值有安全边际。"
        )
    elif report.fundamental_score >= 50:
        args.append(
            f"{report.name}基本面尚可（评分{report.fundamental_score}），"
            f"行业地位稳定，估值处于合理区间，下跌空间有限。"
        )
    else:
        args.append(
            f"{report.name}尽管基本面评分偏低（{report.fundamental_score}），"
            f"但股价已大幅调整，利空已充分消化，技术面出现超卖信号。"
        )

    # 论点2：技术面
    if report.technical_trend == "多头":
        args.append(
            f"技术面多头排列（评分{report.technical_score}），"
            f"均线系统完整，MACD、RSI等技术指标显示上涨趋势完好，"
            f"当前价格获得{report.support_levels[0] if report.support_levels else '均线'}支撑。"
        )
    else:
        args.append(
            f"技术面{report.technical_trend}（评分{report.technical_score}），"
            f"但RSI处于{report.technical_indicators.get('RSI14', 50)}，"
            f"处于超卖区域，反弹概率大。"
        )

    # 论点3：消息面+情绪
    if report.news_sentiment in ("看多",):
        args.append(
            f"市场情绪向好（{report.news_count}条新闻），"
            f"近期有多项利好催化，包括业绩超预期、政策利好等。"
        )
    else:
        args.append(
            f"该股近期无重大利空，{report.name}所属板块轮动机会出现，"
            f"当前价格具备配置价值。"
        )

    return args[:3]


def _generate_bear_arguments(report) -> List[str]:
    """生成空头论点"""
    args = []

    # 论点1：估值压力
    if report.pe > 40:
        args.append(
            f"{report.name}估值偏高（PE={report.pe:.1f}），"
            f"远高于行业平均水平，股价已透支未来1-2年业绩，"
            f"一旦业绩不及预期将出现双杀。"
        )
    elif report.pe <= 0:
        args.append(
            f"{report.name}处于亏损状态（PE={report.pe:.1f}），"
            f"基本面不支持当前估值，需等待业绩拐点。"
        )
    else:
        args.append(
            f"{report.name}估值虽处于合理区间（PE={report.pe:.1f}），"
            f"但市场整体风险偏好下降，估值存在系统性压缩压力。"
        )

    # 论点2：技术面压力
    if report.technical_trend == "空头":
        args.append(
            f"技术面空头排列（评分{report.technical_score}），"
            f"均线系统空头排列，MACD死叉延续，"
            f"下跌趋势完好，下方支撑在{report.support_levels[0] if report.support_levels else '未知'}。"
        )
    else:
        args.append(
            f"技术面虽未破位，但RSI={report.technical_indicators.get('RSI14', 50)}，"
            f"处于高位钝化，上涨动能衰竭，调整概率大。"
        )

    # 论点3：市场与资金
    if report.change_pct < -5:
        args.append(
            f"该股近期跌幅已达{abs(report.change_pct):.1f}%，"
            f"主力资金大幅流出，当前处于下降通道，"
            f"追高风险极大。"
        )
    elif report.volume_ratio > 3:
        args.append(
            f"换手率异常放大（量比={report.volume_ratio:.1f}），"
            f"可能是主力对倒出货，短期风险较大。"
        )
    else:
        args.append(
            f"市场整体成交量低迷，增量资金不足，"
            f"缺乏趋势性上涨动力，应保持谨慎。"
        )

    return args[:3]


def _calculate_confidence(argument: str, is_bull: bool, report) -> int:
    """
    根据论点内容和分析师评分计算置信度。
    这是一个确定性算法，实际使用时可替换为LLM调用。
    """
    base_conf = 60

    # 基本面加分
    if is_bull and report.fundamental_score >= 70:
        base_conf += 15
    elif not is_bull and report.fundamental_score <= 35:
        base_conf += 15

    # 技术面加分
    if is_bull and report.technical_trend == "多头":
        base_conf += 15
    elif not is_bull and report.technical_trend == "空头":
        base_conf += 15

    # 新闻情绪加分
    if is_bull and report.news_sentiment == "看多":
        base_conf += 10
    elif not is_bull and report.news_sentiment == "看空":
        base_conf += 10

    # 价格位置加分
    if report.technical_indicators.get("BOLL_POSITION", 50) > 80 and not is_bull:
        base_conf += 10  # 接近上轨，压力加大
    if report.technical_indicators.get("BOLL_POSITION", 50) < 20 and is_bull:
        base_conf += 10  # 接近下轨，支撑强

    return max(20, min(95, base_conf))

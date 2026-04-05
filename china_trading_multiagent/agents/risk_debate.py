# risk_debate.py — 风险辩论引擎
"""
Risk Debate Engine.
风险管理团队中的三种立场（激进/保守/中立）对交易计划进行风险辩论。
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger("risk_debate")


class RiskVerdict(Enum):
    APPROVE = "APPROVE"      # 批准
    MODIFY = "MODIFY"        # 修改后批准
    REJECT = "REJECT"        # 拒绝
    HOLD = "HOLD"            # 观望


@dataclass
class RiskDebateResult:
    code: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # 三方评分
    aggressive_score: int = 50  # 激进派风险评分（0=无风险，100=极高风险）
    conservative_score: int = 50  # 保守派评分
    neutral_score: int = 50     # 中立派评分

    # 综合评分（加权平均）
    final_risk_score: int = 50

    # 风险项
    top_risks: List[str] = field(default_factory=list)

    # 仓位建议
    suggested_position_pct: float = 0  # 建议仓位 0-100

    # 最终判决
    verdict: str = "HOLD"

    # 风险描述
    risk_summary: str = ""


def run_risk_debate(
    code: str,
    current_price: float,
    target_price: Optional[float],
    stop_loss: Optional[float],
    debate_result,  # DebateResult from bull_bear_debate
    portfolio: Dict[str, Any],
    config=None,  # ChinaTradingConfig
) -> RiskDebateResult:
    """
    运行风险管理辩论。
    激进派、保守派、中立派分别评估同一交易计划，给出风险评分，
    最终综合形成风险判决。
    """
    if config is None:
        from skills.china_trading_multiagent.config.china_config import ChinaTradingConfig
        config = ChinaTradingConfig()

    result = RiskDebateResult(code=code)
    logger.info(f"[RiskDebate] {code} 开始风险辩论")

    # ─── 当前持仓检查 ────────────────────────────────────────────
    existing_position_pct = _get_position_pct(code, portfolio)
    total_position_pct = _get_total_position_pct(portfolio)
    price = current_price

    # ─── 激进派评估 ─────────────────────────────────────────────
    result.aggressive_score = _aggressive_risk_score(
        code=code,
        existing_position_pct=existing_position_pct,
        total_position_pct=total_position_pct,
        debate_result=debate_result,
        config=config,
    )

    # ─── 保守派评估 ─────────────────────────────────────────────
    result.conservative_score = _conservative_risk_score(
        code=code,
        price=price,
        target_price=target_price,
        stop_loss=stop_loss,
        existing_position_pct=existing_position_pct,
        debate_result=debate_result,
        config=config,
    )

    # ─── 中立派评估 ─────────────────────────────────────────────
    result.neutral_score = _neutral_risk_score(
        code=code,
        price=price,
        target_price=target_price,
        stop_loss=stop_loss,
        existing_position_pct=existing_position_pct,
        total_position_pct=total_position_pct,
        debate_result=debate_result,
        config=config,
    )

    # ─── 综合评分（激进30% + 保守50% + 中立20%）───────────────
    result.final_risk_score = int(
        result.aggressive_score * 0.3
        + result.conservative_score * 0.5
        + result.neutral_score * 0.2
    )

    # ─── 风险项识别 ─────────────────────────────────────────────
    result.top_risks = _identify_top_risks(
        code=code,
        price=price,
        existing_position_pct=existing_position_pct,
        total_position_pct=total_position_pct,
        debate_result=debate_result,
        config=config,
    )

    # ─── 仓位建议 ───────────────────────────────────────────────
    result.suggested_position_pct = _suggest_position(
        risk_score=result.final_risk_score,
        decision=debate_result.final_decision,
        conviction=debate_result.conviction,
        existing_position_pct=existing_position_pct,
        config=config,
    )

    # ─── 判决 ──────────────────────────────────────────────────
    result.verdict, result.risk_summary = _make_verdict(
        risk_score=result.final_risk_score,
        top_risks=result.top_risks,
        decision=debate_result.final_decision,
        config=config,
    )

    logger.info(
        f"[RiskDebate] {code} 风险评分: 激进={result.aggressive_score} "
        f"保守={result.conservative_score} 中立={result.neutral_score} "
        f"综合={result.final_risk_score} 判决={result.verdict} "
        f"建议仓位={result.suggested_position_pct}%"
    )

    return result


# ─── 三方评分函数 ────────────────────────────────────────────────

def _aggressive_risk_score(code, existing_position_pct, total_position_pct, debate_result, config) -> int:
    """激进派：关注机会，轻视风险"""
    score = 25  # 默认低风险

    # 已持仓加风险
    if existing_position_pct > 20:
        score += 15
    if existing_position_pct > config.max_single_position_pct:
        score += 30  # 超集中

    # 多空判断
    if debate_result.final_decision == "BEAR":
        score += 20
    elif debate_result.final_decision == "NEUTRAL":
        score += 10

    # 信心不足
    if debate_result.conviction < 40:
        score += 10

    # 总仓位已高
    if total_position_pct > 80:
        score += 15

    return min(100, score)


def _conservative_risk_score(code, price, target_price, stop_loss, existing_position_pct, debate_result, config) -> int:
    """保守派：严格风控，厌恶损失"""
    score = 30  # 默认中等风险

    # 无止损价
    if not stop_loss or stop_loss <= 0:
        score += 30

    # 止损太浅
    if stop_loss and price > 0:
        loss_pct = (price - stop_loss) / price * 100
        if loss_pct < 3:
            score += 15
        elif loss_pct > 15:
            score -= 10  # 止损宽松反而是好事

    # 无目标价
    if not target_price:
        score += 15

    # 多空分歧
    if debate_result.final_decision == "NEUTRAL":
        score += 20
    elif debate_result.final_decision == "BEAR":
        score += 25

    # 单票集中
    if existing_position_pct > config.max_single_position_pct:
        score += 25

    # T+1限制（买入当日无法止损）
    if existing_position_pct == 0:  # 新买入
        score += 10  # T+1流动性风险

    # 涨跌停风险（接近涨停/跌停）
    # 简化：暂不实现，实际应比对 config.limit_up_pct

    return min(100, max(0, score))


def _neutral_risk_score(code, price, target_price, stop_loss, existing_position_pct, total_position_pct, debate_result, config) -> int:
    """中立派：综合权衡"""
    score = 40  # 默认中等

    # 盈亏比
    if price > 0 and target_price and stop_loss:
        profit_pct = (target_price - price) / price * 100
        loss_pct = (price - stop_loss) / price * 100
        if loss_pct > 0:
            ratio = profit_pct / loss_pct
            if ratio >= 3:
                score -= 20  # 盈亏比优秀
            elif ratio >= 2:
                score -= 10
            elif ratio < 1:
                score += 20  # 盈亏比差

    # 置信度
    if debate_result.conviction >= 75:
        score -= 15
    elif debate_result.conviction <= 30:
        score += 20

    # 持仓状态
    if existing_position_pct > 0:
        score -= 5  # 已有持仓，谨慎加仓

    # 总仓位
    if total_position_pct > config.max_total_position_pct:
        score += 30

    return min(100, max(0, score))


def _identify_top_risks(code, price, existing_position_pct, total_position_pct, debate_result, config) -> List[str]:
    """识别TOP3风险"""
    risks = []

    if existing_position_pct > config.max_single_position_pct:
        risks.append(f"单票持仓超限（当前{existing_position_pct:.0f}% > 限额{config.max_single_position_pct}%）")

    if total_position_pct > config.max_total_position_pct:
        risks.append(f"总仓位超限（当前{total_position_pct:.0f}%）")

    if debate_result.final_decision == "NEUTRAL":
        risks.append("多空信号分歧，建议观望")

    if debate_result.conviction < 40:
        risks.append(f"决策置信度偏低（{debate_result.conviction}%）")

    if price > 0 and debate_result.stop_loss:
        loss_pct = (price - debate_result.stop_loss) / price * 100
        if loss_pct > 10:
            risks.append(f"止损幅度较大（{loss_pct:.1f}%）")
        elif loss_pct < 3:
            risks.append(f"止损过于紧密（{loss_pct:.1f}%），容易被震出")

    if len(risks) < 3:
        risks.append(f"T+1制度：当日买入无法当日止损")
        risks.append(f"{config.limit_up_pct}%涨跌停限制：极端行情可能无法成交")

    return risks[:3]


def _suggest_position(risk_score, decision, conviction, existing_position_pct, config) -> float:
    """根据风险评分建议仓位"""
    if risk_score >= 80:
        return 0  # 不买
    elif risk_score >= 60:
        return max(0, min(existing_position_pct, 5))  # 最多5%
    elif risk_score >= 40:
        base = 10
    else:
        base = 20

    # 信心加成
    if conviction >= 80 and decision == "BULL":
        base = min(base + 10, 30)

    # 已有持仓上限
    return min(base, config.max_single_position_pct - existing_position_pct)


def _make_verdict(risk_score, top_risks, decision, config) -> tuple:
    """生成最终判决"""
    if risk_score >= 80:
        return RiskVerdict.REJECT.value, f"风险评分{risk_score}，过高，否决。TOP风险：{'/'.join(top_risks[:2])}"
    elif risk_score >= 60:
        if risk_score >= 70:
            return RiskVerdict.REJECT.value, f"风险评分{risk_score}，偏高，拒绝加仓。"
        return RiskVerdict.MODIFY.value, f"风险评分{risk_score}，可小仓参与，建议降低仓位。"
    elif risk_score >= 40:
        return RiskVerdict.MODIFY.value, f"风险评分中等，建议适度参与（10-15%仓位）。"
    else:
        if decision == "BULL" and len(top_risks) <= 1:
            return RiskVerdict.APPROVE.value, f"风险评分{risk_score}，低风险，可按计划执行。"
        return RiskVerdict.MODIFY.value, f"风险评分{risk_score}，机会大于风险，建议参与但控制仓位。"


# ─── 工具函数 ────────────────────────────────────────────────────

def _get_position_pct(code: str, portfolio: Dict[str, Any]) -> float:
    """获取某只股票的持仓比例"""
    positions = portfolio.get("positions", {})
    code = str(code)
    for pos in positions.values():
        if str(pos.get("code", "")) == code:
            return float(pos.get("position_pct", 0))
    return 0.0


def _get_total_position_pct(portfolio: Dict[str, Any]) -> float:
    """获取总持仓比例"""
    return float(portfolio.get("total_position_pct", 0))

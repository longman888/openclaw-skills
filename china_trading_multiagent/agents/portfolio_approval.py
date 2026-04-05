# portfolio_approval.py — 组合经理审批层
"""
Portfolio Manager Approval.
组合经理综合分析师报告、多空辩论结果、风险评估，
做出最终的"执行/修改/拒绝/观望"决策。
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger("portfolio_approval")


class FinalDecision(Enum):
    APPROVE = "APPROVE"    # 批准，按计划执行
    MODIFY = "MODIFY"      # 修改后执行（调整仓位或时间）
    REJECT = "REJECT"      # 拒绝，不执行
    HOLD = "HOLD"          # 观望，等待更多信息


@dataclass
class ApprovalResult:
    code: str
    name: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # 最终决策
    decision: str = "HOLD"
    decision_reason: str = ""

    # 执行参数（如果批准/修改）
    action: str = ""  # BUY / SELL / HOLD
    quantity: int = 0  # 数量（手，100股=1手）
    price: Optional[float] = None  # 指定价格（可选）
    position_pct: float = 0  # 持仓比例%
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    # 决策依据
    fundamental_score: int = 0
    technical_score: int = 0
    debate_decision: str = ""
    debate_conviction: int = 0
    risk_score: int = 0
    risk_verdict: str = ""

    # 综合评分
    composite_score: float = 50  # 综合评分 0-100

    # 备注
    warnings: List[str] = field(default_factory=list)


def run_portfolio_approval(
    code: str,
    name: str,
    analyst_report,   # AnalystReport
    debate_result,    # DebateResult
    risk_result,     # RiskDebateResult
    portfolio: Dict[str, Any],
    current_price: float,
    config=None,
) -> ApprovalResult:
    """
    组合经理审批流程。
    综合三方输入，做出最终决策。

    决策矩阵：
    - 风险评分 ≥ 75 → REJECT（任何情况下）
    - 风险评分 60-75 → MODIFY（降低仓位）
    - 风险评分 < 60 + 多头 + 置信度 ≥ 60 → APPROVE
    - 多空分歧 → HOLD
    """
    if config is None:
        from skills.china_trading_multiagent.config.china_config import ChinaTradingConfig
        config = ChinaTradingConfig()

    result = ApprovalResult(code=code, name=name)

    logger.info(f"[PortfolioManager] {code} {name} 开始审批")

    # ─── 收集各方输入 ────────────────────────────────────────────
    result.fundamental_score = analyst_report.fundamental_score
    result.technical_score = analyst_report.technical_score
    result.debate_decision = debate_result.final_decision
    result.debate_conviction = debate_result.conviction
    result.risk_score = risk_result.final_risk_score
    result.risk_verdict = risk_result.verdict

    # ─── 综合评分 ───────────────────────────────────────────────
    # 加权：基本面30% + 技术面20% + 辩论30% + 风险20%（风险越高综合分越低）
    risk_factor = (100 - result.risk_score) / 100
    result.composite_score = round(
        result.fundamental_score * 0.30
        + result.technical_score * 0.20
        + (result.debate_conviction if debate_result.final_decision == "BULL" else (50 - result.debate_conviction * 0.5)) * 0.30
        + result.risk_score * risk_factor * 0.20,
        1
    )

    # ─── 检查已有持仓 ───────────────────────────────────────────
    existing_pct = _get_existing_position(code, portfolio)
    result.warnings = []

    if existing_pct > 0:
        result.warnings.append(f"该股票已有持仓：{existing_pct:.1f}%")

    # ─── 决策流程 ───────────────────────────────────────────────

    # 规则1：风险评分过高 → 拒绝
    if result.risk_score >= 75:
        result.decision = FinalDecision.REJECT.value
        result.decision_reason = (
            f"风险评分{result.risk_score}（≥75），超过容忍上限，"
            f"风险管理团队建议：{risk_result.risk_summary}。否决。"
        )
        _log_decision(result, "REJECT", "风险评分过高")
        return result

    # 规则2：空头信号 → 优先考虑卖出
    if debate_result.final_decision == "BEAR" and existing_pct > 0:
        result.decision = FinalDecision.MODIFY.value
        result.action = "SELL"
        result.quantity = _calculate_sell_quantity(existing_pct, portfolio)
        result.decision_reason = (
            f"多空辩论结果为空头（置信度{result.debate_conviction}%），"
            f"建议减持/清仓。风险评分{result.risk_score}可控。"
        )
        _log_decision(result, "MODIFY", "空头信号，清仓")
        return result

    # 规则3：多空分歧 → 观望
    if debate_result.final_decision == "NEUTRAL":
        result.decision = FinalDecision.HOLD.value
        result.decision_reason = (
            f"多空辩论结果为中性（置信度仅{result.debate_conviction}%），"
            f"分析师基本评分{result.fundamental_score}，技术评分{result.technical_score}，"
            f"建议等待更明确信号。"
        )
        _log_decision(result, "HOLD", "多空分歧")
        return result

    # 规则4：多头 + 低风险 → 批准买入
    if (
        debate_result.final_decision == "BULL"
        and result.risk_score < 50
        and result.debate_conviction >= 65
    ):
        position_pct = risk_result.suggested_position_pct
        # 新建仓最大20%，加仓最大到30%
        max_new = min(20, config.max_single_position_pct - existing_pct)
        position_pct = min(position_pct, max_new)

        if position_pct <= 0:
            result.decision = FinalDecision.REJECT.value
            result.decision_reason = f"建议仓位0%，已达持仓上限，拒绝。"
            _log_decision(result, "REJECT", "仓位超限")
            return result

        result.decision = FinalDecision.APPROVE.value
        result.action = "BUY"
        result.position_pct = position_pct
        result.quantity = _calculate_buy_quantity(position_pct, current_price, portfolio)
        result.stop_loss = debate_result.stop_loss
        result.take_profit = debate_result.target_price
        result.decision_reason = (
            f"多头信号（置信度{result.debate_conviction}%）+ 低风险（{result.risk_score}）+ "
            f"综合评分{result.composite_score}。批准{position_pct}%仓位，目标价{result.take_profit}，"
            f"止损{result.stop_loss}。"
        )
        _log_decision(result, "APPROVE", f"多头信号，{position_pct}%仓位")
        return result

    # 规则5：多头但风险偏高 → 修改（降仓）
    if debate_result.final_decision == "BULL" and result.risk_score >= 50:
        position_pct = min(risk_result.suggested_position_pct, 10)
        max_new = min(10, config.max_single_position_pct - existing_pct)
        position_pct = min(position_pct, max_new)

        if position_pct <= 0:
            result.decision = FinalDecision.HOLD.value
            result.decision_reason = "多头信号但风险偏高，且已达持仓上限，观望。"
            _log_decision(result, "HOLD", "多头但仓位满")
            return result

        result.decision = FinalDecision.MODIFY.value
        result.action = "BUY"
        result.position_pct = position_pct
        result.quantity = _calculate_buy_quantity(position_pct, current_price, portfolio)
        result.stop_loss = debate_result.stop_loss
        result.take_profit = debate_result.target_price
        result.decision_reason = (
            f"多头信号（置信度{result.debate_conviction}%），但风险评分偏高（{result.risk_score}），"
            f"建议降低仓位至{position_pct}%，谨慎参与。"
        )
        _log_decision(result, "MODIFY", f"降仓至{position_pct}%")
        return result

    # 兜底：观望
    result.decision = FinalDecision.HOLD.value
    result.decision_reason = f"信号不明确，综合评分{result.composite_score}，等待更多信息。"
    _log_decision(result, "HOLD", "信号不明确")
    return result


# ─── 工具函数 ───────────────────────────────────────────────────

def _get_existing_position(code: str, portfolio: Dict[str, Any]) -> float:
    """获取已有持仓"""
    positions = portfolio.get("positions", {})
    code = str(code)
    for pos in positions.values():
        if str(pos.get("code", "")) == code:
            return float(pos.get("position_pct", 0))
    return 0.0


def _calculate_buy_quantity(position_pct: float, price: float, portfolio: Dict[str, Any]) -> int:
    """根据持仓比例计算买入数量（手）"""
    total_value = float(portfolio.get("total_value", 1000000))  # 默认100万总市值
    target_value = total_value * position_pct / 100
    shares = int(target_value / price / 100) * 100  # 取整到100股
    return max(100, shares)


def _calculate_sell_quantity(existing_pct: float, portfolio: Dict[str, Any]) -> int:
    """根据持仓比例计算卖出数量（手）"""
    total_value = float(portfolio.get("total_value", 1000000))
    sell_value = total_value * existing_pct / 100
    return 0  # 数量由外部根据持仓数据计算


def _log_decision(result: ApprovalResult, decision: str, reason: str):
    logger.info(
        f"[PortfolioManager] {result.code} 决策: {decision} | "
        f"综合={result.composite_score} | 风险={result.risk_score} | "
        f"置信={result.debate_conviction} | {reason}"
    )


def format_decision_report(result: ApprovalResult) -> str:
    """格式化输出决策报告（供 Agent 回复用户使用）"""
    lines = [
        f"\n{'='*50}",
        f"【{result.name} ({result.code}) 交易决策报告】",
        f"{'='*50}",
        f"决策: {result.decision}",
        f"原因: {result.decision_reason}",
        "",
        f"📊 综合评分: {result.composite_score}/100",
        f"   ├─ 基本面: {result.fundamental_score}/100",
        f"   ├─ 技术面: {result.technical_score}/100",
        f"   ├─ 多空辩论: {result.debate_decision} (置信{result.debate_conviction}%)",
        f"   └─ 风险评分: {result.risk_score}/100 ({result.risk_verdict})",
        "",
    ]

    if result.decision in ("APPROVE", "MODIFY"):
        lines += [
            f"📋 执行计划:",
            f"   动作: {result.action}",
            f"   仓位: {result.position_pct}%",
            f"   数量: {result.quantity}股 ({result.quantity // 100}手)",
        ]
        if result.stop_loss:
            lines.append(f"   止损价: ¥{result.stop_loss:.2f}")
        if result.take_profit:
            lines.append(f"   目标价: ¥{result.take_profit:.2f}")

    if result.warnings:
        lines += ["", f"⚠️ 风险提示:"]
        for w in result.warnings:
            lines.append(f"   - {w}")

    lines.append(f"\n{'='*50}")
    return "\n".join(lines)

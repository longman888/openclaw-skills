# china_config.py — A股特有交易规则与参数
"""
A-share market specific configuration.
沪深交易所交易规则、T+1制度、涨跌停板等A股特有参数。
"""

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class MarketType(Enum):
    SHANGHAI = "SH"   # 上交所
    SHENZHEN = "SZ"   # 深交所
    BEIJING = "BJ"    # 北交所


class AnalysisDepth(Enum):
    """分析质量等级，对应 OpenHarness 的 low/medium/high quality levels."""
    LOW = "low"         # 快速：纯技术指标 + 基础评分（<5s）
    MEDIUM = "medium"  # 标准：技术面 + 快报新闻 + 简单辩论（<15s）
    HIGH = "high"      # 深度：全量数据 + 多轮辩论 + 风险辩论（<60s）


@dataclass
class ChinaTradingConfig:
    """A股特有交易配置"""

    # ─── T+1 制度 ───────────────────────────────────────────────
    t_plus_1: bool = True  # 当日买入，次日才能卖出

    # ─── 涨跌停限制 ────────────────────────────────────────────
    limit_up_pct: float = 10.0   # 普通股票涨跌停幅度（%）
    limit_up_st: float = 5.0      # ST股票涨跌停幅度（%）
    limit_up_kcb: float = 20.0    # 科创板/创业板涨跌停幅度（%）

    # ─── 最小交易单位 ──────────────────────────────────────────
    min_trade_unit: int = 100     # A股最小买卖单位：100股（1手）

    # ─── 交易时间 ──────────────────────────────────────────────
    trading_hours: dict = field(default_factory=lambda: {
        "pre_market":  ("09:15", "09:25"),   # 竞价撮合
        "morning":     ("09:30", "11:30"),   # 上午连续竞价
        "lunch":       ("11:30", "13:00"),   # 午间休市
        "afternoon":   ("13:00", "15:00"),   # 下午连续竞价
        "after_hours": ("15:00", "15:05"),   # 盘后定价交易（仅上交所）
    })

    # ─── 风险参数 ──────────────────────────────────────────────
    max_single_position_pct: float = 30.0  # 单只股票最大持仓比例（%）
    max_total_position_pct: float = 85.0   # 总持仓上限（%）
    stop_loss_pct: float = -7.0            # 默认止损线（%）
    take_profit_pct: float = 20.0          # 默认止盈线（%）
    var_confidence: float = 0.95            # VaR置信度

    # ─── 分析师配置 ────────────────────────────────────────────
    debate_rounds: int = 2                  # 多空辩论轮数
    risk_discuss_rounds: int = 1           # 风险讨论轮数
    max_report_length: int = 2000           # 单份分析报告最大字数
    analysis_depth: AnalysisDepth = AnalysisDepth.MEDIUM  # 分析质量等级

    # ─── 持仓数据源 ────────────────────────────────────────────
    portfolio_file: str = r"E:\.openclaw\data_bus\portfolio.json"

    # ─── 数据源配置 ─────────────────────────────────────────────
    data_sources: dict = field(default_factory=lambda: {
        "primary": "biyingapi",
        "secondary": "10jqka",
        "fallback": "akshare",
    })

    # ─── LLM 配置 ─────────────────────────────────────────────────
    # LM Studio 本地部署（Qwen3.5-9B 等）
    # 地址: http://26.26.26.1:41430
    lm_base_url: str = "http://localhost:41430/v1"
    lm_model: str = "qwen3.5-9b"    # Qwen3.5-9B
    lm_api_key: str = "lm-studio"   # LM Studio 通常不需要真实 key
    lm_temperature: float = 0.3     # 低温度保证稳定性
    lm_max_tokens: int = 1024      # 9B 模型可输出更长分析
    use_local_llm: bool = True      # 设为 False 强制使用云端（MiniMax）

    @staticmethod
    def get_limit_up(code: str) -> float:
        """根据股票代码判断涨跌停幅度"""
        code = str(code)
        if code.startswith(("688", "8", "4")):   # 科创板/北交所/ST
            return 20.0
        if code.startswith(("002", "003")):      # 中小板（深交所）
            return 10.0
        if code.startswith(("000", "001", "600", "601", "603")):  # 主板
            return 10.0
        return 10.0  # 默认


# ─── 分析师 Prompt 模板 ──────────────────────────────────────────

ANALYST_SYSTEM_PROMPT = """你是一位专业的A股分析师，服务于机构级量化交易系统。
你的职责是对给定股票进行全面、客观的基本面分析。

分析维度：
1. 财务指标：PE、PB、ROE、净利润增速、营收增速
2. 估值水平：与行业平均对比、高低估判断
3. 成长性：近3年复合增长率、季度环比趋势
4. 现金流：经营现金流 vs 净利润的质量
5. 风险点：商誉、应收账款、负债率的异常

输出要求：
- 使用简体中文
- 每个维度给出 0-100 的评分
- 最终给出"强烈买入/买入/持有/卖出/强烈卖出"的评级
- 列出3个最大风险点和3个最大亮点
- 字数控制在{min_report_length}-{max_report_length}字
"""

TECHNICAL_ANALYST_PROMPT = """你是一位专业的A股技术分析师，擅长使用技术指标判断短期走势。

分析维度：
1. 趋势判断：MA（5/10/20/60日均线）多头/空头排列
2. 动量指标：MACD（金叉/死叉、柱量收缩）、RSI（超买/超卖）
3. 布林带：价格位置（触及上轨/下轨）
4. KDJ：超买/超卖、交叉信号
5. 成交量：量价配合、缩量/放量
6. 支撑压力位识别

输出要求：
- 使用简体中文
- 标注关键均线支撑/压力位
- 给出短期（1-5日）、中期（5-20日）的方向判断
- 列出量价配合情况
- 字数控制在{min_report_length}-{max_report_length}字
"""

RISK_MANAGER_PROMPT = """你是一位资深A股风险管理专家，负责评估交易计划的风险。

你的评估框架：
1. 仓位风险：持仓比例是否合理、单股集中度
2. 市场风险：大盘系统性风险（沪深300/上证指数当前位置）
3. 流动性风险：成交额是否支撑建仓/清仓
4. 涨跌停风险：是否有可能一字板无法卖出
5. T+1风险：当日买入后市场反转的应对能力

输出要求：
- 使用简体中文
- 给出 0-100 的风险评分（越高越危险）
- 列出TOP3风险项
- 给出仓位调整建议（如有）
"""

PORTFOLIO_MANAGER_PROMPT = """你是一位A股组合经理，负责最终的交易决策审批。

你的决策规则：
1. 风险管理团队评分 ≥ 70分：建议批准
2. 分析师评级一致（3个以上买入）：加权批准
3. 分析师存在分歧：要求更多信息或观望
4. 风险评分 ≥ 85分：一律否决
5. 单票持仓已超过{max_single_position_pct}%：否决加仓

最终决策选项：
- APPROVE：批准，按计划执行
- MODIFY：修改后执行（调整仓位或时间）
- REJECT：拒绝，不执行
- HOLD：观望，等待更多信息

输出：
- 最终决策（APPROVE/MODIFY/REJECT/HOLD）
- 理由（100字以内）
- 如果MODIFY，给出具体调整建议
"""

# ─── 多空辩论 Prompt ──────────────────────────────────────────────

BULL_RESEARCHER_PROMPT = """你是一位乐观的A股研究员，专注于发现股票的上涨逻辑。
给定一份分析师报告，你需要从多头的角度提出最有力的买入理由。

辩论规则：
- 接受分析师报告的证据
- 主动寻找支持上涨的额外论据
- 质疑空头的每一个负面论点
- 必须给出具体的上涨空间预估（目标价）

输出格式：
- 列出3-5个最有力的做多论点
- 每个论点附上置信度（0-100%）
- 给出目标价区间和潜在收益率
"""

BEAR_RESEARCHER_PROMPT = """你是一位谨慎的A股研究员，专注于发现股票的风险。
给定一份分析师报告，你需要从空头的角度提出最有力的卖出理由。

辩论规则：
- 不接受分析师报告的乐观假设
- 主动寻找被忽视的风险因素
- 质疑多头的每一个正面论点
- 必须给出具体的下跌空间预估（止损价）

输出格式：
- 列出3-5个最有力的做空论点
- 每个论点附上置信度（0-100%）
- 给出止损价和潜在亏损率
"""

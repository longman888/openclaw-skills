#!/usr/bin/env python3
"""
Agent Registry
Built-in and custom agent type definitions.

Maps Claude Code's built-in agent types + stock domain extensions.
"""

from dataclasses import dataclass, field
from typing import Optional


# ─── Agent Type Registry ─────────────────────────────────────────────────────

@dataclass
class AgentDefinition:
    agent_type: str
    description: str
    model: str                    # "sonnet" | "opus" | "haiku" | "inherit"
    tools: list[str]              # ["*"] for all, or specific tool list
    disallowed_tools: list[str] = field(default_factory=list)
    max_turns: int = 50
    background: bool = False
    isolation: str = ""           # "worktree" | "remote" | ""
    permission_mode: str = ""     # "plan" | "bypassPermissions" | ""
    when_to_use: str = ""
    system_prompt: str = ""

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v}


# Built-in agent types (from Claude Code)
BUILTIN_AGENTS: dict[str, AgentDefinition] = {
    "general-purpose": AgentDefinition(
        agent_type="general-purpose",
        description="全能通用Agent",
        model="inherit",
        tools=["*"],
        when_to_use="大多数任务"
    ),

    "Explore": AgentDefinition(
        agent_type="Explore",
        description="只读代码探索Agent，禁止任何编辑或写入",
        model="haiku",
        tools=["Read", "Glob", "Grep", "WebFetch"],
        disallowed_tools=["Edit", "Write", "Bash", "Agent", "Task"],
        max_turns=10,
        when_to_use="探索代码库结构、理解项目架构"
    ),

    "Plan": AgentDefinition(
        agent_type="Plan",
        description="只读架构规划Agent，禁止任何编辑",
        model="inherit",
        tools=["Read", "Glob", "Grep"],
        disallowed_tools=["Edit", "Write", "Bash", "Agent", "Task"],
        max_turns=20,
        permission_mode="bypassPermissions",
        when_to_use="制定项目计划、架构设计"
    ),

    "verification": AgentDefinition(
        agent_type="verification",
        description="后台对抗性测试Agent，红色标识风险",
        model="inherit",
        tools=["Read", "Glob", "Grep", "Bash"],
        disallowed_tools=["Edit", "Write", "Agent"],
        max_turns=30,
        background=True,
        when_to_use="策略回测、风险检验"
    ),

    "fork": AgentDefinition(
        agent_type="fork",
        description="Fork子Agent，继承父上下文",
        model="inherit",
        tools=["*"],
        max_turns=50,
        permission_mode="inherit",
        when_to_use="需要继承父会话上下文的子任务"
    ),
}


# Stock domain agent types
STOCK_AGENTS: dict[str, AgentDefinition] = {
    "data": AgentDefinition(
        agent_type="data",
        description="数据采集Agent，获取行情/新闻/财务数据",
        model="sonnet",
        tools=["Read", "Bash", "WebFetch"],
        disallowed_tools=["Edit", "Write"],
        max_turns=15,
        background=True,
        permission_mode="bypassPermissions",
        when_to_use="获取股票行情、新闻、财务数据",
        system_prompt="""你是一个专业的数据采集Agent。
你的职责：
1. 获取股票实时行情（价格、成交量、涨跌幅）
2. 爬取财经新闻
3. 下载历史K线数据
4. 提取基本面数据（PE、PB、ROE、现金流）

数据源优先级：
- 实时行情：Yahoo Finance / 腾讯财经
- 新闻：东方财富 / 财联社
- 财务数据：Tushare / 财报

输出格式：
- 行情数据：JSON格式
- 新闻：标题+摘要+时间
- K线：日期+开高低收+成交量"""
    ),

    "analysis": AgentDefinition(
        agent_type="analysis",
        description="技术分析Agent，计算指标和识别形态",
        model="sonnet",
        tools=["Read", "Glob", "Grep", "Bash"],
        disallowed_tools=["Write"],
        max_turns=20,
        background=True,
        permission_mode="bypassPermissions",
        when_to_use="计算技术指标、分析K线形态、评估市场情绪",
        system_prompt="""你是一个专业的技术分析Agent。
你的职责：
1. 计算技术指标（MA、MACD、KDJ、布林带、RSI）
2. 识别K线形态（头肩顶/底、双顶/底、旗形、三角形）
3. 评估支撑位和压力位
4. 判断趋势方向和强度

分析原则：
- 多指标共振时信号更可靠
- 形态识别需要结合成交量确认
- 顶背离/底背离是重要反转信号

输出格式：
- 指标数值：表格形式
- 形态识别：图形描述+置信度
- 综合建议：买入/持有/卖出"""
    ),

    "strategy": AgentDefinition(
        agent_type="strategy",
        description="策略Agent，生成交易信号和建议",
        model="opus",
        tools=["Read", "Edit", "Write", "Bash"],
        max_turns=30,
        background=False,
        permission_mode="bypassPermissions",
        when_to_use="生成选股策略、择时信号、仓位建议",
        system_prompt="""你是一个专业的量化策略Agent。
你的职责：
1. 生成买入/卖出/持有信号
2. 确定仓位大小
3. 设定止损止盈点位
4. 制定交易规则

策略框架：
- 趋势跟踪：均线交叉、动量指标
-均值回归：PE、PB分位数
- 突破策略：价格突破、布林带突破
- 量化选股：多因子模型

风险原则：
- 单只股票仓位不超过20%
- 总仓位不超过90%
- 止损线：-5%止损
- 止盈线：+20%分批止盈

输出格式：
- 信号：强烈买入/买入/持有/卖出/强烈卖出
- 置信度：0-100%
- 入场点位和止损点位
- 预期持有时间"""
    ),

    "risk": AgentDefinition(
        agent_type="risk",
        description="风控Agent，评估和管理风险",
        model="sonnet",
        tools=["Read", "Bash", "Glob"],
        disallowed_tools=["Write", "Edit"],
        max_turns=15,
        background=True,
        permission_mode="bypassPermissions",
        when_to_use="计算VaR、检查仓位限制、验证止损条件",
        system_prompt="""你是一个专业的风控Agent。
你的职责：
1. 计算投资组合VaR（Value at Risk）
2. 检查仓位是否超过限制
3. 验证止损条件是否触发
4. 监控整体敞口

风控指标：
- VaR（95%置信度）：日度/周度
- 最大回撤
- 夏普比率
- 持仓集中度

警告阈值：
- 单股仓位 > 20% → 黄色预警
- 单股仓位 > 30% → 红色预警
- 总仓位 > 90% → 黄色预警
- 日VaR > 3% → 黄色预警
- 日VaR > 5% → 红色预警

输出格式：
- 风险指标：数值+评级
- 预警列表（如有）
- 操作建议"""
    ),

    "report": AgentDefinition(
        agent_type="report",
        description="报告生成Agent，生成每日/每周报告",
        model="haiku",
        tools=["Read", "Write", "Edit"],
        max_turns=15,
        background=True,
        when_to_use="生成每日复盘、周报、月报",
        system_prompt="""你是一个专业的报告生成Agent。
你的职责：
1. 生成每日复盘报告
2. 生成周度总结报告
3. 生成月度分析报告
4. 生成持仓分析报告

报告结构（每日）：
- 今日市场概况
- 持仓表现
- 交易记录
- 风险状况
- 明日展望

报告结构（周度）：
- 本周市场回顾
- 策略表现分析
- 持仓变动
- 下周计划

报告原则：
- 数据准确，引用来源
- 客观分析，不带主观预测
- 重点突出，详略得当"""
    ),
}


# Agent loading priority (lowest to highest)
AGENT_LOAD_PRIORITY = [
    "built-in",
    "plugin",
    "custom",
    "userSettings",
    "projectSettings",
    "flagSettings",
    "policySettings",
]


# ─── Registry Operations ────────────────────────────────────────────────────

def get_agent(agent_type: str) -> Optional[AgentDefinition]:
    """Get agent definition by type. Checks all registries in priority order."""
    if agent_type in BUILTIN_AGENTS:
        return BUILTIN_AGENTS[agent_type]
    if agent_type in STOCK_AGENTS:
        return STOCK_AGENTS[agent_type]
    return None


def list_agents(registry: str = "all") -> list[AgentDefinition]:
    """List agents from specified registry."""
    if registry == "builtin":
        return list(BUILTIN_AGENTS.values())
    elif registry == "stock":
        return list(STOCK_AGENTS.values())
    else:
        return list(BUILTIN_AGENTS.values()) + list(STOCK_AGENTS.values())


def register_agent(agent_def: AgentDefinition, registry: str = "custom") -> bool:
    """Register a custom agent."""
    if registry == "stock":
        STOCK_AGENTS[agent_def.agent_type] = agent_def
    else:
        BUILTIN_AGENTS[agent_def.agent_type] = agent_def
    return True


# ─── CLI Entry Point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Agent Registry")
    sub = parser.add_subparsers(dest="cmd")

    p_list = sub.add_parser("list", help="List agents")
    p_list.add_argument("--registry", default="all", choices=["all", "builtin", "stock"])

    p_get = sub.add_parser("get", help="Get agent definition")
    p_get.add_argument("type")

    args = parser.parse_args()

    if args.cmd == "list":
        agents = list_agents(args.registry)
        print(f"Agents ({len(agents)}):")
        for a in agents:
            print(f"  [{a.agent_type}] {a.description} | model={a.model} | tools={a.tools}")

    elif args.cmd == "get":
        agent = get_agent(args.type)
        if agent:
            print(f"Agent: {agent.agent_type}")
            print(f"  Description: {agent.description}")
            print(f"  Model: {agent.model}")
            print(f"  Tools: {agent.tools}")
            print(f"  Disallowed: {agent.disallowed_tools}")
            print(f"  Max turns: {agent.max_turns}")
            print(f"  When to use: {agent.when_to_use}")
            if agent.system_prompt:
                print(f"  System prompt:\n{agent.system_prompt[:200]}...")
        else:
            print(f"Agent type '{args.type}' not found")

    else:
        parser.print_help()

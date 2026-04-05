# SKILL.md — China A-Share Trading Multi-Agent Framework

> 参考 TauricResearch/TradingAgents (HKUDS, 4.2万⭐) 的多 Agent 辩论架构，
> 针对 A 股市场（沪深交易所）重新构建的量化交易决策系统。

---

## 概述

这是一个**完全自主运行的 A 股多 Agent 交易决策框架**，包含：

1. **分析师团队** — 并行基本面 + 技术面 + 情绪分析
2. **多空辩论引擎** — Bull vs Bear 辩论，裁判综合判定
3. **风险辩论** — 激进 / 保守 / 中立三方风险评估
4. **组合经理审批** — 最终决策（APPROVE / MODIFY / REJECT / HOLD）

核心流程模拟真实金融机构：**研究部 → 交易员 → 风险管理 → 投资委员会**

---

## 架构图

```
用户查询 (股票代码)
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│              ① 分析师团队 (并行)                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ 基本面   │ │ 技术面   │ │ 情绪/新闻 │ │ 实时行情 │  │
│  │ 分析师   │ │ 分析师   │ │ 分析师   │ │ 数据   │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘  │
│       │            │            │            │          │
│       └────────────┴────────────┴────────────┘          │
│                      AnalystReport                      │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│              ② 多空辩论 (BullBearDebate)                 │
│                                                          │
│  Bull研究员 ─┐                                          │
│              ├──→ 投资裁判 ─→ 决策 + 目标价 + 止损价    │
│  Bear研究员 ─┘                                           │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│              ③ 风险辩论 (RiskDebate)                     │
│                                                          │
│  激进派 ─┐                                              │
│  保守派 ─┼──→ 综合风险评分 + 仓位建议 + 风险项识别     │
│  中立派 ─┘                                              │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│              ④ 组合经理审批 (PortfolioApproval)          │
│                                                          │
│  综合: 基本面30% + 技术面20% + 辩论30% + 风险20%        │
│                                                          │
│  最终决策: APPROVE / MODIFY / REJECT / HOLD             │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
                 最终执行报告
```

---

## 决策选项

| 决策 | 含义 | 触发条件 |
|------|------|---------|
| **APPROVE** | 批准，按计划执行 | 多头 + 风险 < 50 + 置信度 ≥ 65% |
| **MODIFY** | 修改后执行（降仓） | 多头 + 风险 50-74，或空头需减持 |
| **REJECT** | 拒绝，不执行 | 风险评分 ≥ 75，或空头高置信度 |
| **HOLD** | 观望，等待更多信息 | 多空分歧 / 信号不明确 |

---

## 使用方法

### 快速调用

```python
from skills.china_trading_multiagent.agents.china_analyst_team import run_analyst_team
from skills.china_trading_multiagent.agents.bull_bear_debate import run_bull_bear_debate
from skills.china_trading_multiagent.agents.risk_debate import run_risk_debate
from skills.china_trading_multiagent.agents.portfolio_approval import (
    run_portfolio_approval,
    format_decision_report,
)
from skills.china_trading_multiagent.data_tools.china_data_adapter import load_portfolio

# 1. 运行分析师团队
report = await run_analyst_team("600519")  # 贵州茅台

# 2. 多空辩论
debate = run_bull_bear_debate(report, current_price=report.current_price)

# 3. 风险辩论
portfolio = load_portfolio()
risk = run_risk_debate(
    code="600519",
    current_price=report.current_price,
    target_price=debate.target_price,
    stop_loss=debate.stop_loss,
    debate_result=debate,
    portfolio=portfolio,
)

# 4. 组合经理审批
approval = run_portfolio_approval(
    code="600519",
    name=report.name,
    analyst_report=report,
    debate_result=debate,
    risk_result=risk,
    portfolio=portfolio,
    current_price=report.current_price,
)

# 5. 输出决策报告
print(format_decision_report(approval))
```

---

## 目录结构

```
china-trading-multiagent/
├── SKILL.md                        ← 本文件
├── agents/
│   ├── china_analyst_team.py       ← 分析师团队（基本面/技术面/情绪）
│   ├── bull_bear_debate.py         ← 多空辩论引擎
│   ├── risk_debate.py              ← 风险辩论（激进/保守/中立）
│   └── portfolio_approval.py       ← 组合经理审批层
├── data_tools/
│   └── china_data_adapter.py       ← A股数据适配器（必盈/同花顺）
├── config/
│   └── china_config.py             ← A股特有配置（T+1/涨跌停/最小单位）
└── references/
    └── tradingagents_architecture.md  ← TradingAgents 原版架构笔记
```

---

## A股特有规则（china_config.py）

| 规则 | 参数 |
|------|------|
| T+1制度 | 当日买入，次日才能卖出 |
| 涨跌停板 | 普通股 ±10%，科创/创业 ±20% |
| 最小交易单位 | 100股（1手） |
| 单票最大持仓 | 30% |
| 总仓位上限 | 85% |
| 默认止损线 | -7% |

---

## 数据源

| 数据类型 | 主数据源 | 备用 |
|---------|---------|------|
| 实时行情 | 必盈API (`biyingapi`) | 同花顺 |
| K线 | 必盈API | — |
| 财务数据 | 必盈API | 同花顺 |
| 新闻 | 必盈API | 东财 |
| 持仓 | `data_bus/portfolio.json` | — |

---

## 与 TradingAgents 的对比

| 维度 | TradingAgents | 本框架 |
|------|--------------|--------|
| 市场 | 美股为主 | **A 股为主** |
| 数据 | Yahoo Finance / Alpha Vantage | **必盈 API / 同花顺** |
| 辩论机制 | Bull/Bear + 裁判 | 同 |
| 风险管理 | 五级评分 | **激进/保守/中立三方辩论** |
| 交易规则 | 无 T+1 | **T+1 + 涨跌停板** |
| 持仓管理 | 模拟 | **连接 portfolio.json** |

---

## 参考

- 原版：[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) (arXiv:2412.20138)
- A股数据源：必盈API (`biyingapi.com`) / 同花顺 (`aimiai.com`)

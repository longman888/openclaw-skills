# TradingAgents 原版架构笔记

> 来源：https://github.com/TauricResearch/TradingAgents (MIT License)
> Paper: arXiv:2412.20138

## 核心模块（LangGraph）

```
tradingagents/
├── graph/
│   ├── trading_graph.py          # 主图（TradingAgentsGraph）
│   ├── conditional_logic.py       # 条件路由
│   ├── setup.py                  # 图构建
│   ├── propagation.py             # 状态传播
│   ├── reflection.py              # 结果反思
│   └── signal_processing.py      # 信号处理
├── agents/
│   ├── analysts/                 # 分析师（基本面/市场/新闻/社交媒体）
│   ├── researchers/              # 研究员（Bull/Bear）
│   ├── managers/                # 经理（Portfolio/Research）
│   ├── trader/                  # 交易员
│   └── risk_mgmt/               # 风险管理（激进/保守/中立辩论者）
└── dataflows/                   # 数据获取层
```

## Agent 状态机

- 使用 LangGraph 的 `StateGraph`
- 每个节点是独立的 LLM Agent（支持 GPT-5.x / Gemini 3.x / Claude 4.x）
- 边表示 Agent 之间的消息传递
- 条件边根据 Agent 输出决定下一步路由

## 多Provider支持

```python
config["llm_provider"] = "openai" | "google" | "anthropic" | "xai" | "openrouter" | "ollama"
config["deep_think_llm"] = "gpt-5.4"      # 复杂推理
config["quick_think_llm"] = "gpt-5.4-mini" # 快速任务
```

## 调用示例

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "anthropic"
config["deep_think_llm"] = "claude-sonnet-4"
config["max_debate_rounds"] = 2

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)
```

## 本框架的适配

本框架（china-trading-multiagent）保留了 TradingAgents 的核心设计：
1. ✅ LangGraph 状态机模式（可以迁移到 LangGraph）
2. ✅ 多 Agent 辩论机制
3. ✅ 三层决策（分析师→辩论→风控→审批）
4. ✅ Provider 无关的 LLM 调用

适配到 A 股：
- 数据源：Yahoo Finance → 必盈API / 同花顺
- 规则：A 股 T+1 / 涨跌停板 / 最小100股
- 市场：美股 → 沪深交易所

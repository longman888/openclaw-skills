---
name: skill-discovery
description: |
  Search for reusable skills across OpenSpace's local registry and cloud community.
  This skill registry indexes BOTH built-in skills AND Claude Code-derived core skills.
  Reusing proven skills saves tokens, improves reliability, and extends your capabilities.
---

# Skill Discovery — 技能发现系统

Discover and browse skills from OpenSpace's local skill library.

## 核心技能索引 (Core Skills from Claude Code)

以下技能**源自 Claude Code (free-code) 源码**，经过适配后集成到 OpenClaw：

### 🧠 记忆与上下文

| 技能 | 描述 | 来源 |
|------|------|------|
| **friday-dream** | 每周五收盘后自动整合记忆（Orient→Gather→Consolidate→Prune）| Claude Code DreamTask |
| **context-compact** | 三层上下文压缩系统（Microcompact / Snip / AutoCompact）| Claude Code autoCompact |

### ⚡ 工具执行

| 技能 | 描述 | 来源 |
|------|------|------|
| **streaming-tool-executor** | 流式工具执行器，并发安全工具并行执行，提升75%性能 | Claude Code StreamingToolExecutor |

### 🤖 多智能体

| 技能 | 描述 | 来源 |
|------|------|------|
| **multi-agent** | Leader-Worker 编排系统，支持文件邮箱协议 | Claude Code Swarm/AgentTool |
| **openharness-hooks** | Hook 系统（cost-tracker / subagent-notify）| HKUDS/OpenHarness |

### 📈 量化策略

| 技能 | 描述 | 来源 |
|------|------|------|
| **stock-data** | 股票数据获取（AkShare / 必盈API / 同花顺）| 自研 |
| **stock-technical** | 技术指标计算（MA / MACD / KDJ / RSI / BOLL）| 自研 |
| **stock-strategy** | 交易信号生成（趋势跟踪/均值回归/动量）| 自研 |
| **stock-risk** | 风险管理系统（VaR / 止损 / 仓位管理）| 自研 |
| **strategy-evolver** | 策略自我演化（生成→回测→评估→变异）| 自研 |
| **china-stock-analysis** | A股综合分析框架 | 自研 |

### 🔧 基础设施

| 技能 | 描述 | 来源 |
|------|------|------|
| **trigger-scheduler** | Cron 任务调度（支持市场时间）| 自研 |
| **delegate-task** | 任务委托给 OpenSpace 执行 | 自研 |
| **metaso-search** | 秘塔AI搜索（默认搜索引擎）| 自研 |

---

## 技能调用约定

### 如何调用核心技能

```python
# 1. context-compact
from skills.context_compact import ContextCompactor
compactor = ContextCompactor(context_window=128_000)
state = compactor.get_token_state(messages)
if compactor.should_auto_compact(messages):
    result = await compactor.auto_compact(messages, llm_client)

# 2. streaming-tool-executor
from skills.streaming_tool_executor import StreamingToolExecutor
executor = StreamingToolExecutor(tools=ctx.tools, ...)
for block in stream_tools():
    executor.add_tool(block)
    for result in executor.get_completed_results():
        yield result

# 3. friday-dream
from skills.friday_dream import FridayDream
dream = FridayDream(ctx)
summary = dream.run()
```

### 技能依赖关系

```
friday-dream
  └── context-compact (记忆整合时压缩上下文)
  └── skill_context (PortfolioData 获取持仓)

multi-agent
  └── openharness-hooks (subagent 生命周期通知)
  └── streaming-tool-executor (并行工具执行)

strategy-evolver
  └── context-compact (压缩回测上下文)
  └── stock-data (获取历史数据)
```

---

## 使用场景

| 场景 | 推荐技能 |
|------|----------|
| 批量分析多只股票 | streaming-tool-executor |
| 防止上下文溢出 | context-compact |
| 周五收盘后记忆整合 | friday-dream |
| 并行采集数据 + 串行执行风控 | streaming-tool-executor |
| 策略自我优化 | strategy-evolver |
| 多任务分解执行 | multi-agent |

---

## 本地搜索

```bash
# 搜索本地技能
Get-ChildItem "E:\.openclaw\skills" -Directory | Select-Object Name
```

---

## 参考

- Claude Code 源码: `E:\AI学习文件夹\下载的程序\claude-code-source-code\free-code-main`
- OpenClaw Skills: `E:\.openclaw\skills\`

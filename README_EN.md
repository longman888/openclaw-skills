# 🎯 OpenClaw Core Skills

[![GitHub Repo](https://img.shields.io/badge/GitHub-openclaw--skills-blue)](https://github.com/longman888/openclaw-skills)

> This skill library is derived from [Claude Code](https://github.com/anthropics/claude-code) (free-code) source code, systematically extracted and adapted for the OpenClaw environment.

**Core Skills** are system-level infrastructure for OpenClaw, providing universal capabilities for all upper-layer skills.

---

## 📦 Core Skills Index

### 🧠 Memory & Context

| Skill | Directory | Description |
|-------|-----------|-------------|
| **friday-dream** | `friday-dream/` | Weekly memory consolidation (Orient→Gather→Consolidate→Prune) |
| **context-compact** | `context-compact/` | 3-layer context compression (Microcompact / Snip / AutoCompact) |

### ⚡ Tool Execution

| Skill | Directory | Description |
|-------|-----------|-------------|
| **streaming-tool-executor** | `streaming-tool-executor/` | Streaming tool executor with parallel execution for concurrency-safe tools, 75% performance improvement |

### 🤖 Multi-Agent

| Skill | Directory | Description |
|-------|-----------|-------------|
| **multi-agent** | `multi-agent/` | Leader-Worker orchestration system with file mailbox protocol |
| **openharness-hooks** | `openharness-hooks/` | Hook system (cost-tracker / subagent-notify) |

### 📈 Quantitative Trading

| Skill | Directory | Description |
|-------|-----------|-------------|
| **stock-data** | `stock-data/` | Stock data acquisition (AkShare / Biying API / Tonghuashun) |
| **stock-technical** | `stock-technical/` | Technical indicators (MA / MACD / KDJ / RSI / BOLL) |
| **stock-strategy** | `stock-strategy/` | Trading signal generation (Trend / Mean Reversion / Momentum) |
| **stock-risk** | `stock-risk/` | Risk management (VaR / Stop Loss / Position Sizing) |
| **strategy-evolver** | `strategy-evolver/` | Self-evolving strategy (Generate→Backtest→Evaluate→Mutate) |
| **china-stock-analysis** | `china-stock-analysis/` | A-share comprehensive analysis framework |

### 🔧 Infrastructure

| Skill | Directory | Description |
|-------|-----------|-------------|
| **trigger-scheduler** | `trigger-scheduler/` | Cron task scheduling (with market hours support) |
| **delegate-task** | `delegate-task/` | Task delegation to OpenSpace |
| **metaso-search** | `metaso-search/` | Metaso AI search (default search engine) |
| **skill-discovery** | `skill-discovery/` | Skill discovery and indexing |

---

## 🚀 Quick Start

### Calling Core Skills

```python
# 1. context-compact - Context compression
from skills.context_compact import ContextCompactor

compactor = ContextCompactor(context_window=128_000)
state = compactor.get_token_state(messages)

if compactor.should_auto_compact(messages):
    result = await compactor.auto_compact(messages, llm_client)

# 2. streaming-tool-executor - Streaming tool execution
from skills.streaming_tool_executor import StreamingToolExecutor

executor = StreamingToolExecutor(
    tool_definitions=tools,
    can_use_tool=ctx.can_use_tool,
    tool_use_context=ctx.tool_context
)

for block in stream_tools():
    executor.add_tool(block)
    for result in executor.get_completed_results():
        yield result  # Display results immediately

# 3. friday-dream - Memory consolidation
from skills.friday_dream import FridayDream

dream = FridayDream(ctx)
summary = dream.run()
```

### Skill Dependencies

```
friday-dream
  └── context-compact (compress context during consolidation)
  └── skill_context (PortfolioData for positions)

multi-agent
  └── openharness-hooks (subagent lifecycle notifications)
  └── streaming-tool-executor (parallel tool execution)

strategy-evolver
  └── context-compact (compress backtest context)
  └── stock-data (historical data)
```

---

## 📚 Skill Documentation

Each skill has its own `SKILL.md` file containing:

- **Concept** — What problem the skill solves
- **API Reference** — Function signatures and parameters
- **Usage Examples** — Common scenario code
- **Integration Guide** — How to work with other skills

---

## 🏗️ Architecture

```
OpenClaw Core System
├── Memory System (friday-dream)
│   └── 4-phase consolidation → MEMORY.md auto-update
│
├── Context Management (context-compact)
│   └── 3-layer compression → Token budget protection → Auto cleanup
│
├── Tool Execution (streaming-tool-executor)
│   └── Concurrent/exclusive scheduling → 75% performance boost
│
├── Multi-Agent (multi-agent)
│   └── Leader-Worker → File mailbox protocol
│
├── Strategy Evolution (strategy-evolver)
│   └── Generate→Backtest→Evaluate→Mutate loop
│
└── Hook System (openharness-hooks)
    └── cost-tracker + subagent-notify
```

---

## 📜 License

This skill library is based on **BSD License** (inherited from Claude Code).

Claude Code original uses BSD License, allowing free use, modification, and distribution.

---

## 🙏 Acknowledgments

- **Anthropic** — Claude Code provides excellent architecture reference
- **HKUDS/OpenHarness** — Hook system design reference
- **AkShare** — A-share data interface support

---

*This skill library is maintained by OpenClaw automation system*

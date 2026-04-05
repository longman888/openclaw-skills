# 🎯 OpenClaw Core Skills

[![GitHub Repo](https://img.shields.io/badge/GitHub-openclaw--skills-blue)](https://github.com/longman888/openclaw-skills)

> This skill library is **derived from [Claude Code](https://github.com/anthropics/claude-code) (free-code) source code**, systematically extracted and adapted for the OpenClaw environment.

---

## 📦 Core Skills Index

All skills are **sourced from Claude Code source code** and can be used as infrastructure by other skills.

| Skill | Description | Source Location |
|-------|-------------|----------------|
| **friday-dream** | Weekly memory consolidation (Orient→Gather→Consolidate→Prune) | `tasks/DreamTask/` |
| **context-compact** | 3-layer context compression (Microcompact / Snip / AutoCompact) | `services/compact/` |
| **streaming-tool-executor** | Streaming tool executor with parallel execution for concurrency-safe tools | `services/tools/StreamingToolExecutor.ts` |
| **multi-agent** | Leader-Worker orchestration system with file mailbox protocol | `src/utils/swarm/`, `src/tools/AgentTool/` |
| **openharness-hooks** | Hook system (cost-tracker / subagent-notify) | Reference: HKUDS/OpenHarness |
| **skill-discovery** | Skill discovery and indexing | Custom |

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

multi-agent
  └── openharness-hooks (subagent lifecycle notifications)
  └── streaming-tool-executor (parallel tool execution)
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

---

*This skill library is maintained by OpenClaw automation system*

---
name: skill-discovery
description: |
  Search for reusable skills across OpenSpace's local registry and cloud community.
  This skill registry indexes Claude Code-derived core skills ONLY.
---

# Skill Discovery — 技能发现系统

Discover and browse skills from OpenSpace's local skill library.

## 核心技能索引 (Core Skills from Claude Code)

以下技能**源自 Claude Code (free-code) 源码**：

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

multi-agent
  └── openharness-hooks (subagent 生命周期通知)
  └── streaming-tool-executor (并行工具执行)
```

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

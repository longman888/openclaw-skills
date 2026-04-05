# 🎯 OpenClaw Core Skills

[![GitHub Repo](https://img.shields.io/badge/GitHub-openclaw--skills-blue)](https://github.com/longman888/openclaw-skills)

> 本技能库**源自 [Claude Code](https://github.com/anthropics/claude-code) (free-code)** 源码，经过系统性提取与适配，集成到 OpenClaw 环境。

---

## 📦 核心技能清单

所有技能均**源自 Claude Code 源码**，可直接被其他技能调用作为基础设施。

| 技能 | 描述 | 源码位置 |
|------|------|----------|
| **friday-dream** | 每周自动整合记忆（Orient→Gather→Consolidate→Prune）| `tasks/DreamTask/` |
| **context-compact** | 三层上下文压缩系统（Microcompact / Snip / AutoCompact）| `services/compact/` |
| **streaming-tool-executor** | 流式工具执行器，并发安全工具并行执行 | `services/tools/StreamingToolExecutor.ts` |
| **multi-agent** | Leader-Worker 编排系统，支持文件邮箱协议 | `src/utils/swarm/`, `src/tools/AgentTool/` |
| **openharness-hooks** | Hook 系统（cost-tracker / subagent-notify）| 参考 HKUDS/OpenHarness |
| **skill-discovery** | 技能发现与索引 | 自研 |

---

## 🚀 快速开始

### 调用核心技能

```python
# 1. context-compact - 上下文压缩
from skills.context_compact import ContextCompactor

compactor = ContextCompactor(context_window=128_000)
state = compactor.get_token_state(messages)

if compactor.should_auto_compact(messages):
    result = await compactor.auto_compact(messages, llm_client)

# 2. streaming-tool-executor - 流式工具执行
from skills.streaming_tool_executor import StreamingToolExecutor

executor = StreamingToolExecutor(
    tool_definitions=tools,
    can_use_tool=ctx.can_use_tool,
    tool_use_context=ctx.tool_context
)

for block in stream_tools():
    executor.add_tool(block)
    for result in executor.get_completed_results():
        yield result  # 立即显示结果

# 3. friday-dream - 记忆整合
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

## 📚 技能文档

每个技能都有独立的 `SKILL.md` 文件，包含：
- **概念说明** — 技能解决的问题
- **API 参考** — 函数签名和参数
- **使用示例** — 常见场景代码
- **集成指南** — 如何与其他技能配合

---

## 🏗️ 架构

```
OpenClaw Core System
├── 记忆系统 (friday-dream)
│   └── 4阶段记忆整合 → MEMORY.md 自动更新
│
├── 上下文管理 (context-compact)
│   └── 三层压缩 → Token预算保护 → 自动清理
│
├── 工具执行 (streaming-tool-executor)
│   └── 并发/独占调度 → 75%性能提升
│
├── 多智能体 (multi-agent)
│   └── Leader-Worker → 文件邮箱协议
│
└── 钩子系统 (openharness-hooks)
    └── cost-tracker + subagent-notify
```

---

## 📜 License

本技能库基于 **BSD License**（继承自 Claude Code）。

Claude Code 原版采用 BSD License，允许自由使用、修改和分发。

---

## 🙏 致谢

- **Anthropic** — Claude Code 提供了优秀的架构参考

---

*本技能库由 OpenClaw 自动化系统维护*

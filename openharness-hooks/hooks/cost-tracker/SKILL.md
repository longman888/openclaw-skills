# SKILL.md — Cost Tracker System

> 参考 HKUDS/OpenHarness 的 CostTracker 设计，构建 OpenClaw 环境下的用量追踪能力。

## 概述

OpenClaw 原生集成 `/status` 和 `/usage` 命令，涵盖：
- 每 session 的模型、Token 消耗、估算费用
- Provider 级别的用量窗口（配额快照）
- 消息级 usage footer（`/usage full`）

本 skill 在此基础上扩展**结构化事件日志**，支持：
- 按工具/模型/会话分组统计
- 长期累计用量存档
- 自定义告警阈值

---

## OpenClaw 原生能力（直接可用）

### /status — 当前 Session 快照

```
Session: agent:main:main
Model: minimax/MiniMax-M2.7
Context: 2,340 / 128,000 tokens
Last reply: 892 tokens out / 1,240 tokens in
Cost: ~$0.023 (estimated)
```

### /usage — 用量级别

| 级别 | 显示内容 |
|------|---------|
| `/usage tokens` | 仅 token 数量 |
| `/usage full` | token + 估算费用（API Key 认证） |
| `/usage off` | 关闭 usage footer |

### openclaw status --usage

查看 Provider 级别的用量窗口（配额快照）。

---

## 结构化日志 Hook（扩展能力）

创建 `~/.openclaw/hooks/cost-tracker/HOOK.md` + `handler.ts`，在每次 `agent_end` 时写入结构化日志：

```markdown
---
name: cost-tracker
description: "跟踪 Agent 运行成本，按模型和工具记录 Token 消耗"
metadata:
  openclaw:
    emoji: "💰"
    events: ["agent:agent_end"]
---
```

```typescript
// handler.ts
import * as fs from "fs";
import * as path from "path";

const LOG_FILE = "E:\\.openclaw\\data_bus\\cost-log.jsonl";

interface UsageRecord {
  timestamp: string;
  sessionKey: string;
  model: string;
  totalTokens: number;
  toolCalls: number;
  durationMs: number;
  estimatedCost?: number;
}

const handler = async (event: any) => {
  if (event.type !== "agent" || event.action !== "end") return;

  const { sessionKey, model, usage, toolCalls, durationMs } = event.context ?? {};
  
  const record: UsageRecord = {
    timestamp: new Date().toISOString(),
    sessionKey: sessionKey ?? "unknown",
    model: model ?? "unknown",
    totalTokens: usage?.total_tokens ?? 0,
    toolCalls: toolCalls ?? 0,
    durationMs: durationMs ?? 0,
    estimatedCost: usage?.estimated_cost,
  };

  const line = JSON.stringify(record) + "\n";
  fs.appendFileSync(LOG_FILE, line, "utf8");
  
  console.log(`[cost-tracker] ${record.model} | ${record.totalTokens} tokens | $${record.estimatedCost ?? "?"}`);
};

export default handler;
```

---

## 模型定价参考（2026 年）

| 模型 | 输入 (/1M tokens) | 输出 (/1M tokens) |
|------|------------------|------------------|
| minimax/MiniMax-M2.7 | $0.07 | $0.28 |
| anthropic/claude-sonnet-4 | $3.00 | $15.00 |
| openai/gpt-4.5 | $2.50 | $10.00 |
| google/gemini-2.0-flash | $0.10 | $0.40 |

---

## 自定义用量告警

在 `before_tool_call` 中追踪慢工具（>30s），在 `agent_end` 时汇总：

```typescript
const SLOW_THRESHOLD_MS = 30_000;
const COST_THRESHOLD_USD = 1.00;

const handler = async (event: any) => {
  if (event.type !== "agent" || event.action !== "end") return;

  const { usage, durationMs } = event.context ?? {};
  const cost = usage?.estimated_cost ?? 0;

  if (cost > COST_THRESHOLD_USD) {
    console.warn(`[cost-alert] HIGH COST: $${cost.toFixed(4)} exceeded threshold $${COST_THRESHOLD_USD}`);
  }

  // 写入汇总
  const summary = {
    date: new Date().toISOString().split("T")[0],
    model: event.context?.model,
    costUSD: cost,
    tokens: usage?.total_tokens,
    durationMs,
  };

  const summaryPath = "E:\\.openclaw\\data_bus\\cost-summary.json";
  const existing = fs.existsSync(summaryPath)
    ? JSON.parse(fs.readFileSync(summaryPath, "utf8"))
    : { daily: [] };
  
  existing.daily.push(summary);
  fs.writeFileSync(summaryPath, JSON.stringify(existing, null, 2));
};

export default handler;
```

---

## 参考

- [OpenClaw API Usage & Costs](https://docs.openclaw.ai/reference/api-usage-costs)
- [OpenClaw Token Use](https://docs.openclaw.ai/reference/token-use)
- [HKUDS OpenHarness cost_tracker.py](https://github.com/HKUDS/OpenHarness/blob/main/src/openharness/core/cost_tracker.py)

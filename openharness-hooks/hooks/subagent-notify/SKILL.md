# SKILL.md — Subagent TaskNotification System

> 参考 HKUDS/OpenHarness 的 Coordinator XML TaskNotification，设计 OpenClaw 环境下的结构化 Subagent 结果通知体系。

## 概述

OpenClaw 原生支持 subagent 生命周期钩子：
- `subagent_spawning` — Subagent 创建前（可干预）
- `subagent_delivery_target` — Subagent 投递目标解析
- `subagent_spawned` — Subagent 已启动
- `subagent_ended` — Subagent 终止（**最佳结果注入点**）

本 skill 利用 `subagent_ended` 钩子，将 subagent 结果格式化为结构化 XML/JSON notification，写入 transcript 并推送给父 session。

---

## XML TaskNotification 格式（参考 OpenHarness）

```xml
<task-notification>
  <task-id>sub-abc123</task-id>
  <status>completed|failed|timeout</status>
  <summary>简短摘要（<80字）</summary>
  <result>完整结果（可超长）</result>
  <usage>
    <total-tokens>2048</total-tokens>
    <duration-ms>4532</duration-ms>
    <model>minimax/MiniMax-M2.7</model>
  </usage>
  <parent-session>agent:main:main</parent-session>
  <timestamp>2026-04-05T02:15:00+08:00</timestamp>
</task-notification>
```

对应的 JSON 等价格式：

```json
{
  "taskNotification": {
    "taskId": "sub-abc123",
    "status": "completed",
    "summary": "完成了数据分析，找到了3个交易机会",
    "result": "...",
    "usage": {
      "totalTokens": 2048,
      "durationMs": 4532,
      "model": "minimax/MiniMax-M2.7"
    },
    "parentSession": "agent:main:main",
    "timestamp": "2026-04-05T02:15:00+08:00"
  }
}
```

---

## Hook 实现

创建 `~/.openclaw/hooks/subagent-notify/HOOK.md` + `handler.ts`：

```markdown
---
name: subagent-notify
description: "Subagent 生命周期结构化通知，将完成结果格式化为 TaskNotification"
metadata:
  openclaw:
    emoji: "📬"
    events: ["agent:subagent_ended"]
---
```

```typescript
// handler.ts

interface TaskNotification {
  taskId: string;
  status: "completed" | "failed" | "timeout" | "cancelled";
  summary: string;
  result: string;
  usage: {
    totalTokens: number;
    durationMs: number;
    model: string;
    toolCalls?: number;
  };
  parentSession: string;
  timestamp: string;
}

const MAX_SUMMARY_CHARS = 80;
const MAX_RESULT_CHARS = 4000;

const summarizeResult = (result: string, maxChars: number): string => {
  if (result.length <= maxChars) return result;
  return result.slice(0, maxChars - 3) + "...";
};

const generateSummary = (result: string): string => {
  // 取结果前80字作为摘要
  const firstLine = result.split("\n").filter(l => l.trim())[0] ?? "";
  return summarizeResult(firstLine, MAX_SUMMARY_CHARS);
};

const handler = async (event: any) => {
  if (event.type !== "agent" || event.action !== "subagent_ended") return;

  const ctx = event.context ?? {};
  const { taskId, status, result, usage, parentSession, spawnId } = ctx;

  const notification: TaskNotification = {
    taskId: taskId ?? spawnId ?? "unknown",
    status: status ?? "failed",
    summary: generateSummary(result ?? ""),
    result: summarizeResult(result ?? "(无结果)", MAX_RESULT_CHARS),
    usage: {
      totalTokens: usage?.total_tokens ?? 0,
      durationMs: usage?.duration_ms ?? 0,
      model: usage?.model ?? "unknown",
      toolCalls: usage?.tool_calls ?? 0,
    },
    parentSession: parentSession ?? "unknown",
    timestamp: new Date().toISOString(),
  };

  // 输出 XML 格式（写入 transcript）
  const xml = `<task-notification>
  <task-id>${notification.taskId}</task-id>
  <status>${notification.status}</status>
  <summary>${notification.summary}</summary>
  <usage>
    <total-tokens>${notification.usage.totalTokens}</total-tokens>
    <duration-ms>${notification.usage.durationMs}</duration-ms>
    <model>${notification.usage.model}</model>
  </usage>
  <parent-session>${notification.parentSession}</parent-session>
  <timestamp>${notification.timestamp}</timestamp>
</task-notification>`;

  // 推送到父 session
  event.messages.push(xml);

  console.log(`[subagent-notify] ${notification.taskId} → ${notification.status} (${notification.usage.durationMs}ms)`);
};

export default handler;
```

---

## subagent_spawning 干预（可选）

在 subagent 启动前注入额外上下文：

```typescript
// 处理 subagent_spawning
const spawnHandler = async (event: any) => {
  if (event.type !== "agent" || event.action !== "subagent_spawning") return;

  const ctx = event.context ?? {};
  
  // 为特定任务注入额外系统提示
  if (ctx.taskDescription?.includes("数据分析")) {
    event.context.systemContext = (event.context.systemContext ?? "") + 
      "\n\n[System] 此任务涉及金融数据，请使用 A股框架进行分析。";
  }
};

export default spawnHandler;
```

---

## 事件完整对照表

| OpenHarness 事件 | OpenClaw 钩子 | 触发时机 |
|-----------------|--------------|---------|
| `task.start` | `subagent_spawning` | Subagent 创建前 |
| — | `subagent_delivery_target` | 投递目标解析后 |
| `task.notification` | `subagent_spawned` | Subagent 已启动 |
| `task.completed` | `subagent_ended` | Subagent 终止 |

---

## 配置父 Session 接收

在 `sessions_send` 时指定 `sessionKey` 或 `label` 即可将结果推送到父 session。

---

## 参考

- [OpenClaw Hooks: Subagent hooks](https://docs.openclaw.ai/automation/hooks#plugin-hook-events)
- [HKUDS OpenHarness coordinator/coordinator_mode.py](https://github.com/HKUDS/OpenHarness/blob/main/src/openharness/coordinator/coordinator_mode.py)
- [OpenClaw sessions_spawn](/tools/sessions-spawn)

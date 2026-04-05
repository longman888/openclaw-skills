---
name: subagent-notify
description: "Subagent 生命周期结构化通知，将完成结果格式化为 XML TaskNotification"
metadata:
  openclaw:
    emoji: "📬"
    events: ["agent:subagent_ended"]
---

# Subagent Notify Hook

在 `subagent_ended` 时，将结果格式化为 OpenHarness 风格的 XML TaskNotification，推送到父 session。

## 事件生命周期

| 钩子 | 时机 |
|------|------|
| `subagent_spawning` | Subagent 创建前 |
| `subagent_spawned` | Subagent 已启动 |
| `subagent_ended` | **本 Hook — 终止时** |

## 输出格式

```xml
<task-notification>
  <task-id>sub-abc123</task-id>
  <status>completed|failed|timeout</status>
  <summary>简短摘要</summary>
  <usage>
    <total-tokens>2048</total-tokens>
    <duration-ms>4532</duration-ms>
    <model>minimax/MiniMax-M2.7</model>
  </usage>
  <parent-session>agent:main:main</parent-session>
  <timestamp>2026-04-05T02:15:00+08:00</timestamp>
</task-notification>
```

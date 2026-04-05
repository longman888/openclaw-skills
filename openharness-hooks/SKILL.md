# SKILL.md — OpenHarness Inspired Systems

> 参考 HKUDS/OpenHarness 的三大核心系统（Hook / CostTracker / TaskNotification），适配 OpenClaw 环境。
> **结论：OpenClaw 已有完整基础设施，三个 skill 均通过配置 + Hook 脚本实现，无需修改 OpenClaw 核心代码。**

## 总览

| 功能 | OpenHarness 设计 | OpenClaw 对应 | 落地状态 |
|------|----------------|--------------|---------|
| Hook System | `PRE_TOOL_USE` / `POST_TOOL_USE` | `before_tool_call` / `after_tool_call` | ✅ 已完整实现 |
| Cost Tracker | `total_tokens` / `tool_uses` / `cost` | `/status` + `session-cost-usage` 模块 | ✅ 已完整实现 |
| TaskNotification | XML `<task-notification>` 格式 | `subagent_ended` 钩子 + `sessions_send` | ✅ 已完整实现 |

---

## 目录结构

```
openharness-hooks/
├── SKILL.md                        ← 本文件（总览）
├── hooks/
│   ├── dangerous-tool-audit/        ← 危险命令拦截 Hook（示例）
│   │   ├── HOOK.md
│   │   └── handler.ts
│   ├── cost-tracker/               ← 用量追踪 Hook
│   │   ├── HOOK.md
│   │   └── handler.ts
│   └── subagent-notify/            ← Subagent 结构化通知 Hook
│       ├── HOOK.md
│       └── handler.ts
└── README.md                        ← 快速启用指南
```

---

## 快速启用（5分钟）

### 第一步：启用内部钩子系统

在 `~/.openclaw/config.json` 中：

```json
{
  "hooks": {
    "internal": {
      "enabled": true
    }
  }
}
```

### 第二步：部署 Hook（选需要的功能）

```powershell
# 复制 Hook 目录到用户钩子目录
Copy-Item -Recurse E:\.openclaw\skills\openharness-hooks\hooks\cost-tracker C:\Users\zhanj\.openclaw\hooks\

# 列出已发现的 Hook
openclaw hooks list
```

### 第三步：重启 Gateway

```bash
openclaw gateway restart
```

---

## 三个子系统的详细说明

### 1. 🔌 Hook System（`before_tool_call` / `after_tool_call`）

文档：`hooks/dangerous-tool-audit/HOOK.md`

OpenClaw 内置 28 个钩子，完全覆盖 OpenHarness 设计：
- **工具前**：`before_tool_call` — 可 block、修改参数、请求审批
- **工具后**：`after_tool_call` — 审计、监控
- **执行流程**：Plugin Hook（Sequential，block 语义明确）

### 2. 💰 Cost Tracker（`/status` + 用量日志）

文档：`hooks/cost-tracker/HOOK.md`

OpenClaw 原生提供：
- `session-cost-usage` 模块（已内置）
- `/status` — 当前 session 快照
- `/usage full|tokens|off` — 用量级别控制
- `openclaw status --usage` — Provider 配额窗口

扩展方案：
- `agent_end` 钩子 → 写入结构化 JSONL 日志
- `before_tool_call` 钩子 → 追踪慢工具（>30s）
- 自定义告警阈值

### 3. 📬 TaskNotification（`subagent_ended` → XML）

文档：`hooks/subagent-notify/HOOK.md`

OpenHarness 的 XML task-notification 格式：

```xml
<task-notification>
  <task-id>sub-abc123</task-id>
  <status>completed</status>
  <summary>完成了数据分析，找到了3个交易机会</summary>
  <usage>
    <total-tokens>2048</total-tokens>
    <duration-ms>4532</duration-ms>
    <model>minimax/MiniMax-M2.7</model>
  </usage>
  <parent-session>agent:main:main</parent-session>
  <timestamp>2026-04-05T02:15:00+08:00</timestamp>
</task-notification>
```

OpenClaw `subagent_ended` 钩子 → 格式化 → `event.messages.push(xml)` → 推送到父 session。

---

## OpenClaw Hook 生态优势（对比 OpenHarness）

| 维度 | OpenHarness | OpenClaw |
|------|------------|----------|
| 钩子数量 | 4 个主要钩子 | **28 个完整钩子** |
| 工具拦截 | 基础 block | **可 block + 修改参数 + 审批流程** |
| 审批机制 | 无 | **Telegram/Discord 原生按钮 + `/approve` 命令** |
| Subagent 钩子 | 无 | **spawning/delivery/spawned/ended 完整生命周期** |
| 安装方式 | 源码修改 | **Skill 目录复制，Gateway 重启即可** |

---

## 参考资料

- OpenClaw Hooks: `~/.openclaw/docs/automation/hooks.md`
- Plugin Hook API: `~/.openclaw/docs/plugins/architecture.md`
- HKUDS OpenHarness: https://github.com/HKUDS/OpenHarness
- Hook 源码: `src/gateway/plugins/plugin-runtime-hooks.ts`
- Cost 模块: `dist/session-cost-usage-*.js`
- Task Registry: `dist/task-registry.*.js`

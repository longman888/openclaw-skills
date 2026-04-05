---
name: cost-tracker
description: "跟踪 Agent 运行成本，按模型和工具记录 Token 消耗，写入结构化日志"
metadata:
  openclaw:
    emoji: "💰"
    events: ["agent:agent_end"]
---

# Cost Tracker Hook

在每次 Agent 运行结束时，将用量数据写入结构化 JSONL 日志。

## 输出文件

- `E:\.openclaw\data_bus\cost-log.jsonl`

## 依赖

- Node.js（内置 `fs` 模块）
- `E:\.openclaw\data_bus\` 目录存在

---
name: dangerous-tool-audit
description: "审计并拦截危险工具调用（rm -rf/format/fdisk 等），记录所有 exec/write/delete 调用"
metadata:
  openclaw:
    emoji: "🔍"
    events: ["tool:before_tool_call"]
---

# Dangerous Tool Audit Hook

在每次工具调用前检查危险模式，发现即 block 并记录日志。

## 拦截规则

| 模式 | 示例 | 行为 |
|------|------|------|
| `rm -rf /` | 系统递归删除 | block |
| `format` | 格式化命令 | block |
| `fdisk` | 磁盘分区 | block |
| `$()` 命令替换 | 注入 | block |
| `del /` / `rm /` | 系统路径删除 | block |

## 配置

无需配置，启用即生效。

## 输出

- 控制台日志（`gateway.log`）
- 无文件写入

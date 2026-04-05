# 快速启用指南 — OpenHarness-Inspired Hooks

## 前置条件

OpenClaw Gateway 已运行。

## 部署步骤

### 1. 复制 Hook 目录

```powershell
# 将所有 hooks 复制到用户钩子目录
cp -r E:\.openclaw\skills\openharness-hooks\hooks\* C:\Users\zhanj\.openclaw\hooks\

# 验证
openclaw hooks list
```

### 2. 验证钩子已发现

```
🎯 dangerous-tool-audit    [tool:before_tool_call]
💰 cost-tracker            [agent:agent_end]
📬 subagent-notify         [agent:subagent_ended]
```

### 3. 配置 Cost 日志路径（如需要）

确认目录存在：
```powershell
New-Item -ItemType Directory -Force -Path E:\.openclaw\data_bus
```

### 4. 重启 Gateway 使钩子生效

```bash
openclaw gateway restart
```

## 验证

执行一个工具调用，检查日志：
```bash
# 查看 gateway 日志
tail -f ~/.openclaw/gateway.log | grep -E "(dangerous-tool-audit|cost-tracker|subagent-notify)"
```

## 卸载

```bash
openclaw hooks disable dangerous-tool-audit
openclaw hooks disable cost-tracker
openclaw hooks disable subagent-notify
# 或直接删除目录
rm -rf C:\Users\zhanj\.openclaw\hooks\cost-tracker
rm -rf C:\Users\zhanj\.openclaw\hooks\subagent-notify
rm -rf C:\Users\zhanj\.openclaw\hooks\dangerous-tool-audit
```

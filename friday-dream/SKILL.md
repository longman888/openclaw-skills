# FridayDream - 每周记忆整合

## 触发条件

- **时间**：每周五 19:00（晚盘扫描之后）
- **信号**：市场收盘后，系统自动触发

## 功能

在后台整合本周所有操作经验，更新长期记忆，删除已失效的策略假设。

## 输入

1. 本周每日 memory 日志（memory/YYYY-MM-DD.md）
2. 本周交易记录（若有）
3. portfolio.json 本周变化
4. 大盘表现（indices）

## 四阶段流程

### Phase 1 - Orient（定位）
- 读取 MEMORY.md 了解当前结构
- 列出已有的主题记忆（investment_framework / sectors / strategies）
- 确认哪些记忆是本周新写入的

### Phase 2 - Gather（收集）
- 扫描 `memory/` 下本周的日志文件
- 提取：选股决策、买卖点、盈亏记录、风控触发、大盘事件
- 识别：哪些记忆与现实矛盾？哪些策略被验证？

### Phase 3 - Consolidate（整合）
- 更新 MEMORY.md 中的策略假设
- 强化本周验证有效的选股逻辑
- 记录新的市场观察
- 修复矛盾的记忆

### Phase 4 - Prune（修剪）
- 入口文件（MEMORY.md）保持精简
- 删除已被证伪的指标信念
- 更新"上次验证时间"戳

## 输出

- 更新后的 MEMORY.md
- 一份本周整合摘要（发送飞书）

## 使用方式

```python
from skills.friday_dream import FridayDream
ctx = SkillContext(session_id="dream-2026-04-04")
dream = FridayDream(ctx)
summary = dream.run()
ctx.send_feishu(f"FridayDream 完成: {summary}")
```

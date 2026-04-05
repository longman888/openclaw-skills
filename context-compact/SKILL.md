# context-compact — 上下文自动压缩系统

> 参考 Claude Code free-code 的 `services/compact/` 实现，构建 OpenClaw 环境下的多层次上下文压缩能力。

## 核心概念

当对话上下文接近模型上下文窗口上限时，自动压缩历史消息，释放 token 空间：

```
┌─────────────────────────────────────────────────────┐
│            Context Size Timeline                      │
├─────────────────────────────────────────────────────┤
│ 0%        WARNING         AUTOCOMPACT      100%     │
│ ├──────────┼──────────────┼────────────────┼──→    │
│ │  安全区  │   警告区     │   压缩触发     │ 阻塞  │
│ └──────────┴──────────────┴────────────────┘       │
│           -20K tokens   -13K tokens     -3K tokens  │
└─────────────────────────────────────────────────────┘
```

## 三层压缩机制

### Layer 1: Microcompact（微压缩）
- **原理**：清除旧工具调用的结果内容，保留 cache 引用
- **触发**：工具结果累积超过阈值
- **代价**：极低（不清除缓存）
- **文件**：`microCompact.ts`

### Layer 2: Snip（片段裁剪）
- **原理**：裁剪指定范围的历史消息
- **触发**：特定消息段不再需要
- **代价**：中等（可能丢失对话历史）
- **文件**：`snipCompact.ts`

### Layer 3: AutoCompact（自动压缩）
- **原理**：调用模型生成对话摘要，替换原始消息
- **触发**：上下文超过 `window - 13K tokens`
- **代价**：高（需要一次 API 调用生成摘要）
- **文件**：`autoCompact.ts`

## 关键阈值配置

```typescript
// 保留给输出的 token 空间
const MAX_OUTPUT_TOKENS_FOR_SUMMARY = 20_000

// 自动压缩阈值（窗口 - 13K）
const AUTOCOMPACT_BUFFER_TOKENS = 13_000

// 警告阈值（窗口 - 20K）
const WARNING_THRESHOLD_BUFFER_TOKENS = 20_000

// 错误阈值（窗口 - 20K）
const ERROR_THRESHOLD_BUFFER_TOKENS = 20_000

// 手动压缩阈值（窗口 - 3K）
const MANUAL_COMPACT_BUFFER_TOKENS = 3_000
```

## 上下文窗口参考（2026年）

| 模型 | 上下文窗口 | AutoCompact 触发点 | 警告点 |
|------|-----------|------------------|--------|
| MiniMax-M2.7 | 128,000 | ~115,000 | ~108,000 |
| Claude Sonnet 4 | 200,000 | ~180,000 | ~180,000 |
| GPT-4.5 | 128,000 | ~115,000 | ~108,000 |

## 压缩结果结构

```typescript
interface CompactionResult {
  // 压缩前 token 数
  preCompactTokenCount: number
  // 压缩后 token 数
  postCompactTokenCount: number
  // 摘要消息列表（替代原始消息）
  summaryMessages: Message[]
  // 被移除的附件
  attachments: AttachmentMessage[]
  // hook 执行结果
  hookResults: HookResultMessage[]
  // 压缩消耗的 token
  compactionUsage?: {
    input_tokens: number
    output_tokens: number
    cache_read_input_tokens?: number
    cache_creation_input_tokens?: number
  }
}
```

## 使用方式

### 手动触发压缩

```python
from skills.context_compact import ContextCompactor

compactor = ContextCompactor(ctx)
result = await compactor.auto_compact()

if result.was_compacted:
    ctx.log(f"压缩成功: {result.pre_count} → {result.post_count} tokens")
    ctx.save_messages(result.summary_messages)
```

### 查询当前状态

```python
state = compactor.get_token_state()
ctx.log(f"""
Token 使用状态:
- 当前: {state.current_tokens}
- 阈值: {state.autocompact_threshold}
- 剩余: {state.percent_left}%
- 警告: {state.is_above_warning_threshold}
""")
```

### 监听压缩事件

```python
# 在 skill context 中注册回调
ctx.on_compaction(lambda result: {
    ctx.send_feishu(f"上下文已压缩: {result.pre_count} → {result.post_count}")
})
```

## 配置选项

```typescript
// SKILL.json
{
  "auto_compact_enabled": true,       // 启用自动压缩
  "warning_buffer_tokens": 20000,     // 警告阈值
  "autocompact_buffer_tokens": 13000, // 自动压缩阈值
  "manual_buffer_tokens": 3000,        // 手动压缩阈值
  "max_consecutive_failures": 3,      // 连续失败后停止重试
  "disable_compact": false             // 完全禁用压缩
}
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `DISABLE_COMPACT` | 完全禁用压缩 |
| `DISABLE_AUTO_COMPACT` | 禁用自动压缩，保留手动 `/compact` |
| `CLAUDE_CODE_AUTO_COMPACT_WINDOW` | 覆盖上下文窗口大小 |
| `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` | 按百分比设置触发点 |

## 压缩副作用处理

### 1. 文件状态同步
压缩后需要重新读取文件，因为之前的 `read` 结果已被清除：

```python
# 压缩后强制刷新文件状态缓存
ctx.file_state.invalidate_all()
```

### 2. 技能列表失效
技能发现结果需要重新执行：

```python
# 重置技能缓存
ctx.skills.reset_discovery()
```

### 3. 对话历史重连
摘要消息需要保留关键决策点：

```python
# 保留的"锚点"消息（不可压缩）
ANCHOR_MESSAGE_TYPES = [
    'user_decision',      # 用户做出的重大决策
    'trade_execution',    # 交易执行记录
    'risk_alert',         # 风控警报
    'strategy_change'     # 策略变更
]
```

## 与 OpenClaw 集成

### Hook 注入点

```python
# 在 agent turn 结束后检查是否需要压缩
ctx.hooks.register('agent:end', async (event) => {
    if compactor.should_auto_compact(event.messages):
        result = await compactor.auto_compact()
        event.messages = result.summary_messages
})
```

### 定时检查

```python
# 每 10 个 turn 检查一次
if ctx.turn_count % 10 == 0:
    state = compactor.get_token_state()
    if state.is_above_warning_threshold:
        ctx.log(f"⚠️ Token 使用率: {100 - state.percent_left}%")
```

## 微压缩详细逻辑

```python
def microcompact(messages: list[Message]) -> list[Message]:
    """
    清除旧工具结果，保留 cache 引用
    只压缩这些工具: Read, Bash, Grep, Glob, WebSearch, WebFetch, Edit, Write
    """
    COMPACTABLE_TOOLS = {
        'Read', 'Bash', 'Grep', 'Glob',
        'WebSearch', 'WebFetch', 'Edit', 'Write'
    }
    
    result = []
    for msg in messages:
        if msg.type == 'assistant':
            # 工具调用保留，结果标记为清除
            result.append(msg)
        elif msg.type == 'user':
            new_content = []
            for block in msg.content:
                if block.type == 'tool_result':
                    if block.tool_name in COMPACTABLE_TOOLS:
                        # 替换为 cache 引用
                        new_content.append({
                            'type': 'text',
                            'text': '[Old tool result content cleared]'
                        })
                    else:
                        new_content.append(block)
                else:
                    new_content.append(block)
            msg.content = new_content
            result.append(msg)
        else:
            result.append(msg)
    
    return result
```

## 自动压缩详细逻辑

```python
async def auto_compact(messages: list[Message]) -> CompactionResult:
    """
    调用模型生成对话摘要
    """
    # 1. 准备压缩提示
    prompt = build_compact_prompt(messages)
    
    # 2. 调用模型生成摘要
    summary_response = await ctx.llm.generate(
        prompt,
        max_tokens=2000,
        system="你是一个对话压缩助手..."
    )
    
    # 3. 构建摘要消息
    summary_msg = Message(
        type='system',
        subtype='compact_summary',
        content=summary_response
    )
    
    # 4. 替换原始消息
    compacted = [summary_msg] + get_recent_messages(messages, last_n=5)
    
    return CompactionResult(
        pre_compact_token_count=count_tokens(messages),
        post_compact_token_count=count_tokens(compacted),
        summary_messages=[summary_msg]
    )
```

## 最佳实践

1. **不要等待阻塞** — 在警告区就开始压缩，不要等到错误区
2. **保留最近消息** — 最后 5-10 条消息保持完整
3. **锚点消息不可压缩** — 交易决策、风控警报等必须保留
4. **监控连续失败** — 3 次压缩失败后停止，避免浪费 API 调用
5. **清理副作用** — 压缩后重置文件缓存、技能发现状态

## 参考实现

- Claude Code `services/compact/autoCompact.ts`
- Claude Code `services/compact/microCompact.ts`
- Claude Code `services/compact/compact.ts`
- Claude Code `services/compact/snipCompact.ts`

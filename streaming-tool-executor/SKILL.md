# streaming-tool-executor — 流式工具执行器

> 参考 Claude Code free-code 的 `services/tools/StreamingToolExecutor.ts` 实现，构建 OpenClaw 环境下的流式工具执行能力。

## 核心概念

传统模式：等待模型完整输出 → 解析工具调用 → 批量执行工具 → 返回结果

```
传统模式 (阻塞):
┌─────────────────────────────────────────────────────────────┐
│ 模型输出 | 工具A | 工具B | 工具C | 等待... → 返回结果       │
└─────────────────────────────────────────────────────────────┘

流式模式 (非阻塞):
┌─────────────────────────────────────────────────────────────┐
│ 模型输出 | 工具A | ─────────────→ A结果                     │
│         | 工具B | ─────────→ B结果  (并行执行)              │
│         | 工具C | ───→ C结果                                │
└─────────────────────────────────────────────────────────────┘
```

## 为什么需要流式执行

1. **用户体验**：工具结果立即显示，无需等待所有工具完成
2. **效率提升**：独立工具可以并行执行
3. **资源利用**：I/O 密集型工具（网络请求）与计算并行

## 工具分类

### Concurrency-Safe（可并发）
- `Read` — 读文件，不修改状态
- `Glob` — 搜索文件，不修改状态
- `Grep` — 搜索文本，不修改状态
- `WebFetch` — 网络请求，只读操作
- `WebSearch` — 网络搜索，只读操作

### Non-Concurrent（必须独占）
- `Bash` — 执行命令，可能修改系统状态
- `Write` — 写文件
- `Edit` — 编辑文件
- `Task` — 启动子任务

## 核心机制

### 1. 工具状态机

```typescript
type ToolStatus = 'queued' | 'executing' | 'completed' | 'yielded'
```

```
queued → executing → completed → yielded
              ↓
          (error)
              ↓
         errored → yielded
```

### 2. 并发控制

```python
# 最多同时执行 N 个并发安全的工具
MAX_CONCURRENT_SAFE = 3

# 非并发工具必须单独执行
# 当前一个非并发工具完成前，后续工具必须等待
```

### 3. 结果缓冲

```python
# 工具结果按接收顺序缓冲
# 保持与模型输出顺序一致
buffer = []

for tool in stream_tools():
    result = execute_tool(tool)
    buffer.append(result)
    
# 所有工具完成后，按顺序yield
for result in buffer:
    yield result
```

## 核心类

```python
class StreamingToolExecutor:
    """
    流式工具执行器
    
    特性:
    - 边接收模型输出边执行工具
    - 并发安全的工具并行执行
    - 非并发工具独占执行
    - 结果按顺序缓冲输出
    """
    
    def __init__(
        self,
        tool_definitions: dict,
        can_use_tool: Callable,
        tool_use_context: dict
    ):
        self.tools: list[TrackedTool] = []
        self.context = tool_use_context
        self.sibling_abort = create_abort_controller()
    
    def add_tool(self, block: ToolUseBlock) -> None:
        """添加工具到执行队列"""
        
    def get_completed_results(self) -> Generator[ToolResult]:
        """获取已完成的结果（流式）"""
        
    def get_remaining_results(self) -> Generator[ToolResult]:
        """获取剩余结果（所有工具完成后）"""
        
    def discard(self) -> None:
        """丢弃所有工具（流式回退时）"""
```

## 使用方式

### 基本使用

```python
from skills.streaming_tool_executor import StreamingToolExecutor

executor = StreamingToolExecutor(
    tools=ctx.tools,
    can_use_tool=ctx.can_use_tool,
    context=ctx.tool_context
)

# 模拟流式接收工具调用
for tool_block in stream_tool_blocks_from_model():
    executor.add_tool(tool_block)
    
    # 立即显示进度
    for result in executor.get_completed_results():
        ctx.log(f"[{result.tool_name}] {result.content[:100]}...")
        yield result

# 获取剩余结果
for result in executor.get_remaining_results():
    yield result
```

### 带并发的使用

```python
async def execute_with_streaming(ctx, model_stream):
    executor = StreamingToolExecutor(
        tools=ctx.tools,
        can_use_tool=ctx.can_use_tool,
        context=ctx.tool_context
    )
    
    results = []
    
    async for event in model_stream:
        if event.type == 'tool_use':
            executor.add_tool(event.tool_block)
            
            # 立即处理已完成的结果
            for result in executor.get_completed_results():
                results.append(result)
                yield result
        
        elif event.type == 'content_block_stop':
            # 所有工具已完成
            for result in executor.get_remaining_results():
                if result not in results:
                    results.append(result)
                    yield result
            
            break
    
    return results
```

### 错误处理

```python
executor = StreamingToolExecutor(...)

for tool_block in stream_tools():
    executor.add_tool(tool_block)

try:
    for result in executor.get_completed_results():
        yield result
except Exception as e:
    # 丢弃未完成的工具
    executor.discard()
    ctx.log(f"工具执行出错: {e}")
    yield create_error_result(...)
```

## 与 OpenClaw 集成

### Tool 定义格式

```python
# OpenClaw 工具格式
tool = {
    'name': 'Read',
    'description': 'Read file contents',
    'input_schema': {
        'type': 'object',
        'properties': {
            'file_path': {'type': 'string'}
        }
    },
    'is_concurrency_safe': lambda input: True,  # 读取总是安全的
    'fn': async (input, context) -> ToolResult
}
```

### 权限检查

```python
class StreamingToolExecutor:
    def __init__(self, ...):
        self.wrapped_can_use_tool = self._wrap_can_use_tool()
    
    async def _wrap_can_use_tool(self, can_use_tool, tool, input):
        """包装权限检查，跟踪拒绝"""
        result = await can_use_tool(tool, input)
        
        if result.behavior != 'allow':
            self.permission_denials.append({
                'tool_name': tool.name,
                'tool_use_id': tool_use_id,
                'tool_input': input
            })
        
        return result
```

## 流式执行流程图

```
┌─────────────────────────────────────────────────────────────┐
│                      模型 Streaming                          │
└──────────────────────────┬──────────────────────────────────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
      ┌──────────┐   ┌──────────┐   ┌──────────┐
      │ tool_use │   │ tool_use │   │ tool_use │
      │  (Read)  │   │  (Bash)  │   │ (Write)  │
      └────┬─────┘   └────┬─────┘   └────┬─────┘
           │              │              │
           ▼ (并发)       ▼ (独占)       ▼ (等待Bash)
      ┌──────────┐   ┌──────────┐   ┌──────────┐
      │ execute  │   │ execute  │   │ queued   │
      │  parallel │   │  alone   │   │   ...    │
      └────┬─────┘   └────┬─────┘   └────┬─────┘
           │              │              │
           ▼              ▼              ▼
      ┌──────────┐   ┌──────────┐   ┌──────────┐
      │ completed│   │ completed│   │ executing│
      │  yield   │   │  yield   │   │   ...    │
      └──────────┘   └──────────┘   └──────────┘
                           │              │
                           └──────┬───────┘
                                  ▼
                           ┌──────────┐
                           │ completed│
                           │  yield   │
                           └──────────┘
```

## 性能对比

| 场景 | 传统模式 | 流式模式 | 提升 |
|------|---------|---------|------|
| 3个读取工具 | 等待: 3s + 3s + 3s = 9s | 并发: 3s | 66% |
| 2读 + 1写 | 等待: 2s + 2s + 5s = 9s | 2s并发 + 5s独占 = 7s | 22% |
| 5个工具混合 | 等待: ~15s | 并发/独占混合: ~8s | 47% |

## 实现注意事项

### 1. Abort Controller

```python
# 创建子 AbortController，用于终止兄弟工具
sibling_abort = create_child_abort_controller(parent_abort)

# 当一个 Bash 工具出错时，立即终止其他兄弟进程
def on_bash_error(tool_id):
    sibling_abort.abort()
```

### 2. 进度消息

```python
# 工具可以输出进度消息，立即 yield
class TrackedTool:
    pending_progress: list[Message] = []
    
    def add_progress(self, msg):
        self.pending_progress.append(msg)
        # 立即通知
        progress_available_resolve()
```

### 3. 工具结果缓存

```python
# 已完成的结果缓存，避免重复获取
completed_cache = {}

def get_completed_results(self):
    for tool in self.tools:
        if tool.status == 'completed' and tool.id not in completed_cache:
            completed_cache[tool.id] = tool.results
            yield tool.results
```

## 最佳实践

1. **保持顺序**：结果必须按工具出现的顺序输出
2. **立即响应**：不要等待所有工具完成才开始输出
3. **正确分类**：准确判断 `is_concurrency_safe`
4. **优雅终止**：Bash 错误时立即终止兄弟进程
5. **资源清理**：discard() 时确保子进程被终止

## 参考实现

- Claude Code `services/tools/StreamingToolExecutor.ts`
- Claude Code `services/tools/toolOrchestration.ts`

"""
streaming-tool-executor — 流式工具执行器

参考 Claude Code free-code 的 services/tools/StreamingToolExecutor.ts 实现
边接收模型输出边执行工具，并发安全的工具并行执行
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Any, Optional, Generator, AsyncGenerator


# ============================================================================
# 常量与类型
# ============================================================================

class ToolStatus(Enum):
    QUEUED = "queued"
    EXECUTING = "executing"
    COMPLETED = "completed"
    YIELDED = "yielded"


@dataclass
class ToolUseBlock:
    """工具调用块"""
    id: str
    name: str
    input: dict = field(default_factory=dict)
    type: str = "tool_use"


@dataclass
class ToolResult:
    """工具执行结果"""
    tool_use_id: str
    tool_name: str
    content: Any
    is_error: bool = False
    error_message: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class ProgressMessage:
    """进度消息"""
    tool_id: str
    content: str
    timestamp: float = 0


@dataclass
class TrackedTool:
    """被追踪的工具"""
    id: str
    block: ToolUseBlock
    status: ToolStatus = ToolStatus.QUEUED
    is_concurrency_safe: bool = True
    promise: Optional[asyncio.Task] = None
    results: list = field(default_factory=list)
    pending_progress: list[ProgressMessage] = field(default_factory=list)
    error: Optional[Exception] = None


@dataclass
class ToolDefinition:
    """工具定义"""
    name: str
    description: str
    input_schema: dict
    fn: Callable
    is_concurrency_safe: Callable[[dict], bool] = None
    
    def __post_init__(self):
        if self.is_concurrency_safe is None:
            # 默认：所有工具都不假设并发安全
            self.is_concurrency_safe = lambda _: False


# ============================================================================
# 工具执行器
# ============================================================================

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
        tool_definitions: list[ToolDefinition],
        can_use_tool: Callable,
        tool_use_context: dict,
        parent_abort: Optional[asyncio.Event] = None
    ):
        self.tools: list[TrackedTool] = []
        self.tool_definitions = {t.name: t for t in tool_definitions}
        self.can_use_tool = can_use_tool
        self.context = tool_use_context
        self.abort = parent_abort or asyncio.Event()
        self.sibling_abort = asyncio.Event()
        
        self.has_errored = False
        self.errored_tool_description = ""
        self.discarded = False
        
        # 用于唤醒 get_remaining_results
        self._progress_available = asyncio.Future()
        
        # 权限拒绝记录
        self.permission_denials = []
        
        # 已 yield 的工具 ID
        self._yielded_ids = set()
    
    def add_tool(self, block: ToolUseBlock) -> None:
        """
        添加工具到执行队列
        
        Args:
            block: 工具调用块（包含 id, name, input）
        """
        if self.discarded:
            return
        
        tool_def = self.tool_definitions.get(block.name)
        
        if tool_def is None:
            # 工具不存在，生成错误结果
            self._add_error_result(block, f"No such tool available: {block.name}")
            return
        
        # 检查并发安全性
        is_safe = self._check_concurrency_safe(tool_def, block.input)
        
        tracked = TrackedTool(
            id=block.id,
            block=block,
            is_concurrency_safe=is_safe
        )
        
        self.tools.append(tracked)
        
        # 立即尝试启动执行
        self._try_start_execution()
    
    def _check_concurrency_safe(
        self,
        tool_def: ToolDefinition,
        input_data: dict
    ) -> bool:
        """检查工具是否并发安全"""
        try:
            if callable(tool_def.is_concurrency_safe):
                return tool_def.is_concurrency_safe(input_data)
            return bool(tool_def.is_concurrency_safe)
        except Exception:
            return False
    
    def _try_start_execution(self) -> None:
        """尝试启动可执行的工具"""
        if self.discarded:
            return
        
        # 检查是否有非并发工具在执行
        has_exclusive = any(
            t.status == ToolStatus.EXECUTING and not t.is_concurrency_safe
            for t in self.tools
        )
        
        if has_exclusive:
            # 等待独占工具完成
            return
        
        # 统计正在执行的并发安全工具
        executing_safe = sum(
            1 for t in self.tools
            if t.status == ToolStatus.EXECUTING and t.is_concurrency_safe
        )
        
        MAX_CONCURRENT_SAFE = 3
        
        if executing_safe >= MAX_CONCURRENT_SAFE:
            # 达到并发上限
            return
        
        # 启动排队的并发安全工具
        for tool in self.tools:
            if (
                tool.status == ToolStatus.QUEUED and
                tool.is_concurrency_safe and
                executing_safe < MAX_CONCURRENT_SAFE
            ):
                self._start_tool(tool)
                executing_safe += 1
    
    def _start_tool(self, tool: TrackedTool) -> None:
        """启动单个工具的执行"""
        tool.status = ToolStatus.EXECUTING
        
        # 创建工具任务
        tool.promise = asyncio.create_task(
            self._execute_tool(tool)
        )
    
    async def _execute_tool(self, tool: TrackedTool) -> None:
        """执行工具"""
        try:
            # 权限检查（支持同步或异步）
            perm_result = self.can_use_tool(
                tool.block.name,
                tool.block.input,
                self.context
            )
            result = perm_result if hasattr(perm_result, 'behavior') else await perm_result
            
            if result.behavior != 'allow':
                self.permission_denials.append({
                    'tool_name': tool.block.name,
                    'tool_use_id': tool.id,
                    'tool_input': tool.block.input
                })
                tool.results.append(ToolResult(
                    tool_use_id=tool.id,
                    tool_name=tool.block.name,
                    content=f"<tool_use_error>Permission denied: {result.behavior}</tool_use_error>",
                    is_error=True,
                    error_message=f"Permission denied: {result.behavior}"
                ))
                tool.status = ToolStatus.COMPLETED
                self._notify_progress()
                self._try_start_execution()
                return
            
            # 执行工具
            tool_def = self.tool_definitions.get(tool.block.name)
            if tool_def:
                result_content = await tool_def.fn(tool.block.input, self.context)
                tool.results.append(ToolResult(
                    tool_use_id=tool.id,
                    tool_name=tool.block.name,
                    content=result_content,
                    is_error=False
                ))
            
            tool.status = ToolStatus.COMPLETED
            self._notify_progress()
            self._try_start_execution()
            
        except asyncio.CancelledError:
            tool.status = ToolStatus.EXECUTING
            tool.results.append(ToolResult(
                tool_use_id=tool.id,
                tool_name=tool.block.name,
                content="<tool_use_error>Tool execution cancelled</tool_use_error>",
                is_error=True,
                error_message="Cancelled"
            ))
            tool.status = ToolStatus.COMPLETED
            self._notify_progress()
            raise
        
        except Exception as e:
            self.has_errored = True
            self.errored_tool_description = tool.block.name
            tool.error = e
            tool.results.append(ToolResult(
                tool_use_id=tool.id,
                tool_name=tool.block.name,
                content=f"<tool_use_error>{str(e)}</tool_use_error>",
                is_error=True,
                error_message=str(e)
            ))
            tool.status = ToolStatus.COMPLETED
            self._notify_progress()
            
            # 如果是独占工具，终止兄弟进程
            if not tool.is_concurrency_safe:
                self.sibling_abort.set()
            
            self._try_start_execution()
    
    def _add_error_result(self, block: ToolUseBlock, error: str) -> None:
        """添加错误结果"""
        tracked = TrackedTool(
            id=block.id,
            block=block,
            status=ToolStatus.COMPLETED,
            is_concurrency_safe=True,
            results=[ToolResult(
                tool_use_id=block.id,
                tool_name=block.name,
                content=f"<tool_use_error>{error}</tool_use_error>",
                is_error=True,
                error_message=error
            )]
        )
        self.tools.append(tracked)
        self._notify_progress()
    
    def _notify_progress(self) -> None:
        """通知有新的进度或结果"""
        if not self._progress_available.done():
            self._progress_available.set_result(None)
        self._progress_available = asyncio.Future()
    
    def get_completed_results(self) -> Generator[ToolResult, None, None]:
        """
        获取已完成的结果（同步版本）
        
        Yields:
            ToolResult: 按顺序返回已完成的结果
        """
        for tool in self.tools:
            if tool.id in self._yielded_ids:
                continue
            
            if tool.status in (ToolStatus.COMPLETED, ToolStatus.YIELDED):
                self._yielded_ids.add(tool.id)
                for result in tool.results:
                    yield result
            
            # 进度消息也立即 yield
            for progress in tool.pending_progress:
                yield ToolResult(
                    tool_use_id=tool.id,
                    tool_name=tool.block.name,
                    content=f"[progress] {progress.content}",
                    is_error=False
                )
            tool.pending_progress.clear()
    
    async def get_completed_results_async(self) -> AsyncGenerator[ToolResult, None]:
        """
        获取已完成的结果（异步版本，支持等待新结果）
        
        Yields:
            ToolResult: 按顺序返回已完成的结果
        """
        while True:
            # 检查是否有新结果
            for tool in self.tools:
                if tool.id not in self._yielded_ids:
                    if tool.status in (ToolStatus.COMPLETED, ToolStatus.YIELDED):
                        self._yielded_ids.add(tool.id)
                        for result in tool.results:
                            yield result
                    
                    # 进度消息
                    while tool.pending_progress:
                        progress = tool.pending_progress.pop(0)
                        yield ToolResult(
                            tool_use_id=tool.id,
                            tool_name=tool.block.name,
                            content=f"[progress] {progress.content}",
                            is_error=False
                        )
            
            # 检查是否全部完成
            if all(t.status in (ToolStatus.COMPLETED, ToolStatus.YIELDED) for t in self.tools):
                break
            
            # 等待新结果
            await self._progress_available
    
    async def get_remaining_results(self) -> AsyncGenerator[ToolResult, None]:
        """
        获取剩余结果（等待所有工具完成）
        
        Yields:
            ToolResult: 返回所有剩余的结果
        """
        # 等待所有工具完成
        for tool in self.tools:
            if tool.promise and not tool.promise.done():
                try:
                    await tool.promise
                except asyncio.CancelledError:
                    pass
        
        # yield 所有未 yield 的结果
        for tool in self.tools:
            if tool.id not in self._yielded_ids:
                self._yielded_ids.add(tool.id)
                for result in tool.results:
                    yield result
    
    def discard(self) -> None:
        """
        丢弃所有待执行和执行中的工具
        
        Called when streaming fallback occurs and results from the 
        failed attempt should be abandoned.
        """
        self.discarded = True
        
        # 取消所有未完成的任务
        for tool in self.tools:
            if tool.promise and not tool.promise.done():
                tool.promise.cancel()
        
        # 标记为已丢弃
        for tool in self.tools:
            tool.status = ToolStatus.YIELDED
    
    def get_status_summary(self) -> dict:
        """获取状态摘要"""
        return {
            'total_tools': len(self.tools),
            'queued': sum(1 for t in self.tools if t.status == ToolStatus.QUEUED),
            'executing': sum(1 for t in self.tools if t.status == ToolStatus.EXECUTING),
            'completed': sum(1 for t in self.tools if t.status == ToolStatus.COMPLETED),
            'has_errored': self.has_errored,
            'discarded': self.discarded
        }


# ============================================================================
# 模拟工具定义
# ============================================================================

def create_simulated_tools() -> list[ToolDefinition]:
    """创建模拟工具定义（用于测试）"""
    
    async def read_file(input: dict, context: dict) -> str:
        """模拟读取文件"""
        await asyncio.sleep(0.5)  # 模拟 I/O
        return f"Content of {input.get('file_path', 'unknown')}"
    
    async def bash(input: dict, context: dict) -> str:
        """模拟执行命令"""
        await asyncio.sleep(1.0)  # 模拟执行
        return f"Executed: {input.get('command', '')}"
    
    async def web_search(input: dict, context: dict) -> str:
        """模拟网络搜索"""
        await asyncio.sleep(0.8)
        return f"Search results for: {input.get('query', '')}"
    
    return [
        ToolDefinition(
            name="Read",
            description="Read file contents",
            input_schema={
                'type': 'object',
                'properties': {
                    'file_path': {'type': 'string'}
                }
            },
            fn=read_file,
            is_concurrency_safe=lambda _: True  # 读取是并发安全的
        ),
        ToolDefinition(
            name="Bash",
            description="Execute shell command",
            input_schema={
                'type': 'object',
                'properties': {
                    'command': {'type': 'string'}
                }
            },
            fn=bash,
            is_concurrency_safe=lambda _: False  # Bash 不是并发安全的
        ),
        ToolDefinition(
            name="WebSearch",
            description="Search the web",
            input_schema={
                'type': 'object',
                'properties': {
                    'query': {'type': 'string'}
                }
            },
            fn=web_search,
            is_concurrency_safe=lambda _: True  # 网络请求是并发安全的
        ),
    ]


# ============================================================================
# 使用示例
# ============================================================================

async def example_usage():
    """使用示例"""
    
    # 创建执行器
    tools = create_simulated_tools()
    executor = StreamingToolExecutor(
        tool_definitions=tools,
        can_use_tool=lambda name, input, ctx: type('Result', (), {'behavior': 'allow'})(),
        tool_use_context={}
    )
    
    # 模拟流式添加工具
    test_blocks = [
        ToolUseBlock(id="1", name="Read", input={"file_path": "a.txt"}),
        ToolUseBlock(id="2", name="WebSearch", input={"query": "test"}),
        ToolUseBlock(id="3", name="Read", input={"file_path": "b.txt"}),
        ToolUseBlock(id="4", name="Bash", input={"command": "echo hi"}),
    ]
    
    for block in test_blocks:
        executor.add_tool(block)
    
    # 获取结果
    print("Results:")
    async for result in executor.get_completed_results_async():
        print(f"  [{result.tool_name}] {result.content[:50]}...")
    
    print("\nStatus:", executor.get_status_summary())


if __name__ == "__main__":
    asyncio.run(example_usage())

"""
context-compact — 上下文自动压缩系统

参考 Claude Code free-code 的 services/compact/ 实现
"""

import os
import re
import json
from dataclasses import dataclass, field
from typing import Callable, Optional
from enum import Enum


# ============================================================================
# 常量配置
# ============================================================================

# 保留给输出的 token 空间（基于 p99.99 压缩输出 17,387 tokens）
MAX_OUTPUT_TOKENS_FOR_SUMMARY = 20_000

# 各阈值配置
AUTOCOMPACT_BUFFER_TOKENS = 13_000
WARNING_THRESHOLD_BUFFER_TOKENS = 20_000
ERROR_THRESHOLD_BUFFER_TOKENS = 20_000
MANUAL_COMPACT_BUFFER_TOKENS = 3_000

# 连续失败后停止重试
MAX_CONSECUTIVE_AUTOCOMPACT_FAILURES = 3

# 可压缩的工具类型
COMPACTABLE_TOOLS = {
    'Read', 'Bash', 'Grep', 'Glob',
    'WebSearch', 'WebFetch', 'Edit', 'Write'
}

# 保留的锚点消息类型（不可压缩）
ANCHOR_MESSAGE_TYPES = {
    'user_decision',      # 用户做出的重大决策
    'trade_execution',    # 交易执行记录
    'risk_alert',         # 风控警报
    'strategy_change',    # 策略变更
    'compact_boundary'    # 压缩边界标记
}


# ============================================================================
# 数据结构
# ============================================================================

class CompactionLevel(Enum):
    NONE = "none"
    MICRO = "micro"       # 微压缩（清除旧工具结果）
    SNIP = "snip"         # 片段裁剪
    AUTO = "auto"         # 自动压缩（生成摘要）


@dataclass
class TokenState:
    """Token 使用状态"""
    current_tokens: int
    context_window: int
    effective_window: int
    auto_compact_threshold: int
    warning_threshold: int
    error_threshold: int
    percent_left: int
    is_above_warning_threshold: bool
    is_above_error_threshold: bool
    is_above_auto_compact_threshold: bool
    is_at_blocking_limit: bool


@dataclass
class CompactionResult:
    """压缩结果"""
    was_compacted: bool
    level: CompactionLevel
    pre_compact_token_count: int
    post_compact_token_count: int
    tokens_freed: int = 0
    summary_messages: list = field(default_factory=list)
    attachments: list = field(default_factory=list)
    hook_results: list = field(default_factory=list)
    compaction_usage: dict = field(default_factory=dict)
    consecutive_failures: int = 0
    error: Optional[str] = None


@dataclass 
class Message:
    """简化版消息结构"""
    type: str  # 'user' | 'assistant' | 'system'
    role: str = 'user'
    content: list = field(default_factory=list)
    tool_calls: list = field(default_factory=list)
    tool_results: list = field(default_factory=list)
    subtype: str = ''
    metadata: dict = field(default_factory=dict)


# ============================================================================
# 工具函数
# ============================================================================

def rough_token_count(text: str) -> int:
    """粗略估算 token 数（中英文混合）"""
    # 中文约 2 chars/token，英文约 4 chars/token
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    english_chars = len(text) - chinese_chars
    return int(chinese_chars / 2 + english_chars / 4)


def estimate_message_tokens(message: Message) -> int:
    """估算单条消息的 token 数"""
    count = 0
    
    for block in message.content:
        if isinstance(block, dict):
            if block.get('type') == 'text':
                count += rough_token_count(block.get('text', ''))
            elif block.get('type') == 'tool_result':
                count += rough_token_count(str(block.get('content', '')))
            elif block.get('type') == 'image':
                count += 2000  # 图片约 2000 tokens
            elif block.get('type') == 'thinking':
                count += rough_token_count(block.get('thinking', ''))
        elif isinstance(block, str):
            count += rough_token_count(block)
    
    return count


def estimate_messages_tokens(messages: list[Message]) -> int:
    """估算多条消息的 token 数"""
    return sum(estimate_message_tokens(msg) for msg in messages)


def is_anchor_message(message: Message) -> bool:
    """判断是否为锚点消息（不可压缩）"""
    if message.type == 'system' and message.subtype in ANCHOR_MESSAGE_TYPES:
        return True
    if message.metadata.get('is_anchor'):
        return True
    return False


# ============================================================================
# 上下文压缩器
# ============================================================================

class ContextCompactor:
    """
    上下文自动压缩器
    
    三层压缩机制:
    1. Microcompact - 清除旧工具结果
    2. Snip - 裁剪消息片段  
    3. AutoCompact - 生成对话摘要
    """
    
    def __init__(
        self,
        context_window: int = 128_000,
        auto_compact_enabled: bool = True,
        warning_buffer: int = WARNING_THRESHOLD_BUFFER_TOKENS,
        autocompact_buffer: int = AUTOCOMPACT_BUFFER_TOKENS,
        manual_buffer: int = MANUAL_COMPACT_BUFFER_TOKENS
    ):
        self.context_window = context_window
        self.auto_compact_enabled = auto_compact_enabled
        self.warning_buffer = warning_buffer
        self.autocompact_buffer = autocompact_buffer
        self.manual_buffer = manual_buffer
        
        # 连续失败计数
        self._consecutive_failures = 0
        
        # 回调函数
        self._on_compaction: list[Callable[[CompactionResult], None]] = []
    
    @property
    def effective_window(self) -> int:
        """有效上下文窗口（减去保留的输出空间）"""
        return self.context_window - MAX_OUTPUT_TOKENS_FOR_SUMMARY
    
    @property
    def auto_compact_threshold(self) -> int:
        """自动压缩阈值"""
        return self.effective_window - self.autocompact_buffer
    
    @property
    def warning_threshold(self) -> int:
        """警告阈值"""
        return self.effective_window - self.warning_buffer
    
    @property
    def error_threshold(self) -> int:
        """错误阈值"""
        return self.effective_window - ERROR_THRESHOLD_BUFFER_TOKENS
    
    @property
    def blocking_limit(self) -> int:
        """阻塞限制"""
        return self.effective_window - self.manual_buffer
    
    def get_token_state(self, messages: list[Message]) -> TokenState:
        """获取当前 token 状态"""
        current_tokens = estimate_messages_tokens(messages)
        
        percent_left = max(0, round(
            (self.auto_compact_threshold - current_tokens) / self.auto_compact_threshold * 100
        ))
        
        return TokenState(
            current_tokens=current_tokens,
            context_window=self.context_window,
            effective_window=self.effective_window,
            auto_compact_threshold=self.auto_compact_threshold,
            warning_threshold=self.warning_threshold,
            error_threshold=self.error_threshold,
            percent_left=percent_left,
            is_above_warning_threshold=current_tokens >= self.warning_threshold,
            is_above_error_threshold=current_tokens >= self.error_threshold,
            is_above_auto_compact_threshold=current_tokens >= self.auto_compact_threshold,
            is_at_blocking_limit=current_tokens >= self.blocking_limit
        )
    
    def should_auto_compact(self, messages: list[Message]) -> bool:
        """检查是否应该自动压缩"""
        if not self.auto_compact_enabled:
            return False
        
        if self._consecutive_failures >= MAX_CONSECUTIVE_AUTOCOMPACT_FAILURES:
            return False
        
        state = self.get_token_state(messages)
        return state.is_above_auto_compact_threshold
    
    def microcompact(self, messages: list[Message]) -> CompactionResult:
        """
        微压缩：清除旧工具结果，保留 cache 引用
        """
        pre_count = estimate_messages_tokens(messages)
        compacted_messages = []
        freed_tokens = 0
        
        for msg in messages:
            if msg.type == 'system':
                compacted_messages.append(msg)
                continue
            
            if msg.type == 'assistant':
                compacted_messages.append(msg)
                continue
            
            if msg.type == 'user':
                new_content = []
                for block in msg.content:
                    if isinstance(block, dict):
                        if block.get('type') == 'tool_result':
                            tool_name = block.get('tool_name', '')
                            if tool_name in COMPACTABLE_TOOLS:
                                # 替换为 cache 引用
                                old_content = str(block.get('content', ''))
                                freed_tokens += rough_token_count(old_content)
                                new_content.append({
                                    'type': 'text',
                                    'text': '[Old tool result content cleared]'
                                })
                            else:
                                new_content.append(block)
                        else:
                            new_content.append(block)
                    else:
                        new_content.append(block)
                
                msg.content = new_content
                compacted_messages.append(msg)
            else:
                compacted_messages.append(msg)
        
        post_count = estimate_messages_tokens(compacted_messages)
        
        return CompactionResult(
            was_compacted=freed_tokens > 0,
            level=CompactionLevel.MICRO,
            pre_compact_token_count=pre_count,
            post_compact_token_count=post_count,
            tokens_freed=freed_tokens,
            summary_messages=compacted_messages
        )
    
    def snip(
        self,
        messages: list[Message],
        start_index: int = 0,
        end_index: Optional[int] = None
    ) -> CompactionResult:
        """
        片段裁剪：移除指定范围的消息
        
        Args:
            messages: 消息列表
            start_index: 裁剪起始索引
            end_index: 裁剪结束索引（None = 到倒数第5条）
        """
        if end_index is None:
            end_index = len(messages) - 5  # 保留最后5条
        
        pre_count = estimate_messages_tokens(messages)
        
        # 找到锚点消息（不可裁剪）
        anchor_indices = set()
        for i, msg in enumerate(messages):
            if is_anchor_message(msg):
                anchor_indices.add(i)
        
        # 构建裁剪范围（排除锚点）
        snip_range = set(range(start_index, end_index)) - anchor_indices
        
        compacted_messages = []
        for i, msg in enumerate(messages):
            if i in snip_range:
                continue
            compacted_messages.append(msg)
        
        post_count = estimate_messages_tokens(compacted_messages)
        
        return CompactionResult(
            was_compacted=len(snip_range) > 0,
            level=CompactionLevel.SNIP,
            pre_compact_token_count=pre_count,
            post_compact_token_count=post_count,
            tokens_freed=pre_count - post_count,
            summary_messages=compacted_messages
        )
    
    async def auto_compact(
        self,
        messages: list[Message],
        llm_client=None,
        compact_prompt: Optional[str] = None
    ) -> CompactionResult:
        """
        自动压缩：调用模型生成对话摘要
        
        Args:
            messages: 消息列表
            llm_client: LLM 客户端（用于生成摘要）
            compact_prompt: 自定义压缩提示
        """
        if not self.auto_compact_enabled:
            return CompactionResult(
                was_compacted=False,
                level=CompactionLevel.NONE,
                pre_compact_token_count=estimate_messages_tokens(messages),
                post_compact_token_count=estimate_messages_tokens(messages),
                error="Auto-compact disabled"
            )
        
        pre_count = estimate_messages_tokens(messages)
        
        # 如果 LLM 客户端不可用，执行微压缩作为后备
        if llm_client is None:
            result = self.microcompact(messages)
            result.level = CompactionLevel.AUTO
            return result
        
        try:
            # 构建压缩提示
            if compact_prompt is None:
                compact_prompt = self._build_compact_prompt(messages)
            
            # 调用模型生成摘要
            response = await llm_client.generate(
                compact_prompt,
                max_tokens=2000,
                system="你是一个对话压缩助手。请简洁地总结对话要点，保留关键信息。"
            )
            
            # 构建摘要消息
            summary_msg = Message(
                type='system',
                role='system',
                subtype='compact_summary',
                content=[{'type': 'text', 'text': response}],
                metadata={'original_message_count': len(messages)}
            )
            
            # 保留最近的锚点消息（最后5条）
            recent_messages = messages[-5:]
            compacted = [summary_msg] + recent_messages
            
            post_count = estimate_messages_tokens(compacted)
            
            # 重置连续失败计数
            self._consecutive_failures = 0
            
            result = CompactionResult(
                was_compacted=True,
                level=CompactionLevel.AUTO,
                pre_compact_token_count=pre_count,
                post_compact_token_count=post_count,
                tokens_freed=pre_count - post_count,
                summary_messages=compacted
            )
            
            # 触发回调
            for callback in self._on_compaction:
                callback(result)
            
            return result
            
        except Exception as e:
            self._consecutive_failures += 1
            return CompactionResult(
                was_compacted=False,
                level=CompactionLevel.AUTO,
                pre_compact_token_count=pre_count,
                post_compact_token_count=pre_count,
                consecutive_failures=self._consecutive_failures,
                error=str(e)
            )
    
    def _build_compact_prompt(self, messages: list[Message]) -> str:
        """构建压缩提示"""
        # 提取关键信息
        conversation_summary = []
        for msg in messages[:-5]:  # 排除最近5条
            if msg.type == 'user':
                content = self._extract_text_content(msg.content)
                if content:
                    conversation_summary.append(f"用户: {content[:200]}")
            elif msg.type == 'assistant':
                content = self._extract_text_content(msg.content)
                if content:
                    conversation_summary.append(f"助手: {content[:200]}")
        
        return f"""请简洁地总结以下对话的要点，保留关键信息、决策和结论：

{'---'.join(conversation_summary[-20:])}  # 最多20条

要求：
1. 保留所有关键决策和结论
2. 保留重要的数值和数据
3. 用简洁的bullet points组织
4. 不超过500字"""
    
    def _extract_text_content(self, content: list) -> str:
        """从消息内容中提取文本"""
        texts = []
        for block in content:
            if isinstance(block, dict):
                if block.get('type') == 'text':
                    texts.append(block.get('text', ''))
            elif isinstance(block, str):
                texts.append(block)
        return ' '.join(texts)
    
    def register_callback(self, callback: Callable[[CompactionResult], None]):
        """注册压缩完成回调"""
        self._on_compaction.append(callback)
    
    def clear_callbacks(self):
        """清除所有回调"""
        self._on_compaction.clear()


# ============================================================================
# 便捷函数
# ============================================================================

def create_compactor(
    context_window: int = 128_000,
    auto_compact_enabled: bool = True
) -> ContextCompactor:
    """创建上下文压缩器"""
    # 检查环境变量覆盖
    if os.environ.get('DISABLE_COMPACT'):
        auto_compact_enabled = False
    
    return ContextCompactor(
        context_window=context_window,
        auto_compact_enabled=auto_compact_enabled
    )

"""
agent-nudge — Agent 主动记忆与技能进化系统

融合 Hermes Agent 的三大特性:
1. Agent Nudges — 主动提醒保存重要信息
2. Skills Hub — 开放技能市场
3. Skills Self-Improvement — 技能自进化

源自 NousResearch/hermes-agent 源码
"""

import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

# ============================================================================
# 常量
# ============================================================================

SKILLS_DIR = Path.home() / ".openclaw" / "skills"
HUB_DIR = SKILLS_DIR / ".hub"
QUARANTINE_DIR = HUB_DIR / "quarantine"
AUDIT_LOG = HUB_DIR / "audit.log"

# 信任等级
class TrustLevel(Enum):
    BUILTIN = "builtin"      # 官方内置
    TRUSTED = "trusted"     # 认证开发者
    COMMUNITY = "community"  # 社区贡献


# ============================================================================
# 数据结构
# ============================================================================

@dataclass
class SkillMeta:
    """技能元数据"""
    name: str
    description: str
    source: str           # "official", "github", "community"
    identifier: str       # source-specific ID
    trust_level: TrustLevel
    repo: Optional[str] = None
    path: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    author: str = ""
    version: str = "1.0.0"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class SkillBundle:
    """技能包"""
    name: str
    files: dict[str, str]  # path -> content
    source: str
    identifier: str
    trust_level: TrustLevel
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def get_hash(self) -> str:
        """计算内容哈希"""
        content = json.dumps(self.files, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class ScanResult:
    """安全扫描结果"""
    is_safe: bool
    score: float = 1.0
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    
    @property
    def is_ask(self) -> bool:
        """需要用户确认"""
        return not self.is_safe and len(self.warnings) > 0


@dataclass
class NudgeTrigger:
    """Nudge 触发条件"""
    type: str  # "memory" / "skill"
    reason: str
    content: str
    confidence: float  # 0.0 - 1.0
    timestamp: datetime = field(default_factory=datetime.now)


# ============================================================================
# 安全扫描
# ============================================================================

class SkillsGuard:
    """技能安全扫描器"""
    
    # 可信仓库
    TRUSTED_REPOS = {
        "NousResearch/hermes-agent",
        "anthropics/claude-code",
        "openclaw/openclaw-skills",
        "longman888/openclaw-s-free-code-skills"
    }
    
    # 危险模式
    DANGEROUS_PATTERNS = [
        r"eval\s*\(",           # eval() 执行
        r"exec\s*\(",           # exec() 执行
        r"__import__\s*\(",      # 动态导入
        r"os\.system\s*\(",      # 系统命令
        r"subprocess\s*\(",      # 子进程
        r"requests\.get\s*\(",   # 网络请求
        r"open\s*\([^w]",       # 文件写入
        r"shutil\.rmtree\s*\(", # 目录删除
    ]
    
    def __init__(self, skills_dir: Path = SKILLS_DIR):
        self.skills_dir = skills_dir
        self.quarantine_dir = QUARANTINE_DIR
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        """确保目录存在"""
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
    
    def scan_file(self, file_path: Path) -> ScanResult:
        """扫描单个文件"""
        issues = []
        warnings = []
        
        try:
            content = file_path.read_text(encoding="utf-8")
            
            # 检查危险模式
            for pattern in self.DANGEROUS_PATTERNS:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    warnings.append(f"Found dangerous pattern: {pattern}")
            
            # 检查 API key 泄露
            if re.search(r"api[_-]?key\s*=\s*['\"][a-zA-Z0-9]{20,}", content, re.IGNORECASE):
                warnings.append("Possible API key detected")
            
            # 检查 base64 编码的可执行内容
            if re.search(r"base64\.b64decode\s*\(", content):
                warnings.append("Base64 decode detected")
            
            # 计算安全分数
            score = 1.0 - (len(warnings) * 0.2) - (len(issues) * 0.5)
            score = max(0.0, min(1.0, score))
            
            return ScanResult(
                is_safe=len(issues) == 0 and score >= 0.5,
                score=score,
                issues=issues,
                warnings=warnings
            )
            
        except Exception as e:
            return ScanResult(
                is_safe=False,
                score=0.0,
                issues=[f"Scan error: {str(e)}"]
            )
    
    def scan_skill(self, skill_dir: Path) -> ScanResult:
        """扫描整个技能目录"""
        all_issues = []
        all_warnings = []
        total_score = 0
        file_count = 0
        
        for file_path in skill_dir.rglob("*"):
            if file_path.is_file() and file_path.suffix in [".py", ".md", ".yaml", ".json", ".sh"]:
                result = self.scan_file(file_path)
                all_issues.extend(result.issues)
                all_warnings.extend(result.warnings)
                total_score += result.score
                file_count += 1
        
        if file_count == 0:
            return ScanResult(is_safe=True, score=1.0)
        
        avg_score = total_score / file_count
        
        return ScanResult(
            is_safe=len(all_issues) == 0 and avg_score >= 0.5,
            score=avg_score,
            issues=all_issues,
            warnings=all_warnings
        )
    
    def quarantine(self, skill_dir: Path, reason: str) -> Path:
        """隔离可疑技能"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        quarantine_name = f"{skill_dir.name}_quarantined_{timestamp}"
        quarantine_path = self.quarantine_dir / quarantine_name
        
        shutil.move(str(skill_dir), str(quarantine_path))
        
        # 记录审计日志
        self._log_audit("QUARANTINE", skill_dir.name, reason)
        
        return quarantine_path
    
    def _log_audit(self, action: str, skill_name: str, reason: str):
        """记录审计日志"""
        timestamp = datetime.now(timezone.utc).isoformat()
        log_entry = f"{timestamp} | {action} | {skill_name} | {reason}\n"
        
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(log_entry)


# ============================================================================
# Skills Hub
# ============================================================================

class SkillsHub:
    """技能市场"""
    
    def __init__(self, skills_dir: Path = SKILLS_DIR, guard: Optional[SkillsGuard] = None):
        self.skills_dir = skills_dir
        self.guard = guard or SkillsGuard(skills_dir)
        self.guard._ensure_dirs()
    
    def bundle(self, skill_name: str) -> SkillBundle:
        """打包技能"""
        skill_dir = self.skills_dir / skill_name
        
        if not skill_dir.exists():
            raise ValueError(f"Skill not found: {skill_name}")
        
        files = {}
        for file_path in skill_dir.rglob("*"):
            if file_path.is_file():
                rel_path = file_path.relative_to(skill_dir)
                files[str(rel_path)] = file_path.read_text(encoding="utf-8")
        
        return SkillBundle(
            name=skill_name,
            files=files,
            source="local",
            identifier=f"local/{skill_name}",
            trust_level=TrustLevel.TRUSTED  # 本地技能默认可信
        )
    
    def publish(self, bundle: SkillBundle, hub_url: str) -> bool:
        """发布技能到市场"""
        # 扫描安全
        scan_result = self._scan_bundle(bundle)
        
        if not scan_result.is_safe:
            self.guard.quarantine(
                self.skills_dir / bundle.name,
                f"Security scan failed: {scan_result.issues}"
            )
            return False
        
        # TODO: 实现实际的发布逻辑
        # 调用 hub_url API 上传 bundle
        
        self.guard._log_audit("PUBLISH", bundle.name, f"Published to {hub_url}")
        return True
    
    def install(self, meta: SkillMeta) -> bool:
        """从市场安装技能"""
        # TODO: 实现实际的安装逻辑
        # 从 meta.source 下载 bundle
        # 安全扫描
        # 安装到 skills_dir
        
        self.guard._log_audit("INSTALL", meta.name, f"From {meta.source}")
        return True
    
    def search(self, query: str, tags: list[str] = None) -> list[SkillMeta]:
        """搜索技能"""
        # TODO: 实现实际的搜索逻辑
        # 调用 hub API 搜索
        
        return []
    
    def _scan_bundle(self, bundle: SkillBundle) -> ScanResult:
        """扫描技能包"""
        # 创建临时目录
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_skill = Path(tmpdir) / bundle.name
            tmp_skill.mkdir()
            
            # 写入文件
            for path, content in bundle.files.items():
                file_path = tmp_skill / path
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content, encoding="utf-8")
            
            # 扫描
            return self.guard.scan_skill(tmp_skill)


# ============================================================================
# Skill 管理器
# ============================================================================

class SkillManager:
    """技能管理器 — 创建、更新、删除技能"""
    
    MAX_NAME_LENGTH = 64
    MAX_DESCRIPTION_LENGTH = 1024
    MAX_CONTENT_CHARS = 100_000
    
    VALID_NAME_RE = re.compile(r'^[a-z0-9][a-z0-9._-]*$')
    
    def __init__(self, skills_dir: Path = SKILLS_DIR, guard: Optional[SkillsGuard] = None):
        self.skills_dir = skills_dir
        self.guard = guard or SkillsGuard(skills_dir)
        self.guard._ensure_dirs()
    
    def create(
        self,
        name: str,
        description: str,
        content: str,
        tags: list[str] = None,
        author: str = "OpenClaw Agent"
    ) -> tuple[bool, str]:
        """创建新技能"""
        # 验证名称
        if len(name) > self.MAX_NAME_LENGTH:
            return False, f"Name too long (max {self.MAX_NAME_LENGTH})"
        
        if not self.VALID_NAME_RE.match(name):
            return False, "Invalid name format (use a-z, 0-9, ., -, _)"
        
        if len(description) > self.MAX_DESCRIPTION_LENGTH:
            return False, f"Description too long (max {self.MAX_DESCRIPTION_LENGTH})"
        
        # 创建目录
        skill_dir = self.skills_dir / name
        if skill_dir.exists():
            return False, f"Skill already exists: {name}"
        
        skill_dir.mkdir(parents=True, exist_ok=True)
        
        # 写入 SKILL.md
        skill_md = skill_dir / "SKILL.md"
        frontmatter = {
            "name": name,
            "description": description,
            "tags": tags or [],
            "author": author,
            "version": "1.0.0",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        yaml_content = yaml_dump(frontmatter)
        skill_md.write_text(f"---\n{yaml_content}---\n\n{content}", encoding="utf-8")
        
        # 安全扫描
        scan_result = self.guard.scan_skill(skill_dir)
        
        if not scan_result.is_safe:
            shutil.rmtree(skill_dir)
            return False, f"Security scan failed: {scan_result.issues}"
        
        if scan_result.warnings:
            logging.warning(f"Skill {name} has warnings: {scan_result.warnings}")
        
        self.guard._log_audit("CREATE", name, "New skill created by agent")
        
        return True, f"Skill created: {name}"
    
    def update(
        self,
        name: str,
        content: str = None,
        description: str = None,
        tags: list[str] = None
    ) -> tuple[bool, str]:
        """更新现有技能"""
        skill_dir = self.skills_dir / name
        
        if not skill_dir.exists():
            return False, f"Skill not found: {name}"
        
        skill_md = skill_dir / "SKILL.md"
        
        if not skill_md.exists():
            return False, f"SKILL.md not found in {name}"
        
        # 读取现有内容
        frontmatter, body = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
        
        # 更新字段
        if description:
            frontmatter["description"] = description
        if tags:
            frontmatter["tags"] = tags
        
        frontmatter["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        # 更新内容
        new_content = f"---\n{yaml_dump(frontmatter)}---\n\n{content or body}"
        skill_md.write_text(new_content, encoding="utf-8")
        
        # 安全扫描
        scan_result = self.guard.scan_skill(skill_dir)
        
        if not scan_result.is_safe:
            return False, f"Security scan failed: {scan_result.issues}"
        
        self.guard._log_audit("UPDATE", name, "Skill updated by agent")
        
        return True, f"Skill updated: {name}"
    
    def delete(self, name: str) -> tuple[bool, str]:
        """删除技能"""
        skill_dir = self.skills_dir / name
        
        if not skill_dir.exists():
            return False, f"Skill not found: {name}"
        
        # 检查是否是内置技能
        if (skill_dir / ".builtin").exists():
            return False, "Cannot delete builtin skill"
        
        shutil.rmtree(skill_dir)
        self.guard._log_audit("DELETE", name, "Skill deleted by agent")
        
        return True, f"Skill deleted: {name}"
    
    def list_skills(self) -> list[dict[str, Any]]:
        """列出所有技能"""
        skills = []
        
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            
            frontmatter, _ = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
            
            skills.append({
                "name": frontmatter.get("name", skill_dir.name),
                "description": frontmatter.get("description", ""),
                "tags": frontmatter.get("tags", []),
                "author": frontmatter.get("author", ""),
                "version": frontmatter.get("version", "1.0.0"),
                "path": str(skill_dir)
            })
        
        return skills


# ============================================================================
# Agent Nudge 系统
# ============================================================================

class AgentNudge:
    """
    Agent 主动提醒系统
    
    在后台线程中检查对话，触发:
    1. 记忆保存 (memory_save)
    2. 技能创建/更新 (skill_create/update)
    """
    
    MEMORY_REVIEW_PROMPT = """Review the conversation above and consider saving to memory if appropriate.

Focus on:
1. Has the user revealed things about themselves — their persona, desires, preferences, or personal details worth remembering?
2. Has the user expressed expectations about how you should behave, their work style, or ways they want you to operate?

If something stands out, save it using the memory tool.
If nothing is worth saving, just say 'Nothing to save.' and stop."""

    SKILL_REVIEW_PROMPT = """Review the conversation above and consider saving or updating a skill if appropriate.

Focus on: was a non-trivial approach used to complete a task that required trial and error, or changing course due to experiential findings along the way, or did the user expect or desire a different method or outcome?

If a relevant skill already exists, update it with what you learned.
Otherwise, create a new skill if the approach is reusable.
If nothing is worth saving, just say 'Nothing to save.' and stop."""

    def __init__(
        self,
        memory_callback: Callable[[str], Any] = None,
        skill_callback: Callable[[str, str], Any] = None,
        nudge_interval: int = 10  # 每 N 轮对话触发一次
    ):
        self.memory_callback = memory_callback
        self.skill_callback = skill_callback
        self.nudge_interval = nudge_interval
        self.turn_count = 0
        self._callbacks = []
    
    def register_memory_callback(self, callback: Callable[[str], Any]):
        """注册记忆保存回调"""
        self._callbacks.append(("memory", callback))
    
    def register_skill_callback(self, callback: Callable[[str, str], Any]):
        """注册技能更新回调"""
        self._callbacks.append(("skill", callback))
    
    def on_turn_end(self, messages: list) -> Optional[NudgeTrigger]:
        """
        每次对话结束时调用
        
        Returns: NudgeTrigger if nudge was spawned, None otherwise
        """
        self.turn_count += 1
        
        if self.turn_count % self.nudge_interval != 0:
            return None
        
        # 检查是否应该触发 nudge
        trigger = self._check_triggers(messages)
        
        if trigger:
            self._spawn_background_review(messages, trigger)
        
        return trigger
    
    def _check_triggers(self, messages: list) -> Optional[NudgeTrigger]:
        """检查触发条件"""
        # 简单实现：检查是否有用户输入
        user_inputs = [
            msg.get("content", "") 
            for msg in messages 
            if msg.get("role") == "user"
        ]
        
        if len(user_inputs) < 3:
            return None
        
        # 检查是否有关键词
        memory_keywords = ["我喜欢", "我偏好", "记住", "偏好", "不要", "总是", "从来不", "希望", "期望"]
        skill_keywords = ["试试", "尝试", "方法", "这样不行", "换一种", "改进", "换个"]
        
        # 获取最近 N 条用户消息
        recent_count = min(5, len(user_inputs))
        last_user = " ".join(user_inputs[-recent_count:]) if user_inputs else ""
        
        # 记忆触发
        for keyword in memory_keywords:
            if keyword in last_user:
                return NudgeTrigger(
                    type="memory",
                    reason=f"Keyword trigger: {keyword}",
                    content=self.MEMORY_REVIEW_PROMPT,
                    confidence=0.7
                )
        
        # 技能触发
        for keyword in skill_keywords:
            if keyword in last_user:
                return NudgeTrigger(
                    type="skill",
                    reason=f"Keyword trigger: {keyword}",
                    content=self.SKILL_REVIEW_PROMPT,
                    confidence=0.6
                )
        
        return None
    
    def _spawn_background_review(self, messages: list, trigger: NudgeTrigger):
        """启动后台审查线程"""
        def run_review():
            try:
                # TODO: 实现实际的 LLM 调用来审查对话
                # 这里简化实现
                
                # 通知回调
                for ntype, callback in self._callbacks:
                    if ntype == trigger.type:
                        callback(trigger.content)
                        
            except Exception as e:
                logging.debug(f"Background review failed: {e}")
        
        thread = threading.Thread(target=run_review, daemon=True, name="bg-nudge")
        thread.start()


# ============================================================================
# 工具函数
# ============================================================================

def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """解析 YAML frontmatter"""
    if not content.startswith("---"):
        return {}, content
    
    end_match = re.search(r"\n---\s*\n", content[3:])
    if not end_match:
        return {}, content
    
    yaml_content = content[3:end_match.start() + 3]
    body = content[end_match.end() + 3:]
    
    try:
        import yaml
        frontmatter = yaml.safe_load(yaml_content) or {}
    except Exception:
        frontmatter = {}
    
    return frontmatter, body


def yaml_dump(data: dict) -> str:
    """安全的 YAML 序列化"""
    try:
        import yaml
        return yaml.dump(data, allow_unicode=True, default_flow_style=False)
    except Exception:
        # Fallback
        lines = []
        for k, v in data.items():
            if isinstance(v, list):
                lines.append(f"{k}:")
                for item in v:
                    lines.append(f"  - {item}")
            else:
                lines.append(f"{k}: {v}")
        return "\n".join(lines)


# ============================================================================
# 便捷函数
# ============================================================================

def create_nudge_system(
    memory_callback: Callable[[str], Any] = None,
    skill_callback: Callable[[str, str], Any] = None
) -> AgentNudge:
    """创建 Nudge 系统"""
    return AgentNudge(
        memory_callback=memory_callback,
        skill_callback=skill_callback
    )


def create_skill_manager() -> SkillManager:
    """创建技能管理器"""
    return SkillManager()


def create_skills_hub() -> SkillsHub:
    """创建技能市场"""
    return SkillsHub()

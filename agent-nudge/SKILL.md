---
name: agent-nudge
description: |
  Agent主动记忆和技能进化系统 — 融合 Hermes Agent 的三大特性:
  1. Agent Nudges — 主动提醒保存重要信息
  2. Skills Hub — 开放技能市场，技能可共享进化  
  3. Skills Self-Improvement — 技能在使用中自动优化
  
  源自 NousResearch/hermes-agent 源码
---

# agent-nudge — Agent 主动记忆与技能进化系统

> 融合 Hermes Agent 的 3 大核心特性，让 OpenClaw Agent 具备**主动学习**能力

---

## 三大特性

### 1. 🤖 Agent Nudges（主动提醒）

**原理**: 在每次对话结束后，Agent 自动检查是否需要保存重要信息到记忆

```
对话结束 
  ↓
后台线程启动
  ↓
检查记忆触发条件:
  - 用户透露了个人信息/偏好?
  - 有值得记住的重要决策?
  - 用户的期望/工作风格?
  ↓
有则保存，无则跳过
```

**触发条件**:
- `_memory_nudge_interval` 周期性检查
- 每次对话结束自动检查

### 2. 🏪 Skills Hub（技能市场）

**原理**: 技能可发布到开放市场，供其他 Agent 下载使用

| 组件 | 说明 |
|------|------|
| **SkillMeta** | 技能元数据（name, description, tags, source）|
| **SkillBundle** | 技能包（文件集合 + 元数据）|
| **Security Scan** | 安装前安全扫描（防恶意代码）|
| **Trust Level** | builtin / trusted / community 分级 |

**数据流**:
```
创建技能 → 安全扫描 → 隔离区 → 审核通过 → 发布到 Hub
                                      ↓
其他 Agent → 搜索 Hub → 下载 → 安全扫描 → 安装
```

### 3. 🔄 Skills Self-Improvement（技能自进化）

**原理**: Agent 在使用中发现更好的方法，自动更新技能

**触发场景**:
- 任务需要 trial and error
- 因经验改变了方法
- 用户期望不同的结果
- 非平凡的问题解决过程

**操作**:
- `skill_create` — 创建新技能
- `skill_edit` — 更新现有技能
- `skill_patch` — 局部修改技能
- `skill_delete` — 删除技能

---

## 核心实现

### Nudge 触发器

```python
class AgentNudge:
    """主动提醒系统"""
    
    MEMORY_REVIEW_PROMPT = """
    检查对话，思考:
    1. 用户是否透露了个人信息/偏好/期望?
    2. 有没有重要的决策需要记住?
    
    如果有重要内容，用 memory_save 保存。
    否则回复 'Nothing to save.'
    """
    
    SKILL_REVIEW_PROMPT = """
    检查对话，思考:
    1. 是否有非平凡的方法解决了问题?
    2. 是否需要 trial and error?
    3. 用户期望的方法是否与实际不同?
    
    如果有价值的方法，创建或更新技能。
    否则回复 'Nothing to save.'
    """
    
    def should_nudge(self, session: dict) -> bool:
        """判断是否触发 nudge"""
        # 每 N 轮对话触发一次
        # 或者在特定关键词出现时触发
        pass
    
    def spawn_background_review(self, messages: list):
        """启动后台审查线程"""
        thread = threading.Thread(target=self._run_review)
        thread.start()
```

### Skill Bundle 结构

```python
@dataclass
class SkillBundle:
    name: str
    files: dict[str, str]  # path -> content
    source: str
    identifier: str
    trust_level: str  # builtin/trusted/community
    tags: list[str]
    
    def scan_security(self) -> ScanResult:
        """安装前安全扫描"""
        
    def publish_to_hub(self, hub_url: str):
        """发布到技能市场"""
```

### Skill 自进化循环

```
任务执行
  ↓
结果不理想? → 是 → 尝试新方法 → 更新技能
  ↓ (否)
检查是否比现有方法更好?
  ↓ (是)
更新技能中的步骤
  ↓
技能下次被调用时使用新方法
```

---

## OpenClaw 集成

### 1. 启用 Agent Nudge

```python
# 在 session 开始时注册
nudge = AgentNudge(ctx)
nudge.register_memory_callback(ctx.memory_save)
nudge.register_skill_callback(ctx.skill_manager)

# 每 10 轮对话触发一次
if turn_count % 10 == 0:
    nudge.spawn_memory_review(messages)
```

### 2. 技能发布到 Hub

```python
# 发布技能
hub = SkillHub(ctx)
bundle = hub.bundle("my-skill")
scan_result = bundle.scan()

if scan_result.is_safe:
    hub.publish(bundle, "https://agentskills.io")
    
# 或从 Hub 安装
skill = hub.search("stock analysis")
hub.install(skill)
```

### 3. 技能自进化

```python
skill_manager = SkillManager(ctx)

# 在任务成功后自动调用
async def after_task(task, result):
    if task.requires_trial_and_error:
        await skill_manager.update_or_create(
            name=task.skill_name,
            description=task.description,
            content=task.learned_steps
        )
```

---

## 与现有技能的集成

```
friday-dream
  └── agent-nudge (提供主动记忆触发)

skill-discovery
  └── agent-nudge (Skills Hub 集成)

context-compact
  └── agent-nudge (压缩后触发 nudge 检查)
```

---

## 安全机制

### 安装前扫描

```python
class SkillsGuard:
    """技能安全扫描器"""
    
    # 可信路径
    TRUSTED_REPOS = {
        "NousResearch/hermes-agent",
        "anthropics/claude-code",
        "openclaw/openclaw-skills"
    }
    
    def scan_skill(self, skill_dir: Path) -> ScanResult:
        """扫描技能目录"""
        # 1. 静态分析
        # 2. 沙箱执行测试
        # 3. 依赖检查
        # 4. 权限最小化检查
```

### 信任等级

| 等级 | 来源 | 自动安装 |
|------|------|----------|
| **builtin** | 官方内置 | ✅ |
| **trusted** | 认证开发者 | ✅ |
| **community** | 社区贡献 | ⚠️ 需要确认 |

---

## 参考

- Hermes Agent 源码: `agent/run_agent.py` (_spawn_background_review)
- Hermes Agent 源码: `tools/skill_manager_tool.py` (技能管理)
- Hermes Agent 源码: `tools/skills_hub.py` (技能市场)
- Hermes Agent 源码: `tools/skills_guard.py` (安全扫描)

---

*本技能融合自 NousResearch/hermes-agent*

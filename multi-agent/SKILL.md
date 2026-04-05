---
name: multi-agent
description: |
  Multi-agent Leader-Worker orchestration system with file mailbox protocol.
  Triggers when: (1) user asks to spawn sub-agents or delegate tasks;
  (2) complex tasks need parallel decomposition;
  (3) task requires specialized agents (data/analysis/strategy/risk).
  Based on Claude Code's Swarm architecture (src/utils/swarm/, src/tools/AgentTool/).
  Provides: three execution backends, file mailbox IPC, permission sync,
  and stock-domain agent types (data/analysis/strategy/risk/verification).
---

# Multi-Agent System

## Architecture Overview

```
User Request (Leader Agent)
        │
        ▼
┌─────────────────────────────────────────────────────┐
│              Leader / Coordinator                     │
│  Task Decomposition → Spawn Workers → Collect Results │
└──────┬──────────────┬──────────────┬────────────────┘
       │              │              │
   ┌───▼───┐   ┌────▼────┐   ┌────▼─────┐
   │InProc  │   │  Tmux   │   │ ITerm2   │
   │Backend │   │ Backend │   │ Backend  │
   └────────┘   └─────────┘   └──────────┘
       │              │              │
   AsyncLocal    tmux分屏       it2 CLI
   Storage隔离   文件邮箱       控制iTerm2
```

## Agent Types (Stock Domain)

| Type | Model | Tools | Purpose |
|------|-------|-------|---------|
| `data` | Sonnet | Read/Bash/WebFetch | 行情/新闻/财务数据采集 |
| `analysis` | Sonnet | Read/Grep/Calc | 技术指标/基本面分析 |
| `strategy` | Opus | Read/Edit | 策略生成/信号输出 |
| `risk` | Sonnet | Read/Calc | 仓位计算/止损/敞口 |
| `verification` | Sonnet | Read | 对抗性策略检验（红色标识） |
| `report` | Haiku | Read/Edit | 报告生成 |

## Core Concepts

### Leader Agent

The main agent that:
1. Receives user task
2. Decomposes into subtasks
3. Spawns appropriate worker agents
4. Collects and synthesizes results
5. Returns final answer to user

### Worker Agents

Specialized agents that:
- Run independently (synchronously or asynchronously)
- Communicate via SendMessage
- Report results back to Leader
- Request permission for sensitive operations

### File Mailbox Protocol

Each agent has a JSON mailbox for inter-agent communication:

```
~/.claude/teams/{team_name}/inboxes/{agent_name}.json
```

```json
{
  "messages": [
    {
      "id": "msg_001",
      "from": "leader",
      "type": "text",
      "content": "Analyze AAPL technical indicators",
      "timestamp": "2026-04-02T08:00:00Z",
      "read": false,
      "summary": "分析AAPL技术指标"
    }
  ]
}
```

### Message Types

| Type | Description | Direction |
|------|-------------|-----------|
| `text` | Plain text message | Any |
| `shutdown_request` | Request agent shutdown | Leader → Worker |
| `shutdown_approved` | Shutdown confirmation | Worker → Leader |
| `permission_request` | Request operation approval | Worker → Leader |
| `permission_response` | Approve/deny | Leader → Worker |
| `idle_notification` | Worker is idle | Worker → Leader |
| `result` | Task result | Worker → Leader |

## Execution Backends

### 1. InProcess Backend (default)

All workers run in the same process via `AsyncLocalStorage`:

```python
import contextvars

agent_context = contextvars.ContextVar("agent_context")

def run_worker(agent_id: str, task: str, context: dict):
    token = agent_context.set({**context, "agent_id": agent_id})
    try:
        return execute_agent_task(task)
    finally:
        agent_context.reset(token)

def get_current_agent() -> str:
    ctx = agent_context.get()
    return ctx.get("agent_id", "leader")
```

**Pros:** Zero IPC overhead, fast context switching
**Cons:** No true parallelism, shared memory

### 2. Tmux Backend

Each worker is a Claude CLI process in a tmux pane.

```
┌─────────────────┬──────────────────┐
│     Leader      │    Worker A      │
├─────────────────┼──────────────────┤
│                 │    Worker B      │
├─────────────────┼──────────────────┤
│                 │    Worker C      │
└─────────────────┴──────────────────┘
```

**Pros:** True parallelism, persistent sessions
**Cons:** Requires tmux, platform-specific

### 3. Backend Selection

```python
def detect_backend() -> str:
    if in_tmux():
        return "tmux"
    elif in_iterm2() and has_it2_cli():
        return "iterm2"
    elif has_tmux():
        return "tmux-external"
    else:
        return "inprocess"  # fallback
```

## Leader Workflow

```
1. RECEIVE task from user
     ↓
2. DECOMPOSE into subtasks
   e.g., "分析新能源板块" →
     - [data] 获取板块成分股
     - [analysis] 技术分析每只股
     - [risk] 评估整体风险
     - [strategy] 生成持仓建议
     ↓
3. SPAWN workers for each subtask
     ↓
4. MONITOR mailbox for results
     poll interval: 500ms
     ↓
5. COLLECT results (timeout: 5min per worker)
     ↓
6. SYNTHESIZE final response
     ↓
7. SEND shutdown to workers
```

## Permission Flow

When a worker needs elevated permissions (e.g., write files, send messages):

```
Worker executes sensitive operation
     ↓
Worker PAUSES execution
     ↓
Worker sends permission_request to Leader mailbox
     ↓
Leader displays request to user
     (with worker badge: "Worker B is requesting permission to...")
     ↓
User approves/denies
     ↓
Leader sends permission_response to Worker mailbox
     ↓
Worker RESUMES or ABORTS
```

## Stock Domain Agents

### data Agent

**Responsibilities:**
- Fetch real-time quotes (Yahoo Finance, Tushare)
- Scrape financial news
- Download historical K-line data
- Pull fundamental data (PE, PB, ROE, cash flow)

**Tool set:** `Bash`, `Read`, `WebFetch`, `Write`

### analysis Agent

**Responsibilities:**
- Calculate technical indicators (MA, MACD, KDJ, Bollinger Bands)
- Identify chart patterns (head-shoulders, double-bottom)
- Evaluate fundamentals (valuation, growth, profitability)
- Generate sentiment scores

**Tool set:** `Read`, `Grep`, `Glob`, `Calc` (via Bash/Python)

### strategy Agent

**Responsibilities:**
- Generate buy/sell/hold signals
- Determine position sizing
- Suggest entry/exit points
- Create trading rules

**Tool set:** `Read`, `Edit`, `Write` (to strategy files)

### risk Agent

**Responsibilities:**
- Calculate portfolio VaR
- Monitor position limits
- Check stop-loss triggers
- Verify margin requirements

**Tool set:** `Read`, `Calc` (risk calculations)

### verification Agent

**Responsibilities:**
- Backtest strategy against historical data
- Identify strategy weaknesses
- Stress test with adverse scenarios
- Verify risk limits

**Convention:** Results shown with red indicators for risks found

**Tool set:** `Read`, `Bash` (backtest engine)

## Scripts

- `scripts/mailbox_manager.py` — File mailbox CRUD + protocol
- `scripts/leader_engine.py` — Leader orchestration logic
- `scripts/agent_registry.py` — Agent type definitions

## References

- `references/swarm-protocol.md` — Detailed message protocol spec
- `references/stock-agents.md` — Stock domain agent specifications

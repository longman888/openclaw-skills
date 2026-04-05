# Swarm Protocol Reference

## File Mailbox Protocol

### File Structure

```
~/.claude/teams/{team_name}/inboxes/
├── leader.json         # Leader's mailbox
├── worker_task_1.json  # Worker 1 mailbox
├── worker_task_2.json  # Worker 2 mailbox
└── {agent}.json        # Any named agent
```

### Mailbox JSON Schema

```json
{
  "version": "1.0",
  "agent_name": "worker_1",
  "team_name": "default",
  "messages": [
    {
      "id": "msg_001",
      "type": "text",
      "from_agent": "leader",
      "content": "Analyze TSLA technical indicators",
      "timestamp": "2026-04-02T08:00:00Z",
      "read": false,
      "summary": "分析TSLA技术指标",
      "color": "#4A90D9"
    }
  ],
  "created_at": "2026-04-02T08:00:00Z",
  "updated_at": "2026-04-02T08:00:00Z"
}
```

### Message Protocol Flows

#### Text Message Flow

```
Leader                    Worker
   |                         |
   |---- send_text() ------->|
   |    type: text           |
   |    content: task desc   |
   |                         |
   |<--- pop_unread() -------|
   |    reads message        |
   |                         |
   |---- work --------------|
   |                         |
   |<--- send_result() ------|
   |    type: result         |
   |    success: true        |
   |    content: analysis    |
```

#### Permission Request Flow

```
Worker                    Leader                    User
  |                         |                         |
  |---- permission_request ->|                         |
  |    operation: Write     |                         |
  |    file: ./report.md    |                         |
  |                         | Display dialog           |
  |                         |------------------------>|
  |                         |                         |
  |                         |<---- User approves -----|
  |                         |                         |
  |<-- permission_response -|                         |
  |    approved: true       |                         |
  |                         |                         |
  |---- continue work ----->|
```

#### Shutdown Flow

```
Leader                    Worker
  |                         |
  |---- shutdown_request -->|
  |                         |
  |    [finish current]     |
  |                         |
  |<--- shutdown_approved --|
  |                         |
  |    [exit]               |
```

## Agent Definition Schema

```json
{
  "agentType": "data",
  "description": "数据采集Agent",
  "whenToUse": "获取股票行情、新闻、财务数据",
  "tools": ["Read", "Bash", "WebFetch"],
  "disallowedTools": ["Edit", "Write"],
  "model": "sonnet",
  "permissionMode": "bypassPermissions",
  "maxTurns": 15,
  "background": true,
  "isolation": "worktree",
  "getSystemPrompt": "..."
}
```

## Leader Command Reference

```python
# Decompose task
leader.decompose("分析腾讯今日行情并给出建议")

# Spawn worker
leader.spawn_worker(subtask)

# Send task
leader.send_task_to_worker("worker_1", task)

# Collect results
results = leader.collect_results(timeout_seconds=300)

# Synthesize
final = leader.synthesize()

# Shutdown
leader.shutdown_workers()
```

## InProcess Backend — AsyncLocalStorage

```python
import contextvars

agent_context: contextvars.ContextVar[dict] = contextvars.ContextVar("agent_context")

def run_worker(task_id: str, prompt: str, system_prompt: str = ""):
    """Run a worker in the same process."""
    ctx = {
        "task_id": task_id,
        "agent_type": get_agent_type(task_id),
        "system_prompt": system_prompt,
        "messages": []
    }
    token = agent_context.set(ctx)
    try:
        return execute_agent_loop(prompt)
    finally:
        agent_context.reset(token)

def get_current_context() -> dict:
    return agent_context.get()
```

## Tmux Backend Commands

```bash
# Create named session
tmux new-session -d -s claude-swarm-$$

# Send command to pane
tmux send-keys -t claude-swarm-$$.0 "claude --agent $AGENT_TYPE" C-m

# Split pane
tmux split-window -t claude-swarm-$$ -h

# List panes
tmux list-panes -t claude-swarm-$$
```

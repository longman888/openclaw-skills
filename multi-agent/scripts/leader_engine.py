#!/usr/bin/env python3
"""
Multi-Agent Leader Engine
Orchestrates task decomposition, worker spawning, result collection.

Leader workflow:
1. RECEIVE task from user
2. DECOMPOSE into subtasks
3. SPAWN workers for each subtask
4. MONITOR mailbox for results
5. COLLECT results (with timeout)
6. SYNTHESIZE final response
7. SEND shutdown to workers
"""

import asyncio
import logging
import time
import json
from dataclasses import dataclass, field
from typing import Optional, Callable
from enum import Enum

from mailbox_manager import (
    MailboxMessage, MessageType,
    send_text, send_shutdown_request, send_result,
    pop_unread, load_mailbox, create_mailbox,
    read_messages
)

# ─── Logging ────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("leader-engine")


# ─── Task Decomposition ─────────────────────────────────────────────────────

@dataclass
class SubTask:
    agent_type: str          # "data", "analysis", "strategy", "risk", etc.
    description: str          # Human-readable task description
    prompt: str               # The actual prompt to send to worker
    timeout_seconds: int = 300
    depends_on: list[str] = field(default_factory=list)  # task IDs this depends on
    id: str = ""              # Assigned by leader


@dataclass
class TaskResult:
    task_id: str
    agent_name: str
    success: bool
    content: str = ""
    error: str = ""
    duration_seconds: float = 0.0


class LeaderEngine:
    """
    Orchestrates multi-agent task execution.
    """

    def __init__(self, team_name: str = "default", leader_name: str = "leader"):
        self.team_name = team_name
        self.leader_name = leader_name
        self.tasks: dict[str, SubTask] = {}
        self.results: dict[str, TaskResult] = {}
        self.worker_mailboxes: dict[str, str] = {}  # task_id -> worker_name
        self._poll_interval = 0.5  # seconds

    # ── Task Decomposition ────────────────────────────────────────────────

    def decompose(self, user_task: str) -> list[SubTask]:
        """
        Decompose a user task into subtasks.
        In production, this could use an LLM for smart decomposition.
        For now, uses rule-based patterns.
        """
        tasks = []
        task_counter = 0

        # Pattern: check for stock analysis keywords
        stock_keywords = ["股票", "分析", "行情", "交易", "持仓", "技术指标",
                          "基本面", "财报", "预警", "选股", "AAPL", "TSLA", "腾讯"]

        is_stock_task = any(kw in user_task for kw in stock_keywords)

        if is_stock_task:
            # Data collection task
            if any(k in user_task for k in ["行情", "价格", "实时", "获取", "查看"]):
                task_counter += 1
                tasks.append(SubTask(
                    id=f"task_{task_counter}",
                    agent_type="data",
                    description="获取股票行情数据",
                    prompt=f"执行数据采集任务：\n{user_task}\n\n请获取相关股票的实时行情数据。"
                ))

            # Technical analysis task
            if any(k in user_task for k in ["分析", "指标", "K线", "MACD", "均线", "技术"]):
                task_counter += 1
                tasks.append(SubTask(
                    id=f"task_{task_counter}",
                    agent_type="analysis",
                    description="技术分析",
                    prompt=f"执行技术分析任务：\n{user_task}\n\n请计算技术指标并给出分析。"
                ))

            # Risk assessment task
            if any(k in user_task for k in ["风险", "止损", "仓位", "敞口", "VaR"]):
                task_counter += 1
                tasks.append(SubTask(
                    id=f"task_{task_counter}",
                    agent_type="risk",
                    description="风险评估",
                    prompt=f"执行风险评估任务：\n{user_task}\n\n请评估相关风险并给出建议。"
                ))

            # Strategy task
            if any(k in user_task for k in ["策略", "建议", "操作", "买入", "卖出", "持有"]):
                task_counter += 1
                tasks.append(SubTask(
                    id=f"task_{task_counter}",
                    agent_type="strategy",
                    description="策略建议",
                    prompt=f"执行策略生成任务：\n{user_task}\n\n请生成具体的交易策略建议。"
                ))

            # Verification task
            if any(k in user_task for k in ["验证", "检验", "回测", "测试"]):
                task_counter += 1
                tasks.append(SubTask(
                    id=f"task_{task_counter}",
                    agent_type="verification",
                    description="策略验证",
                    prompt=f"执行策略验证任务：\n{user_task}\n\n请进行对抗性检验和回测。"
                ))

        # Default: general purpose agent
        if not tasks:
            tasks.append(SubTask(
                id="task_1",
                agent_type="general",
                description="通用任务",
                prompt=user_task
            ))

        self.tasks = {t.id: t for t in tasks}
        log.info(f"Decomposed into {len(tasks)} subtasks: {[t.agent_type for t in tasks]}")
        return tasks

    # ── Worker Spawning ───────────────────────────────────────────────────

    def spawn_worker(self, task: SubTask) -> str:
        """
        Spawn a worker agent for a subtask.
        Returns worker name.
        In production, this would create actual agent processes/sessions.
        """
        worker_name = f"worker_{task.id}"

        # Ensure mailbox exists for this worker
        create_mailbox(self.team_name, worker_name)

        # In production, spawn actual agent here:
        # - For InProcess: create async task
        # - For Tmux: spawn Claude CLI in tmux pane
        # - For remote: call sessions_spawn API
        log.info(f"Spawned {task.agent_type} agent: {worker_name}")
        log.info(f"  Prompt: {task.prompt[:100]}...")

        self.worker_mailboxes[task.id] = worker_name
        return worker_name

    def send_task_to_worker(self, worker_name: str, task: SubTask) -> bool:
        """Send task prompt to worker mailbox."""
        mid = send_text(
            to=worker_name,
            from_=self.leader_name,
            content=task.prompt,
            team=self.team_name,
            summary=f"Task: {task.description}"
        )
        return mid is not None

    # ── Result Collection ─────────────────────────────────────────────────

    def collect_results(self, timeout_seconds: int = 300) -> dict[str, TaskResult]:
        """
        Poll worker mailboxes for results until all complete or timeout.
        Returns dict of task_id -> TaskResult.
        """
        start_time = time.time()
        pending_tasks = set(self.tasks.keys())

        log.info(f"Collecting results for {len(pending_tasks)} tasks (timeout={timeout_seconds}s)")

        while pending_tasks and (time.time() - start_time) < timeout_seconds:
            for task_id in list(pending_tasks):
                worker_name = self.worker_mailboxes.get(task_id)
                if not worker_name:
                    continue

                # Poll unread messages
                messages = pop_unread(self.team_name, worker_name)

                for msg in messages:
                    if msg.type == MessageType.RESULT.value:
                        result = TaskResult(
                            task_id=task_id,
                            agent_name=worker_name,
                            success=msg.success,
                            content=msg.content,
                            error=msg.error_msg,
                            duration_seconds=time.time() - start_time
                        )
                        self.results[task_id] = result
                        pending_tasks.remove(task_id)
                        log.info(f"Received result from {worker_name}: success={msg.success}")

                    elif msg.type == MessageType.ERROR.value:
                        result = TaskResult(
                            task_id=task_id,
                            agent_name=worker_name,
                            success=False,
                            error=msg.content,
                            duration_seconds=time.time() - start_time
                        )
                        self.results[task_id] = result
                        pending_tasks.remove(task_id)
                        log.warning(f"Error from {worker_name}: {msg.content}")

                    elif msg.type == MessageType.IDLE_NOTIFICATION.value:
                        # Worker is idle but hasn't sent result yet
                        pass

            if pending_tasks:
                time.sleep(self._poll_interval)

        # Mark timed-out tasks
        for task_id in pending_tasks:
            if task_id not in self.results:
                self.results[task_id] = TaskResult(
                    task_id=task_id,
                    agent_name=self.worker_mailboxes.get(task_id, "unknown"),
                    success=False,
                    error=f"Timeout after {timeout_seconds}s",
                    duration_seconds=time.time() - start_time
                )
                log.warning(f"Task {task_id} timed out")

        return self.results

    # ── Synthesis ─────────────────────────────────────────────────────────

    def synthesize(self) -> str:
        """
        Combine all task results into a final response.
        In production, this could use an LLM for natural synthesis.
        """
        if not self.results:
            return "No results to synthesize."

        lines = ["## 多Agent执行结果\n"]

        for task_id, result in self.results.items():
            task = self.tasks.get(task_id)
            if not task:
                continue

            status = "✅" if result.success else "❌"
            lines.append(f"### {status} [{task.agent_type}] {task.description}\n")

            if result.success:
                lines.append(f"{result.content}\n")
            else:
                lines.append(f"**错误:** {result.error}\n")

            lines.append(f"*(耗时: {result.duration_seconds:.1f}s)*\n")
            lines.append("\n")

        return "\n".join(lines)

    # ── Shutdown ──────────────────────────────────────────────────────────

    def shutdown_workers(self):
        """Send shutdown request to all workers."""
        for task_id, worker_name in self.worker_mailboxes.items():
            send_shutdown_request(
                to=worker_name,
                from_=self.leader_name,
                team=self.team_name,
                reason="Task complete"
            )
            log.info(f"Sent shutdown request to {worker_name}")

    # ── Main Execute ─────────────────────────────────────────────────────

    def execute(self, user_task: str, timeout_seconds: int = 300) -> str:
        """
        Full leader workflow:
        1. Decompose
        2. Spawn workers
        3. Send tasks
        4. Collect results
        5. Synthesize
        6. Shutdown
        """
        # Step 1: Decompose
        tasks = self.decompose(user_task)

        # Step 2 & 3: Spawn workers and send tasks
        for task in tasks:
            worker = self.spawn_worker(task)
            self.send_task_to_worker(worker, task)

        # Step 4: Collect results
        results = self.collect_results(timeout_seconds)

        # Step 5: Synthesize
        response = self.synthesize()

        # Step 6: Shutdown
        self.shutdown_workers()

        return response


# ─── CLI Entry Point ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Multi-Agent Leader Engine")
    parser.add_argument("task", help="User task description")
    parser.add_argument("--team", default="default", help="Team name")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout in seconds")

    args = parser.parse_args()

    engine = LeaderEngine(team_name=args.team)
    result = engine.execute(args.task, timeout_seconds=args.timeout)
    print(result)

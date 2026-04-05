#!/usr/bin/env python3
"""
Trigger Scheduler Manager
Based on Claude Code's AGENT_TRIGGERS architecture

Provides:
- CRUD operations for triggers
- Cron expression parsing and validation
- Next-run calculation
- Trigger persistence to JSON
"""

import os
import json
import uuid
import time
import logging
import subprocess
import platform
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional
from datetime import datetime, timedelta
from enum import Enum

# ─── Path Configuration ───────────────────────────────────────────────────────
# OpenClaw workspace override (set OPENCLAW_TRIGGER_DIR env var to customize)
TRIGGER_DIR = Path(os.environ.get(
    "OPENCLAW_TRIGGER_DIR",
    Path.home() / ".claude" / "triggers" if platform.system() != "Windows"
    else r"E:\.openclaw\triggers"
))
TRIGGER_FILE = "triggers.json"
LOCK_FILE = ".lock"

# Default cooldowns by trigger type
DEFAULT_COOLDOWNS = {
    "cron": 3600,
    "price_above": 300,
    "price_below": 300,
    "price_change_pct": 300,
    "volume_spike": 600,
    "news_keywords": 600,
    "signal_detected": 60,
    "portfolio_threshold": 300,
}

# ─── Logging ────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("trigger-scheduler")


# ─── Trigger Schema ─────────────────────────────────────────────────────────

@dataclass
class TriggerPayload:
    kind: str = "agentTurn"   # "agentTurn" | "systemEvent"
    message: str = ""
    model: str = ""
    thinking: str = ""

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class TriggerDelivery:
    mode: str = "announce"   # "announce" | "webhook" | "none"
    channel: str = ""
    to: str = ""

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class Trigger:
    id: str
    name: str
    type: str              # "cron" | "price_above" | "price_below" | etc.
    enabled: bool = True
    # Cron fields
    schedule: str = ""     # cron expression
    timezone: str = "Asia/Shanghai"
    # Condition fields (for price/news/signal triggers)
    symbol: str = ""
    threshold: float = 0.0
    condition: str = ""    # e.g., "macd_golden_cross"
    keywords: str = ""     # comma-separated for news triggers
    # Payload
    payload: TriggerPayload = field(default_factory=TriggerPayload)
    # Execution
    session_target: str = "isolated"   # "isolated" | "main" | "subagent"
    delivery: TriggerDelivery = field(default_factory=TriggerDelivery)
    # State
    cooldown_seconds: int = 0
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    run_count: int = 0
    consecutive_failures: int = 0
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "enabled": self.enabled,
            "schedule": self.schedule,
            "timezone": self.timezone,
            "symbol": self.symbol,
            "threshold": self.threshold,
            "condition": self.condition,
            "keywords": self.keywords,
            "payload": self.payload.to_dict() if isinstance(self.payload, TriggerPayload) else self.payload,
            "sessionTarget": self.session_target,
            "delivery": self.delivery.to_dict() if isinstance(self.delivery, TriggerDelivery) else self.delivery,
            "cooldownSeconds": self.cooldown_seconds,
            "lastRun": self.last_run,
            "nextRun": self.next_run,
            "runCount": self.run_count,
            "consecutiveFailures": self.consecutive_failures,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }
        return {k: v for k, v in d.items() if v != "" and v != 0 and v is not None}

    @classmethod
    def from_dict(cls, d: dict) -> "Trigger":
        payload = d.pop("payload", {})
        if isinstance(payload, dict):
            payload = TriggerPayload(**payload)
        delivery = d.pop("delivery", {})
        if isinstance(delivery, dict):
            delivery = TriggerDelivery(**delivery)
        # Map snake_case from dict to camelCase fields
        d["session_target"] = d.pop("sessionTarget", "isolated")
        d["cooldown_seconds"] = d.pop("cooldownSeconds", DEFAULT_COOLDOWNS.get(d.get("type", "cron"), 3600))
        d["last_run"] = d.pop("lastRun", None)
        d["next_run"] = d.pop("nextRun", None)
        d["run_count"] = d.pop("runCount", 0)
        d["consecutive_failures"] = d.pop("consecutiveFailures", 0)
        d["created_at"] = d.pop("createdAt", "")
        d["updated_at"] = d.pop("updatedAt", "")
        return cls(payload=payload, delivery=delivery, **d)


# ─── Store ───────────────────────────────────────────────────────────────────

class TriggerStore:
    """Persistent JSON store for triggers."""

    def __init__(self, store_dir: Optional[Path] = None):
        self.store_dir = store_dir or TRIGGER_DIR
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.store_file = self.store_dir / TRIGGER_FILE

    def _load_all(self) -> dict:
        if not self.store_file.exists():
            return {}
        try:
            with open(self.store_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}

    def _save_all(self, data: dict):
        with open(self.store_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def list(self, include_disabled: bool = False) -> list[Trigger]:
        data = self._load_all()
        triggers = []
        for d in data.get("triggers", []):
            t = Trigger.from_dict(d)
            if include_disabled or t.enabled:
                triggers.append(t)
        return triggers

    def get(self, trigger_id: str) -> Optional[Trigger]:
        data = self._load_all()
        for d in data.get("triggers", []):
            if d.get("id") == trigger_id:
                return Trigger.from_dict(d)
        return None

    def add(self, trigger: Trigger) -> bool:
        data = self._load_all()
        if "triggers" not in data:
            data["triggers"] = []
        # Check duplicate
        for existing in data["triggers"]:
            if existing["id"] == trigger.id:
                return False
        data["triggers"].append(trigger.to_dict())
        self._save_all(data)
        log.info(f"Added trigger: {trigger.name} ({trigger.id})")
        return True

    def update(self, trigger: Trigger) -> bool:
        data = self._load_all()
        for i, d in enumerate(data.get("triggers", [])):
            if d.get("id") == trigger.id:
                data["triggers"][i] = trigger.to_dict()
                self._save_all(data)
                log.info(f"Updated trigger: {trigger.name}")
                return True
        return False

    def remove(self, trigger_id: str) -> bool:
        data = self._load_all()
        before = len(data.get("triggers", []))
        data["triggers"] = [d for d in data.get("triggers", [])
                            if d.get("id") != trigger_id]
        if len(data["triggers"]) < before:
            self._save_all(data)
            log.info(f"Removed trigger: {trigger_id}")
            return True
        return False

    def enable(self, trigger_id: str) -> bool:
        t = self.get(trigger_id)
        if t:
            t.enabled = True
            t.next_run = calculate_next_run(t)
            return self.update(t)
        return False

    def disable(self, trigger_id: str) -> bool:
        t = self.get(trigger_id)
        if t:
            t.enabled = False
            return self.update(t)
        return False


# ─── Cron Parsing ────────────────────────────────────────────────────────────

def parse_cron(expression: str) -> tuple[list[int], list[int], list[int], list[int], list[int]]:
    """
    Parse a cron expression into 5 fields: minute, hour, day, month, weekday.
    Supports: * , - /
    Returns: (minutes, hours, days, months, weekdays)
    """
    parts = expression.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {expression}")

    # (min, max) for each field: minute, hour, day, month, weekday
    FIELD_RANGES = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 7)]

    fields = []
    for i, part in enumerate(parts):
        min_val, max_val = FIELD_RANGES[i]
        parsed = parse_cron_field(part, min_val, max_val)
        fields.append(parsed)
    return tuple(fields)


def parse_cron_field(field_str: str, min_val: int, max_val: int) -> list[int]:
    """Parse a single cron field. Supports *, -, ,, /."""
    result = set()

    if field_str == "*":
        return list(range(min_val, max_val + 1))

    for part in field_str.split(","):
        if "/" in part:
            base, step = part.split("/")
            step_val = int(step)
            if base == "*":
                # */N: every N from min_val to max_val
                vals = list(range(min_val, max_val + 1, step_val))
            else:
                base_int = int(base)
                vals = list(range(base_int, max_val + 1, step_val))
            result.update(vals)
        elif "-" in part:
            start, end = part.split("-")
            result.update(range(int(start), int(end) + 1))
        else:
            result.add(int(part))

    return sorted(result)


def calculate_next_run(trigger: Trigger) -> Optional[str]:
    """Calculate the next run time for a cron trigger."""
    if trigger.type != "cron" or not trigger.schedule:
        return None

    try:
        minutes, hours, _, _, weekdays = parse_cron(trigger.schedule)
    except ValueError:
        return None

    now = datetime.now()
    # Simple: find next matching weekday + hour + minute
    for delta_days in range(366):
        check_date = now + timedelta(days=delta_days)
        if check_date.weekday() + 1 not in weekdays and weekdays != list(range(1, 8)):
            continue
        for hour in hours:
            for minute in minutes:
                candidate = check_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if candidate > now:
                    return candidate.isoformat()
    return None


def is_in_cooldown(trigger: Trigger) -> bool:
    """Check if trigger is in cooldown period."""
    if trigger.last_run is None or trigger.cooldown_seconds <= 0:
        return False
    last = datetime.fromisoformat(trigger.last_run.replace("Z", "+00:00"))
    elapsed = (datetime.now() - last.replace(tzinfo=None)).total_seconds()
    return elapsed < trigger.cooldown_seconds


def validate_trigger(trigger: Trigger) -> tuple[bool, str]:
    """Validate trigger definition."""
    if not trigger.name:
        return False, "name is required"
    if not trigger.type:
        return False, "type is required"
    if trigger.type not in ("cron", "price_above", "price_below", "price_change_pct",
                             "volume_spike", "news_keywords", "signal_detected",
                             "portfolio_threshold"):
        return False, f"unknown trigger type: {trigger.type}"
    if trigger.type == "cron" and not trigger.schedule:
        return False, "cron trigger requires schedule"
    if trigger.type.startswith("price") and not trigger.symbol:
        return False, "price trigger requires symbol"
    if trigger.payload.kind not in ("agentTurn", "systemEvent"):
        return False, f"unknown payload kind: {trigger.payload.kind}"
    return True, "ok"


# ─── Trigger Execution ────────────────────────────────────────────────────────

def execute_trigger(trigger: Trigger) -> tuple[bool, str]:
    """
    Execute a trigger's payload.
    Returns (success, message).
    """
    if is_in_cooldown(trigger):
        return False, f"Trigger in cooldown ({trigger.cooldown_seconds}s)"

    if trigger.payload.kind == "agentTurn":
        # In real implementation, this would spawn an isolated session
        # or send to the main session
        log.info(f"Executing agentTurn: {trigger.name}")
        log.info(f"  Message: {trigger.payload.message[:100]}...")
        # Here we would call sessions_spawn or cron.add
        return True, f"AgentTurn executed: {trigger.payload.message[:50]}..."

    elif trigger.payload.kind == "systemEvent":
        log.info(f"Would inject systemEvent: {trigger.payload.message[:50]}...")
        return True, f"SystemEvent queued"

    return False, "Unknown payload kind"


def record_run(store: TriggerStore, trigger_id: str, success: bool):
    """Record a trigger run (success or failure)."""
    t = store.get(trigger_id)
    if t:
        t.last_run = datetime.now().isoformat() + "Z"
        t.run_count += 1
        if success:
            t.consecutive_failures = 0
        else:
            t.consecutive_failures += 1
        t.next_run = calculate_next_run(t) if t.enabled else None
        store.update(t)


# ─── CLI Entry Point ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Trigger Scheduler Manager")
    sub = parser.add_subparsers(dest="cmd")

    p_list = sub.add_parser("list", help="List triggers")
    p_list.add_argument("--all", action="store_true", help="Include disabled")

    p_add = sub.add_parser("add", help="Add a trigger from JSON file")
    p_add.add_argument("file", help="JSON file with trigger definition")

    p_enable = sub.add_parser("enable", help="Enable a trigger")
    p_enable.add_argument("id")

    p_disable = sub.add_parser("disable", help="Disable a trigger")
    p_disable.add_argument("id")

    p_remove = sub.add_parser("remove", help="Remove a trigger")
    p_remove.add_argument("id")

    p_run = sub.add_parser("run", help="Run a trigger now")
    p_run.add_argument("id")

    p_next = sub.add_parser("next", help="Calculate next run time")
    p_next.add_argument("schedule")

    args = parser.parse_args()
    store = TriggerStore()

    if args.cmd == "list":
        triggers = store.list(include_disabled=args.all)
        print(f"Triggers ({len(triggers)}):")
        for t in triggers:
            status = "✅" if t.enabled else "❌"
            next_run = t.next_run or "—"
            print(f"  {status} [{t.id[:8]}] {t.name} | next={next_run} | runs={t.run_count}")

    elif args.cmd == "add":
        with open(args.file, "r", encoding="utf-8") as f:
            d = json.load(f)
        trigger = Trigger.from_dict(d)
        trigger.id = trigger.id or str(uuid.uuid4())[:12]
        trigger.cooldown_seconds = trigger.cooldown_seconds or DEFAULT_COOLDOWNS.get(trigger.type, 3600)
        trigger.next_run = calculate_next_run(trigger) if trigger.schedule else None
        valid, msg = validate_trigger(trigger)
        if valid:
            if store.add(trigger):
                print(f"Added: {trigger.id}")
            else:
                print("Failed: trigger ID already exists")
        else:
            print(f"Validation failed: {msg}")

    elif args.cmd == "enable":
        store.enable(args.id)
        print(f"Enabled: {args.id}")

    elif args.cmd == "disable":
        store.disable(args.id)
        print(f"Disabled: {args.id}")

    elif args.cmd == "remove":
        store.remove(args.id)
        print(f"Removed: {args.id}")

    elif args.cmd == "run":
        t = store.get(args.id)
        if t:
            success, msg = execute_trigger(t)
            record_run(store, args.id, success)
            print(f"{'✅' if success else '❌'} {msg}")
        else:
            print("Trigger not found")

    elif args.cmd == "next":
        # Validate cron expression
        try:
            parse_cron(args.schedule)
            print(f"Valid cron: {args.schedule}")
        except ValueError as e:
            print(f"Invalid: {e}")

    else:
        parser.print_help()

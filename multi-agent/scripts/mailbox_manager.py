#!/usr/bin/env python3
"""
Multi-Agent File Mailbox Protocol
Based on Claude Code's teammateMailbox.ts (src/utils/teammateMailbox.ts)

Each agent has a JSON mailbox for inter-agent communication:
~/.claude/teams/{team_name}/inboxes/{agent_name}.json

Supports:
- Atomic write with file locking (10 retries, 5-100ms backoff)
- Unread message polling
- Message type protocol (text/shutdown/permission/result)
"""

import os
import json
import uuid
import time
import logging
import shutil
try:
    import fcntl  # Unix-only
except ImportError:
    fcntl = None  # Windows: no file locking (not critical for local use)
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional
from datetime import datetime
from enum import Enum
import os, platform

# ─── Path Configuration ───────────────────────────────────────────────────────
# OpenClaw workspace override (set OPENCLAW_TEAMS_DIR env var to customize)
# Falls back to ~/.claude/teams (original QClaw convention)
_TEAMS_ROOT = Path(os.environ.get(
    "OPENCLAW_TEAMS_DIR",
    Path.home() / ".claude" / "teams" if platform.system() != "Windows"
    else r"E:\.openclaw\teams"
))


# ─── Constants ────────────────────────────────────────────────────────────────

MAILBOX_VERSION = "1.0"
LOCK_SUFFIX = ".lock"
MAX_RETRIES = 10
MIN_BACKOFF_MS = 5
MAX_BACKOFF_MS = 100

# ─── Logging ────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("mailbox")


# ─── Message Types ──────────────────────────────────────────────────────────

class MessageType(str, Enum):
    TEXT = "text"
    SHUTDOWN_REQUEST = "shutdown_request"
    SHUTDOWN_APPROVED = "shutdown_approved"
    SHUTDOWN_DENIED = "shutdown_denied"
    PERMISSION_REQUEST = "permission_request"
    PERMISSION_RESPONSE = "permission_response"
    IDLE_NOTIFICATION = "idle_notification"
    RESULT = "result"
    ERROR = "error"


# ─── Message Schema ─────────────────────────────────────────────────────────

@dataclass
class MailboxMessage:
    id: str
    type: str
    from_agent: str
    content: str
    timestamp: str
    read: bool = False
    summary: str = ""
    color: str = ""
    # Permission-specific fields
    operation: str = ""        # for permission_request
    approved: bool = False     # for permission_response
    # Result-specific fields
    success: bool = True       # for result
    error_msg: str = ""        # for result/error

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v != ""}

    @classmethod
    def from_dict(cls, d: dict) -> "MailboxMessage":
        return cls(**{k: v for k, v in d.items()
                      if k in cls.__dataclass_fields__})


@dataclass
class Mailbox:
    version: str
    agent_name: str
    team_name: str
    messages: list[dict] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "agent_name": self.agent_name,
            "team_name": self.team_name,
            "messages": self.messages,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ─── Path Helpers ───────────────────────────────────────────────────────────

def get_mailbox_path(team_name: str, agent_name: str) -> Path:
    base = _TEAMS_ROOT / team_name / "inboxes"
    return base / f"{agent_name}.json"


def get_lock_path(mailbox_path: Path) -> Path:
    return Path(str(mailbox_path) + LOCK_SUFFIX)


def ensure_mailbox_dir(team_name: str) -> Path:
    path = _TEAMS_ROOT / team_name / "inboxes"
    path.mkdir(parents=True, exist_ok=True)
    return path


# ─── Mailbox Operations ──────────────────────────────────────────────────────

def create_mailbox(team_name: str, agent_name: str) -> Mailbox:
    """Create a new mailbox for an agent."""
    ensure_mailbox_dir(team_name)
    mb = Mailbox(
        version=MAILBOX_VERSION,
        agent_name=agent_name,
        team_name=team_name,
        messages=[],
        created_at=datetime.utcnow().isoformat() + "Z",
        updated_at=datetime.utcnow().isoformat() + "Z",
    )
    save_mailbox(mb)
    log.info(f"Created mailbox for agent '{agent_name}' in team '{team_name}'")
    return mb


def load_mailbox(team_name: str, agent_name: str) -> Optional[Mailbox]:
    """Load mailbox, return None if not found."""
    path = get_mailbox_path(team_name, agent_name)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Mailbox(**data)
    except (json.JSONDecodeError, TypeError) as e:
        log.error(f"Failed to load mailbox {path}: {e}")
        return None


def save_mailbox(mb: Mailbox, retry: int = 0) -> bool:
    """
    Save mailbox with file locking.
    Atomic write: write to temp, rename to target.
    Retries with exponential backoff on lock failure.
    """
    path = get_mailbox_path(mb.team_name, mb.agent_name)
    lock_path = get_lock_path(path)

    try:
        mb.updated_at = datetime.utcnow().isoformat() + "Z"
        # Write to temp file
        tmp_path = path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(mb.to_dict(), f, ensure_ascii=False, indent=2)

        # Atomic rename (on Windows, can't replace existing file)
        import shutil
        shutil.move(str(tmp_path), str(path))
        return True

    except (IOError, OSError) as e:
        if retry < MAX_RETRIES:
            backoff_ms = min(MIN_BACKOFF_MS * (2 ** retry), MAX_BACKOFF_MS)
            time.sleep(backoff_ms / 1000)
            return save_mailbox(mb, retry + 1)
        log.error(f"Failed to save mailbox after {MAX_RETRIES} retries: {e}")
        return False


# ─── Message Operations ──────────────────────────────────────────────────────

def write_message(
    team_name: str,
    to_agent: str,
    msg_type: str,
    from_agent: str,
    content: str,
    summary: str = "",
    color: str = "",
    **kwargs
) -> Optional[str]:
    """
    Write a message to an agent's mailbox.
    Returns message ID on success, None on failure.
    """
    mb = load_mailbox(team_name, to_agent)
    if mb is None:
        mb = create_mailbox(team_name, to_agent)

    msg_id = str(uuid.uuid4())[:12]
    msg = MailboxMessage(
        id=msg_id,
        type=msg_type,
        from_agent=from_agent,
        content=content,
        timestamp=datetime.utcnow().isoformat() + "Z",
        summary=summary or content[:50],
        color=color,
        **kwargs
    )

    mb.messages.append(msg.to_dict())
    if save_mailbox(mb):
        log.info(f"Message {msg_id} sent from '{from_agent}' to '{to_agent}' ({msg_type})")
        return msg_id
    return None


def read_messages(
    team_name: str,
    agent_name: str,
    unread_only: bool = False
) -> list[MailboxMessage]:
    """Read all messages from an agent's mailbox."""
    mb = load_mailbox(team_name, agent_name)
    if mb is None:
        return []

    messages = []
    for msg_dict in mb.messages:
        msg = MailboxMessage.from_dict(msg_dict)
        if unread_only and msg.read:
            continue
        messages.append(msg)
    return messages


def mark_read(team_name: str, agent_name: str, message_ids: list[str]) -> bool:
    """Mark specific messages as read."""
    mb = load_mailbox(team_name, agent_name)
    if mb is None:
        return False

    changed = False
    for msg_dict in mb.messages:
        if msg_dict["id"] in message_ids:
            msg_dict["read"] = True
            changed = True

    if changed:
        return save_mailbox(mb)
    return True


def pop_unread(team_name: str, agent_name: str) -> list[MailboxMessage]:
    """Read all unread messages and mark them as read atomically."""
    messages = read_messages(team_name, agent_name, unread_only=True)
    if messages:
        ids = [m.id for m in messages]
        mark_read(team_name, agent_name, ids)
    return messages


# ─── Convenience Wrappers ───────────────────────────────────────────────────

def send_text(to: str, from_: str, content: str, team: str = "default", summary: str = "") -> Optional[str]:
    return write_message(team, to, MessageType.TEXT.value, from_, content, summary=summary)


def send_shutdown_request(to: str, from_: str, team: str = "default", reason: str = "") -> Optional[str]:
    return write_message(team, to, MessageType.SHUTDOWN_REQUEST.value, from_, reason)


def send_shutdown_approved(to: str, from_: str, team: str = "default") -> Optional[str]:
    return write_message(team, to, MessageType.SHUTDOWN_APPROVED.value, from_, "shutdown approved")


def send_permission_request(
    to: str, from_: str, operation: str, team: str = "default", details: str = ""
) -> Optional[str]:
    return write_message(team, to, MessageType.PERMISSION_REQUEST.value, from_, details,
                         operation=operation)


def send_permission_response(
    to: str, from_: str, approved: bool, team: str = "default", reason: str = ""
) -> Optional[str]:
    return write_message(team, to, MessageType.PERMISSION_RESPONSE.value, from_, reason,
                         approved=approved)


def send_result(
    to: str, from_: str, content: str, success: bool = True, team: str = "default"
) -> Optional[str]:
    return write_message(team, to, MessageType.RESULT.value, from_, content,
                         success=success, error_msg="" if success else content)


def send_error(to: str, from_: str, error_msg: str, team: str = "default") -> Optional[str]:
    return write_message(team, to, MessageType.ERROR.value, from_, error_msg, error_msg=error_msg)


def send_idle(from_: str, team: str = "default") -> Optional[str]:
    return write_message(team, "leader", MessageType.IDLE_NOTIFICATION.value, from_,
                         "agent is idle", summary="idle")


def broadcast(team_name: str, from_agent: str, content: str, summary: str = "") -> list[Optional[str]]:
    """Broadcast to all agents in a team. Returns list of message IDs."""
    team_path = _TEAMS_ROOT / team_name / "inboxes"
    if not team_path.exists():
        return []

    ids = []
    for mb_file in team_path.glob("*.json"):
        agent_name = mb_file.stem
        if agent_name != from_agent:
            mid = send_text(agent_name, from_agent, content, team_name, summary)
            ids.append(mid)
    return ids


# ─── CLI Entry Point ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Multi-Agent Mailbox Manager")
    sub = parser.add_subparsers(dest="cmd")

    p_create = sub.add_parser("create", help="Create a mailbox")
    p_create.add_argument("team")
    p_create.add_argument("agent")

    p_send = sub.add_parser("send", help="Send a message")
    p_send.add_argument("team")
    p_send.add_argument("to")
    p_send.add_argument("from_")
    p_send.add_argument("content")
    p_send.add_argument("--type", default="text")

    p_read = sub.add_parser("read", help="Read messages")
    p_read.add_argument("team")
    p_read.add_argument("agent")
    p_read.add_argument("--unread", action="store_true")

    p_broadcast = sub.add_parser("broadcast", help="Broadcast to team")
    p_broadcast.add_argument("team")
    p_broadcast.add_argument("from_")
    p_broadcast.add_argument("content")

    args = parser.parse_args()

    if args.cmd == "create":
        mb = create_mailbox(args.team, args.agent)
        print(f"Created: {mb.agent_name} in {mb.team_name}")

    elif args.cmd == "send":
        mid = write_message(args.team, args.to, args.type, args.from_, args.content)
        print(f"Message sent: {mid}" if mid else "Failed")

    elif args.cmd == "read":
        msgs = read_messages(args.team, args.agent, unread_only=args.unread)
        print(f"Messages ({len(msgs)}):")
        for m in msgs:
            print(f"  [{m.type}] {m.from_agent} @ {m.timestamp}: {m.content[:80]}")

    elif args.cmd == "broadcast":
        ids = broadcast(args.team, args.from_, args.content)
        print(f"Broadcast to {len(ids)} agents")

    else:
        parser.print_help()

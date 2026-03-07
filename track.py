#!/usr/bin/env python3
"""
Claude Code tool usage tracker hook script.
Handles: PreToolUse, PermissionRequest, PostToolUse, PostToolUseFailure
"""
import sys
import json
import sqlite3
import time
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tool_tracker.db")


def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tool_uses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tool_use_id TEXT,
            session_id TEXT,
            agent_type TEXT,
            tool_name TEXT,
            cwd TEXT,
            tool_input TEXT,
            started_at REAL,
            permission_requested_at REAL,
            ended_at REAL,
            success INTEGER,
            error TEXT,
            tool_response TEXT
        )
    """)
    # add columns to existing DBs that predate this schema
    for col, typedef in [("agent_type", "TEXT"), ("tool_response", "TEXT")]:
        try:
            conn.execute(f"ALTER TABLE tool_uses ADD COLUMN {col} {typedef}")
        except Exception:
            pass
    conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON tool_uses (session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tool_use_id ON tool_uses (tool_use_id)")
    conn.commit()


def find_pending_id(conn, session_id, tool_name, tool_use_id=None):
    """Find the most recent unfinished row for this tool call."""
    if tool_use_id:
        row = conn.execute(
            "SELECT id FROM tool_uses WHERE tool_use_id = ? AND ended_at IS NULL",
            (tool_use_id,)
        ).fetchone()
        if row:
            return row[0]
    # Fallback: most recent unfinished row for session + tool name
    row = conn.execute(
        """SELECT id FROM tool_uses
           WHERE session_id = ? AND tool_name = ? AND ended_at IS NULL
           ORDER BY started_at DESC LIMIT 1""",
        (session_id, tool_name)
    ).fetchone()
    return row[0] if row else None


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    event = data.get("hook_event_name", "")
    session_id = data.get("session_id", "")
    tool_name = data.get("tool_name", "")
    tool_use_id = data.get("tool_use_id")
    now = time.time()

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    if event == "PreToolUse":
        conn.execute(
            """INSERT INTO tool_uses
               (tool_use_id, session_id, agent_type, tool_name, cwd, tool_input, started_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                tool_use_id,
                session_id,
                data.get("agent_type"),
                tool_name,
                data.get("cwd"),
                json.dumps(data.get("tool_input", {})),
                now,
            ),
        )
        conn.commit()

    elif event == "PermissionRequest":
        row_id = find_pending_id(conn, session_id, tool_name, tool_use_id)
        if row_id:
            conn.execute(
                "UPDATE tool_uses SET permission_requested_at = ? WHERE id = ?",
                (now, row_id),
            )
            conn.commit()

    elif event in ("PostToolUse", "PostToolUseFailure"):
        success = 1 if event == "PostToolUse" else 0
        error = data.get("error") if event == "PostToolUseFailure" else None
        response = data.get("tool_response")
        row_id = find_pending_id(conn, session_id, tool_name, tool_use_id)
        if row_id:
            conn.execute(
                "UPDATE tool_uses SET ended_at = ?, success = ?, error = ?, tool_response = ? WHERE id = ?",
                (now, success, error, json.dumps(response) if response is not None else None, row_id),
            )
            conn.commit()

    conn.close()


if __name__ == "__main__":
    main()

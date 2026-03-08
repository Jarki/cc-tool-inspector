#!/usr/bin/env python3
"""
Claude Code tool usage tracker hook script.
Handles: UserPromptSubmit, PreToolUse, PermissionRequest, PostToolUse, PostToolUseFailure
"""
import sys
import json
import sqlite3
import time

from db import DB_PATH, init_db, find_pending_id, truncate_response


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("track.py: invalid JSON on stdin", file=sys.stderr)
        sys.exit(0)

    event = data.get("hook_event_name", "")
    session_id = data.get("session_id", "")
    tool_name = data.get("tool_name", "")
    tool_use_id = data.get("tool_use_id")
    now = time.time()

    with sqlite3.connect(DB_PATH) as conn:
        init_db(conn)

        if event == "UserPromptSubmit":
            prompt = data.get("prompt", "")
            conn.execute(
                "INSERT OR IGNORE INTO sessions (session_id, initial_prompt, created_at) VALUES (?, ?, ?)",
                (session_id, prompt, now),
            )

        elif event == "PreToolUse":
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

        elif event == "PermissionRequest":
            row_id = find_pending_id(conn, session_id, tool_name, tool_use_id)
            if row_id:
                conn.execute(
                    "UPDATE tool_uses SET permission_requested_at = ? WHERE id = ?",
                    (now, row_id),
                )
            else:
                print(f"track.py: no pending row for PermissionRequest {tool_use_id}", file=sys.stderr)

        elif event in ("PostToolUse", "PostToolUseFailure"):
            success = 1 if event == "PostToolUse" else 0
            error = data.get("error") if event == "PostToolUseFailure" else None
            row_id = find_pending_id(conn, session_id, tool_name, tool_use_id)
            if row_id:
                conn.execute(
                    "UPDATE tool_uses SET ended_at = ?, success = ?, error = ?, tool_response = ? WHERE id = ?",
                    (now, success, error, truncate_response(data.get("tool_response")), row_id),
                )
            else:
                print(f"track.py: no pending row for {event} {tool_use_id}", file=sys.stderr)


if __name__ == "__main__":
    main()

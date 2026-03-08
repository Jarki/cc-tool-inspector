"""
Shared database layer — DB path, schema, helpers.
Imported by both track.py (writes) and the dashboard (reads).
"""
import json
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tool_tracker.db")

# Truncate large responses to keep the DB manageable.
TOOL_RESPONSE_MAX = 8_000  # characters


def init_db(conn):
    conn.execute("PRAGMA journal_mode=WAL")
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
    # Migrate existing DBs that predate this schema.
    existing = {row[1] for row in conn.execute("PRAGMA table_info(tool_uses)")}
    for col, typedef in [("agent_type", "TEXT"), ("tool_response", "TEXT")]:
        if col not in existing:
            conn.execute(f"ALTER TABLE tool_uses ADD COLUMN {col} {typedef}")
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
    # Fallback: most recent unfinished row for session + tool name.
    row = conn.execute(
        """SELECT id FROM tool_uses
           WHERE session_id = ? AND tool_name = ? AND ended_at IS NULL
           ORDER BY started_at DESC LIMIT 1""",
        (session_id, tool_name)
    ).fetchone()
    return row[0] if row else None


def truncate_response(response):
    """Serialize and truncate tool_response to avoid bloating the DB."""
    if response is None:
        return None
    serialized = json.dumps(response)
    if len(serialized) > TOOL_RESPONSE_MAX:
        serialized = serialized[:TOOL_RESPONSE_MAX] + "…[truncated]"
    return serialized


def query(sql, params=()):
    """Read-only query helper — returns a list of dicts."""
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]

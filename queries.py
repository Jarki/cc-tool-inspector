"""
Read-only SQL queries for the dashboard.
Never executes DML — dashboard never writes to the DB.
"""
from db import query


def get_sessions():
    return query("""
        SELECT
            session_id,
            MIN(started_at) as first_seen,
            MAX(COALESCE(ended_at, started_at)) as last_seen,
            COUNT(*) as total_calls,
            SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
            SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failures,
            SUM(CASE WHEN ended_at IS NULL THEN 1 ELSE 0 END) as in_progress,
            (SELECT cwd FROM tool_uses t2 WHERE t2.session_id = t1.session_id ORDER BY started_at ASC LIMIT 1) as cwd
        FROM tool_uses t1
        GROUP BY session_id
        ORDER BY first_seen DESC
        LIMIT 50
    """)


def get_session(session_id):
    return query("""
        SELECT
            id, tool_use_id, agent_type, tool_name, cwd, tool_input,
            started_at, permission_requested_at, ended_at,
            success, error, tool_response
        FROM tool_uses
        WHERE session_id = ?
        ORDER BY started_at ASC
    """, (session_id,))

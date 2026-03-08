# AGENTS.md

Guidelines for AI agents working in this repository.

## What this repo is

A modular tool-use tracker for Claude Code. `track.py` is a hook script that writes every tool event to SQLite. `dashboard.py` serves a local web UI that reads from that database.

## Module layout

```
tooltracker/
├── db.py          — Shared DB layer: DB_PATH, init_db, query, find_pending_id, truncate_response
├── queries.py     — Read-only SQL: get_sessions(), get_session()
├── handler.py     — HTTP handler: routes /api/* and serves static/
├── dashboard.py   — Entrypoint: starts HTTPServer on port 7337
├── track.py       — Hook script: stdin JSON → SQLite writes
└── static/
    ├── index.html — HTML skeleton
    ├── style.css  — All CSS
    └── app.js     — All JS
```

`tool_tracker.db` is auto-created on the first hook call. Do not commit it.

## Constraints

- **No third-party dependencies.** All Python files use the stdlib only.
- **track.py must be non-blocking.** It runs inside a Claude Code hook with a 5-second timeout. `db.py` does no I/O at import time — `DB_PATH` is just a string constant. Don't add anything slow to the import path.
- **dashboard.py / queries.py are read-only.** They never write to the database. Only `track.py` calls `init_db` and executes DML.
- **SQLite WAL mode is required.** `db.py` sets `PRAGMA journal_mode=WAL` on every connection. Don't remove this.
- **handler.py guards against path traversal.** The `_static` method uses `os.path.realpath` to verify paths stay inside `static/`. Don't weaken this check.

## Dependency graph

```
track.py   → db.py
dashboard.py → handler.py → queries.py → db.py
```

No circular imports. `db.py` has no internal imports beyond stdlib.

## Schema

Table `tool_uses` in `tool_tracker.db`:

| Column | Type | Notes |
|---|---|---|
| `tool_use_id` | TEXT | From Claude Code hook payload |
| `session_id` | TEXT | Indexed |
| `agent_type` | TEXT | Nullable |
| `tool_name` | TEXT | e.g. `Read`, `Bash`, `Edit` |
| `cwd` | TEXT | Working directory at call time |
| `tool_input` | TEXT | JSON-serialised tool arguments |
| `started_at` | REAL | Unix timestamp (PreToolUse) |
| `permission_requested_at` | REAL | Unix timestamp (PermissionRequest), nullable |
| `ended_at` | REAL | Unix timestamp (PostToolUse/Failure), nullable |
| `success` | INTEGER | 1 = ok, 0 = failed, NULL = in progress |
| `error` | TEXT | Nullable |
| `tool_response` | TEXT | Truncated to 8 000 chars |

Adding columns: use `ALTER TABLE … ADD COLUMN` guarded by a `PRAGMA table_info` check (see `init_db` in `db.py`). Never drop or rename existing columns.

## Dashboard UI

Frontend lives in `static/`. No build step — edit files directly. Key JS globals in `app.js`:

- `currentSession` — session ID string or null
- `currentRows` — flat array of row dicts for the selected session
- `renderTimeline(rows)` — redraws swim-lane timeline
- `renderStats(rows)` — redraws file-access and Bash stats panels
- `renderSessions(sessions)` — redraws the sidebar list

When adding new stats panels, follow the `.sp` / `.sp-table` CSS pattern in `style.css`.

## Things to avoid

- Don't add a build system, bundler, or template engine.
- Don't introduce a web framework; `http.server.BaseHTTPRequestHandler` is intentional.
- Don't store unbounded data in `tool_response` — the 8 000-char truncation in `truncate_response()` (in `db.py`) must stay.
- Don't bind the dashboard to `0.0.0.0` by default; it defaults to `127.0.0.1`.
- Don't add I/O or slow operations to module-level code in `db.py` — it is imported by `track.py` on every hook invocation.

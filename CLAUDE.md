# CLAUDE.md

## Project

Modular Claude Code tool-use tracker. See `AGENTS.md` for full architecture notes and schema. See `README.md` for setup and usage.

## Module layout

| File | Role |
|---|---|
| `db.py` | Shared DB layer — `DB_PATH`, `init_db`, `query`, `find_pending_id`, `truncate_response` |
| `queries.py` | Read-only SQL queries — `get_sessions`, `get_session` |
| `handler.py` | HTTP handler — routes API endpoints and serves `static/` |
| `dashboard.py` | Thin entrypoint — starts `HTTPServer` |
| `track.py` | Hook script — reads stdin JSON, writes to SQLite |
| `static/index.html` | HTML skeleton |
| `static/style.css` | All CSS |
| `static/app.js` | All JS |

## Hard rules

- No third-party dependencies — stdlib only.
- `track.py` runs inside a 5-second hook timeout. Keep it fast; no I/O at import time.
- `queries.py` and `dashboard.py` never write to the database. Only `track.py` does.
- Always set `PRAGMA journal_mode=WAL` when opening the database (`db.py` handles this).
- Never bind the dashboard to `0.0.0.0` by default (`TRACKER_HOST` env var exists for that).
- Keep `truncate_response()` in `db.py` — `tool_response` must stay capped at 8 000 chars.

## Running locally

```sh
python3 dashboard.py          # http://localhost:7337
TRACKER_PORT=8080 python3 dashboard.py
```

## Editing the UI

Frontend lives in `static/` — no build step. Edit `style.css`, `app.js`, or `index.html` directly. Use `.sp` / `.sp-table` CSS classes for new stats panels. Call `renderStats(rows)` alongside `renderTimeline(rows)` whenever rows change.

## Schema changes

Add columns only via `ALTER TABLE … ADD COLUMN`, gated by a `PRAGMA table_info` check (see `init_db` in `db.py`). Never drop or rename existing columns.

# tooltracker

Tracks every Claude Code tool call and shows them in a local web dashboard.

## How it works

`track.py` is a hook script that Claude Code calls before and after every tool use. It writes to a SQLite database. `dashboard.py` is a small stdlib HTTP server that reads from that database and serves a timeline UI.

## Setup

### 1. Register the hooks

Add the following to `~/.claude/settings.json` under the top-level `"hooks"` key:

```json
"hooks": {
  "PreToolUse": [{
    "matcher": "",
    "hooks": [{ "type": "command", "command": "python3 /path/to/tooltracker/track.py", "timeout": 5, "async": true }]
  }],
  "PermissionRequest": [{
    "matcher": "",
    "hooks": [{ "type": "command", "command": "python3 /path/to/tooltracker/track.py", "timeout": 5, "async": true }]
  }],
  "PostToolUse": [{
    "matcher": "",
    "hooks": [{ "type": "command", "command": "python3 /path/to/tooltracker/track.py", "timeout": 5, "async": true }]
  }],
  "PostToolUseFailure": [{
    "matcher": "",
    "hooks": [{ "type": "command", "command": "python3 /path/to/tooltracker/track.py", "timeout": 5, "async": true }]
  }]
}
```

Replace `/path/to/tooltracker/` with the actual directory. No need to restart Claude Code — hooks are picked up immediately.

### 2. Start the dashboard

```sh
python3 /path/to/tooltracker/dashboard.py
```

Then open http://localhost:7337.

The dashboard auto-refreshes every 3 seconds. No browser extension or external dependency needed — stdlib only.

## Configuration

| Env var | Default | Description |
|---|---|---|
| `TRACKER_HOST` | `127.0.0.1` | Host to bind the dashboard to |
| `TRACKER_PORT` | `7337` | Port to bind the dashboard to |

```sh
TRACKER_HOST=0.0.0.0 python3 dashboard.py   # expose on the local network
```

## Dashboard

The left sidebar lists recent sessions (most recent first). Click one to load its timeline.

**Timeline** shows each tool as a swim lane. Bars are colour-coded:

| Colour | Meaning |
|---|---|
| Green | Completed successfully |
| Red | Failed |
| Yellow → Blue | Permission prompt wait → execution after approval |
| Purple (pulsing) | Still running |

Hover any bar for full details: timestamps, duration, tool input, response, errors.

Toggle **Show gaps** to switch between a compact sequential view and a time-proportional layout that shows real pauses between calls.

**Stats panels** appear below the timeline for sessions that used file or shell tools:

- **File access** — which files were Read / Written / Edited, and how many times each
- **Bash — most called** — commands ranked by call count, with avg and max duration
- **Bash — slowest** — same data ranked by worst-case duration

## Files

| File | Purpose |
|---|---|
| `db.py` | Shared DB layer — schema, helpers, `query()` |
| `queries.py` | Read-only SQL queries for the dashboard |
| `handler.py` | HTTP handler — API routes and static file serving |
| `dashboard.py` | Entrypoint — starts the web server |
| `track.py` | Hook script — called by Claude Code, writes to SQLite |
| `static/` | Frontend — `index.html`, `style.css`, `app.js` |
| `tool_tracker.db` | SQLite database — auto-created on first hook call |

## Notes

- `tool_response` is stored truncated to 8 000 characters to keep the database small.
- The database uses WAL mode so reads (dashboard) and writes (hooks) don't block each other.
- To reset all data: `rm tool_tracker.db`. It will be recreated automatically.

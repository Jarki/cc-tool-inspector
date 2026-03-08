# tooltracker

A Claude Code plugin that records every tool call your AI session makes and displays them in a local web dashboard. See exactly which files were read, what shell commands ran, how long each tool took, when permission prompts appeared, and what failed — across all your sessions, in real time.

Data stays entirely local: a single SQLite file, no external services, no third-party dependencies.

## Install

```sh
claude plugin add /path/to/tooltracker
```

The plugin registers all hooks automatically. Once installed, every Claude Code session is tracked without any further setup.

## Start the dashboard

```sh
/dashboard
```

Or run it directly:

```sh
python3 /path/to/tooltracker/dashboard.py
```

Then open http://localhost:7337. The dashboard auto-refreshes every 3 seconds.

## Configuration

| Env var | Default | Description |
|---|---|---|
| `TRACKER_HOST` | `127.0.0.1` | Host to bind the dashboard to |
| `TRACKER_PORT` | `7337` | Port to bind the dashboard to |

```sh
TRACKER_HOST=0.0.0.0 python3 dashboard.py   # expose on the local network
```

## Dashboard

The left sidebar lists recent sessions (most recent first), each labelled with a human-readable name derived from its UUID (e.g. *amber-albatross*). The first line of the session's initial user prompt is shown below the name. Click a session to load its timeline. The sidebar can be collapsed with the toggle button; the state is remembered across page loads.

**Timeline** shows each tool as a swim lane. Bars are colour-coded:

| Colour | Meaning |
|---|---|
| Green | Completed successfully |
| Red | Failed |
| Yellow → Blue | Permission prompt wait → execution after approval |
| Purple (pulsing) | Still running |

Hover any bar for full details: timestamps, duration, tool input, response, errors.

Toggle **Show gaps** to switch between a compact sequential view and a time-proportional layout that shows real pauses between calls.

**Bash timeline** appears below the main timeline when the session contains Bash calls. It shows every shell command as its own swim lane, grouped and colour-coded the same way as the main timeline.

**Stats panels** appear below for sessions that used file or shell tools:

- **File access** — which files were Read / Written / Edited, and how many times each
- **Bash — most called** — commands ranked by call count, with avg and max duration
- **Bash — slowest** — same data ranked by worst-case duration

## How it works

`track.py` is a hook script that Claude Code calls before and after every tool use. It writes to a SQLite database. `dashboard.py` is a small stdlib HTTP server that reads from that database and serves a timeline UI.

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

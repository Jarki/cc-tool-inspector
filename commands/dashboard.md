---
description: Start, stop, or check the tooltracker web dashboard
argument-hint: start | stop | status (default: start)
allowed-tools: ["Bash"]
---

Manage the tooltracker dashboard at http://localhost:7337.

The dashboard is served by `${CLAUDE_PLUGIN_ROOT}/dashboard.py` on port 7337 (override with `TRACKER_PORT`). A PID file at `/tmp/tooltracker-dashboard.pid` tracks the running process.

## Action: start (default)

Check if the dashboard is already running. If it is, tell the user and show the URL. If not, start it in the background:

```bash
nohup python3 "${CLAUDE_PLUGIN_ROOT}/dashboard.py" >/tmp/tooltracker-dashboard.log 2>&1 &
echo $! > /tmp/tooltracker-dashboard.pid
```

Then confirm it started and print the URL.

## Action: stop

Read the PID from `/tmp/tooltracker-dashboard.pid` and kill the process. Remove the PID file. If no PID file exists, say it is not running.

## Action: status

Check whether the PID in `/tmp/tooltracker-dashboard.pid` is still alive. Report running (with URL) or stopped. Also show the tail of `/tmp/tooltracker-dashboard.log` if it exists.

---

Determine the action from `$ARGUMENTS` (default to `start`) and execute the appropriate steps above.

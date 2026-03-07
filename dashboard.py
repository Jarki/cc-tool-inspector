#!/usr/bin/env python3
"""
Claude Code tool tracker dashboard — session timeline view.
Run this script then open http://192.168.22.40:7337
"""
import sqlite3
import json
import os
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tool_tracker.db")
PORT = 7337


def query(sql, params=()):
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


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
            MAX(cwd) as cwd
        FROM tool_uses
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


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Claude Tool Tracker</title>
<style>
  :root {
    --bg: #0d1117; --surface: #161b22; --surface2: #21262d; --surface3: #2d333b;
    --border: #30363d; --text: #e6edf3; --muted: #8b949e;
    --accent: #58a6ff; --green: #3fb950; --red: #f85149;
    --yellow: #e3b341; --purple: #bc8cff; --orange: #f0883e;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: ui-monospace,"SF Mono",Menlo,monospace; font-size: 13px; display: flex; height: 100vh; overflow: hidden; }

  /* ── Sidebar ── */
  #sidebar { width: 280px; min-width: 200px; background: var(--surface); border-right: 1px solid var(--border); display: flex; flex-direction: column; overflow: hidden; resize: horizontal; }
  #sidebar-header { padding: 12px 16px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; }
  #sidebar-header h1 { font-size: 13px; font-weight: 600; }
  .live-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--green); animation: blink 2s infinite; }
  @keyframes blink { 0%,100%{opacity:1} 50%{opacity:.3} }
  #session-list { overflow-y: auto; flex: 1; }
  .session-item { padding: 9px 14px; cursor: pointer; border-bottom: 1px solid var(--border); transition: background .1s; }
  .session-item:hover { background: var(--surface2); }
  .session-item.active { background: var(--surface3); border-left: 2px solid var(--accent); }
  .s-id { color: var(--accent); font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .s-meta { color: var(--muted); font-size: 11px; margin-top: 2px; display: flex; gap: 6px; flex-wrap: wrap; }
  .s-cwd { color: var(--muted); font-size: 10px; margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .pill { padding: 1px 5px; border-radius: 3px; font-size: 10px; font-weight: 600; }
  .pill-g { background:#1a3a1e; color:var(--green); }
  .pill-r { background:#3a1a1a; color:var(--red); }
  .pill-y { background:#3a2e10; color:var(--yellow); }

  /* ── Main ── */
  #main { flex: 1; display: flex; flex-direction: column; overflow: hidden; min-width: 0; }
  #main-header { padding: 10px 18px; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 10px; flex-wrap: wrap; min-height: 42px; }
  #session-title { font-size: 12px; font-weight: 600; color: var(--muted); }
  #session-title span { color: var(--accent); }
  .chip { background: var(--surface2); border: 1px solid var(--border); border-radius: 4px; padding: 1px 7px; font-size: 11px; color: var(--muted); }
  .chip b { color: var(--text); }

  #tl-wrap { flex: 1; overflow: auto; padding: 14px 18px; }

  /* ── Legend ── */
  #legend { display: flex; gap: 14px; margin-bottom: 12px; align-items: center; flex-wrap: wrap; }
  .leg { display: flex; align-items: center; gap: 5px; font-size: 11px; color: var(--muted); }
  .leg-sw { width: 11px; height: 11px; border-radius: 2px; flex-shrink: 0; }

  /* ── Axis ── */
  #axis { position: relative; height: 16px; margin-left: var(--label-w); margin-bottom: 2px; font-size: 10px; color: var(--muted); }
  .ax-tick { position: absolute; transform: translateX(-50%); white-space: nowrap; }

  /* ── Swim lanes ── */
  :root { --label-w: 120px; --row-h: 30px; --bar-h: 18px; }
  #timeline { }
  .lane { display: flex; align-items: center; margin-bottom: 3px; }
  .lane-label {
    width: var(--label-w); min-width: var(--label-w);
    text-align: right; padding-right: 10px;
    font-size: 11px; font-weight: 600; color: var(--text);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .lane-track {
    flex: 1; position: relative; height: var(--row-h); overflow: hidden;
  }
  /* baseline rule */
  .lane-track::after {
    content:''; position: absolute; top: 50%; left: 0; right: 0;
    height: 1px; background: var(--surface2);
  }

  /* individual bar */
  .tl-bar {
    position: absolute;
    top: calc((var(--row-h) - var(--bar-h)) / 2);
    height: var(--bar-h);
    border-radius: 3px;
    display: flex; overflow: hidden;
    min-width: 3px; cursor: pointer;
    transition: filter .12s;
    z-index: 1;
  }
  .tl-bar:hover { filter: brightness(1.35); }
  .seg-perm { background: var(--yellow); }
  .seg-exec { background: var(--accent); }
  .seg-ok   { background: var(--green); }
  .seg-err  { background: var(--red); }
  .seg-run  { background: var(--purple); animation: pulse 1s infinite alternate; }
  @keyframes pulse { from{opacity:.55} to{opacity:1} }

  /* call-number badge inside bar — absolutely positioned so segments fill the full width */
  .bar-num { position: absolute; right: 2px; top: 50%; transform: translateY(-50%); font-size: 9px; color: #fff9; pointer-events: none; }

  /* ── Tooltip ── */
  #tt {
    position: fixed; background: var(--surface); border: 1px solid var(--border);
    border-radius: 6px; padding: 10px 14px; font-size: 12px; pointer-events: none;
    z-index: 200; max-width: 460px; box-shadow: 0 8px 28px #0009; display: none;
  }
  .tt-name { font-size: 13px; font-weight: 700; color: var(--accent); margin-bottom: 7px; }
  .tt-grid { display: grid; grid-template-columns: 110px 1fr; row-gap: 3px; }
  .tt-k { color: var(--muted); }
  .tt-v { color: var(--text); word-break: break-all; }
  .tt-v.red { color: var(--red); }
  .tt-v.grn { color: var(--green); }
  .tt-section { margin-top: 8px; border-top: 1px solid var(--border); padding-top: 8px; font-size: 11px; }
  .tt-section-title { color: var(--muted); font-size: 10px; text-transform: uppercase; letter-spacing: .4px; margin-bottom: 4px; }
  .tt-code { background: var(--surface2); border-radius: 3px; padding: 5px 7px; color: var(--muted); white-space: pre-wrap; word-break: break-all; max-height: 130px; overflow-y: auto; }

  #empty { color: var(--muted); padding: 48px; text-align: center; }
</style>
</head>
<body>

<div id="sidebar">
  <div id="sidebar-header">
    <h1>Sessions</h1>
    <div class="live-dot" title="auto-refreshing"></div>
  </div>
  <div id="session-list"></div>
</div>

<div id="main">
  <div id="main-header">
    <div id="session-title">Select a session</div>
  </div>
  <div id="tl-wrap">
    <div id="empty">← Pick a session</div>
    <div id="legend" style="display:none">
      <span style="color:var(--muted);font-size:11px">Legend:</span>
      <div class="leg"><div class="leg-sw" style="background:var(--yellow)"></div>Perm wait</div>
      <div class="leg"><div class="leg-sw" style="background:var(--accent)"></div>Exec after perm</div>
      <div class="leg"><div class="leg-sw" style="background:var(--green)"></div>Completed</div>
      <div class="leg"><div class="leg-sw" style="background:var(--red)"></div>Failed</div>
      <div class="leg"><div class="leg-sw" style="background:var(--purple)"></div>Running</div>
      <label class="leg" style="margin-left:auto;cursor:pointer;user-select:none">
        <input type="checkbox" id="gap-toggle" style="accent-color:var(--accent)">
        Show gaps
      </label>
    </div>
    <div id="axis"></div>
    <div id="timeline"></div>
  </div>
</div>

<div id="tt"></div>

<script>
let currentSession = null;
let showGaps = false;
// map session_id -> flat list of rows
let sessionRows = {};

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('gap-toggle').addEventListener('change', function() {
    showGaps = this.checked;
    if (currentSession && sessionRows[currentSession]) renderTimeline(sessionRows[currentSession]);
  });
});

// ── Formatting helpers ────────────────────────────────────────────────────────
function fmt(sec) {
  if (sec == null) return '—';
  if (sec < 0.001) return '<1ms';
  if (sec < 1) return (sec * 1000).toFixed(0) + 'ms';
  return sec.toFixed(3) + 's';
}
function fmtTs(ts) {
  if (!ts) return '—';
  return new Date(ts * 1000).toLocaleTimeString('en-GB', {
    hour12: false, hour:'2-digit', minute:'2-digit', second:'2-digit', fractionalSecondDigits: 3
  });
}
function fmtAxisTs(ts) {
  if (!ts) return '';
  return new Date(ts * 1000).toLocaleTimeString('en-GB', {
    hour12: false, hour:'2-digit', minute:'2-digit', second:'2-digit'
  });
}
function fmtJson(s) {
  try { return JSON.stringify(JSON.parse(s), null, 2); }
  catch { return s || ''; }
}
function esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Tooltip ───────────────────────────────────────────────────────────────────
const tt = document.getElementById('tt');
document.addEventListener('mousemove', e => {
  if (tt.style.display !== 'none') {
    let x = e.clientX + 18, y = e.clientY + 10;
    if (x + tt.offsetWidth  > window.innerWidth  - 10) x = e.clientX - tt.offsetWidth  - 10;
    if (y + tt.offsetHeight > window.innerHeight - 10) y = e.clientY - tt.offsetHeight - 10;
    tt.style.left = x + 'px'; tt.style.top = y + 'px';
  }
});

function showTt(e, row) {
  const dur      = row.ended_at ? row.ended_at - row.started_at : null;
  const permWait = row.permission_requested_at && row.ended_at
                   ? row.permission_requested_at - row.started_at : null;
  const execAfterPerm = row.permission_requested_at && row.ended_at
                   ? row.ended_at - row.permission_requested_at : null;

  const statusHtml = row.ended_at == null
    ? '<span style="color:var(--yellow)">running…</span>'
    : row.success
      ? '<span class="tt-v grn">ok</span>'
      : '<span class="tt-v red">failed</span>';

  let inputSection = '';
  if (row.tool_input) {
    const parsed = (() => { try { return JSON.parse(row.tool_input); } catch { return null; } })();
    if (parsed) {
      // show each key as its own labelled block
      const entries = Object.entries(parsed).map(([k, v]) => {
        const val = typeof v === 'string' ? v : JSON.stringify(v, null, 2);
        return `<div class="tt-section-title">${esc(k)}</div><div class="tt-code">${esc(val)}</div>`;
      }).join('');
      inputSection = `<div class="tt-section">${entries}</div>`;
    }
  }

  let responseSection = '';
  if (row.tool_response) {
    responseSection = `<div class="tt-section"><div class="tt-section-title">tool_response</div><div class="tt-code">${esc(fmtJson(row.tool_response))}</div></div>`;
  }

  let errorSection = row.error
    ? `<div class="tt-section"><div class="tt-section-title">error</div><div class="tt-code" style="color:var(--red)">${esc(row.error)}</div></div>`
    : '';

  tt.innerHTML = `
    <div class="tt-name">${esc(row.tool_name)}${row.agent_type ? ` <span style="color:var(--muted);font-weight:400;font-size:11px">via ${esc(row.agent_type)}</span>` : ''}</div>
    <div class="tt-grid">
      <span class="tt-k">status</span><span>${statusHtml}</span>
      <span class="tt-k">started</span><span class="tt-v">${fmtTs(row.started_at)}</span>
      ${row.permission_requested_at ? `<span class="tt-k">perm requested</span><span class="tt-v">${fmtTs(row.permission_requested_at)}</span>` : ''}
      <span class="tt-k">ended</span><span class="tt-v">${fmtTs(row.ended_at)}</span>
      <span class="tt-k">total</span><span class="tt-v">${fmt(dur)}</span>
      ${permWait     != null ? `<span class="tt-k">perm wait</span><span class="tt-v" style="color:var(--yellow)">${fmt(permWait)}</span>` : ''}
      ${execAfterPerm!= null ? `<span class="tt-k">exec</span><span class="tt-v" style="color:var(--accent)">${fmt(execAfterPerm)}</span>` : ''}
      ${row.cwd ? `<span class="tt-k">cwd</span><span class="tt-v" style="color:var(--muted);font-size:11px">${esc(row.cwd)}</span>` : ''}
    </div>
    ${inputSection}${responseSection}${errorSection}
  `;
  tt.style.display = 'block';
  tt.style.left = (e.clientX + 18) + 'px';
  tt.style.top  = (e.clientY + 10) + 'px';
}
function hideTt() { tt.style.display = 'none'; }

// ── Timeline renderer (swim lanes) ───────────────────────────────────────────
function renderTimeline(rows) {
  const tlEl     = document.getElementById('timeline');
  const legendEl = document.getElementById('legend');
  const axisEl   = document.getElementById('axis');
  const emptyEl  = document.getElementById('empty');

  if (!rows || rows.length === 0) {
    tlEl.innerHTML = ''; legendEl.style.display = 'none'; axisEl.innerHTML = '';
    emptyEl.style.display = 'block';
    emptyEl.textContent = 'No tool calls yet.';
    return;
  }
  emptyEl.style.display = 'none';
  legendEl.style.display = 'flex';

  const N = rows.length;
  let getPos, axHtml = '';

  if (!showGaps) {
    // ── Sequential mode: equal slot per call, no time gaps ──
    const GAP_PCT = Math.min(0.3, 20 / N);
    const slotW   = 100 / N;
    const barW    = slotW - GAP_PCT;
    getPos = (row, rank) => ({ left: rank * slotW + GAP_PCT / 2, width: barW });

    const TICKS = N === 1 ? 1 : Math.min(N, 8);
    for (let i = 0; i < TICKS; i++) {
      const idx = N === 1 ? 0 : Math.round(i / (TICKS - 1) * (N - 1));
      const pct = (idx / N) * 100 + slotW / 2;
      axHtml += `<span class="ax-tick" style="left:${pct}%">${fmtAxisTs(rows[idx].started_at)}</span>`;
    }
  } else {
    // ── Time-proportional mode: position by real timestamp ──
    const tMin = rows[0].started_at;
    const tMax = rows.reduce((m, r) => Math.max(m, r.ended_at || r.started_at), tMin);
    const span = (tMax - tMin) || 1;
    const minW = Math.max(0.4, 60 / (rows.length));  // min bar width in %

    getPos = (row, rank) => {
      const left  = (row.started_at - tMin) / span * 100;
      const durPct = row.ended_at ? (row.ended_at - row.started_at) / span * 100 : minW;
      return { left, width: Math.max(minW, durPct) };
    };

    const TICKS = 6;
    for (let i = 0; i < TICKS; i++) {
      const pct = i / (TICKS - 1) * 100;
      const ts  = tMin + i / (TICKS - 1) * span;
      axHtml += `<span class="ax-tick" style="left:${pct}%">${fmtAxisTs(ts)}</span>`;
    }
  }
  axisEl.innerHTML = axHtml;

  // Group into swim lanes by tool_name, preserving original row indices for tooltips.
  const laneMap = new Map();
  rows.forEach((r, i) => {
    if (!laneMap.has(r.tool_name)) laneMap.set(r.tool_name, []);
    laneMap.get(r.tool_name).push({ row: r, rank: i });
  });

  // Sort lanes by first appearance
  const lanes = [...laneMap.entries()].sort(
    (a, b) => a[1][0].rank - b[1][0].rank
  );

  tlEl.innerHTML = lanes.map(([toolName, entries]) => {
    const barsHtml = entries.map(({ row, rank }) => {
      const { left, width } = getPos(row, rank);

      let segs = '';
      const callNum = rank + 1;
      const badge = entries.length > 1
        ? `<span class="bar-num">${callNum}</span>` : '';

      if (!row.ended_at) {
        segs = `<div class="seg-run" style="flex:1"></div>${badge}`;
      } else if (!row.success) {
        segs = `<div class="seg-err" style="flex:1"></div>${badge}`;
      } else if (row.permission_requested_at) {
        const permFrac = (row.permission_requested_at - row.started_at)
                         / (row.ended_at - row.started_at);
        const pp = Math.min(permFrac * 100, 97);
        segs = `<div class="seg-perm" style="width:${pp}%"></div>`
             + `<div class="seg-exec" style="flex:1"></div>${badge}`;
      } else {
        segs = `<div class="seg-ok" style="flex:1"></div>${badge}`;
      }

      return `<div class="tl-bar"
        style="left:${left}%;width:${width}%"
        onmouseenter="showTt(event, sessionRows[currentSession][${rank}])"
        onmouseleave="hideTt()"
      >${segs}</div>`;
    }).join('');

    return `<div class="lane">
      <div class="lane-label" title="${esc(toolName)}">${esc(toolName)}</div>
      <div class="lane-track">${barsHtml}</div>
    </div>`;
  }).join('');
}

// ── Session list renderer ─────────────────────────────────────────────────────
function renderSessions(sessions) {
  document.getElementById('session-list').innerHTML = sessions.map(s => {
    const time = new Date(s.first_seen * 1000).toLocaleTimeString('en-GB', {hour12:false});
    const date = new Date(s.first_seen * 1000).toLocaleDateString('en-GB', {month:'short', day:'numeric'});
    const cwd  = (s.cwd || '').replace(/.*\/([^/]+\/[^/]+)$/, '…/$1');
    return `<div class="session-item ${s.session_id === currentSession ? 'active' : ''}"
         onclick="selectSession('${s.session_id}')">
      <div class="s-id">${s.session_id.slice(0,8)}…</div>
      <div class="s-meta">
        <span>${date} ${time}</span>
        ${s.successes  ? `<span class="pill pill-g">${s.successes} ok</span>` : ''}
        ${s.failures   ? `<span class="pill pill-r">${s.failures} err</span>` : ''}
        ${s.in_progress? `<span class="pill pill-y">${s.in_progress} …</span>` : ''}
      </div>
      <div class="s-cwd" title="${esc(s.cwd || '')}">${esc(cwd)}</div>
    </div>`;
  }).join('');
}

function updateHeader(rows, sid) {
  const el = document.getElementById('session-title');
  if (!rows?.length) { el.innerHTML = `Session <span>${sid.slice(0,8)}…</span>`; return; }
  const dur = rows.at(-1).ended_at ? rows.at(-1).ended_at - rows[0].started_at : null;
  const ok  = rows.filter(r => r.success === 1).length;
  const err = rows.filter(r => r.success === 0).length;
  const run = rows.filter(r => r.ended_at == null).length;
  el.innerHTML = `Session <span>${sid.slice(0,8)}…</span>
    <span class="chip"><b>${rows.length}</b> calls</span>
    ${ok  ? `<span class="chip" style="color:var(--green)"><b>${ok}</b> ok</span>` : ''}
    ${err ? `<span class="chip" style="color:var(--red)"><b>${err}</b> failed</span>` : ''}
    ${run ? `<span class="chip" style="color:var(--yellow)"><b>${run}</b> running</span>` : ''}
    ${dur != null ? `<span class="chip">span <b>${fmt(dur)}</b></span>` : ''}`;
}

// ── Data fetching ─────────────────────────────────────────────────────────────
async function selectSession(id) {
  currentSession = id;
  const [sRes, rRes] = await Promise.all([
    fetch('/api/sessions'),
    fetch('/api/session?id=' + encodeURIComponent(id)),
  ]);
  const [sessions, rows] = await Promise.all([sRes.json(), rRes.json()]);
  sessionRows[id] = rows;
  renderSessions(sessions);
  renderTimeline(rows);
  updateHeader(rows, id);
}

async function refresh() {
  const sRes = await fetch('/api/sessions');
  const sessions = await sRes.json();
  renderSessions(sessions);
  if (currentSession) {
    const rRes = await fetch('/api/session?id=' + encodeURIComponent(currentSession));
    const rows = await rRes.json();
    sessionRows[currentSession] = rows;
    renderTimeline(rows);
    updateHeader(rows, currentSession);
  }
}

refresh();
setInterval(refresh, 3000);
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        if parsed.path == "/api/sessions":
            body = json.dumps(get_sessions()).encode()
            ct = "application/json"
        elif parsed.path == "/api/session":
            sid = qs.get("id", [""])[0]
            body = json.dumps(get_session(sid)).encode()
            ct = "application/json"
        elif parsed.path in ("/", "/index.html"):
            body = HTML.encode()
            ct = "text/html"
        else:
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002
        pass


if __name__ == "__main__":
    server = HTTPServer(("192.168.22.40", PORT), Handler)
    print(f"Dashboard running at http://192.168.22.40:{PORT}")
    print(f"Database: {DB_PATH}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")

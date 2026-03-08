let currentSession = null;
let showGaps = true;
let currentRows = [];

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('gap-toggle').addEventListener('change', function() {
    showGaps = this.checked;
    if (currentSession && currentRows.length) {
      renderTimeline(currentRows);
      renderBashTimeline(currentRows);
    }
  });
  document.getElementById('session-list').addEventListener('click', e => {
    const item = e.target.closest('.session-item');
    if (item?.dataset.sessionId) selectSession(item.dataset.sessionId);
  });

  // Sidebar collapse/expand
  const sidebar = document.getElementById('sidebar');
  if (localStorage.getItem('sidebar-collapsed') === '1') sidebar.classList.add('collapsed');
  document.getElementById('sidebar-toggle').addEventListener('click', () => {
    const collapsed = sidebar.classList.toggle('collapsed');
    localStorage.setItem('sidebar-collapsed', collapsed ? '1' : '0');
  });
});

// ── Session name generator ────────────────────────────────────────────────────
// Derives a stable human-readable name from a session UUID (no server changes needed).
const SESSION_ADJS = [
  'amber','azure','bold','brave','calm','cobalt','crisp','deft','dry','dusty',
  'early','eager','fair','fast','fern','flat','free','frosty','gold','green',
  'grey','hardy','hazy','idle','inky','jade','keen','lazy','lean','lemon',
  'light','lime','lofty','lunar','misty','mild','mint','neat','neon','noble',
  'oaken','odd','olive','pale','pine','plain','polar','prime','proud','quick',
  'quiet','rapid','red','regal','rosy','rough','royal','rusty','sandy','sharp',
  'shy','silver','slim','slow','smoky','snowy','soft','solar','stark','steel',
  'still','stone','stout','sunny','swift','tall','tame','tan','teal','thin',
  'tidy','tiny','tired','torn','tough','true','turquoise','vivid','warm','wild',
  'wiry','wispy','worn','young','zesty','zinc','iron','icy','grand','glad',
];
const SESSION_NOUNS = [
  'albatross','ape','bear','beetle','bison','boar','bobcat','bullfrog','capybara',
  'cheetah','clam','cobra','condor','coyote','crane','crow','deer','dingo','dove',
  'duck','eagle','elk','emu','falcon','ferret','finch','flamingo','fox','gecko',
  'gnu','goat','goose','gopher','gorilla','hawk','heron','hippo','horse','hyena',
  'ibis','iguana','jackal','jaguar','jay','kite','koala','lemur','leopard','lion',
  'lizard','llama','lynx','magpie','mink','mole','moose','moth','mule','newt',
  'okapi','osprey','otter','owl','panda','parrot','pelican','penguin','pike',
  'porcupine','puma','python','quail','rabbit','raven','rhino','robin','salmon',
  'seal','shark','skunk','sloth','snail','sparrow','spider','stork','swan','tapir',
  'tiger','toad','toucan','trout','turtle','viper','vole','vulture','walrus',
  'weasel','wolf','wombat','woodpecker','wren','yak','zebra',
];
function sessionName(uuid) {
  // Hash the first 16 hex chars into two independent 32-bit numbers
  const h1 = parseInt(uuid.replace(/-/g,'').slice(0, 8), 16) >>> 0;
  const h2 = parseInt(uuid.replace(/-/g,'').slice(8,16), 16) >>> 0;
  const adj  = SESSION_ADJS [h1 % SESSION_ADJS.length];
  const noun = SESSION_NOUNS[h2 % SESSION_NOUNS.length];
  return `${adj}-${noun}`;
}

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
  let usePixels = false, totalTrackPx = 0;

  // Pre-compute positions keyed by row index (rank).
  const posCache = new Map();

  if (!showGaps) {
    // ── Sequential mode: equal slot per call, no time gaps ──
    const GAP_PCT = Math.min(0.3, 20 / N);
    const slotW   = 100 / N;
    const barW    = slotW - GAP_PCT;
    getPos = (row, rank) => {
      if (!posCache.has(rank)) posCache.set(rank, { left: rank * slotW + GAP_PCT / 2, width: barW });
      return posCache.get(rank);
    };

    rows.forEach((r, i) => getPos(r, i));

    const TICKS = N === 1 ? 1 : Math.min(N, 8);
    for (let i = 0; i < TICKS; i++) {
      const idx = N === 1 ? 0 : Math.round(i / (TICKS - 1) * (N - 1));
      const pct = (idx / N) * 100 + slotW / 2;
      axHtml += `<span class="ax-tick" style="left:${pct}%">${fmtAxisTs(rows[idx].started_at)}</span>`;
    }
  } else {
    // ── Time-proportional mode: pixel scale, scrollable ──
    usePixels = true;
    const VIEWPORT_SEC = 300; // 5 minutes fills the visible track width
    const LABEL_W = 120;      // must match --label-w
    const tlWrap  = document.getElementById('tl-wrap');
    const availW  = Math.max(400, tlWrap.clientWidth - LABEL_W - 36); // 36 = 2×18px padding
    const pxPerSec = availW / VIEWPORT_SEC;

    const tMin = rows[0].started_at;
    const tMax = rows.reduce((m, r) => Math.max(m, r.ended_at || r.started_at), tMin);
    const span = (tMax - tMin) || 1;
    totalTrackPx = Math.max(availW, span * pxPerSec);

    getPos = (row, rank) => {
      if (!posCache.has(rank)) {
        const left  = (row.started_at - tMin) * pxPerSec;
        const width = row.ended_at ? (row.ended_at - row.started_at) * pxPerSec : (totalTrackPx - left);
        posCache.set(rank, { left, width });
      }
      return posCache.get(rank);
    };
    rows.forEach((r, i) => getPos(r, i));

    // Axis ticks: 6 evenly-spaced labels across the full track width
    const TICKS = 6;
    for (let i = 0; i < TICKS; i++) {
      const frac = i / (TICKS - 1);
      const px   = frac * totalTrackPx;
      const ts   = tMin + frac * span;
      axHtml += `<span class="ax-tick" style="left:${px}px">${fmtAxisTs(ts)}</span>`;
    }
  }
  axisEl.style.width = usePixels ? totalTrackPx + 'px' : '';
  axisEl.innerHTML = axHtml;

  // Group into swim lanes by tool_name, preserving original row indices for tooltips.
  const laneMap = new Map();
  rows.forEach((r, i) => {
    if (!laneMap.has(r.tool_name)) laneMap.set(r.tool_name, []);
    laneMap.get(r.tool_name).push({ row: r, rank: i });
  });

  // Sort lanes by first appearance.
  const lanes = [...laneMap.entries()].sort(
    (a, b) => a[1][0].rank - b[1][0].rank
  );

  tlEl.innerHTML = lanes.map(([toolName, entries]) => {
    // Sort entries by left position, then cap widths to prevent overlap within the lane.
    const sorted = [...entries].sort((a, b) => posCache.get(a.rank).left - posCache.get(b.rank).left);
    const cappedWidth = new Map();
    const LANE_GAP = usePixels ? 1 : 0.2;
    sorted.forEach((entry, i) => {
      const pos  = posCache.get(entry.rank);
      const next = sorted[i + 1];
      const maxW = next ? posCache.get(next.rank).left - pos.left - LANE_GAP : (usePixels ? totalTrackPx : 100) - pos.left;
      cappedWidth.set(entry.rank, Math.min(pos.width, Math.max(0, maxW)));
    });

    const barsHtml = entries.map(({ row, rank }) => {
      const { left } = posCache.get(rank);
      const width = showGaps ? cappedWidth.get(rank) : posCache.get(rank).width;

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

      const unit = usePixels ? 'px' : '%';
      return `<div class="tl-bar"
        style="left:${left}${unit};width:${width}${unit}"
        onmouseenter="showTt(event, currentRows[${rank}])"
        onmouseleave="hideTt()"
      >${segs}</div>`;
    }).join('');

    const trackStyle = usePixels ? ` style="width:${totalTrackPx}px;flex:none"` : '';
    return `<div class="lane">
      <div class="lane-label" title="${esc(toolName)}">${esc(toolName)}</div>
      <div class="lane-track"${trackStyle}>${barsHtml}</div>
    </div>`;
  }).join('');
}

// ── Bash-only timeline ────────────────────────────────────────────────────────
function renderBashTimeline(rows) {
  const tlEl    = document.getElementById('bash-timeline');
  const axisEl  = document.getElementById('bash-axis');
  const section = document.getElementById('bash-tl-section');
  const countEl = document.getElementById('bash-tl-count');

  const entries = rows.map((r, i) => ({ row: r, rank: i }))
                      .filter(e => e.row.tool_name === 'Bash');

  if (!entries.length) { section.style.display = 'none'; return; }
  section.style.display = '';
  countEl.textContent = entries.length + ' calls';

  let axHtml = '', usePixels = false, totalTrackPx = 0;
  const posCache = new Map();

  if (!showGaps) {
    const N = entries.length;
    const GAP_PCT = Math.min(0.3, 20 / N);
    const slotW   = 100 / N;
    const barW    = slotW - GAP_PCT;
    entries.forEach((e, i) => {
      posCache.set(e.rank, { left: i * slotW + GAP_PCT / 2, width: barW });
    });
    const TICKS = N === 1 ? 1 : Math.min(N, 8);
    for (let i = 0; i < TICKS; i++) {
      const idx = N === 1 ? 0 : Math.round(i / (TICKS - 1) * (N - 1));
      const pct = (idx / N) * 100 + slotW / 2;
      axHtml += `<span class="ax-tick" style="left:${pct}%">${fmtAxisTs(entries[idx].row.started_at)}</span>`;
    }
  } else {
    usePixels = true;
    const VIEWPORT_SEC = 300;
    const LABEL_W = 120;
    const tlWrap  = document.getElementById('tl-wrap');
    const availW  = Math.max(400, tlWrap.clientWidth - LABEL_W - 36);
    const pxPerSec = availW / VIEWPORT_SEC;
    const tMin = entries[0].row.started_at;
    const tMax = entries.reduce((m, e) => Math.max(m, e.row.ended_at || e.row.started_at), tMin);
    const span = (tMax - tMin) || 1;
    totalTrackPx = Math.max(availW, span * pxPerSec);
    entries.forEach(e => {
      const left  = (e.row.started_at - tMin) * pxPerSec;
      const width = e.row.ended_at ? (e.row.ended_at - e.row.started_at) * pxPerSec : (totalTrackPx - left);
      posCache.set(e.rank, { left, width });
    });
    const TICKS = 6;
    for (let i = 0; i < TICKS; i++) {
      const frac = i / (TICKS - 1);
      axHtml += `<span class="ax-tick" style="left:${frac * totalTrackPx}px">${fmtAxisTs(tMin + frac * span)}</span>`;
    }
  }
  axisEl.style.width = usePixels ? totalTrackPx + 'px' : '';
  axisEl.innerHTML = axHtml;

  // Group into lanes by first line of command
  const laneMap = new Map();
  entries.forEach(e => {
    const inp = (() => { try { return JSON.parse(e.row.tool_input) || {}; } catch { return {}; } })();
    const key = (inp.command || '').trim().split('\n')[0].trim().slice(0, 55) || '(empty)';
    if (!laneMap.has(key)) laneMap.set(key, []);
    laneMap.get(key).push(e);
  });
  const lanes = [...laneMap.entries()].sort((a, b) => a[1][0].rank - b[1][0].rank);

  tlEl.innerHTML = lanes.map(([label, laneEntries]) => {
    const sorted = [...laneEntries].sort((a, b) => posCache.get(a.rank).left - posCache.get(b.rank).left);
    const cappedWidth = new Map();
    const LANE_GAP = usePixels ? 1 : 0.2;
    sorted.forEach((entry, i) => {
      const pos  = posCache.get(entry.rank);
      const next = sorted[i + 1];
      const maxW = next ? posCache.get(next.rank).left - pos.left - LANE_GAP : (usePixels ? totalTrackPx : 100) - pos.left;
      cappedWidth.set(entry.rank, Math.min(pos.width, Math.max(0, maxW)));
    });

    const barsHtml = laneEntries.map(({ row, rank }) => {
      const { left } = posCache.get(rank);
      const width = showGaps ? cappedWidth.get(rank) : posCache.get(rank).width;
      const badge = laneEntries.length > 1 ? `<span class="bar-num">${rank + 1}</span>` : '';

      let segs;
      if (!row.ended_at) {
        segs = `<div class="seg-run" style="flex:1"></div>${badge}`;
      } else if (!row.success) {
        segs = `<div class="seg-err" style="flex:1"></div>${badge}`;
      } else if (row.permission_requested_at) {
        const permFrac = (row.permission_requested_at - row.started_at) / (row.ended_at - row.started_at);
        segs = `<div class="seg-perm" style="width:${Math.min(permFrac * 100, 97)}%"></div>`
             + `<div class="seg-exec" style="flex:1"></div>${badge}`;
      } else {
        segs = `<div class="seg-ok" style="flex:1"></div>${badge}`;
      }

      const unit = usePixels ? 'px' : '%';
      return `<div class="tl-bar"
        style="left:${left}${unit};width:${width}${unit}"
        onmouseenter="showTt(event, currentRows[${rank}])"
        onmouseleave="hideTt()"
      >${segs}</div>`;
    }).join('');

    const trackStyle = usePixels ? ` style="width:${totalTrackPx}px;flex:none"` : '';
    return `<div class="lane">
      <div class="lane-label" title="${esc(label)}">${esc(label)}</div>
      <div class="lane-track"${trackStyle}>${barsHtml}</div>
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
         data-session-id="${esc(s.session_id)}">
      <div class="s-id" title="${esc(s.session_id)}">${esc(sessionName(s.session_id))}</div>
      <div class="s-meta">
        <span>${date} ${time}</span>
        ${s.successes  ? `<span class="pill pill-g">${s.successes} ok</span>` : ''}
        ${s.failures   ? `<span class="pill pill-r">${s.failures} err</span>` : ''}
        ${s.in_progress? `<span class="pill pill-y">${s.in_progress} …</span>` : ''}
      </div>
      <div class="s-cwd" title="${esc(s.cwd || '')}">${esc(cwd)}</div>
      ${s.initial_prompt ? `<div class="s-prompt" title="${esc(s.initial_prompt)}">${esc(s.initial_prompt.split('\n')[0].slice(0, 80))}</div>` : ''}
    </div>`;
  }).join('');
}

function updateHeader(rows, sid, prompt) {
  const el = document.getElementById('session-title');
  const promptHtml = prompt
    ? `<div class="session-prompt" title="${esc(prompt)}">${esc(prompt.split('\n')[0].slice(0, 120))}</div>`
    : '';
  if (!rows?.length) {
    el.innerHTML = `Session <span>${esc(sessionName(sid))}</span>${promptHtml}`;
    return;
  }
  const dur = rows.at(-1).ended_at ? rows.at(-1).ended_at - rows[0].started_at : null;
  const ok  = rows.filter(r => r.success === 1).length;
  const err = rows.filter(r => r.success === 0).length;
  const run = rows.filter(r => r.ended_at == null).length;
  el.innerHTML = `Session <span>${esc(sessionName(sid))}</span>
    <span class="chip"><b>${rows.length}</b> calls</span>
    ${ok  ? `<span class="chip" style="color:var(--green)"><b>${ok}</b> ok</span>` : ''}
    ${err ? `<span class="chip" style="color:var(--red)"><b>${err}</b> failed</span>` : ''}
    ${run ? `<span class="chip" style="color:var(--yellow)"><b>${run}</b> running</span>` : ''}
    ${dur != null ? `<span class="chip">span <b>${fmt(dur)}</b></span>` : ''}
    ${promptHtml}`;
}

// ── Stats panels ──────────────────────────────────────────────────────────────
function parseInput(s) {
  try { return JSON.parse(s) || {}; } catch { return {}; }
}

function shortPath(p) {
  const parts = p.replace(/\\/g, '/').split('/').filter(Boolean);
  return parts.length <= 2 ? p : '…/' + parts.slice(-2).join('/');
}

function renderStats(rows) {
  const el = document.getElementById('stats');
  if (!rows || !rows.length) { el.style.display = 'none'; return; }

  // ── File access: Read / Write / Edit ────────────────────────────────────
  const fileMap = new Map();
  const bumpFile = (path, key) => {
    if (!fileMap.has(path)) fileMap.set(path, { reads: 0, writes: 0, edits: 0 });
    fileMap.get(path)[key]++;
  };
  for (const r of rows) {
    const inp = parseInput(r.tool_input);
    if      (r.tool_name === 'Read'  && inp.file_path) bumpFile(inp.file_path, 'reads');
    else if (r.tool_name === 'Write' && inp.file_path) bumpFile(inp.file_path, 'writes');
    else if (r.tool_name === 'Edit'  && inp.file_path) bumpFile(inp.file_path, 'edits');
  }
  const files = [...fileMap.entries()]
    .map(([p, v]) => ({ path: p, ...v, total: v.reads + v.writes + v.edits }))
    .sort((a, b) => b.total - a.total)
    .slice(0, 15);

  // ── Bash commands ────────────────────────────────────────────────────────
  const cmdMap = new Map();
  for (const r of rows) {
    if (r.tool_name !== 'Bash' || !r.ended_at) continue;
    const inp = parseInput(r.tool_input);
    const key = (inp.command || '').trim().split('\n')[0].trim().slice(0, 80);
    if (!key) continue;
    const dur = r.ended_at - r.started_at;
    if (!cmdMap.has(key)) cmdMap.set(key, { cmd: key, count: 0, totalDur: 0, maxDur: 0, errors: 0 });
    const e = cmdMap.get(key);
    e.count++;
    e.totalDur += dur;
    e.maxDur = Math.max(e.maxDur, dur);
    if (!r.success) e.errors++;
  }
  const cmdsByCount = [...cmdMap.values()].sort((a, b) => b.count  - a.count ).slice(0, 15);
  const cmdsByDur   = [...cmdMap.values()].sort((a, b) => b.maxDur - a.maxDur).slice(0, 15);

  // ── Render ───────────────────────────────────────────────────────────────
  const dash = `<span class="muted">—</span>`;

  const filesHtml = files.length ? `
    <div class="sp">
      <div class="sp-head">File access — Read · Write · Edit</div>
      <table class="sp-table">
        <tr><th>path</th><th>R</th><th>W</th><th>E</th><th>total</th></tr>
        ${files.map(f => `<tr>
          <td title="${esc(f.path)}"><span>${esc(shortPath(f.path))}</span></td>
          <td>${f.reads  ? `<span class="cnt-r">${f.reads}</span>`  : dash}</td>
          <td>${f.writes ? `<span class="cnt-w">${f.writes}</span>` : dash}</td>
          <td>${f.edits  ? `<span class="cnt-e">${f.edits}</span>`  : dash}</td>
          <td><span class="cnt">${f.total}</span></td>
        </tr>`).join('')}
      </table>
    </div>` : '';

  const cmdRowHtml = (c) => `<tr>
    <td title="${esc(c.cmd)}"><span>${esc(c.cmd.length > 52 ? c.cmd.slice(0, 52) + '…' : c.cmd)}</span></td>
    <td><span class="cnt">${c.count}</span>${c.errors ? ` <span class="cnt-e" style="font-size:10px">${c.errors}✕</span>` : ''}</td>
    <td><span class="dur-avg">${fmt(c.totalDur / c.count)}</span></td>
    <td><span class="muted">${fmt(c.maxDur)}</span></td>
  </tr>`;

  const bashHtml = cmdsByCount.length ? `
    <div class="sp">
      <div class="sp-head">Bash — most called</div>
      <table class="sp-table">
        <tr><th>command</th><th>calls</th><th>avg</th><th>max</th></tr>
        ${cmdsByCount.map(cmdRowHtml).join('')}
      </table>
    </div>
    <div class="sp">
      <div class="sp-head">Bash — slowest (by max duration)</div>
      <table class="sp-table">
        <tr><th>command</th><th>calls</th><th>avg</th><th>max</th></tr>
        ${cmdsByDur.map(cmdRowHtml).join('')}
      </table>
    </div>` : '';

  const hasContent = filesHtml || bashHtml;
  el.style.display = hasContent ? 'block' : 'none';
  el.innerHTML = hasContent ? `<div class="stats-grid">${filesHtml}${bashHtml}</div>` : '';
}

// ── Data fetching ─────────────────────────────────────────────────────────────
async function selectSession(id) {
  currentSession = id;
  try {
    const [sRes, rRes] = await Promise.all([
      fetch('/api/sessions'),
      fetch('/api/session?id=' + encodeURIComponent(id)),
    ]);
    const [sessions, rows] = await Promise.all([sRes.json(), rRes.json()]);
    currentRows = rows;
    renderSessions(sessions);
    renderTimeline(rows);
    renderBashTimeline(rows);
    renderStats(rows);
    const prompt = sessions.find(s => s.session_id === id)?.initial_prompt;
    updateHeader(rows, id, prompt);
  } catch (err) {
    console.error('selectSession failed:', err);
  }
}

async function refresh() {
  try {
    const sRes = await fetch('/api/sessions');
    const sessions = await sRes.json();
    renderSessions(sessions);
    if (currentSession) {
      const rRes = await fetch('/api/session?id=' + encodeURIComponent(currentSession));
      const rows = await rRes.json();
      currentRows = rows;
      renderTimeline(rows);
      renderBashTimeline(rows);
      renderStats(rows);
      const prompt = sessions.find(s => s.session_id === currentSession)?.initial_prompt;
      updateHeader(rows, currentSession, prompt);
    }
  } catch (err) {
    console.error('refresh failed:', err);
  }
}

refresh();
setInterval(refresh, 3000);

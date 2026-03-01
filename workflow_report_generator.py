#!/usr/bin/env python3
"""
workflow_report_generator.py
=============================
Generates a dark-themed HTML report from the per-device workflow_tracker.

Tracker structure:
{
  "juniper_mx204": {
    "device_info": {"host","vendor","model","hostname","version","timestamp"},
    "pre-checks":  {"tasks": {task_name: {status,error,title,logs}}, "commands": [{cmd,output,json}]},
    "upgrade":     {"tasks": {...}},
    "post-checks": {"tasks": {...}, "commands": [...]}
  }
}

Changes:
  - logs is now a plain string (not a list)
  - "View Logs" button shown ONLY on failed tasks
  - Device details card moves below dropdown, updates dynamically per device selected
  - generate_html_report() writes a timestamped file per call
  - generate_artificial_workflow_data() uses string logs
"""

from datetime import datetime
import json
import os


PHASE_META = {
    'pre-checks':  {'label': 'Pre-Checks',  'color': '#2563eb'},
    'upgrade':     {'label': 'Upgrade',     'color': '#7c3aed'},
    'post-checks': {'label': 'Post-Checks', 'color': '#059669'},
}
PHASES = ['pre-checks', 'upgrade', 'post-checks']


def _esc(s):
    return (str(s)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


# ─────────────────────────────────────────────────────────────
# Build task table tbody for ONE device
# ─────────────────────────────────────────────────────────────
def build_tbody(device_data: dict, device_key: str) -> tuple:
    """Returns (tbody_html, total, success, failed)"""
    rows   = []
    total  = success = failed = 0
    row_id = 0
    prefix = device_key.replace('-', '_')

    for phase_key in PHASES:
        phase_block = device_data.get(phase_key, {})
        tasks = phase_block.get('tasks', phase_block)
        if not tasks:
            continue

        meta       = PHASE_META[phase_key]
        task_count = len(tasks)

        for idx, (task_name, td) in enumerate(tasks.items()):
            status   = td.get('status', '')
            is_ok    = status == 'Success'
            is_blank = not status

            total += 1
            if is_ok:
                success += 1
            else:
                failed += 1

            display_name = td.get('title', task_name)
            remark       = td.get('message', '') or td.get('error', '')
            # logs is now a plain string
            logs         = td.get('logs', '') or ''
            lid          = f'log-{prefix}-{row_id}'

            if idx == 0:
                phase_cell = (
                    f'<td class="phase-cell" rowspan="{task_count}" '
                    f'style="border-left:4px solid {meta["color"]};">'
                    f'<span class="phase-name" style="color:{meta["color"]};">'
                    f'{meta["label"]}</span></td>'
                )
            else:
                phase_cell = ''

            if remark:
                rc = 'remark-ok' if is_ok else 'remark-err'
                remark_html = f'<span class="{rc}">{_esc(remark)}</span>'
            else:
                remark_html = '<span class="remark-na">—</span>'

            # Only show "View Logs" button on FAILED tasks that have a log string
            if not is_ok and not is_blank and logs:
                log_block = (
                    f'<button class="log-btn" оnclick="toggleLog(\'{lid}\')" '
                    f'aria-expanded="false">View Logs</button>'
                    f'<div id="{lid}" class="log-drawer" hidden>'
                    f'<div class="log-line">{_esc(logs)}</div>'
                    f'</div>'
                )
            else:
                log_block = ''

            if is_blank:
                badge_html = '<span class="badge badge-blank">—</span>'
            else:
                status_cls = 'success' if is_ok else 'failed'
                badge_html = f'<span class="badge badge-{status_cls}">{_esc(status)}</span>'

            row_cls = ' failed-row' if (not is_ok and not is_blank) else ''
            rows.append(
                f'<tr class="task-row{row_cls}">'
                f'{phase_cell}'
                f'<td class="subtask-cell">{_esc(display_name)}{log_block}</td>'
                f'<td class="status-cell">{badge_html}</td>'
                f'<td class="remark-cell">{remark_html}</td>'
                f'</tr>'
            )
            row_id += 1

        rows.append('<tr class="phase-sep"><td colspan="4"></td></tr>')

    return '\n'.join(rows), total, success, failed


# ─────────────────────────────────────────────────────────────
# Build command output section for ONE device
# ─────────────────────────────────────────────────────────────
def build_commands_section(device_data: dict, device_key: str) -> str:
    prefix   = device_key.replace('-', '_')
    sections = []

    for phase_key in ('pre-checks', 'post-checks'):
        cmds = device_data.get(phase_key, {}).get('commands', [])
        if not cmds:
            continue

        meta  = PHASE_META[phase_key]
        items = []
        for i, entry in enumerate(cmds):
            cmd_label = _esc(entry.get('cmd', ''))
            raw_out   = _esc(entry.get('output', '') or '(empty)')
            json_out  = entry.get('json', {})
            json_str  = _esc(json.dumps(json_out, indent=2)) if json_out else '(not parsed)'
            raw_id  = f'raw-{prefix}-{phase_key.replace("-","")}-{i}'
            json_id = f'jsn-{prefix}-{phase_key.replace("-","")}-{i}'

            items.append(f"""
<div class="cmd-block">
  <div class="cmd-label">{cmd_label}</div>
  <div class="cmd-toggles">
    <button class="log-btn" оnclick="toggleLog('{raw_id}')">Raw Output</button>
    <button class="log-btn" оnclick="toggleLog('{json_id}')">Parsed JSON</button>
  </div>
  <div id="{raw_id}" class="log-drawer" hidden><div class="log-line">{raw_out}</div></div>
  <div id="{json_id}" class="log-drawer" hidden><pre class="jb-inline">{json_str}</pre></div>
</div>""")

        sections.append(f"""
<div class="cmd-phase-block">
  <div class="cmd-phase-title" style="color:{meta['color']};">{meta['label']} — Command Outputs</div>
  {''.join(items)}
</div>""")

    return '\n'.join(sections) if sections else ''


# ─────────────────────────────────────────────────────────────
# Build per-device stats block (injected into HTML as JSON for JS)
# ─────────────────────────────────────────────────────────────
def build_device_info_json(workflow_data: dict) -> str:
    """Returns a JS-safe JSON string of device_info per device_key."""
    info_map = {}
    for dk, device_data in workflow_data.items():
        info = device_data.get('device_info', {})
        info_map[dk] = {
            'host':     info.get('host',     '—') or '—',
            'vendor':   (info.get('vendor',  '—') or '—').upper(),
            'model':    (info.get('model',   '—') or '—').upper(),
            'hostname': info.get('hostname', '—') or '—',
            'version':  info.get('version',  '—') or '—',
            'timestamp':info.get('timestamp','—') or '—',
        }
    return json.dumps(info_map)


# ─────────────────────────────────────────────────────────────
# Build one full device panel (no device card — moved to JS)
# ─────────────────────────────────────────────────────────────
def build_device_panel(device_key: str, device_data: dict, is_first: bool) -> str:
    tbody, total, success, failed = build_tbody(device_data, device_key)
    cmd_section = build_commands_section(device_data, device_key)

    pct      = round(success / total * 100) if total else 0
    pill_cls = 'ok' if (failed == 0 and total > 0) else ('fail' if (success == 0 and total > 0) else 'partial')
    pill_txt = 'ALL PASSED' if (failed == 0 and total > 0) else (f'{failed} FAILED' if total > 0 else 'NO TASKS')

    display = 'block' if is_first else 'none'

    return f"""
<div class="device-panel" id="panel-{_esc(device_key)}" style="display:{display};">

  <div class="dev-header">
    <div>
      <span class="dev-key">{_esc(device_key)}</span>
      <span class="pill {pill_cls}" style="margin-left:1rem;">{pill_txt}</span>
    </div>
    <div class="meta-ts" id="ts-{_esc(device_key)}"></div>
  </div>

  <div class="stats">
      <div class="sc tot"><span class="n">{total}</span><span class="l">Total Tasks</span>
        <div class="prog"><div class="progbar" style="width:{pct}%"></div></div></div>
      <div class="sc ok"><span class="n`">{success}/{total}</span><span class="l">Passed</span></div>
      <div class="sc err"><span class="n">{failed}</span><span class="l">Failed</span></div>
    </div>

  <div class="tw">
    <table>
      <colgroup><col class="ct"><col class="cs"><col class="cst"><col class="cr"></colgroup>
      <thead><tr><th>Phase</th><th>Subtask</th><th>Status</th><th>Remark</th></tr></thead>
      <tbody>
{tbody}
      </tbody>
    </table>
  </div>

  {cmd_section}

</div>"""


def _overall_stats(workflow_data: dict) -> tuple:
    total = success = failed = 0
    for device_data in workflow_data.values():
        for phase_key in PHASES:
            phase_block = device_data.get(phase_key, {})
            tasks = phase_block.get('tasks', phase_block)
            for td in tasks.values():
                st = td.get('status', '')
                if st:
                    total += 1
                    if st == 'Success':
                        success += 1
                    else:
                        failed += 1
    return total, success, failed


# ─────────────────────────────────────────────────────────────
# Main generator — writes a NEW timestamped file every call
# ─────────────────────────────────────────────────────────────
def generate_html_report(workflow_data: dict, output_dir: str = '.') -> str:
    """
    Writes a timestamped HTML report each time it is called.
    Returns the full path of the written file.
    """
    device_keys = list(workflow_data.keys())
    now         = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ts_file     = datetime.now().strftime('%d_%m_%y_%H_%M_%S')

    total_all, success_all, failed_all = _overall_stats(workflow_data)
    pill_cls = 'ok' if failed_all == 0 else ('fail' if success_all == 0 else 'partial')
    pill_txt = (f'ALL {total_all} TASKS PASSED' if failed_all == 0 else f'{failed_all} TASK(S) FAILED')

    dropdown_options = '\n'.join(
      f'<option value="{_esc(dk)}"{" selected" if i == 0 else ""}>'
      f'{_esc(dk)} — {_esc(workflow_data[dk].get("device_info", {}).get("host", "—"))}'
      f'</option>'
      for i, dk in enumerate(device_keys)
  )
    device_panels = '\n'.join(
        build_device_panel(dk, workflow_data[dk], i == 0)
        for i, dk in enumerate(device_keys)
    )

    device_info_json = build_device_info_json(workflow_data)
    json_html        = _esc(json.dumps(workflow_data, indent=2))

    # first device key for initial JS render
    first_key = _esc(device_keys[0]) if device_keys else ''

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Workflow Report — {len(device_keys)} Device(s)</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:#0d0f14;--surf:#13161e;--surf2:#1a1e28;
  --border:#252a38;--border2:#2e3547;
  --text:#e2e8f0;--muted:#64748b;--muted2:#94a3b8;
  --accent:#38bdf8;--ok:#22c55e;--err:#f43f5e;--warn:#f59e0b;
  --mono:"Fira Code",monospace;--sans:"Inter",sans-serif;
  --r:8px;--shadow:0 4px 24px rgba(0,0,0,.5);
}}
html{{font-size:15px}}
body{{font-family:var(--sans);background:var(--bg);color:var(--text);min-height:100vh;padding:2.5rem 1.5rem 5rem}}
.wrap{{max-width:1160px;margin:0 auto}}
.hdr{{display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;margin-bottom:1.5rem;padding-bottom:1.5rem;border-bottom:1px solid var(--border)}}
.hdr h1{{font-size:1.6rem;font-weight:700;letter-spacing:-.01em;color:var(--text);line-height:1.25}}
.hdr h1 span{{color:var(--accent)}}
.hdr .meta{{font-family:var(--mono);font-size:.7rem;color:var(--muted);margin-top:.4rem;line-height:1.9}}
.pill{{display:inline-block;padding:.28rem .85rem;border-radius:4px;font-family:var(--mono);font-size:.7rem;font-weight:600;letter-spacing:.06em;white-space:nowrap;margin-top:.35rem;text-transform:uppercase}}
.pill.ok{{background:rgba(34,197,94,.1);color:var(--ok);border:1px solid rgba(34,197,94,.25)}}
.pill.fail{{background:rgba(244,63,94,.1);color:var(--err);border:1px solid rgba(244,63,94,.25)}}
.pill.partial{{background:rgba(245,158,11,.1);color:var(--warn);border:1px solid rgba(245,158,11,.25)}}
.selector-bar{{display:flex;align-items:center;gap:1rem;background:var(--surf);border:1px solid var(--border);border-radius:var(--r);padding:1rem 1.25rem;margin-bottom:1.5rem;}}
.selector-bar label{{font-size:.65rem;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);font-weight:600;white-space:nowrap;}}
.device-select{{font-family:var(--mono);font-size:.82rem;font-weight:600;background:var(--surf2);color:var(--accent);border:1px solid var(--border2);border-radius:4px;padding:.4rem .75rem;cursor:pointer;min-width:220px;outline:none;}}
.device-select:focus{{border-color:var(--accent)}}
.device-select option{{background:var(--surf2);color:var(--text)}}
.device-count{{font-family:var(--mono);font-size:.68rem;color:var(--muted)}}
/* Device info card — rendered by JS below the dropdown */
.dev-card{{background:var(--surf);border:1px solid var(--border);border-radius:var(--r);padding:1.25rem 1.5rem;display:flex;flex-wrap:wrap;gap:2.5rem;margin-bottom:1.5rem}}
.df{{display:flex;flex-direction:column;gap:.25rem}}
.df .lbl{{font-size:.62rem;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);font-weight:600}}
.df .val{{font-family:var(--mono);font-size:.88rem;color:var(--accent)}}
.dev-header{{display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem;padding-bottom:.75rem;border-bottom:1px solid var(--border);}}
.dev-key{{font-family:var(--mono);font-size:1.1rem;font-weight:700;color:var(--text)}}
.meta-ts{{font-family:var(--mono);font-size:.68rem;color:var(--muted)}}
.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;margin-bottom:1.5rem}}
.sc{{background:var(--surf);border:1px solid var(--border);border-radius:var(--r);padding:1.25rem 1.5rem;display:flex;flex-direction:column;gap:.3rem}}
.sc .n{{font-size:2.1rem;font-weight:700;line-height:1;letter-spacing:-.02em;font-family:var(--mono)}}
.sc.tot .n{{color:var(--accent)}} .sc.ok .n{{color:var(--ok)}} .sc.err .n{{color:var(--err)}}
.sc .l{{font-size:.63rem;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);font-weight:600}}
.prog{{margin-top:.5rem;height:3px;background:var(--border);border-radius:99px;overflow:hidden}}
.progbar{{height:100%;border-radius:99px;background:linear-gradient(90deg,var(--ok),#86efac)}}
.tw{{background:var(--surf);border:1px solid var(--border);border-radius:var(--r);overflow:hidden;box-shadow:var(--shadow);margin-bottom:2rem}}
table{{width:100%;border-collapse:collapse}}
col.ct{{width:12%}} col.cs{{width:24%}} col.cst{{width:10%}} col.cr{{width:54%}}
thead tr{{background:var(--surf2);border-bottom:2px solid var(--border)}}
thead th{{padding:.75rem 1.25rem;font-size:.65rem;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);font-weight:600;text-align:left}}
.task-row td{{padding:.75rem 1.25rem;vertical-align:top;border-bottom:1px solid var(--border);font-size:.84rem;line-height:1.5}}
.task-row:hover td{{background:var(--surf2);transition:background .1s}}
.task-row.failed-row{{background:rgba(244,63,94,.02)}}
.phase-sep td{{padding:0!important;height:6px;background:var(--bg);border:none!important}}
.phase-cell{{vertical-align:middle!important;text-align:center;padding:.75rem .75rem!important;border-right:1px solid var(--border);background:rgba(255,255,255,.008)}}
.phase-name{{font-size:.62rem;text-transform:uppercase;letter-spacing:.09em;font-weight:700;line-height:1.3}}
.subtask-cell{{font-family:var(--mono);font-size:.77rem!important;color:#cbd5e1;word-break:break-word}}
.status-cell{{text-align:center;vertical-align:middle!important}}
.badge{{display:inline-block;padding:.2rem .6rem;border-radius:3px;font-size:.65rem;font-weight:600;letter-spacing:.05em;font-family:var(--mono);white-space:nowrap;text-transform:uppercase}}
.badge-success{{background:rgba(34,197,94,.12);color:var(--ok);border:1px solid rgba(34,197,94,.28)}}
.badge-failed{{background:rgba(244,63,94,.12);color:var(--err);border:1px solid rgba(244,63,94,.28)}}
.badge-blank{{background:transparent;color:var(--muted);border:1px solid var(--border)}}
.remark-cell{{font-family:var(--mono);font-size:.75rem!important;color:var(--muted2);word-break:break-word}}
.remark-ok{{color:#86efac}} .remark-err{{color:#fca5a5}} .remark-na{{color:var(--border)}}
.log-btn{{display:inline-block;margin-top:.4rem;margin-right:.3rem;padding:.14rem .5rem;background:rgba(244,63,94,.06);border:1px solid rgba(244,63,94,.22);border-radius:3px;font-family:var(--mono);font-size:.62rem;font-weight:600;color:var(--err);cursor:pointer;user-select:none;transition:background .12s;letter-spacing:.04em;}}
.log-btn:hover{{background:rgba(244,63,94,.14);border-color:rgba(244,63,94,.4)}}
.cmd-block .log-btn{{background:rgba(56,189,248,.06);border:1px solid rgba(56,189,248,.18);color:var(--accent);}}
.cmd-block .log-btn:hover{{background:rgba(56,189,248,.14);border-color:rgba(56,189,248,.38)}}
.log-drawer{{margin-top:.42rem;background:#08090e;border:1px solid var(--border2);border-radius:4px;padding:.5rem .8rem;overflow-x:auto;}}
.log-line{{font-family:var(--mono);font-size:.69rem;line-height:1.9;color:#fca5a5;white-space:pre-wrap;word-break:break-all;}}
.cmd-block .log-line{{color:#7dd3fc;border-bottom:1px solid rgba(255,255,255,.03);}}
.cmd-block .log-line:last-child{{border-bottom:none}}
.cmd-phase-block{{margin-bottom:2rem}}
.cmd-phase-title{{font-size:.78rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;margin-bottom:.75rem;font-family:var(--mono);}}
.cmd-block{{background:var(--surf);border:1px solid var(--border);border-radius:var(--r);padding:1rem 1.25rem;margin-bottom:.75rem;}}
.cmd-label{{font-family:var(--mono);font-size:.82rem;color:var(--text);font-weight:600;margin-bottom:.5rem}}
.cmd-toggles{{display:flex;gap:.5rem;flex-wrap:wrap}}
.jb-inline{{margin-top:.5rem;font-family:var(--mono);font-size:.7rem;line-height:1.7;color:#94a3b8;white-space:pre;overflow-x:auto;}}
.json-sec{{margin-top:1.5rem}}
.json-sec summary{{cursor:pointer;user-select:none;list-style:none;display:inline-flex;align-items:center;gap:.5rem;font-size:.72rem;font-weight:600;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);padding:.5rem 0;transition:color .12s;font-family:var(--mono);}}
.json-sec summary::-webkit-details-marker{{display:none}}
.json-sec[open] summary{{color:var(--accent)}}
.json-sec summary:hover{{color:var(--accent)}}
pre.jb{{margin-top:.7rem;background:var(--surf);border:1px solid var(--border);border-radius:var(--r);padding:1.2rem 1.4rem;font-family:var(--mono);font-size:.73rem;line-height:1.75;color:#94a3b8;overflow-x:auto;white-space:pre;box-shadow:var(--shadow);}}
.ft{{margin-top:3rem;padding-top:1rem;border-top:1px solid var(--border);font-size:.67rem;color:var(--muted);font-family:var(--mono);text-align:center}}
@media(max-width:640px){{.stats{{grid-template-columns:1fr}}.hdr{{flex-direction:column}}.selector-bar{{flex-direction:column;align-items:flex-start}}.device-select{{width:100%}}}}
</style>
</head>
<body>
<div class="wrap">

<header class="hdr">
  <div>
    <h1>Network Device <span>Workflow Report</span></h1>
    <p class="meta">Generated: {now}<br>{len(device_keys)} device(s) processed</p>
  </div>
  <div><span class="pill {pill_cls}">{_esc(pill_txt)}</span></div>
</header>

<!-- Dropdown selector -->
<div class="selector-bar">
  <label for="device-select">Device</label>
  <select id="device-select" class="device-select" оnchange="selectDevice(this.value)">
    {dropdown_options}
  </select>
  <span class="device-count">{len(device_keys)} device(s) in this report</span>
</div>

<!-- Device info card — populated by JS, sits between dropdown and panels -->
<div class="dev-card" id="dev-info-card">
  <div class="df"><span class="lbl">Host / IP</span><span class="val" id="di-host">—</span></div>
  <div class="df"><span class="lbl">Vendor</span><span class="val" id="di-vendor">—</span></div>
  <div class="df"><span class="lbl">Model</span><span class="val" id="di-model">—</span></div>
  <div class="df"><span class="lbl">Hostname</span><span class="val" id="di-hostname">—</span></div>
  <div class="df"><span class="lbl">Version</span><span class="val" id="di-version">—</span></div>
  <div class="df"><span class="lbl">Run At</span><span class="val" id="di-timestamp">—</span></div>
</div>

{device_panels}

<details class="json-sec">
  <summary>Raw Workflow JSON (all devices)</summary>
  <pre class="jb">{json_html}</pre>
</details>

<footer class="ft">workflow_report_generator.py / {now}</footer>

</div>

<script>
var DEVICE_INFO = {device_info_json};

function updateInfoCard(key) {{
  var d = DEVICE_INFO[key];
  if (!d) return;
  document.getElementById('di-host').textContent      = d.host      || '—';
  document.getElementById('di-vendor').textContent    = d.vendor    || '—';
  document.getElementById('di-model').textContent     = d.model     || '—';
  document.getElementById('di-hostname').textContent  = d.hostname  || '—';
  document.getElementById('di-version').textContent   = d.version   || '—';
  document.getElementById('di-timestamp').textContent = d.timestamp || '—';
}}

function selectDevice(key) {{
  document.querySelectorAll('.device-panel').forEach(function(p) {{
    p.style.display = 'none';
  }});
  var panel = document.getElementById('panel-' + key);
  if (panel) panel.style.display = 'block';
  updateInfoCard(key);
}}

function toggleLog(id) {{
  var el = document.getElementById(id);
  if (!el) return;
  el.hidden = !el.hidden;
  var parent = el.parentElement;
  parent.querySelectorAll('.log-btn').forEach(function(btn) {{
    var oc = btn.getAttribute('оnclick') || '';
    if (oc.indexOf(id) !== -1) {{
      btn.textContent = el.hidden
        ? btn.textContent.replace('Hide', 'View')
        : btn.textContent.replace('View', 'Hide');
    }}
  }});
}}

// Initialise card with first device on load
updateInfoCard('{first_key}');
</script>
</body>
</html>"""

    os.makedirs(output_dir, exist_ok=True)
    filename  = f"workflow_report_{ts_file}.html"
    file_path = os.path.join(output_dir, filename)
    with open(file_path, 'w') as f:
        f.write(html)
    return file_path



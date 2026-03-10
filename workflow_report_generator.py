#!/usr/bin/env python3
"""
workflow_report_generator.py
=============================
Generates a dark-themed HTML report from device_results.

device_results structure (per device_key):
{
  "status":      "",
  "device_info": {"host", "vendor", "model", "hostname", "version"},
  "pre": {
      "connect":                   {"ping", "status": True|False, "exception": ""},
      "execute_show_commands":     {"status": str, "exception": "", "commands": [{cmd,output,json,exception}]},
      "show_version":              {"status": str, "exception": "", "version": "", "platform": ""},
      "check_storage":             {"status": str, "deleted_files": [], "exception": "", "sufficient": False},
      "backup_active_filesystem":  {"status": str, "exception": "", "disk_count": ""},
      "backup_running_config":     {"status": str, "exception": "", "destination": "", "config_file": ""},
      "transfer_image":            {"status": str, "exception": "", "image": "", "destination": ""},
      "validate_md5":              {"status": str, "exception": "", "expected": "", "computed": "", "match": False},
      "disable_re_protect_filter": {"status": str, "exception": ""},
  },
  "upgrade": {
      "status":     "not_started"|"in_progress"|"completed"|"failed"|"rolled_back",
      "initial_os": str,
      "target_os":  str,
      "exception":  str,
      "hops": [
          {"image": str, "status": str, "exception": str, "md5_match": bool}
      ]
  },
  "post": {
      "connect":               {"status": str, "exception": ""},
      "execute_show_commands": {"status": str, "exception": "", "commands": [{cmd,output,json,exception}]},
      "show_version":          {"status": str, "exception": "", "version": "", "platform": ""},
  }
}
"""

from datetime import datetime
import json
import os


# ── display names ─────────────────────────────────────────────────────────────
PRE_TASK_TITLES = {
    "connect":                   "Connect to Device",
    "execute_show_commands":     "Collect Show Outputs",
    "show_version":              "Show Version",
    "check_storage":             "Check Storage",
    "backup_active_filesystem":  "Backup Active Filesystem",
    "backup_running_config":     "Backup Running Config",
    "transfer_image":            "Transfer Image",
    "validate_md5":              "Validate MD5",
    "disable_re_protect_filter": "Disable RE Protect Filter",
}

POST_TASK_TITLES = {
    "connect":               "Connect to Device",
    "execute_show_commands": "Collect Show Outputs",
    "show_version":          "Show Version",
}

PHASE_META = {
    "pre":     {"label": "Pre-Checks",  "color": "#38bdf8"},
    "upgrade": {"label": "Upgrade",     "color": "#a78bfa"},
    "post":    {"label": "Post-Checks", "color": "#34d399"},
    "report":  {"label": "Report",      "color": "#fb923c"},
}


def _esc(s):
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _norm_status(raw) -> str:
    if raw is True:
        return "ok"
    if raw is False:
        return "failed"
    if isinstance(raw, str):
        s = raw.strip().lower()
        if s in ("success", "true", "completed", "ok", "passed", "skipped"):
            return "ok"
        if s in ("failed", "false", "error", "rollback_failed"):
            return "failed"
        if s == "not_started":
            return "not_started"
        if s in ("in_progress", "rolled_back", "low_space_cleaned"):
            return s
        if s == "":
            return ""
        return raw
    return str(raw) if raw is not None else ""


# ─────────────────────────────────────────────────────────────────────────────
# Command drawer (shared by pre + post execute_show_commands)
# Always renders — shows placeholder if commands list is empty
# ─────────────────────────────────────────────────────────────────────────────
def _build_cmd_drawer(cmds: list, prefix: str, phase: str) -> str:
    drawer_id = f"cmds-{prefix}-{phase}"

    if not cmds:
        return (f'<div class="cmd-drawer" hidden id="{drawer_id}">'
                f'<div class="cmd-empty">No commands collected for this phase.</div>'
                f'</div>')

    items = []
    for i, entry in enumerate(cmds):
        cmd_label = _esc(entry.get("cmd", ""))
        raw_out   = _esc(entry.get("output", "") or "(empty)")
        json_out  = entry.get("json", {})
        json_str  = _esc(json.dumps(json_out, indent=2)) if json_out else "(not parsed)"
        exc_str   = _esc(entry.get("exception", "") or "")
        ok        = (exc_str == "")

        raw_id  = f"raw-{prefix}-{phase}-{i}"
        json_id = f"jsn-{prefix}-{phase}-{i}"
        exc_id  = f"exc-{prefix}-{phase}-{i}"

        dot_cls = "dot-ok" if ok else "dot-fail"
        row_cls = "cmd-row ok" if ok else "cmd-row fail"
        err_btn = (f'<button class="mini-btn mini-err" '
                   f'onclick="tgl(\'{exc_id}\')">Why?</button>') if not ok else ""

        items.append(f"""<div class="{row_cls}">
  <div class="cm-hd">
    <span class="dot {dot_cls}"></span>
    <code class="cm-cmd">{cmd_label}</code>
    <div class="cm-btns">
      <button class="mini-btn" onclick="tgl('{raw_id}')">Raw</button>
      <button class="mini-btn" onclick="tgl('{json_id}')">JSON</button>
      {err_btn}
    </div>
  </div>
  <div id="{raw_id}" class="log-box" hidden><pre>{raw_out}</pre></div>
  <div id="{json_id}" class="log-box" hidden><pre>{json_str}</pre></div>
  {"" if ok else f'<div id="{exc_id}" class="log-box err-box" hidden><pre>{exc_str}</pre></div>'}
</div>""")

    return (f'<div class="cmd-drawer" hidden id="{drawer_id}">'
            f'<div class="cmd-list">{"".join(items)}</div></div>')


# ─────────────────────────────────────────────────────────────────────────────
# Upgrade hops table
# ─────────────────────────────────────────────────────────────────────────────
def _build_hops_rows(hops: list, prefix: str) -> str:
    if not hops:
        return ""
    rows = []
    for i, hop in enumerate(hops):
        image   = _esc(hop.get("image", "—"))
        raw_st  = hop.get("status", "not_started")
        status  = _norm_status(raw_st)
        exc     = _esc(hop.get("exception", "") or "")
        md5     = hop.get("md5_match", None)

        if status == "ok":
            badge = '<span class="badge b-ok">OK</span>'
        elif status == "not_started":
            badge = '<span class="badge b-ns">—</span>'
        elif status in ("failed", "rollback_failed"):
            badge = '<span class="badge b-fail">Failed</span>'
        elif status == "rolled_back":
            badge = '<span class="badge b-warn">Rolled Back</span>'
        else:
            badge = f'<span class="badge b-ns">{_esc(status)}</span>'

        if md5 is True:
            md5_html = '<span class="badge b-ok">✓</span>'
        elif md5 is False:
            md5_html = '<span class="badge b-fail">✗</span>'
        else:
            md5_html = '<span class="badge b-ns">—</span>'

        exc_html = f'<span class="remark-err">{exc}</span>' if exc else '<span class="remark-na">—</span>'

        rows.append(
            f'<tr class="task-row">'
            f'<td class="subtask-cell mono">{i+1}</td>'
            f'<td class="subtask-cell mono">{image}</td>'
            f'<td class="status-cell">{badge}</td>'
            f'<td class="status-cell">{md5_html}</td>'
            f'<td class="remark-cell">{exc_html}</td>'
            f'</tr>'
        )
    return "\n".join(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Diff utilities
# ─────────────────────────────────────────────────────────────────────────────
def _intra_diff_html(removed: str, added: str) -> tuple:
    """Return (pre_html, post_html) with char-level highlights."""
    rem_esc = _esc(removed)
    add_esc = _esc(added)
    pre_html  = f'<span class="diff-del-inline">{rem_esc}</span>' if removed else ""
    post_html = f'<span class="diff-add-inline">{add_esc}</span>' if added  else ""
    return pre_html, post_html


def _build_report_section(report: dict, prefix: str) -> str:
    """
    Build the side-by-side diff section for the report phase.
    Returns HTML string (empty string if no diffs or report not generated).
    """
    status = report.get("status", "pending")
    exc    = report.get("exception", "") or ""
    diff   = report.get("diff", {})

    color   = PHASE_META["report"]["color"]
    sec_id  = f"report-diff-{prefix}"

    # ── status badge ──────────────────────────────────────────────────────────
    norm = _norm_status(status)
    if norm == "ok":
        badge = '<span class="badge b-ok">Generated</span>'
    elif status == "pending":
        badge = '<span class="badge b-ns">Pending</span>'
    elif norm == "failed":
        badge = '<span class="badge b-fail">Failed</span>'
    else:
        badge = f'<span class="badge b-ns">{_esc(status)}</span>'

    exc_html = (f'<span class="remark-err">{_esc(exc)}</span>'
                if exc else '<span class="remark-na">—</span>')

    # ── no diffs ──────────────────────────────────────────────────────────────
    if not diff:
        no_diff = ('<div class="diff-none">No differences found between pre and post outputs.</div>'
                   if status in ("generated", "ok")
                   else '<div class="diff-none">Diff not yet available.</div>')
        return f'''<tr class="task-row">
<td class="phase-cell" rowspan="2" style="border-left:3px solid {color};">
  <span class="phase-lbl" style="color:{color};">Report</span></td>
<td class="subtask-cell"><span class="mono">Diff Status</span></td>
<td class="status-cell">{badge}</td>
<td class="remark-cell">{exc_html}</td>
</tr>
<tr class="task-row">
<td class="subtask-cell" colspan="3">{no_diff}</td>
</tr>
<tr class="phase-sep"><td colspan="4"></td></tr>'''

    # ── build per-command diff tables ─────────────────────────────────────────
    cmd_blocks = []
    for cmd_str, entries in diff.items():
        if not entries:
            continue

        tbl_id    = f"diff-{prefix}-{abs(hash(cmd_str)) % 999999}"
        cmd_label = _esc(cmd_str)

        changed = sum(1 for e in entries
                      if e.get("pre","N/A") != "N/A" and e.get("post","N/A") != "N/A"
                      and e.get("change","") != "")
        added   = sum(1 for e in entries if e.get("pre","N/A")  == "N/A")
        removed = sum(1 for e in entries if e.get("post","N/A") == "N/A")

        summary_parts = []
        if added:   summary_parts.append(f'<span class="diff-cnt add">+{added}</span>')
        if removed: summary_parts.append(f'<span class="diff-cnt del">−{removed}</span>')
        if changed: summary_parts.append(f'<span class="diff-cnt chg">~{changed}</span>')
        summary_html = " ".join(summary_parts) or ""

        rows = []
        for entry in entries:
            pre_val    = entry.get("pre",    "N/A")
            post_val   = entry.get("post",   "N/A")
            change     = entry.get("change", "")

            if pre_val == "N/A":
                # pure addition
                pre_html  = '<span class="diff-na">N/A</span>'
                post_html = f'<span class="diff-add">{_esc(post_val)}</span>'
                row_cls   = "dr-add"
            elif post_val == "N/A":
                # pure deletion
                pre_html  = f'<span class="diff-del">{_esc(pre_val)}</span>'
                post_html = '<span class="diff-na">N/A</span>'
                row_cls   = "dr-del"
            elif isinstance(change, list) and len(change) == 2:
                # intra-line diff: highlight changed chars within context
                removed_chars, added_chars = change
                # show full line with highlights embedded
                pre_base  = _esc(pre_val.replace(removed_chars, ""))
                post_base = _esc(post_val.replace(added_chars,  ""))
                pre_html  = f'{pre_base}<span class="diff-del-inline">{_esc(removed_chars)}</span>'
                post_html = f'{post_base}<span class="diff-add-inline">{_esc(added_chars)}</span>'
                row_cls   = "dr-chg"
            else:
                # whole-line change (change == "")
                pre_html  = f'<span class="diff-del">{_esc(pre_val)}</span>'
                post_html = f'<span class="diff-add">{_esc(post_val)}</span>'
                row_cls   = "dr-chg"

            rows.append(
                f'<tr class="{row_cls}">'
                f'<td class="diff-pre mono">{pre_html}</td>'
                f'<td class="diff-sep"></td>'
                f'<td class="diff-post mono">{post_html}</td>'
                f'</tr>'
            )

        cmd_blocks.append(f'''
<div class="diff-cmd-block">
  <div class="diff-cmd-hd">
    <button class="mini-btn" onclick="tgl(\'{tbl_id}\')">
      <code>{cmd_label}</code>
    </button>
    <span class="diff-summary">{summary_html}</span>
  </div>
  <div id="{tbl_id}" class="diff-tbl-wrap" hidden>
    <table class="diff-tbl">
      <thead><tr>
        <th class="diff-th-pre">PRE</th>
        <th class="diff-th-sep"></th>
        <th class="diff-th-post">POST</th>
      </tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>
  </div>
</div>''')

    cmd_count   = len(diff)
    diff_toggle = f' <button class="mini-btn" onclick="tgl(\'{sec_id}\')">View Diffs ({cmd_count})</button>'
    diff_drawer = (f'<div class="diff-drawer" hidden id="{sec_id}">'
                   + "".join(cmd_blocks)
                   + '</div>')

    return f'''<tr class="task-row">
<td class="phase-cell" rowspan="2" style="border-left:3px solid {color};">
  <span class="phase-lbl" style="color:{color};">Report</span></td>
<td class="subtask-cell"><span class="mono">Diff Status</span></td>
<td class="status-cell">{badge}</td>
<td class="remark-cell">{exc_html}</td>
</tr>
<tr class="task-row">
<td class="subtask-cell" colspan="3">
  <span class="mono" style="color:var(--muted2);">{cmd_count} command(s) with differences</span>
  {diff_toggle}
  {diff_drawer}
</td>
</tr>
<tr class="phase-sep"><td colspan="4"></td></tr>'''


# ─────────────────────────────────────────────────────────────────────────────
# Build rows for pre or post phase
# ─────────────────────────────────────────────────────────────────────────────
def _build_phase_rows(tasks: dict, titles: dict, phase_key: str,
                      prefix: str, phase_meta: dict) -> tuple:
    """Returns (rows_html, total, success, failed)"""
    rows    = []
    total   = success = failed = 0
    color   = phase_meta["color"]
    label   = phase_meta["label"]
    count   = len(tasks)
    first   = True

    for task_name, td in tasks.items():
        if not isinstance(td, dict):
            continue

        raw_st  = td.get("status", "")
        status  = _norm_status(raw_st)
        is_ok   = status == "ok"
        is_blank= status in ("", "not_started")
        exc     = td.get("exception", "") or ""
        display = titles.get(task_name, task_name.replace("_", " ").title())

        total += 1
        if is_ok:       success += 1
        elif not is_blank: failed += 1

        # phase cell (rowspan on first row only)
        if first:
            phase_cell = (
                f'<td class="phase-cell" rowspan="{count}" '
                f'style="border-left:3px solid {color};">'
                f'<span class="phase-lbl" style="color:{color};">{label}</span>'
                f'</td>'
            )
            first = False
        else:
            phase_cell = ""

        # badge
        if is_blank:
            badge = '<span class="badge b-ns">—</span>'
        elif is_ok:
            badge = '<span class="badge b-ok">OK</span>'
        else:
            badge = '<span class="badge b-fail">Failed</span>'

        # remark
        if exc:
            remark = f'<span class="remark-err">{_esc(exc)}</span>'
        else:
            remark = '<span class="remark-na">—</span>'

        # for execute_show_commands — always render toggle + drawer (even if empty)
        cmd_toggle = ""
        cmd_drawer = ""
        if task_name == "execute_show_commands":
            cmds   = td.get("commands", [])
            btn_id = f"cmds-{prefix}-{phase_key}"
            count  = len(cmds)
            lbl    = f"Outputs ({count})"
            cmd_toggle = (f' <button class="mini-btn" '
                          f'onclick="tgl(\'{btn_id}\')">{ lbl}</button>')
            cmd_drawer = _build_cmd_drawer(cmds, prefix, phase_key)

        subtask_html = (
            f'<span class="mono">{_esc(display)}</span>'
            f'{cmd_toggle}'
            f'{cmd_drawer}'
        )

        row_cls = " failed-row" if (not is_ok and not is_blank) else ""
        rows.append(
            f'<tr class="task-row{row_cls}">'
            f'{phase_cell}'
            f'<td class="subtask-cell">{subtask_html}</td>'
            f'<td class="status-cell">{badge}</td>'
            f'<td class="remark-cell">{remark}</td>'
            f'</tr>'
        )

    rows.append('<tr class="phase-sep"><td colspan="4"></td></tr>')
    return "\n".join(rows), total, success, failed


# ─────────────────────────────────────────────────────────────────────────────
# Build full table body for one device
# ─────────────────────────────────────────────────────────────────────────────
def build_tbody(device_data: dict, device_key: str) -> tuple:
    """Returns (tbody_html, total, success, failed)"""
    prefix   = device_key.replace(".", "_").replace("-", "_")
    all_rows = []
    total = success = failed = 0

    # ── PRE ──────────────────────────────────────────────────────────────────
    pre_tasks = {k: v for k, v in device_data.get("pre", {}).items()}
    if pre_tasks:
        rows, t, s, f = _build_phase_rows(
            pre_tasks, PRE_TASK_TITLES, "pre", prefix, PHASE_META["pre"]
        )
        all_rows.append(rows)
        total += t; success += s; failed += f

    # ── UPGRADE ───────────────────────────────────────────────────────────────
    upg = device_data.get("upgrade", {})
    if upg:
        color      = PHASE_META["upgrade"]["color"]
        upg_status = _norm_status(upg.get("status", ""))
        initial_os = _esc(upg.get("initial_os", "—") or "—")
        target_os  = _esc(upg.get("target_os",  "—") or "—")
        upg_exc    = _esc(upg.get("exception",  "") or "")
        hops       = upg.get("hops", [])
        hop_count  = len(hops)

        if upg_status == "ok":
            upg_badge = '<span class="badge b-ok">Completed</span>'
        elif upg_status == "not_started":
            upg_badge = '<span class="badge b-ns">Not Started</span>'
        elif upg_status in ("failed", "rollback_failed"):
            upg_badge = '<span class="badge b-fail">Failed</span>'
        elif upg_status == "rolled_back":
            upg_badge = '<span class="badge b-warn">Rolled Back</span>'
        elif upg_status == "in_progress":
            upg_badge = '<span class="badge b-ip">In Progress</span>'
        else:
            upg_badge = f'<span class="badge b-ns">{_esc(upg_status)}</span>'

        upg_remark = f'<span class="remark-err">{upg_exc}</span>' if upg_exc else '<span class="remark-na">—</span>'

        # hops drawer
        hop_drawer = ""
        hop_toggle = ""
        if hops:
            hops_id    = f"hops-{prefix}"
            hop_toggle = f' <button class="mini-btn" onclick="tgl(\'{hops_id}\')">Hops ({hop_count})</button>'
            hop_rows   = _build_hops_rows(hops, prefix)
            hop_drawer = f"""<div class="cmd-drawer" hidden id="{hops_id}">
  <table class="hop-table">
    <thead><tr><th>#</th><th>Image</th><th>Status</th><th>MD5</th><th>Remark</th></tr></thead>
    <tbody>{hop_rows}</tbody>
  </table>
</div>"""

        # summary row
        all_rows.append(
            f'<tr class="task-row">'
            f'<td class="phase-cell" rowspan="3" style="border-left:3px solid {color};">'
            f'<span class="phase-lbl" style="color:{color};">Upgrade</span></td>'
            f'<td class="subtask-cell"><span class="mono">Overall Status</span></td>'
            f'<td class="status-cell">{upg_badge}</td>'
            f'<td class="remark-cell">{upg_remark}</td>'
            f'</tr>'
        )
        all_rows.append(
            f'<tr class="task-row">'
            f'<td class="subtask-cell"><span class="mono">OS Path</span></td>'
            f'<td class="status-cell"></td>'
            f'<td class="remark-cell mono" style="color:var(--muted2);">'
            f'{initial_os} → {target_os}</td>'
            f'</tr>'
        )
        all_rows.append(
            f'<tr class="task-row">'
            f'<td class="subtask-cell"><span class="mono">Hop Details</span>'
            f'{hop_toggle}{hop_drawer}</td>'
            f'<td class="status-cell"></td>'
            f'<td class="remark-cell"></td>'
            f'</tr>'
        )
        all_rows.append('<tr class="phase-sep"><td colspan="4"></td></tr>')

        # count upgrade as 1 task
        total += 1
        if upg_status == "ok":       success += 1
        elif upg_status not in ("", "not_started"): failed += 1

    # ── POST ──────────────────────────────────────────────────────────────────
    post_tasks = {k: v for k, v in device_data.get("post", {}).items()}
    if post_tasks:
        rows, t, s, f = _build_phase_rows(
            post_tasks, POST_TASK_TITLES, "post", prefix, PHASE_META["post"]
        )
        all_rows.append(rows)
        total += t; success += s; failed += f

    # ── REPORT (diff) ─────────────────────────────────────────────────────────
    report = device_data.get("report", {})
    if report:
        report_rows = _build_report_section(report, prefix)
        all_rows.append(report_rows)
        total += 1
        rpt_st = _norm_status(report.get("status", ""))
        if rpt_st == "ok":                  success += 1
        elif rpt_st not in ("", "pending"): failed  += 1

    return "\n".join(all_rows), total, success, failed


# ─────────────────────────────────────────────────────────────────────────────
# Phase summary cards
# ─────────────────────────────────────────────────────────────────────────────
def _phase_summary(device_data: dict) -> dict:
    """Returns dict of phase -> (total, ok, failed) for summary cards."""
    out = {}
    for ph in ("pre", "post"):
        tasks = device_data.get(ph, {})
        t = s = f = 0
        for td in tasks.values():
            if not isinstance(td, dict): continue
            st = _norm_status(td.get("status", ""))
            if st in ("", "not_started"): continue
            t += 1
            if st == "ok": s += 1
            else: f += 1
        out[ph] = (t, s, f)

    upg = device_data.get("upgrade", {})
    st  = _norm_status(upg.get("status", ""))
    hop_count = len(upg.get("hops", []))
    hop_ok    = sum(1 for h in upg.get("hops", []) if _norm_status(h.get("status","")) == "ok")
    out["upgrade"] = (hop_count, hop_ok, hop_count - hop_ok)

    rpt     = device_data.get("report", {})
    rpt_st  = _norm_status(rpt.get("status", ""))
    diff_n  = len(rpt.get("diff", {}))
    rpt_ok  = 1 if rpt_st == "ok"     else 0
    rpt_f   = 1 if rpt_st == "failed" else 0
    out["report"] = (1 if rpt else 0, rpt_ok, rpt_f)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Device panel
# ─────────────────────────────────────────────────────────────────────────────
def build_device_panel(device_key: str, device_data: dict, is_first: bool) -> str:
    tbody, total, success, failed = build_tbody(device_data, device_key)
    summary = _phase_summary(device_data)

    pct      = round(success / total * 100) if total else 0
    pill_cls = "ok" if failed == 0 and total > 0 else ("fail" if success == 0 and total > 0 else "partial")
    pill_txt = "ALL PASSED" if failed == 0 and total > 0 else (f"{failed} FAILED" if total > 0 else "NO TASKS")

    display  = "block" if is_first else "none"
    tbl_id   = f"tbl-{device_key.replace('.','_').replace('-','_')}"

    def phase_card(key):
        t, s, f = summary.get(key, (0, 0, 0))
        meta    = PHASE_META[key]
        pct_ph  = round(s / t * 100) if t else 0
        cls     = "ok" if f == 0 and t > 0 else ("fail" if s == 0 and t > 0 else "partial")
        label   = "Hops" if key == "upgrade" else "Tasks"
        return f"""<div class="ph-card">
  <div class="ph-top">
    <span class="ph-lbl" style="color:{meta['color']};">{meta['label']}</span>
    <span class="pill {cls}" style="font-size:.58rem;">{s}/{t} {label}</span>
  </div>
  <div class="prog"><div class="progbar" style="width:{pct_ph}%;background:{meta['color']};"></div></div>
</div>"""

    return f"""<div class="device-panel" id="panel-{_esc(device_key)}" style="display:{display};">

  <div class="dev-header">
    <div class="dev-left">
      <span class="dev-key">{_esc(device_key)}</span>
      <span class="pill {pill_cls}">{pill_txt}</span>
    </div>
    <div class="meta-ts" id="ts-{_esc(device_key)}"></div>
  </div>

  <div class="dev-info-row" id="info-{_esc(device_key)}">
    <div class="df"><span class="lbl">Host</span><span class="val" id="di-host-{_esc(device_key)}">—</span></div>
    <div class="df"><span class="lbl">Vendor</span><span class="val" id="di-vendor-{_esc(device_key)}">—</span></div>
    <div class="df"><span class="lbl">Model</span><span class="val" id="di-model-{_esc(device_key)}">—</span></div>
    <div class="df"><span class="lbl">Hostname</span><span class="val" id="di-hostname-{_esc(device_key)}">—</span></div>
    <div class="df"><span class="lbl">Version</span><span class="val" id="di-version-{_esc(device_key)}">—</span></div>
  </div>

  <div class="ph-summary">
    {phase_card("pre")}
    {phase_card("upgrade")}
    {phase_card("post")}
    {phase_card("report")}
  </div>

  <div id="{tbl_id}" class="tw">
    <table>
      <colgroup><col class="ct"><col class="cs"><col class="cst"><col class="cr"></colgroup>
      <thead><tr><th>Phase</th><th>Task</th><th>Status</th><th>Remark</th></tr></thead>
      <tbody>
{tbody}
      </tbody>
    </table>
  </div>

</div>"""


# ─────────────────────────────────────────────────────────────────────────────
# Overall stats
# ─────────────────────────────────────────────────────────────────────────────
def _overall_stats(workflow_data: dict) -> tuple:
    total = success = failed = 0
    for device_data in workflow_data.values():
        for ph in ("pre", "post"):
            for td in device_data.get(ph, {}).values():
                if not isinstance(td, dict): continue
                st = _norm_status(td.get("status", ""))
                if st in ("", "not_started"): continue
                total += 1
                if st == "ok": success += 1
                else: failed += 1
        upg = device_data.get("upgrade", {})
        st  = _norm_status(upg.get("status", ""))
        if st not in ("", "not_started"):
            total += 1
            if st == "ok": success += 1
            else: failed += 1
    return total, success, failed


# ─────────────────────────────────────────────────────────────────────────────
# Device info JS map
# ─────────────────────────────────────────────────────────────────────────────
def _device_info_json(workflow_data: dict) -> str:
    info_map = {}
    for dk, dd in workflow_data.items():
        info = dd.get("device_info", {})
        info_map[dk] = {
            "host":     info.get("host",     "—") or "—",
            "vendor":   (info.get("vendor",  "—") or "—").upper(),
            "model":    (info.get("model",   "—") or "—").upper(),
            "hostname": info.get("hostname", "—") or "—",
            "version":  info.get("version",  "—") or "—",
        }
    return json.dumps(info_map)


# ─────────────────────────────────────────────────────────────────────────────
# Main entry — generate_html_report
# ─────────────────────────────────────────────────────────────────────────────
def generate_html_report(workflow_data: dict, output_dir: str = ".") -> str:
    safe_data = {
        dk: {k: v for k, v in slot.items() if k not in ("conn", "yaml")}
        for dk, slot in workflow_data.items()
    }

    device_keys  = list(safe_data.keys())
    now          = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ts_file      = datetime.now().strftime("%d_%m_%y_%H_%M_%S")
    total_all, success_all, failed_all = _overall_stats(safe_data)

    pill_cls = "ok" if failed_all == 0 else ("fail" if success_all == 0 else "partial")
    pill_txt = (f"ALL {total_all} TASKS PASSED" if failed_all == 0
                else f"{failed_all} TASK(S) FAILED")

    dropdown_opts = "\n".join(
        f'<option value="{_esc(dk)}"{" selected" if i == 0 else ""}>'
        f'{_esc(dk)} — {_esc(safe_data[dk].get("device_info", {}).get("host", "—"))}'
        f'</option>'
        for i, dk in enumerate(device_keys)
    )
    device_panels = "\n".join(
        build_device_panel(dk, safe_data[dk], i == 0)
        for i, dk in enumerate(device_keys)
    )

    di_json   = _device_info_json(safe_data)
    json_html = _esc(json.dumps(safe_data, indent=2, default=str))
    first_key = device_keys[0] if device_keys else ""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Workflow Report — {len(device_keys)} Device(s)</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:#0a0c10;--surf:#111318;--surf2:#181c24;--surf3:#1e2330;
  --border:#1f2535;--border2:#2a3044;
  --text:#dde3f0;--muted:#4a5568;--muted2:#8896aa;
  --accent:#38bdf8;--ok:#22c55e;--err:#f43f5e;--warn:#f59e0b;
  --mono:"JetBrains Mono",monospace;--sans:"DM Sans",sans-serif;
  --r:6px;
}}
body{{font-family:var(--sans);background:var(--bg);color:var(--text);min-height:100vh;padding:2rem 1rem 4rem;font-size:14px}}
.wrap{{max-width:1080px;margin:0 auto}}

/* header */
.hdr{{display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;
      margin-bottom:1.5rem;padding-bottom:1.25rem;border-bottom:1px solid var(--border)}}
.hdr h1{{font-size:1.35rem;font-weight:700;color:var(--text);letter-spacing:-.01em}}
.hdr h1 span{{color:var(--accent)}}
.hdr .sub{{font-family:var(--mono);font-size:.68rem;color:var(--muted2);margin-top:.3rem}}

/* pills */
.pill{{display:inline-block;padding:.2rem .65rem;border-radius:3px;
       font-family:var(--mono);font-size:.65rem;font-weight:600;
       letter-spacing:.05em;text-transform:uppercase;white-space:nowrap}}
.pill.ok{{background:rgba(34,197,94,.1);color:var(--ok);border:1px solid rgba(34,197,94,.2)}}
.pill.fail{{background:rgba(244,63,94,.1);color:var(--err);border:1px solid rgba(244,63,94,.2)}}
.pill.partial{{background:rgba(245,158,11,.1);color:var(--warn);border:1px solid rgba(245,158,11,.2)}}

/* selector */
.sel-bar{{display:flex;align-items:center;gap:.75rem;background:var(--surf);
          border:1px solid var(--border);border-radius:var(--r);
          padding:.75rem 1rem;margin-bottom:1.25rem}}
.sel-bar label{{font-size:.6rem;text-transform:uppercase;letter-spacing:.1em;
                color:var(--muted);font-weight:600;white-space:nowrap}}
.dev-sel{{font-family:var(--mono);font-size:.78rem;background:var(--surf2);color:var(--accent);
          border:1px solid var(--border2);border-radius:4px;padding:.35rem .65rem;
          cursor:pointer;min-width:200px;outline:none}}
.dev-sel:focus{{border-color:var(--accent)}}
.dev-sel option{{background:var(--surf2);color:var(--text)}}
.dev-cnt{{font-family:var(--mono);font-size:.62rem;color:var(--muted);margin-left:auto}}

/* device panel */
.device-panel{{animation:fadeIn .2s ease}}
@keyframes fadeIn{{from{{opacity:0;transform:translateY(4px)}}to{{opacity:1;transform:none}}}}

.dev-header{{display:flex;align-items:center;justify-content:space-between;
             margin-bottom:1rem;padding-bottom:.75rem;border-bottom:1px solid var(--border)}}
.dev-left{{display:flex;align-items:center;gap:.75rem;flex-wrap:wrap}}
.dev-key{{font-family:var(--mono);font-size:.95rem;font-weight:600;color:var(--text)}}
.meta-ts{{font-family:var(--mono);font-size:.62rem;color:var(--muted)}}

/* device info row */
.dev-info-row{{display:flex;flex-wrap:wrap;gap:1.5rem;background:var(--surf);
               border:1px solid var(--border);border-radius:var(--r);
               padding:.9rem 1.1rem;margin-bottom:1rem}}
.df{{display:flex;flex-direction:column;gap:.2rem}}
.df .lbl{{font-size:.58rem;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);font-weight:600}}
.df .val{{font-family:var(--mono);font-size:.8rem;color:var(--accent)}}

/* phase summary */
.ph-summary{{display:grid;grid-template-columns:repeat(4,1fr);gap:.75rem;margin-bottom:1rem}}
.ph-card{{background:var(--surf);border:1px solid var(--border);border-radius:var(--r);padding:.8rem 1rem}}
.ph-top{{display:flex;align-items:center;justify-content:space-between;margin-bottom:.5rem}}
.ph-lbl{{font-size:.65rem;text-transform:uppercase;letter-spacing:.08em;font-weight:700;font-family:var(--mono)}}
.prog{{height:2px;background:var(--border);border-radius:99px;overflow:hidden}}
.progbar{{height:100%;border-radius:99px;transition:width .4s ease}}

/* expand button */
.tw-toggle{{margin-bottom:.5rem}}
.expand-btn{{background:var(--surf2);border:1px solid var(--border2);border-radius:var(--r);
             color:var(--muted2);font-family:var(--mono);font-size:.72rem;
             padding:.4rem .85rem;cursor:pointer;transition:all .15s}}
.expand-btn:hover{{border-color:var(--accent);color:var(--accent)}}
.expand-btn.open{{color:var(--accent);border-color:var(--accent)}}

/* table */
.tw{{background:var(--surf);border:1px solid var(--border);border-radius:var(--r);
     overflow:hidden;margin-bottom:1.5rem}}
table{{width:100%;border-collapse:collapse}}
col.ct{{width:11%}} col.cs{{width:26%}} col.cst{{width:9%}} col.cr{{width:54%}}
thead tr{{background:var(--surf2);border-bottom:2px solid var(--border)}}
thead th{{padding:.6rem 1rem;font-size:.6rem;text-transform:uppercase;letter-spacing:.1em;
          color:var(--muted);font-weight:600;text-align:left}}
.task-row td{{padding:.65rem 1rem;vertical-align:top;border-bottom:1px solid var(--border);font-size:.8rem;line-height:1.5}}
.task-row:hover td{{background:rgba(255,255,255,.015)}}
.task-row.failed-row{{background:rgba(244,63,94,.018)}}
.phase-sep td{{padding:0!important;height:4px;background:var(--bg);border:none!important}}
.phase-cell{{vertical-align:middle!important;text-align:center;padding:.6rem .5rem!important;
             border-right:1px solid var(--border);background:rgba(255,255,255,.005)}}
.phase-lbl{{font-size:.58rem;text-transform:uppercase;letter-spacing:.08em;font-weight:700;
            font-family:var(--mono);writing-mode:vertical-lr;transform:rotate(180deg);
            display:inline-block}}
.subtask-cell{{word-break:break-word}}
.mono{{font-family:var(--mono);font-size:.75rem;color:#c8d3e8}}
.status-cell{{text-align:center;vertical-align:middle!important}}
.remark-cell{{font-family:var(--mono);font-size:.72rem!important;word-break:break-word}}
.remark-err{{color:#fca5a5}} .remark-na{{color:var(--border)}} .remark-ok{{color:#86efac}}

/* badges */
.badge{{display:inline-block;padding:.15rem .5rem;border-radius:3px;
        font-size:.6rem;font-weight:600;letter-spacing:.05em;
        font-family:var(--mono);white-space:nowrap;text-transform:uppercase}}
.b-ok{{background:rgba(34,197,94,.1);color:var(--ok);border:1px solid rgba(34,197,94,.2)}}
.b-fail{{background:rgba(244,63,94,.1);color:var(--err);border:1px solid rgba(244,63,94,.2)}}
.b-ns{{background:transparent;color:var(--muted);border:1px solid var(--border)}}
.b-warn{{background:rgba(245,158,11,.1);color:var(--warn);border:1px solid rgba(245,158,11,.2)}}
.b-ip{{background:rgba(56,189,248,.1);color:var(--accent);border:1px solid rgba(56,189,248,.2)}}

/* mini buttons */
.mini-btn{{display:inline-block;margin:.2rem .15rem 0 0;padding:.1rem .42rem;
           background:rgba(56,189,248,.06);border:1px solid rgba(56,189,248,.18);
           border-radius:3px;font-family:var(--mono);font-size:.58rem;font-weight:600;
           color:var(--accent);cursor:pointer;letter-spacing:.04em;transition:all .12s}}
.mini-btn:hover{{background:rgba(56,189,248,.14);border-color:rgba(56,189,248,.38)}}
.mini-btn.mini-err{{background:rgba(244,63,94,.06);border-color:rgba(244,63,94,.22);color:var(--err)}}
.mini-btn.mini-err:hover{{background:rgba(244,63,94,.14)}}

/* log / cmd boxes */
.log-box{{margin-top:.4rem;background:#060810;border:1px solid var(--border2);
          border-radius:4px;padding:.5rem .7rem;overflow-x:auto}}
.log-box pre{{font-family:var(--mono);font-size:.66rem;line-height:1.8;
              color:#7dd3fc;white-space:pre-wrap;word-break:break-all}}
.err-box pre{{color:#fca5a5}}
.cmd-drawer{{margin-top:.4rem}}
.cmd-list{{display:flex;flex-direction:column;gap:.4rem}}
.cmd-empty{{font-family:var(--mono);font-size:.7rem;color:var(--muted);padding:.5rem .6rem;font-style:italic}}
.cmd-row{{background:var(--surf2);border:1px solid var(--border);border-radius:var(--r);padding:.5rem .7rem}}
.cmd-row.ok{{border-color:rgba(34,197,94,.18)}}
.cmd-row.fail{{border-color:rgba(244,63,94,.22);background:rgba(244,63,94,.02)}}
.cm-hd{{display:flex;align-items:center;gap:.4rem;flex-wrap:wrap}}
.dot{{width:7px;height:7px;border-radius:50%;flex-shrink:0}}
.dot-ok{{background:var(--ok)}} .dot-fail{{background:var(--err)}}
.cm-cmd{{font-family:var(--mono);font-size:.72rem;color:#cbd5e1;flex:1;min-width:0;word-break:break-all}}
.cm-btns{{display:flex;gap:.25rem;flex-wrap:wrap;margin-left:auto}}

/* hop table */
.hop-table{{width:100%;border-collapse:collapse;font-size:.75rem;margin-top:.4rem}}
.hop-table th{{padding:.35rem .6rem;font-size:.58rem;text-transform:uppercase;
               letter-spacing:.08em;color:var(--muted);font-weight:600;
               background:var(--surf3);border-bottom:1px solid var(--border);text-align:left}}
.hop-table td{{padding:.4rem .6rem;border-bottom:1px solid var(--border);font-family:var(--mono);font-size:.72rem}}

/* JSON */
.json-sec{{margin-top:1.5rem}}
.json-sec summary{{cursor:pointer;font-family:var(--mono);font-size:.68rem;font-weight:600;
                   text-transform:uppercase;letter-spacing:.08em;color:var(--muted);
                   padding:.4rem 0;transition:color .12s;list-style:none}}
.json-sec[open] summary,.json-sec summary:hover{{color:var(--accent)}}
.json-sec summary::-webkit-details-marker{{display:none}}
pre.jb{{margin-top:.6rem;background:var(--surf);border:1px solid var(--border);
        border-radius:var(--r);padding:1rem 1.2rem;font-family:var(--mono);
        font-size:.68rem;line-height:1.75;color:#8896aa;overflow-x:auto;white-space:pre}}
.ft{{margin-top:2.5rem;padding-top:.75rem;border-top:1px solid var(--border);
     font-size:.62rem;color:var(--muted);font-family:var(--mono);text-align:center}}

/* ── diff / report ──────────────────────────────────────────────────────── */
.diff-drawer{{margin-top:.5rem;display:flex;flex-direction:column;gap:.6rem}}
.diff-cmd-block{{background:var(--surf2);border:1px solid var(--border);border-radius:var(--r);overflow:hidden}}
.diff-cmd-hd{{display:flex;align-items:center;gap:.6rem;padding:.5rem .75rem;flex-wrap:wrap}}
.diff-cmd-hd code{{font-family:var(--mono);font-size:.72rem;color:#cbd5e1}}
.diff-summary{{display:flex;gap:.3rem;margin-left:auto}}
.diff-cnt{{font-family:var(--mono);font-size:.62rem;font-weight:700;padding:.1rem .35rem;border-radius:3px}}
.diff-cnt.add{{background:rgba(34,197,94,.12);color:var(--ok);border:1px solid rgba(34,197,94,.25)}}
.diff-cnt.del{{background:rgba(244,63,94,.12);color:var(--err);border:1px solid rgba(244,63,94,.25)}}
.diff-cnt.chg{{background:rgba(245,158,11,.12);color:var(--warn);border:1px solid rgba(245,158,11,.25)}}
.diff-tbl-wrap{{overflow-x:auto;border-top:1px solid var(--border)}}
.diff-tbl{{width:100%;border-collapse:collapse;table-layout:fixed}}
.diff-tbl th,.diff-tbl td{{padding:.35rem .65rem;font-family:var(--mono);font-size:.68rem;line-height:1.6;word-break:break-all}}
.diff-th-pre{{width:48%;background:rgba(244,63,94,.06);color:var(--err);font-size:.58rem;text-transform:uppercase;letter-spacing:.08em;font-weight:600;border-bottom:1px solid var(--border)}}
.diff-th-post{{width:48%;background:rgba(34,197,94,.06);color:var(--ok);font-size:.58rem;text-transform:uppercase;letter-spacing:.08em;font-weight:600;border-bottom:1px solid var(--border)}}
.diff-th-sep{{width:4px;background:var(--bg);border-bottom:1px solid var(--border)}}
.dr-add td{{background:rgba(34,197,94,.04)}}
.dr-del td{{background:rgba(244,63,94,.04)}}
.dr-chg td{{background:rgba(245,158,11,.03)}}
.diff-tbl tr:not(:last-child) td{{border-bottom:1px solid rgba(255,255,255,.04)}}
.diff-sep{{width:4px!important;padding:0!important;background:var(--border)}}
.diff-pre{{color:#fca5a5!important;vertical-align:top}}
.diff-post{{color:#86efac!important;vertical-align:top}}
.diff-add{{color:var(--ok)}} .diff-del{{color:var(--err)}}
.diff-add-inline{{background:rgba(34,197,94,.22);color:var(--ok);border-radius:2px;padding:0 1px}}
.diff-del-inline{{background:rgba(244,63,94,.22);color:var(--err);border-radius:2px;padding:0 1px}}
.diff-na{{color:var(--muted);font-style:italic}}
.diff-none{{font-family:var(--mono);font-size:.72rem;color:var(--muted);padding:.4rem 0;font-style:italic}}
@media(max-width:600px){{
  .ph-summary{{grid-template-columns:repeat(2,1fr)}}
  .hdr{{flex-direction:column}}
  .sel-bar{{flex-direction:column;align-items:flex-start}}
  .dev-sel{{width:100%}}
}}
</style>
</head>
<body>
<div class="wrap">

<header class="hdr">
  <div>
    <h1>Network Device <span>Workflow Report</span></h1>
    <p class="sub">Generated: {now} &nbsp;·&nbsp; {len(device_keys)} device(s)</p>
  </div>
  <span class="pill {pill_cls}">{_esc(pill_txt)}</span>
</header>

<div class="sel-bar">
  <label for="dev-sel">Device</label>
  <select id="dev-sel" class="dev-sel" onchange="selectDevice(this.value)">
    {dropdown_opts}
  </select>
  <span class="dev-cnt">{len(device_keys)} device(s)</span>
</div>

{device_panels}

<details class="json-sec">
  <summary>▶ Raw JSON (all devices)</summary>
  <pre class="jb">{json_html}</pre>
</details>

<footer class="ft">workflow_report_generator.py · {now}</footer>
</div>

<script>
var DI = {di_json};

function updateInfo(key) {{
  var d = DI[key]; if (!d) return;
  var set = function(id, v) {{ var el = document.getElementById(id); if (el) el.textContent = v || '—'; }};
  set('di-host-'+key, d.host);
  set('di-vendor-'+key, d.vendor);
  set('di-model-'+key, d.model);
  set('di-hostname-'+key, d.hostname);
  set('di-version-'+key, d.version);
}}

function selectDevice(key) {{
  document.querySelectorAll('.device-panel').forEach(function(p){{ p.style.display='none'; }});
  var p = document.getElementById('panel-'+key);
  if (p) p.style.display='block';
  updateInfo(key);
}}

function tgl(id) {{
  var el = document.getElementById(id);
  if (el) el.hidden = !el.hidden;
}}

function toggleTable(id, btn) {{
  var el = document.getElementById(id);
  if (!el) return;
  el.hidden = !el.hidden;
  btn.classList.toggle('open', !el.hidden);
  btn.textContent = el.hidden ? '▶ Show Full Task Table' : '▼ Hide Task Table';
}}

document.addEventListener('DOMContentLoaded', function() {{
  updateInfo('{_esc(first_key)}');
}});
</script>
</body>
</html>"""

    os.makedirs(output_dir, exist_ok=True)
    filename  = f"workflow_report_{ts_file}.html"
    file_path = os.path.join(output_dir, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html)
    return file_path


# ─────────────────────────────────────────────────────────────────────────────
# mock_device_results  — build a realistic device_results dict for testing
#
# Usage:
#   data = mock_device_results()
#   path = generate_html_report(data, output_dir=".")
#
# Parameters (all optional):
#   devices   – list of dicts, each with keys:
#                 host, vendor, model, hostname,
#                 curr_os, target_os, hops (list of dicts with image/os keys),
#                 pre_fail  (task name to force-fail, e.g. "validate_md5"),
#                 upgrade_status ("completed"|"failed"|"not_started"|"rolled_back")
#   If devices is None, two Juniper devices are created automatically.
# ─────────────────────────────────────────────────────────────────────────────
def mock_device_results(devices: list = None) -> dict:
    import random, hashlib

    # ── default device specs ──────────────────────────────────────────────────
    if devices is None:
        devices = [
            {
                "host":           "10.0.0.1",
                "vendor":         "juniper",
                "model":          "MX204",
                "hostname":       "core-router-01",
                "curr_os":        "21.4R3.15",
                "target_os":      "22.4R3.25",
                "hops": [
                    {"image": "junos-vmhost-mx-22.1R1.10.tgz", "os": "22.1R1.10"},
                    {"image": "junos-vmhost-mx-22.4R3.25.tgz", "os": "22.4R3.25"},
                ],
                "pre_fail":       None,          # e.g. "validate_md5"
                "upgrade_status": "completed",
            },
            {
                "host":           "10.0.0.2",
                "vendor":         "juniper",
                "model":          "MX480",
                "hostname":       "core-router-02",
                "curr_os":        "21.2R1.11",
                "target_os":      "22.4R3.25",
                "hops": [
                    {"image": "junos-vmhost-mx-22.4R3.25.tgz", "os": "22.4R3.25"},
                ],
                "pre_fail":       "validate_md5",  # simulate a checksum failure
                "upgrade_status": "not_started",
            },
        ]

    def _md5(s: str) -> str:
        return hashlib.md5(s.encode()).hexdigest()

    def _show_cmds(vendor: str, model: str, phase: str) -> list:
        """Realistic Juniper show command outputs with raw text + parsed JSON."""

        # ── show chassis fpc detail | no-more ────────────────────────────────
        fpc_raw = (
            "Slot 0 information:\n"
            "  State                               Online\n"
            "  Total CPU DRAM                   2048 MB\n"
            "  Total RLDRAM                      256 MB\n"
            "  Total DDR DRAM                   4096 MB\n"
            "  FIPS Capable                        False\n"
            "  Temperature                        38 degrees C / 100 degrees F\n"
            "  Start time:                        2024-01-10 08:23:11 UTC\n"
            "  Uptime:                            5 days, 6 hours, 12 minutes, 44 seconds\n"
        )
        fpc_json = {
            "slots": [{
                "slot": 0, "state": "Online",
                "total_cpu_dram": "2048 MB", "total_rldram": "256 MB",
                "total_ddr_dram": "4096 MB", "fips_capable": "False",
                "temperature": "38 degrees C / 100 degrees F",
                "start_time": "2024-01-10 08:23:11 UTC",
                "uptime": "5 days, 6 hours, 12 minutes, 44 seconds",
            }]
        }

        # ── show interfaces terse | no-more ──────────────────────────────────
        iface_raw = (
            "Interface               Admin Link Proto    Local                 Remote\n"
            "ge-0/0/0                up    up\n"
            "ge-0/0/0.0              up    up   inet     192.168.1.1/30\n"
            "ge-0/0/1                up    up\n"
            "ge-0/0/1.0              up    up   inet     10.0.0.1/30\n"
            "lo0                     up    up\n"
            "lo0.0                   up    up   inet     127.0.0.1           --> 0/0\n"
        )
        iface_json = {
            "interfaces": [
                {"name": "ge-0/0/0", "admin": "up", "link": "up", "proto": "inet", "local": "192.168.1.1/30"},
                {"name": "ge-0/0/1", "admin": "up", "link": "up", "proto": "inet", "local": "10.0.0.1/30"},
                {"name": "lo0",      "admin": "up", "link": "up", "proto": "inet", "local": "127.0.0.1"},
            ]
        }

        # ── show bgp summary | no-more ────────────────────────────────────────
        bgp_raw = (
            "Groups: 2  Peers: 4  Down peers: 0\n"
            "Table          Tot Paths  Act Paths  Suppressed  History  Damp State  Pending\n"
            "inet.0               284       280           0        0           0        0\n"
            "Peer              AS      InPkt     OutPkt  LastEvt  Holdtime  Up/Down  State|#Active/Received/Accepted/Damped...\n"
            "10.0.0.10      65001      14829      14820  Establish       90 2d 4:12:08 Establ\n"
            "  inet.0: 142/142/142/0\n"
            "10.0.0.11      65001      14810      14815  Establish       90 2d 4:11:55 Establ\n"
            "  inet.0: 138/142/142/0\n"
        )
        bgp_json = {
            "bgp_summary": {
                "groups": 2, "peers": 4, "down_peers": 0,
                "peers_detail": [
                    {"peer": "10.0.0.10", "as": 65001, "state": "Established",
                     "updown": "2d 4:12:08", "active_routes": 142, "received_routes": 142},
                    {"peer": "10.0.0.11", "as": 65001, "state": "Established",
                     "updown": "2d 4:11:55", "active_routes": 138, "received_routes": 142},
                ]
            }
        }

        # ── show route summary | no-more ──────────────────────────────────────
        route_raw = (
            "Autonomous system number: 65000\n"
            "Router ID: 10.0.0.1\n\n"
            "inet.0: 142500 destinations, 142501 routes (142498 active, 0 holddown, 3 hidden)\n"
            "              Direct:      5 routes,      5 active\n"
            "               Local:      5 routes,      5 active\n"
            "                 BGP:  142491 routes,  142488 active\n"
            "inet6.0: 4120 destinations, 4121 routes (4120 active, 0 holddown, 0 hidden)\n"
            "              Direct:      2 routes,      2 active\n"
            "                 BGP:   4119 routes,   4118 active\n"
        )
        route_json = {
            "route_summary": {
                "router_id": "10.0.0.1", "as": 65000,
                "tables": [
                    {"table": "inet.0",  "destinations": 142500, "routes": 142501,
                     "active": 142498, "holddown": 0, "hidden": 3},
                    {"table": "inet6.0", "destinations": 4120,   "routes": 4121,
                     "active": 4120,   "holddown": 0, "hidden": 0},
                ]
            }
        }

        return [
            {
                "cmd":       "show chassis fpc detail | no-more",
                "output":    fpc_raw,
                "json":      fpc_json,
                "exception": "",
            },
            {
                "cmd":       "show interfaces terse | no-more",
                "output":    iface_raw,
                "json":      iface_json,
                "exception": "",
            },
            {
                "cmd":       "show bgp summary | no-more",
                "output":    bgp_raw,
                "json":      bgp_json,
                "exception": "",
            },
            {
                "cmd":       "show route summary | no-more",
                "output":    route_raw,
                "json":      route_json,
                "exception": "",
            },
        ]

    result = {}

    for spec in devices:
        host    = spec["host"]
        vendor  = spec["vendor"].lower()
        model   = str(spec["model"]).lower().replace("-", "")
        ip_key  = host.replace(".", "_")
        dk      = f"{ip_key}_{vendor}_{model}"

        curr_os   = spec["curr_os"]
        target_os = spec["target_os"]
        hops_spec = spec.get("hops", [])
        pre_fail  = spec.get("pre_fail")          # task name to force-fail
        upg_st    = spec.get("upgrade_status", "completed")

        good_md5 = _md5(f"{host}-image")

        # ── pre-checks ────────────────────────────────────────────────────────
        def _pre_status(task):
            if pre_fail and task == pre_fail:
                return "failed"
            return "ok"

        def _pre_exc(task):
            if pre_fail and task == pre_fail:
                excmap = {
                    "connect":                   "SSH connection refused (timeout 30s)",
                    "show_version":              "Could not parse version from output",
                    "check_storage":             "Insufficient disk space: 1.2 GB available, 4.0 GB required",
                    "backup_active_filesystem":  "request vmhost snapshot timed out after 900s",
                    "backup_running_config":     "SCP transfer failed: Permission denied (publickey)",
                    "transfer_image":            "SCP transfer failed: No route to host 192.168.1.100",
                    "validate_md5":              f"Checksum mismatch: expected={good_md5} computed={_md5('bad')}",
                    "disable_re_protect_filter": "disableReProtectFilter returned False",
                }
                return excmap.get(task, "Unknown error")
            return ""

        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        pre = {
            "connect": {
                "status":    _pre_status("connect"),
                "exception": _pre_exc("connect"),
                "ping":      True,
            },
            "execute_show_commands": {
                "status":    "ok",
                "exception": "",
                "commands":  _show_cmds(vendor, model, "pre"),
            },
            "show_version": {
                "status":    _pre_status("show_version"),
                "exception": _pre_exc("show_version"),
                "version":   curr_os,
                "platform":  spec["model"],
            },
            "check_storage": {
                "status":        _pre_status("check_storage"),
                "exception":     _pre_exc("check_storage"),
                "deleted_files": [],
                "sufficient":    pre_fail != "check_storage",
            },
            "backup_active_filesystem": {
                "status":     _pre_status("backup_active_filesystem"),
                "exception":  _pre_exc("backup_active_filesystem"),
                "disk_count": "dual",
            },
            "backup_running_config": {
                "status":      _pre_status("backup_running_config"),
                "exception":   _pre_exc("backup_running_config"),
                "config_file": f"{vendor}_{model}_{ts}",
                "destination": "192.168.1.100",
            },
            "transfer_image": {
                "status":      _pre_status("transfer_image"),
                "exception":   _pre_exc("transfer_image"),
                "image":       hops_spec[-1]["image"] if hops_spec else "",
                "destination": "/var/tmp/",
            },
            "validate_md5": {
                "status":    _pre_status("validate_md5"),
                "exception": _pre_exc("validate_md5"),
                "expected":  good_md5,
                "computed":  good_md5 if pre_fail != "validate_md5" else _md5("bad"),
                "match":     pre_fail != "validate_md5",
            },
        }

        # ── upgrade ───────────────────────────────────────────────────────────
        hop_entries = []
        for i, h in enumerate(hops_spec):
            if upg_st == "completed":
                h_status  = "ok"
                h_exc     = ""
                h_md5     = True
            elif upg_st == "not_started":
                h_status  = "not_started"
                h_exc     = ""
                h_md5     = False
            elif upg_st == "failed":
                # last hop fails, earlier ones ok
                h_status  = "failed" if i == len(hops_spec) - 1 else "ok"
                h_exc     = "imageUpgrade timed out waiting for reboot" if h_status == "failed" else ""
                h_md5     = True
            elif upg_st == "rolled_back":
                h_status  = "rolled_back"
                h_exc     = ""
                h_md5     = True
            else:
                h_status  = "not_started"
                h_exc     = ""
                h_md5     = False

            hop_entries.append({
                "image":     h["image"],
                "status":    h_status,
                "exception": h_exc,
                "md5_match": h_md5,
            })

        upg_exc = ""
        if upg_st == "failed":
            upg_exc = "imageUpgrade timed out waiting for reboot on final hop"

        upgrade = {
            "status":     upg_st,
            "initial_os": curr_os,
            "target_os":  target_os,
            "exception":  upg_exc,
            "hops":       hop_entries,
        }

        # ── post-checks ───────────────────────────────────────────────────────
        post_ok = (upg_st == "completed" and pre_fail is None)
        post = {
            "connect": {
                "status":    "ok" if post_ok else "not_started",
                "exception": "",
            },
            "execute_show_commands": {
                "status":    "ok" if post_ok else "not_started",
                "exception": "",
                "commands":  _show_cmds(vendor, model, "post") if post_ok else [],
            },
            "show_version": {
                "status":    "ok" if post_ok else "not_started",
                "exception": "",
                "version":   target_os if post_ok else "",
                "platform":  spec["model"],
            },
        }

        # ── report (diff) ─────────────────────────────────────────────────────
        if post_ok:
            report = {
                "status":    "generated",
                "exception": "",
                "diff": {
                    "show chassis fpc detail | no-more": [
                        {
                            "pre":    "  State                               Online",
                            "post":   "  State                               Online",
                            "change": "",
                        },
                        {
                            "pre":    "  Total CPU DRAM                   2048 MB",
                            "post":   "  Total CPU DRAM                   2048 MB",
                            "change": "",
                        },
                        {
                            "pre":    "  Temperature                        38 degrees C / 100 degrees F",
                            "post":   "  Temperature                        41 degrees C / 106 degrees F",
                            "change": ["38 degrees C / 100 degrees F", "41 degrees C / 106 degrees F"],
                        },
                        {
                            "pre":    "  Uptime:                            5 days, 6 hours, 12 minutes, 44 seconds",
                            "post":   "  Uptime:                            0 days, 0 hours, 4 minutes, 12 seconds",
                            "change": ["5 days, 6 hours, 12 minutes, 44 seconds", "0 days, 0 hours, 4 minutes, 12 seconds"],
                        },
                    ],
                    "show interfaces terse | no-more": [
                        {
                            "pre":    "ge-0/0/0                up    up",
                            "post":   "ge-0/0/0                up    up",
                            "change": "",
                        },
                    ],
                    "show bgp summary | no-more": [
                        {
                            "pre":    "10.0.0.10      65001      14829      14820  Establish       90 2d 4:12:08 Establ",
                            "post":   "N/A",
                            "change": "",
                        },
                        {
                            "pre":    "N/A",
                            "post":   "10.0.0.10      65001          5          4  Establish       90 0d 0:04:10 Establ",
                            "change": "",
                        },
                        {
                            "pre":    "10.0.0.11      65001      14810      14815  Establish       90 2d 4:11:55 Establ",
                            "post":   "N/A",
                            "change": "",
                        },
                        {
                            "pre":    "N/A",
                            "post":   "10.0.0.11      65001          4          4  Establish       90 0d 0:04:08 Establ",
                            "change": "",
                        },
                    ],
                    "show route summary | no-more": [
                        {
                            "pre":    "inet.0: 142500 destinations, 142501 routes (142498 active, 0 holddown, 3 hidden)",
                            "post":   "inet.0: 142498 destinations, 142499 routes (142498 active, 0 holddown, 1 hidden)",
                            "change": ["142500 destinations, 142501 routes (142498 active, 0 holddown, 3 hidden)",
                                       "142498 destinations, 142499 routes (142498 active, 0 holddown, 1 hidden)"],
                        },
                    ],
                },
            }
        else:
            report = {
                "status":    "pending",
                "exception": "" if not pre_fail else f"Pre-check failed at {pre_fail} — diff skipped",
                "diff":      {},
            }

        result[dk] = {
            "status":      upg_st if pre_fail is None else "failed",
            "device_info": {
                "host":     host,
                "vendor":   vendor,
                "model":    spec["model"],
                "hostname": spec["hostname"],
                "version":  curr_os,
            },
            "pre":     pre,
            "upgrade": upgrade,
            "post":    post,
            "report":  report,
        }

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Quick self-test — run this file directly to generate a sample report
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    data = mock_device_results()
    path = generate_html_report(data, output_dir=".")
    print(f"Report written: {path}")
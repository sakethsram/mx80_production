#!/usr/bin/env python3
"""
workflow_report_generator.py
Pre + Upgrade + Post driven by actual JSON data.
"""

from datetime import datetime
import json
import os
import difflib as _dl


PRE_TASK_TITLES = {
    "connect":                   "Connect to Device",
    "execute_show_commands":     "Collect Show Outputs",
    "show_version":              "Show Version",
    "check_storage":             "Check Storage",
    "backup_active_filesystem":  "Backup Active Filesystem",
    "backup_running_config":     "Backup Running Config",
    "transfer_image":            "Transfer Image",
    "verify_checksum":           "Verify Checksum",
    "disable_re_protect_filter": "Disable RE Protect Filter",
}

POST_TASK_TITLES = {
    "connect":               "Connect to Device",
    "show_version":          "Show Version (Post-Upgrade)",
    "execute_show_commands": "Collect Show Outputs (Post-Upgrade)",
}

PHASE_META = {
    "pre":     {"label": "Pre-Checks",  "color": "#38bdf8"},
    "upgrade": {"label": "Upgrade",     "color": "#a78bfa"},
    "post":    {"label": "Post-Checks", "color": "#34d399"},
    "report":  {"label": "Report",      "color": "#fb923c"},
}


# ─── helpers ──────────────────────────────────────────────────────────────────

def _esc(s):
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _norm_status(raw) -> str:
    if raw is True:  return "ok"
    if raw is False: return "failed"
    if isinstance(raw, str):
        s = raw.strip().lower()
        if s in ("success", "true", "completed", "ok", "passed",
                 "skipped", "generated", "low_space_cleaned"):
            return "ok"
        if s in ("failed", "false", "error", "rollback_failed"):
            return "failed"
        if s == "not_started":               return "not_started"
        if s in ("in_progress", "rolled_back"): return s
        if s == "":                          return ""
        return raw
    return str(raw) if raw is not None else ""


def _badge(status: str) -> str:
    m = {
        "ok":             '<span class="badge b-ok">OK</span>',
        "failed":         '<span class="badge b-fail">Failed</span>',
        "rollback_failed":'<span class="badge b-fail">Failed</span>',
        "not_started":    '<span class="badge b-ns">—</span>',
        "":               '<span class="badge b-ns">—</span>',
        "rolled_back":    '<span class="badge b-warn">Rolled Back</span>',
        "in_progress":    '<span class="badge b-ip">In Progress</span>',
        "low_space_cleaned": '<span class="badge b-warn">Cleaned</span>',
    }
    return m.get(status, f'<span class="badge b-ns">{_esc(status)}</span>')


def _remark(exc: str) -> str:
    return (f'<span class="remark-err">{_esc(exc)}</span>'
            if exc else '<span class="remark-na">—</span>')


# ─── command output drawer ────────────────────────────────────────────────────

def _cmd_drawer(cmds: list, prefix: str, phase: str) -> str:
    did = f"cmds-{prefix}-{phase}"
    if not cmds:
        return (f'<div class="cmd-drawer" hidden id="{did}">'
                f'<div class="cmd-empty">No commands collected.</div></div>')
    items = []
    for i, e in enumerate(cmds):
        lbl    = _esc(e.get("cmd", ""))
        raw    = _esc(e.get("output", "") or "(empty)")
        jobj   = e.get("json", {})
        jstr   = _esc(json.dumps(jobj, indent=2)) if jobj else "(not parsed)"
        exc    = _esc(e.get("exception", "") or "")
        ok     = exc == ""
        rid, jid, eid = (f"raw-{prefix}-{phase}-{i}",
                         f"jsn-{prefix}-{phase}-{i}",
                         f"exc-{prefix}-{phase}-{i}")
        err_btn = (f'<button class="mini-btn mini-err" onclick="tgl(\'{eid}\')">Why?</button>'
                   if not ok else "")
        items.append(f"""<div class="{'cmd-row ok' if ok else 'cmd-row fail'}">
  <div class="cm-hd">
    <span class="dot {'dot-ok' if ok else 'dot-fail'}"></span>
    <code class="cm-cmd">{lbl}</code>
    <div class="cm-btns">
      <button class="mini-btn" onclick="tgl('{rid}')">Raw</button>
      <button class="mini-btn" onclick="tgl('{jid}')">JSON</button>
      {err_btn}
    </div>
  </div>
  <div id="{rid}" class="log-box" hidden><pre>{raw}</pre></div>
  <div id="{jid}" class="log-box" hidden><pre>{jstr}</pre></div>
  {"" if ok else f'<div id="{eid}" class="log-box err-box" hidden><pre>{exc}</pre></div>'}
</div>""")
    return (f'<div class="cmd-drawer" hidden id="{did}">'
            f'<div class="cmd-list">{"".join(items)}</div></div>')


# ─── verify_checksum list ─────────────────────────────────────────────────────

def _checksum_drawer(entries: list, prefix: str):
    if not entries:
        return "", ""
    rows = []
    for i, e in enumerate(entries):
        image    = _esc(e.get("image", "—"))
        status   = _norm_status(e.get("status", "not_started"))
        match    = e.get("match", None)
        expected = _esc(e.get("expected", "—"))
        computed = _esc(e.get("computed", "—") or "—")
        exc      = _esc(e.get("exception", "") or "")
        match_html = ('<span class="badge b-ok">✓ Match</span>'    if match is True  else
                      '<span class="badge b-fail">✗ Mismatch</span>' if match is False else
                      '<span class="badge b-ns">—</span>')
        exc_part = f'<br><span class="remark-err">{exc}</span>' if exc else ""
        rows.append(
            f'<tr class="task-row">'
            f'<td class="subtask-cell mono">{i+1}</td>'
            f'<td class="subtask-cell mono" style="word-break:break-all;font-size:.65rem;">{image}</td>'
            f'<td class="status-cell">{_badge(status)}</td>'
            f'<td class="status-cell">{match_html}</td>'
            f'<td class="remark-cell mono" style="font-size:.63rem;line-height:1.7;">'
            f'<span style="color:var(--muted2);">exp:</span> {expected}<br>'
            f'<span style="color:var(--muted2);">got:</span> {computed}{exc_part}</td>'
            f'</tr>'
        )
    cid    = f"chk-{prefix}"
    toggle = f'<button class="mini-btn" onclick="tgl(\'{cid}\')">Checksums ({len(entries)})</button>'
    drawer = (f'<div class="cmd-drawer" hidden id="{cid}">'
              f'<table class="hop-table"><thead><tr>'
              f'<th>#</th><th>Image</th><th>Status</th><th>Match</th><th>Checksums</th>'
              f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')
    return toggle, drawer


# ─── upgrade hops ─────────────────────────────────────────────────────────────

def _hops_rows(hops: list) -> str:
    rows = []
    for i, hop in enumerate(hops):
        image  = _esc(hop.get("image", "—"))
        status = _norm_status(hop.get("status", "not_started"))
        exc    = _esc(hop.get("exception", "") or "")
        md5    = hop.get("md5_match", None)
        conn   = hop.get("connect") if isinstance(hop.get("connect"), dict) else {}
        conn_st = _norm_status(conn.get("status", "not_started")) if conn else "not_started"
        conn_at = conn.get("attempt", "") if conn else ""
        conn_html = (f'<span class="badge b-ok">✓{" att "+str(conn_at) if conn_at else ""}</span>'
                     if conn_st == "ok" else _badge(conn_st))
        md5_html = ('<span class="badge b-ok">✓</span>'    if md5 is True  else
                    '<span class="badge b-fail">✗</span>'  if md5 is False else
                    '<span class="badge b-ns">—</span>')
        rows.append(
            f'<tr class="task-row{"" if status in ("ok","not_started","") else " failed-row"}">'
            f'<td class="hop-num-cell">{i+1}</td>'
            f'<td class="hop-image-cell">{image}</td>'
            f'<td class="hop-status-cell">{_badge(status)}</td>'
            f'<td class="hop-status-cell">{md5_html}</td>'
            f'<td class="hop-status-cell">{conn_html}</td>'
            f'<td class="hop-remark-cell">{"<span class=remark-err>" + exc + "</span>" if exc else "<span class=remark-na>—</span>"}</td>'
            f'</tr>'
        )
    return "\n".join(rows)


# ─── pre-phase rows ───────────────────────────────────────────────────────────

def _pre_rows(tasks: dict, prefix: str) -> tuple:
    color = PHASE_META["pre"]["color"]
    label = PHASE_META["pre"]["label"]
    items = [(n, d) for n, d in tasks.items() if isinstance(d, (dict, list))]
    count = len(items)
    rows  = []
    total = success = failed = 0
    first = True

    for name, data in items:

        # ── verify_checksum is a LIST ─────────────────────────────────────────
        if name == "verify_checksum" and isinstance(data, list):
            if not data:
                agg = "not_started"
            elif all(_norm_status(e.get("status","")) == "ok" for e in data):
                agg = "ok"
            elif any(_norm_status(e.get("status","")) == "failed" for e in data):
                agg = "failed"
            else:
                agg = _norm_status(data[0].get("status", "not_started"))

            is_blank = agg in ("", "not_started")
            total += 1
            if agg == "ok":   success += 1
            elif not is_blank: failed += 1

            toggle, drawer = _checksum_drawer(data, prefix)
            pc = (f'<td class="phase-cell" rowspan="{count}" '
                  f'style="border-left:3px solid {color};">'
                  f'<span class="phase-lbl" style="color:{color};">{label}</span></td>'
                  ) if first else ""
            first = False
            rows.append(
                f'<tr class="task-row{"" if (agg == "ok" or is_blank) else " failed-row"}">'
                f'{pc}'
                f'<td class="subtask-cell"><span class="mono">'
                f'{PRE_TASK_TITLES.get(name, name)}</span> {toggle}{drawer}</td>'
                f'<td class="status-cell">{_badge(agg)}</td>'
                f'<td class="remark-cell"><span class="remark-na">—</span></td>'
                f'</tr>'
            )
            continue

        # ── standard dict task ────────────────────────────────────────────────
        status   = _norm_status(data.get("status", ""))
        is_blank = status in ("", "not_started")
        exc      = data.get("exception", "") or ""
        display  = PRE_TASK_TITLES.get(name, name.replace("_", " ").title())

        total += 1
        if status == "ok":   success += 1
        elif not is_blank:   failed  += 1

        pc = (f'<td class="phase-cell" rowspan="{count}" '
              f'style="border-left:3px solid {color};">'
              f'<span class="phase-lbl" style="color:{color};">{label}</span></td>'
              ) if first else ""
        first = False

        toggle = drawer = ""
        if name == "execute_show_commands":
            cmds   = data.get("commands", [])
            bid    = f"cmds-{prefix}-pre"
            toggle = f'<button class="mini-btn" onclick="tgl(\'{bid}\')">Outputs ({len(cmds)})</button>'
            drawer = _cmd_drawer(cmds, prefix, "pre")

        # task-specific remarks
        if name == "connect":
            ping = data.get("ping", None)
            parts = []
            if ping is not None:
                p = str(ping).lower()
                parts.append(f'<span class="remark-ok">ping: {_esc(p)}</span>'
                              if p in ("up","true")
                              else f'<span class="remark-err">ping: {_esc(p)}</span>')
            if exc: parts.append(f'<span class="remark-err">{_esc(exc)}</span>')
            remark = " &nbsp;·&nbsp; ".join(parts) or '<span class="remark-na">—</span>'

        elif name == "check_storage":
            parts = []
            deleted = data.get("deleted_files", [])
            if deleted: parts.append('<span class="remark-ok">files cleaned</span>')
            if data.get("sufficient") is False and status != "ok":
                parts.append('<span class="remark-err">insufficient space</span>')
            if exc: parts.append(f'<span class="remark-err">{_esc(exc)}</span>')
            remark = " &nbsp;·&nbsp; ".join(parts) or '<span class="remark-na">—</span>'

        elif name == "backup_active_filesystem":
            dc = data.get("disk_count", "")
            parts = []
            if dc: parts.append(f'<span class="mono" style="color:var(--muted2);">disks: {_esc(dc)}</span>')
            if exc: parts.append(f'<span class="remark-err">{_esc(exc)}</span>')
            remark = " &nbsp;·&nbsp; ".join(parts) or '<span class="remark-na">—</span>'

        elif name == "backup_running_config":
            cfg  = data.get("config_file","") or data.get("log_file","")
            dest = data.get("destination","")
            parts = []
            if cfg:  parts.append(f'<span class="mono" style="color:var(--muted2);">{_esc(cfg)}</span>')
            if dest: parts.append(f'<span class="mono" style="color:var(--muted2);">&#8594; {_esc(dest)}</span>')
            if exc:  parts.append(f'<span class="remark-err">{_esc(exc)}</span>')
            remark = " ".join(parts) or '<span class="remark-na">—</span>'

        elif name == "transfer_image":
            img  = data.get("image","")
            dest = data.get("destination","")
            parts = []
            if img:  parts.append(f'<span class="mono" style="color:var(--muted2);">{_esc(img)}</span>')
            if dest: parts.append(f'<span class="mono" style="color:var(--muted2);">&#8594; {_esc(dest)}</span>')
            if exc:  parts.append(f'<span class="remark-err">{_esc(exc)}</span>')
            remark = " ".join(parts) or '<span class="remark-na">—</span>'

        elif name == "show_version":
            ver  = data.get("version","")
            plat = data.get("platform","")
            hn   = data.get("hostname","")
            parts = []
            if hn:   parts.append(f'<span class="mono" style="color:var(--accent);">{_esc(hn)}</span>')
            if plat: parts.append(f'<span class="mono" style="color:var(--muted2);">{_esc(plat)}</span>')
            if ver:  parts.append(f'<span class="mono" style="color:var(--muted2);">v{_esc(ver)}</span>')
            if exc:  parts.append(f'<span class="remark-err">{_esc(exc)}</span>')
            remark = " &nbsp;·&nbsp; ".join(parts) or '<span class="remark-na">—</span>'

        else:
            remark = _remark(exc)

        row_cls = "" if (status == "ok" or is_blank) else " failed-row"
        rows.append(
            f'<tr class="task-row{row_cls}">'
            f'{pc}'
            f'<td class="subtask-cell"><span class="mono">{_esc(display)}</span>'
            f' {toggle}{drawer}</td>'
            f'<td class="status-cell">{_badge(status)}</td>'
            f'<td class="remark-cell">{remark}</td>'
            f'</tr>'
        )

    rows.append('<tr class="phase-sep"><td colspan="4"></td></tr>')
    return "\n".join(rows), total, success, failed


# ─── upgrade rows ─────────────────────────────────────────────────────────────

def _upgrade_rows(upg: dict, prefix: str) -> tuple:
    color      = PHASE_META["upgrade"]["color"]
    upg_status = _norm_status(upg.get("status", ""))
    initial_os = _esc(upg.get("initial_os", "—") or "—")
    target_os  = _esc(upg.get("target_os",  "—") or "—")
    upg_exc    = _esc(upg.get("exception",  "") or "")
    hops       = upg.get("hops", [])

    conn_raw  = upg.get("connect") if isinstance(upg.get("connect"), dict) else {}
    conn_st   = _norm_status(conn_raw.get("status", "not_started")) if conn_raw else "not_started"
    conn_exc  = _esc(conn_raw.get("exception", "") or "") if conn_raw else ""

    if upg_status == "ok":             upg_badge = '<span class="badge b-ok">Completed</span>'
    elif upg_status == "not_started":  upg_badge = '<span class="badge b-ns">Not Started</span>'
    elif upg_status in ("failed","rollback_failed"):
                                       upg_badge = '<span class="badge b-fail">Failed</span>'
    elif upg_status == "rolled_back":  upg_badge = '<span class="badge b-warn">Rolled Back</span>'
    elif upg_status == "in_progress":  upg_badge = '<span class="badge b-ip">In Progress</span>'
    else:                              upg_badge = f'<span class="badge b-ns">{_esc(upg_status)}</span>'

    upg_remark = f'<span class="remark-err">{upg_exc}</span>' if upg_exc else '<span class="remark-na">—</span>'

    hop_toggle = hop_drawer = ""
    if hops:
        hid        = f"hops-{prefix}"
        hop_toggle = f'<button class="mini-btn" onclick="tgl(\'{hid}\')">Hops ({len(hops)})</button>'
        hop_drawer = (
            f'<div class="cmd-drawer" hidden id="{hid}">'
            f'<div class="hop-table-wrap">'
            f'<table class="hop-table"><thead><tr>'
            f'<th class="hop-th-num">#</th>'
            f'<th class="hop-th-image">Image</th>'
            f'<th class="hop-th-status">Status</th>'
            f'<th class="hop-th-status">MD5</th>'
            f'<th class="hop-th-status">Reconnect</th>'
            f'<th class="hop-th-remark">Remark</th>'
            f'</tr></thead><tbody>{_hops_rows(hops)}</tbody></table>'
            f'</div></div>'
        )

    rows = [
        (f'<tr class="task-row{"" if upg_status in ("ok","not_started","") else " failed-row"}">'
         f'<td class="phase-cell" rowspan="4" style="border-left:3px solid {color};">'
         f'<span class="phase-lbl" style="color:{color};">Upgrade</span></td>'
         f'<td class="subtask-cell"><span class="mono">Overall Status</span></td>'
         f'<td class="status-cell">{upg_badge}</td>'
         f'<td class="remark-cell">{upg_remark}</td>'
         f'</tr>'),

        (f'<tr class="task-row">'
         f'<td class="subtask-cell"><span class="mono">Upgrade Connect</span></td>'
         f'<td class="status-cell">{_badge(conn_st)}</td>'
         f'<td class="remark-cell">{_remark(conn_exc)}</td>'
         f'</tr>'),

        (f'<tr class="task-row">'
         f'<td class="subtask-cell"><span class="mono">OS Path</span></td>'
         f'<td class="status-cell"></td>'
         f'<td class="remark-cell mono" style="color:var(--muted2);">'
         f'{initial_os} &#8594; {target_os}</td>'
         f'</tr>'),

        (f'<tr class="task-row">'
         f'<td class="subtask-cell"><span class="mono">Hop Details</span>'
         f' {hop_toggle}{hop_drawer}</td>'
         f'<td class="status-cell"></td>'
         f'<td class="remark-cell"></td>'
         f'</tr>'),

        '<tr class="phase-sep"><td colspan="4"></td></tr>',
    ]

    total   = 1
    success = 1 if upg_status == "ok" else 0
    failed  = 1 if upg_status not in ("", "ok", "not_started") else 0
    return "\n".join(rows), total, success, failed


# ─── post rows (real data) ────────────────────────────────────────────────────

def _post_rows(post: dict, prefix: str) -> tuple:
    color = PHASE_META["post"]["color"]
    label = PHASE_META["post"]["label"]

    task_order = ["connect", "show_version", "execute_show_commands"]
    count  = len(task_order)
    rows   = []
    total  = success = failed = 0
    first  = True

    for name in task_order:
        display = POST_TASK_TITLES.get(name, name.replace("_", " ").title())
        data    = post.get(name, {})

        if not data:
            pc = (f'<td class="phase-cell" rowspan="{count}" '
                  f'style="border-left:3px solid {color};">'
                  f'<span class="phase-lbl" style="color:{color};">{label}</span></td>'
                  ) if first else ""
            first = False
            rows.append(
                f'<tr class="task-row">{pc}'
                f'<td class="subtask-cell"><span class="mono">{_esc(display)}</span></td>'
                f'<td class="status-cell"><span class="badge b-ns">—</span></td>'
                f'<td class="remark-cell"><span class="remark-na">—</span></td>'
                f'</tr>'
            )
            continue

        status   = _norm_status(data.get("status", ""))
        is_blank = status in ("", "not_started")
        exc      = data.get("exception", "") or ""

        total += 1
        if status == "ok":   success += 1
        elif not is_blank:   failed  += 1

        pc = (f'<td class="phase-cell" rowspan="{count}" '
              f'style="border-left:3px solid {color};">'
              f'<span class="phase-lbl" style="color:{color};">{label}</span></td>'
              ) if first else ""
        first = False

        toggle = drawer = ""

        if name == "show_version":
            ver  = data.get("version","")
            plat = data.get("platform","")
            hn   = data.get("hostname","")
            parts = []
            if hn:   parts.append(f'<span class="mono" style="color:var(--accent);">{_esc(hn)}</span>')
            if plat: parts.append(f'<span class="mono" style="color:var(--muted2);">{_esc(plat)}</span>')
            if ver:  parts.append(f'<span class="mono" style="color:#86efac;">v{_esc(ver)}</span>')
            if exc:  parts.append(f'<span class="remark-err">{_esc(exc)}</span>')
            remark = " &nbsp;·&nbsp; ".join(parts) or '<span class="remark-na">—</span>'

        elif name == "execute_show_commands":
            cmds   = data.get("commands", [])
            bid    = f"cmds-{prefix}-post"
            toggle = f'<button class="mini-btn" onclick="tgl(\'{bid}\')">Outputs ({len(cmds)})</button>'
            drawer = _cmd_drawer(cmds, prefix, "post")
            remark = _remark(exc)

        elif name == "connect":
            remark = _remark(exc)

        else:
            remark = _remark(exc)

        row_cls = "" if (status == "ok" or is_blank) else " failed-row"
        rows.append(
            f'<tr class="task-row{row_cls}">'
            f'{pc}'
            f'<td class="subtask-cell"><span class="mono">{_esc(display)}</span>'
            f' {toggle}{drawer}</td>'
            f'<td class="status-cell">{_badge(status)}</td>'
            f'<td class="remark-cell">{remark}</td>'
            f'</tr>'
        )

    rows.append('<tr class="phase-sep"><td colspan="4"></td></tr>')
    return "\n".join(rows), total, success, failed


# ─── report / diff phase ──────────────────────────────────────────────────────

import difflib as _difflib


def _inline_diff_html(pre_out: str, post_out: str) -> tuple:
    """
    Given two full command outputs (multi-line strings), returns
    (pre_html, post_html) with highlighted tokens.
    """
    pre_lines  = pre_out.splitlines() if pre_out else []
    post_lines = post_out.splitlines() if post_out else []
    matcher    = _difflib.SequenceMatcher(None, pre_lines, post_lines, autojunk=False)

    pre_col  = []
    post_col = []

    def _mark_line_diff(a: str, b: str):
        sm     = _difflib.SequenceMatcher(None, a, b, autojunk=False)
        ha, hb = [], []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                ha.append(_esc(a[i1:i2]))
                hb.append(_esc(b[j1:j2]))
            elif tag == "replace":
                ha.append(f'<mark class="diff-del">{_esc(a[i1:i2])}</mark>')
                hb.append(f'<mark class="diff-ins">{_esc(b[j1:j2])}</mark>')
            elif tag == "delete":
                ha.append(f'<mark class="diff-del">{_esc(a[i1:i2])}</mark>')
            elif tag == "insert":
                hb.append(f'<mark class="diff-ins">{_esc(b[j1:j2])}</mark>')
        return "".join(ha), "".join(hb)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for ln in pre_lines[i1:i2]:
                pre_col.append(f'<span class="diff-eq">{_esc(ln)}</span>')
                post_col.append(f'<span class="diff-eq">{_esc(ln)}</span>')
        elif tag == "replace":
            a_blk = pre_lines[i1:i2]
            b_blk = post_lines[j1:j2]
            pairs = min(len(a_blk), len(b_blk))
            for k in range(pairs):
                ha, hb = _mark_line_diff(a_blk[k], b_blk[k])
                pre_col.append(f'<span class="diff-line-del">{ha}</span>')
                post_col.append(f'<span class="diff-line-ins">{hb}</span>')
            for k in range(pairs, len(a_blk)):
                pre_col.append(f'<span class="diff-line-del">{_esc(a_blk[k])}</span>')
                post_col.append(f'<span class="diff-na">N/A</span>')
            for k in range(pairs, len(b_blk)):
                pre_col.append(f'<span class="diff-na">N/A</span>')
                post_col.append(f'<span class="diff-line-ins">{_esc(b_blk[k])}</span>')
        elif tag == "delete":
            for ln in pre_lines[i1:i2]:
                pre_col.append(f'<span class="diff-line-del">{_esc(ln)}</span>')
                post_col.append(f'<span class="diff-na">N/A</span>')
        elif tag == "insert":
            for ln in post_lines[j1:j2]:
                pre_col.append(f'<span class="diff-na">N/A</span>')
                post_col.append(f'<span class="diff-line-ins">{_esc(ln)}</span>')

    pre_html  = "\n".join(pre_col)  or "<span class='diff-na'>(empty)</span>"
    post_html = "\n".join(post_col) or "<span class='diff-na'>(empty)</span>"
    return pre_html, post_html


def _report_rows(diff: dict, device_data: dict, prefix: str) -> str:
    """
    Renders Phase 4 summary rows in the table.
    Shows only two summary lines: Diff Status + Commands compared/changed.
    Per-command rows and orange badges are removed.
    """
    color = PHASE_META["report"]["color"]

    if not diff:
        rows = [
            (f'<tr class="task-row">'
             f'<td class="phase-cell" rowspan="2" style="border-left:3px solid {color};">'
             f'<span class="phase-lbl" style="color:{color};">Report</span></td>'
             f'<td class="subtask-cell"><span class="mono">Diff Status</span></td>'
             f'<td class="status-cell"><span class="badge b-ns">Pending</span></td>'
             f'<td class="remark-cell"><span class="remark-na">—</span></td>'
             f'</tr>'),
            (f'<tr class="task-row">'
             f'<td class="subtask-cell" colspan="3">'
             f'<div class="diff-none">Diff will be available after post-checks complete.</div>'
             f'</td></tr>'),
            '<tr class="phase-sep"><td colspan="4"></td></tr>',
        ]
        return "\n".join(rows)

    changed_cmds = sorted(diff.keys())
    total_cmds   = len(changed_cmds)

    pre_cmds  = device_data.get("pre",  {}).get("execute_show_commands", {}).get("commands", [])
    post_cmds = device_data.get("post", {}).get("execute_show_commands", {}).get("commands", [])
    pre_map   = {c["cmd"]: c.get("output", "") for c in pre_cmds}
    post_map  = {c["cmd"]: c.get("output", "") for c in post_cmds}
    total_compared = len(set(pre_map) | set(post_map))

    # Build "Show Diff" buttons for each changed command inline in the summary row
    diff_buttons = " ".join(
        f'<button class="mini-btn" style="font-size:.5rem;" onclick="tglDiff(\'diff-{prefix}-{abs(hash(cmd)) % 999999}\')">'
        f'{_esc(cmd)}</button>'
        for cmd in changed_cmds
    )

    rows = [
        # Row 1: Diff Status
        (f'<tr class="task-row">'
         f'<td class="phase-cell" rowspan="2" style="border-left:3px solid {color};">'
         f'<span class="phase-lbl" style="color:{color};">Report</span></td>'
         f'<td class="subtask-cell"><span class="mono">Diff Status</span></td>'
         f'<td class="status-cell"><span class="badge b-ok">Complete</span></td>'
         f'<td class="remark-cell mono" style="color:var(--muted2);">'
         f'{total_cmds} changed &nbsp;·&nbsp; {total_compared} compared</td>'
         f'</tr>'),
        # Row 2: Show Diff buttons (vertical stack)
        (f'<tr class="task-row">'
         f'<td class="subtask-cell" colspan="3">'
         f'<span class="mono" style="color:var(--muted2);font-size:.63rem;display:block;margin-bottom:.3rem;">Show diff:</span>'
         f'<div style="display:flex;flex-direction:column;align-items:flex-start;gap:.25rem;">{diff_buttons}</div>'
         f'</td></tr>'),
        '<tr class="phase-sep"><td colspan="4"></td></tr>',
    ]

    return "\n".join(rows)


def _diff_section(diff: dict, device_data: dict, prefix: str) -> str:
    """
    Renders the full-width diff section that lives BELOW the main table.
    """
    if not diff:
        return ""

    pre_cmds  = device_data.get("pre",  {}).get("execute_show_commands", {}).get("commands", [])
    post_cmds = device_data.get("post", {}).get("execute_show_commands", {}).get("commands", [])
    pre_map   = {c["cmd"]: c.get("output", "") for c in pre_cmds}
    post_map  = {c["cmd"]: c.get("output", "") for c in post_cmds}

    blocks = []
    for cmd in sorted(diff.keys()):
        pre_out  = pre_map.get(cmd, "")
        post_out = post_map.get(cmd, "")
        pre_html, post_html = _inline_diff_html(pre_out, post_out)
        did = f"diff-{prefix}-{abs(hash(cmd)) % 999999}"

        blocks.append(f"""
<div class="diff-block" id="{did}" hidden>
  <div class="diff-block-hdr">
    <div class="diff-block-cmd">
      <code class="diff-block-cmdname">{_esc(cmd)}</code>
    </div>
    <button class="mini-btn mini-err" onclick="tglDiff('{did}')">Close</button>
  </div>
  <div class="diff-grid">
    <div class="diff-col-hdr">Pre-Upgrade</div>
    <div class="diff-col-hdr">Post-Upgrade</div>
    <div class="diff-pane"><pre>{pre_html}</pre></div>
    <div class="diff-pane"><pre>{post_html}</pre></div>
  </div>
</div>""")

    return f'<div class="diff-section" id="diffsec-{prefix}">{"".join(blocks)}</div>'


# ─── full tbody ───────────────────────────────────────────────────────────────

def build_tbody(device_data: dict, device_key: str) -> tuple:
    prefix   = device_key.replace(".", "_").replace("-", "_")
    all_rows = []
    total = success = failed = 0

    pre = device_data.get("pre", {})
    if pre:
        r, t, s, f = _pre_rows(pre, prefix)
        all_rows.append(r); total += t; success += s; failed += f

    upg = device_data.get("upgrade", {})
    if upg:
        r, t, s, f = _upgrade_rows(upg, prefix)
        all_rows.append(r); total += t; success += s; failed += f

    post = device_data.get("post", {})
    r, t, s, f = _post_rows(post, prefix)
    all_rows.append(r); total += t; success += s; failed += f

    diff = device_data.get("diff", {})
    all_rows.append(_report_rows(diff, device_data, prefix))

    return "\n".join(all_rows), total, success, failed


# ─── phase summary for cards ──────────────────────────────────────────────────

def _phase_summary(device_data: dict) -> dict:
    out = {}

    pre = device_data.get("pre", {})
    t = s = f = 0
    for name, td in pre.items():
        if isinstance(td, list):
            if not td: continue
            st = ("ok"     if all(_norm_status(e.get("status","")) == "ok" for e in td) else
                  "failed" if any(_norm_status(e.get("status","")) == "failed" for e in td) else
                  _norm_status(td[0].get("status","not_started")))
        elif isinstance(td, dict):
            st = _norm_status(td.get("status",""))
        else:
            continue
        if st in ("","not_started"): continue
        t += 1
        if st == "ok": s += 1
        else: f += 1
    out["pre"] = (t, s, f)

    hops = device_data.get("upgrade", {}).get("hops", [])
    hok  = sum(1 for h in hops if _norm_status(h.get("status","")) == "ok")
    out["upgrade"] = (len(hops), hok, len(hops) - hok)

    post = device_data.get("post", {})
    pt = ps = pf = 0
    for name in ("connect", "show_version", "execute_show_commands"):
        td = post.get(name, {})
        if not td: continue
        st = _norm_status(td.get("status",""))
        if st in ("","not_started"): continue
        pt += 1
        if st == "ok": ps += 1
        else: pf += 1
    out["post"] = (pt, ps, pf)

    diff = device_data.get("diff", {})
    out["report"] = (len(diff), len(diff), 0) if diff else (0, 0, 0)
    return out


# ─── device panel ─────────────────────────────────────────────────────────────

def build_device_panel(device_key: str, device_data: dict, is_first: bool) -> str:
    tbody, total, success, failed = build_tbody(device_data, device_key)
    summary  = _phase_summary(device_data)
    prefix   = device_key.replace(".", "_").replace("-", "_")
    diff     = device_data.get("diff", {})
    diff_sec = _diff_section(diff, device_data, prefix)

    pill_cls = ("ok"     if failed == 0 and total > 0 else
                "fail"   if success == 0 and total > 0 else "partial")
    pill_txt = ("ALL PASSED"            if failed == 0 and total > 0 else
                f"{failed} FAILED"      if total > 0 else "NO TASKS")

    def phase_card(key):
        t, s, f = summary.get(key, (0, 0, 0))
        meta  = PHASE_META[key]
        pct   = round(s / t * 100) if t else 0
        stub  = key in ("report",)
        if stub:
            cls, inner = "partial", "—"
        else:
            cls   = "ok" if f == 0 and t > 0 else ("fail" if s == 0 and t > 0 else "partial")
            label = "Hops" if key == "upgrade" else "Tasks"
            inner = f"{s}/{t} {label}" if t > 0 else "—"
        return (f'<div class="ph-card">'
                f'<div class="ph-top">'
                f'<span class="ph-lbl" style="color:{meta["color"]};">{meta["label"]}</span>'
                f'<span class="pill {cls}" style="font-size:.58rem;">{inner}</span>'
                f'</div>'
                f'<div class="prog"><div class="progbar" style="width:{pct}%;background:{meta["color"]};"></div></div>'
                f'</div>')

    dk = _esc(device_key)
    return f"""<div class="device-panel" id="panel-{dk}" style="display:{'block' if is_first else 'none'};">

  <div class="dev-header">
    <div class="dev-left">
      <span class="dev-key">{dk}</span>
      <span class="pill {pill_cls}">{pill_txt}</span>
    </div>
    <div class="meta-ts" id="ts-{dk}"></div>
  </div>

  <div class="dev-info-row" id="info-{dk}">
    <div class="df"><span class="lbl">Host</span><span class="val" id="di-host-{dk}">—</span></div>
    <div class="df"><span class="lbl">Vendor</span><span class="val" id="di-vendor-{dk}">—</span></div>
    <div class="df"><span class="lbl">Model</span><span class="val" id="di-model-{dk}">—</span></div>
    <div class="df"><span class="lbl">Hostname</span><span class="val" id="di-hostname-{dk}">—</span></div>
    <div class="df"><span class="lbl">Version (Pre)</span><span class="val" id="di-pre-version-{dk}">—</span></div>
    <div class="df"><span class="lbl">Version (Post)</span><span class="val" id="di-post-version-{dk}" style="color:#86efac;">—</span></div>
  </div>

  <div class="ph-summary">
    {phase_card("pre")}
    {phase_card("upgrade")}
    {phase_card("post")}
    {phase_card("report")}
  </div>

  <div class="tw">
    <table>
      <colgroup><col class="ct"><col class="cs"><col class="cst"><col class="cr"></colgroup>
      <thead><tr><th>Phase</th><th>Task</th><th>Status</th><th>Remark</th></tr></thead>
      <tbody>
{tbody}
      </tbody>
    </table>
  </div>

{diff_sec}

</div>"""


# ─── overall stats ────────────────────────────────────────────────────────────

def _overall_stats(workflow_data: dict) -> tuple:
    total = success = failed = 0
    for dd in workflow_data.values():
        for name, td in dd.get("pre", {}).items():
            if isinstance(td, list):
                if not td: continue
                st = ("ok"     if all(_norm_status(e.get("status","")) == "ok" for e in td) else
                      "failed" if any(_norm_status(e.get("status","")) == "failed" for e in td) else
                      _norm_status(td[0].get("status","not_started")))
            elif isinstance(td, dict):
                st = _norm_status(td.get("status",""))
            else:
                continue
            if st in ("","not_started"): continue
            total += 1
            if st == "ok": success += 1
            else: failed += 1

        st = _norm_status(dd.get("upgrade",{}).get("status",""))
        if st not in ("","not_started"):
            total += 1
            if st == "ok": success += 1
            else: failed += 1

        for name in ("connect", "show_version", "execute_show_commands"):
            td = dd.get("post",{}).get(name, {})
            if not td: continue
            st = _norm_status(td.get("status",""))
            if st in ("","not_started"): continue
            total += 1
            if st == "ok": success += 1
            else: failed += 1

    return total, success, failed


def _device_info_json(workflow_data: dict) -> str:
    out = {}
    for dk, dd in workflow_data.items():
        pre_ver  = dd.get("pre",  {}).get("show_version", {}).get("version", "") or "—"
        post_ver = dd.get("post", {}).get("show_version", {}).get("version", "") or "—"
        out[dk] = {
            "host":         dd.get("device_info",{}).get("host","—") or "—",
            "vendor":       (dd.get("device_info",{}).get("vendor","—") or "—").upper(),
            "model":        (dd.get("device_info",{}).get("model","—") or "—").upper(),
            "hostname":     dd.get("device_info",{}).get("hostname","—") or "—",
            "pre_version":  pre_ver,
            "post_version": post_ver,
        }
    return json.dumps(out)


# ─── HTML generation ──────────────────────────────────────────────────────────

def generate_html_report(workflow_data: dict, output_dir: str = ".") -> str:
    safe_data = {
        dk: {k: v for k, v in slot.items() if k not in ("conn","yaml")}
        for dk, slot in workflow_data.items()
    }
    device_keys = list(safe_data.keys())
    now         = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ts_file     = datetime.now().strftime("%d_%m_%y_%H_%M_%S")
    total_all, success_all, failed_all = _overall_stats(safe_data)

    pill_cls = "ok" if failed_all == 0 else ("fail" if success_all == 0 else "partial")
    pill_txt = (f"ALL {total_all} TASKS PASSED" if failed_all == 0
                else f"{failed_all} TASK(S) FAILED")

    dropdown_opts = "\n".join(
        f'<option value="{_esc(dk)}"{" selected" if i==0 else ""}>'
        f'{_esc(dk)} — {_esc(safe_data[dk].get("device_info",{}).get("host","—"))}'
        f'</option>'
        for i, dk in enumerate(device_keys)
    )
    device_panels = "\n".join(
        build_device_panel(dk, safe_data[dk], i==0)
        for i, dk in enumerate(device_keys)
    )
    di_json   = _device_info_json(safe_data)
    json_html = _esc(json.dumps(safe_data, indent=2, default=str))
    first_key = _esc(device_keys[0]) if device_keys else ""

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
.wrap{{max-width:1160px;margin:0 auto}}
.hdr{{display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;
      margin-bottom:1.5rem;padding-bottom:1.25rem;border-bottom:1px solid var(--border)}}
.hdr h1{{font-size:1.35rem;font-weight:700;color:var(--text);letter-spacing:-.01em}}
.hdr h1 span{{color:var(--accent)}}
.hdr .sub{{font-family:var(--mono);font-size:.68rem;color:var(--muted2);margin-top:.3rem}}
.pill{{display:inline-block;padding:.2rem .65rem;border-radius:3px;font-family:var(--mono);
       font-size:.65rem;font-weight:600;letter-spacing:.05em;text-transform:uppercase;white-space:nowrap}}
.pill.ok{{background:rgba(34,197,94,.1);color:var(--ok);border:1px solid rgba(34,197,94,.2)}}
.pill.fail{{background:rgba(244,63,94,.1);color:var(--err);border:1px solid rgba(244,63,94,.2)}}
.pill.partial{{background:rgba(245,158,11,.1);color:var(--warn);border:1px solid rgba(245,158,11,.2)}}
.sel-bar{{display:flex;align-items:center;gap:.75rem;background:var(--surf);
          border:1px solid var(--border);border-radius:var(--r);padding:.75rem 1rem;margin-bottom:1.25rem}}
.sel-bar label{{font-size:.6rem;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);font-weight:600;white-space:nowrap}}
.dev-sel{{font-family:var(--mono);font-size:.78rem;background:var(--surf2);color:var(--accent);
          border:1px solid var(--border2);border-radius:4px;padding:.35rem .65rem;
          cursor:pointer;min-width:200px;outline:none}}
.dev-sel:focus{{border-color:var(--accent)}}
.dev-sel option{{background:var(--surf2);color:var(--text)}}
.dev-cnt{{font-family:var(--mono);font-size:.62rem;color:var(--muted);margin-left:auto}}
.device-panel{{animation:fadeIn .2s ease}}
@keyframes fadeIn{{from{{opacity:0;transform:translateY(4px)}}to{{opacity:1;transform:none}}}}
.dev-header{{display:flex;align-items:center;justify-content:space-between;
             margin-bottom:1rem;padding-bottom:.75rem;border-bottom:1px solid var(--border)}}
.dev-left{{display:flex;align-items:center;gap:.75rem;flex-wrap:wrap}}
.dev-key{{font-family:var(--mono);font-size:.95rem;font-weight:600;color:var(--text)}}
.meta-ts{{font-family:var(--mono);font-size:.62rem;color:var(--muted)}}
.dev-info-row{{display:flex;flex-wrap:wrap;gap:1.5rem;background:var(--surf);
               border:1px solid var(--border);border-radius:var(--r);padding:.9rem 1.1rem;margin-bottom:1rem}}
.df{{display:flex;flex-direction:column;gap:.2rem}}
.df .lbl{{font-size:.58rem;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);font-weight:600}}
.df .val{{font-family:var(--mono);font-size:.8rem;color:var(--accent)}}
.ph-summary{{display:grid;grid-template-columns:repeat(4,1fr);gap:.75rem;margin-bottom:1rem}}
.ph-card{{background:var(--surf);border:1px solid var(--border);border-radius:var(--r);padding:.8rem 1rem}}
.ph-top{{display:flex;align-items:center;justify-content:space-between;margin-bottom:.5rem}}
.ph-lbl{{font-size:.65rem;text-transform:uppercase;letter-spacing:.08em;font-weight:700;font-family:var(--mono)}}
.prog{{height:2px;background:var(--border);border-radius:99px;overflow:hidden}}
.progbar{{height:100%;border-radius:99px;transition:width .4s ease}}
.tw{{background:var(--surf);border:1px solid var(--border);border-radius:var(--r);overflow:hidden;margin-bottom:1rem}}
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
            font-family:var(--mono);writing-mode:vertical-lr;transform:rotate(180deg);display:inline-block}}
.subtask-cell{{word-break:break-word}}
.mono{{font-family:var(--mono);font-size:.75rem;color:#c8d3e8}}
.status-cell{{text-align:center;vertical-align:middle!important}}
.remark-cell{{font-family:var(--mono);font-size:.72rem!important;word-break:break-word}}
.remark-err{{color:#fca5a5}} .remark-na{{color:var(--border2)}} .remark-ok{{color:#86efac}}
.badge{{display:inline-block;padding:.15rem .5rem;border-radius:3px;font-size:.6rem;font-weight:600;
        letter-spacing:.05em;font-family:var(--mono);white-space:nowrap;text-transform:uppercase}}
.b-ok{{background:rgba(34,197,94,.1);color:var(--ok);border:1px solid rgba(34,197,94,.2)}}
.b-fail{{background:rgba(244,63,94,.1);color:var(--err);border:1px solid rgba(244,63,94,.2)}}
.b-ns{{background:transparent;color:var(--muted);border:1px solid var(--border)}}
.b-warn{{background:rgba(245,158,11,.1);color:var(--warn);border:1px solid rgba(245,158,11,.2)}}
.b-ip{{background:rgba(56,189,248,.1);color:var(--accent);border:1px solid rgba(56,189,248,.2)}}
.mini-btn{{display:inline-block;margin:.2rem .15rem 0 0;padding:.1rem .42rem;
           background:rgba(56,189,248,.06);border:1px solid rgba(56,189,248,.18);
           border-radius:3px;font-family:var(--mono);font-size:.58rem;font-weight:600;
           color:var(--accent);cursor:pointer;letter-spacing:.04em;transition:all .12s}}
.mini-btn:hover{{background:rgba(56,189,248,.14);border-color:rgba(56,189,248,.38)}}
.mini-btn.mini-err{{background:rgba(244,63,94,.06);border-color:rgba(244,63,94,.22);color:var(--err)}}
.mini-btn.mini-err:hover{{background:rgba(244,63,94,.14)}}
.log-box{{margin-top:.4rem;background:#060810;border:1px solid var(--border2);
          border-radius:4px;padding:.5rem .7rem;overflow-x:auto}}
.log-box pre{{font-family:var(--mono);font-size:.66rem;line-height:1.8;color:#7dd3fc;white-space:pre-wrap;word-break:break-all}}
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

/* ── hops table ────────────────────────────────────────────────── */
.hop-table-wrap{{overflow-x:auto;width:100%;border-radius:4px}}
.hop-table{{border-collapse:collapse;font-size:.75rem;margin-top:.4rem;
            min-width:780px;table-layout:auto;width:100%}}
.hop-table th{{padding:.4rem .9rem;font-size:.58rem;text-transform:uppercase;letter-spacing:.08em;
               color:var(--muted);font-weight:600;background:var(--surf3);
               border-bottom:1px solid var(--border);text-align:left;white-space:nowrap}}
.hop-table td{{padding:.45rem .9rem;border-bottom:1px solid var(--border);
               font-family:var(--mono);font-size:.72rem;white-space:nowrap}}
.hop-num-cell{{width:2.5rem;text-align:center}}
.hop-image-cell{{min-width:320px;white-space:nowrap;word-break:keep-all}}
.hop-status-cell{{width:7rem;text-align:center}}
.hop-remark-cell{{min-width:200px;white-space:normal;word-break:break-word}}

.diff-none{{font-family:var(--mono);font-size:.72rem;color:var(--muted);padding:.4rem 0;font-style:italic}}

/* ════════════════════════════════════════════════════════════════
   FULL-WIDTH DIFF SECTION (below the main table)
   ════════════════════════════════════════════════════════════════ */
.diff-section{{
  display:flex;
  flex-direction:column;
  gap:.75rem;
  margin-bottom:1.5rem;
}}

.diff-block{{
  background:var(--surf);
  border:1px solid var(--border2);
  border-radius:var(--r);
  overflow:visible;
  animation:fadeIn .18s ease;
}}

.diff-block-hdr{{
  display:flex;
  align-items:center;
  justify-content:space-between;
  padding:.6rem 1rem;
  background:var(--surf3);
  border-bottom:1px solid var(--border);
  gap:1rem;
}}

.diff-block-cmd{{
  display:flex;
  align-items:center;
  gap:.6rem;
  min-width:0;
  flex:1;
}}

.diff-block-label{{
  font-family:var(--mono);
  font-size:.55rem;
  font-weight:700;
  text-transform:uppercase;
  letter-spacing:.1em;
  color:var(--warn);
  background:rgba(245,158,11,.08);
  border:1px solid rgba(245,158,11,.2);
  border-radius:3px;
  padding:.1rem .35rem;
  flex-shrink:0;
}}

.diff-block-cmdname{{
  font-family:var(--mono);
  font-size:.78rem;
  color:#c8d3e8;
  word-break:break-all;
}}

/* Side-by-side diff grid — full width, equal halves */
.diff-grid{{
  display:grid;
  grid-template-columns:1fr 1fr;
  grid-template-rows:auto 1fr;
}}

.diff-col-hdr{{
  padding:.4rem 1rem;
  font-family:var(--mono);
  font-size:.6rem;
  text-transform:uppercase;
  letter-spacing:.08em;
  color:var(--muted);
  font-weight:600;
  background:var(--surf2);
  border-bottom:1px solid var(--border);
}}
.diff-col-hdr:first-of-type{{
  border-right:1px solid var(--border);
}}

.diff-pane{{
  background:#060810;
  padding:.75rem 1.1rem;
  overflow:hidden;
  max-height:520px;
  overflow-y:auto;
}}
.diff-pane:first-of-type{{
  border-right:1px solid var(--border2);
}}

.diff-pane pre{{
  font-family:var(--mono);
  font-size:.62rem;
  line-height:1.85;
  color:#8896aa;
  white-space:pre-wrap;
  word-break:break-all;
  overflow-wrap:break-word;
  tab-size:4;
}}

/* Diff line styles */
.diff-eq{{color:#8896aa}}
.diff-line-del{{
  display:block;
  background:rgba(244,63,94,.10);
  border-left:3px solid rgba(244,63,94,.55);
  padding-left:6px;
  margin-left:-6px;
  color:#fca5a5;
}}
.diff-line-ins{{
  display:block;
  background:rgba(34,197,94,.08);
  border-left:3px solid rgba(34,197,94,.45);
  padding-left:6px;
  margin-left:-6px;
  color:#86efac;
}}
.diff-na{{
  display:block;
  color:var(--muted);
  font-style:italic;
  opacity:.45;
}}
mark.diff-del{{
  background:rgba(244,63,94,.38);
  color:#fca5a5;
  border-radius:2px;
  padding:0 2px;
}}
mark.diff-ins{{
  background:rgba(34,197,94,.28);
  color:#86efac;
  border-radius:2px;
  padding:0 2px;
}}

/* ═══════════════════════════════════════════════════════════════ */

.json-sec{{margin-top:1.5rem}}
.json-sec summary{{cursor:pointer;font-family:var(--mono);font-size:.68rem;font-weight:600;
                   text-transform:uppercase;letter-spacing:.08em;color:var(--muted);
                   padding:.4rem 0;transition:color .12s;list-style:none}}
.json-sec[open] summary,.json-sec summary:hover{{color:var(--accent)}}
.json-sec summary::-webkit-details-marker{{display:none}}
pre.jb{{margin-top:.6rem;background:var(--surf);border:1px solid var(--border);border-radius:var(--r);
        padding:1rem 1.2rem;font-family:var(--mono);font-size:.68rem;line-height:1.75;
        color:#8896aa;overflow-x:auto;white-space:pre}}
.ft{{margin-top:2.5rem;padding-top:.75rem;border-top:1px solid var(--border);
     font-size:.62rem;color:var(--muted);font-family:var(--mono);text-align:center}}
@media(max-width:600px){{
  .ph-summary{{grid-template-columns:repeat(2,1fr)}}
  .hdr{{flex-direction:column}}
  .sel-bar{{flex-direction:column;align-items:flex-start}}
  .dev-sel{{width:100%}}
  .diff-grid{{grid-template-columns:1fr}}
  .diff-col-hdr:first-of-type,.diff-pane:first-of-type{{border-right:none;border-bottom:1px solid var(--border)}}
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
  <summary>&#9654; Raw JSON (all devices)</summary>
  <pre class="jb">{json_html}</pre>
</details>

<footer class="ft">workflow_report_generator.py &nbsp;·&nbsp; {now}</footer>
</div>

<script>
var DI = {di_json};
function updateInfo(key) {{
  var d = DI[key]; if (!d) return;
  var set = function(id,v){{ var el=document.getElementById(id); if(el) el.textContent=v||'—'; }};
  set('di-host-'+key,         d.host);
  set('di-vendor-'+key,       d.vendor);
  set('di-model-'+key,        d.model);
  set('di-hostname-'+key,     d.hostname);
  set('di-pre-version-'+key,  d.pre_version);
  set('di-post-version-'+key, d.post_version);
}}
function selectDevice(key) {{
  document.querySelectorAll('.device-panel').forEach(function(p){{p.style.display='none';}});
  var p=document.getElementById('panel-'+key);
  if(p) p.style.display='block';
  updateInfo(key);
}}
function tgl(id) {{
  var el=document.getElementById(id);
  if(el) el.hidden=!el.hidden;
}}
function tglDiff(id) {{
  var el=document.getElementById(id);
  if(!el) return;
  var wasHidden = el.hidden;
  el.hidden = !wasHidden;
  if(!el.hidden) {{
    setTimeout(function(){{ el.scrollIntoView({{behavior:'smooth',block:'nearest'}}); }}, 50);
  }}
}}
document.addEventListener('DOMContentLoaded',function(){{
  updateInfo('{first_key}');
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

if __name__ == "__main__":
    import sys
    from pathlib import Path

    if len(sys.argv) > 1:
        json_path = Path(sys.argv[1])
        if not json_path.exists():
            print(f"ERROR: File not found: {json_path}")
            sys.exit(1)

        with open(json_path, encoding="utf-8") as f:
            raw = json.load(f)

        first_val = next(iter(raw.values()), None)
        if isinstance(first_val, dict) and any(k in first_val for k in ("pre", "upgrade", "post")):
            workflow_data = raw
        else:
            workflow_data = {json_path.stem: raw}

        path = generate_html_report(workflow_data, output_dir=".")
        print(f"Report written: {path}")

    else:
        path = generate_html_report(sample, output_dir=".")
        print(f"Report written: {path}")
import sys
import json
import logging

from lib.utilities import *

# ─────────────────────────────────────────────────────────────
# Module logger
# ─────────────────────────────────────────────────────────────
logger = logging.getLogger("run_checks")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | run_checks | %(message)s",
        datefmt="%H:%M:%S"
    ))
    logger.addHandler(h)
    logger.propagate = False

# ─────────────────────────────────────────────────────────────
# Build parser registries once at import time
# ─────────────────────────────────────────────────────────────
JUNIPER_REGISTRY = build_registries()

VENDOR_REGISTRY = {
    "juniper": JUNIPER_REGISTRY,
}


# ═════════════════════════════════════════════════════════════
# STEP 1 — Collect outputs
# ═════════════════════════════════════════════════════════════
def collect_device_output(device_key, vendor, commands, check_type, conn, log):
    """Send each command to the live device via SSH conn. Returns raw entries list."""
    print(f"[{device_key}] [{check_type.upper()}] LIVE collection — {len(commands)} command(s)")
    entries = []
    for cmd in commands:
        print(f"[{device_key}] Sending: '{cmd}'")
        try:
            output  = conn.send_command(cmd)
            preview = output.strip().splitlines()[0][:80] if output.strip() else "<empty>"
            log.debug(f"[{device_key}] '{cmd}' preview: {preview}")
            print(f"[{device_key}] ✓ '{cmd}' — {len(output)} chars received")
            entries.append({"command": cmd, "output": output, "json_output": {}})
        except Exception as e:
            print(f"[{device_key}] ✗ '{cmd}' failed: {e}")
            entries.append({"command": cmd, "output": "", "json_output": {"error": str(e)}})
    print(f"[{device_key}] Live collection done — {len(entries)} entries")
    return entries


# ═════════════════════════════════════════════════════════════
# STEP 2 — Store raw entries in global_config.device_results
# ═════════════════════════════════════════════════════════════
def persist_raw_output(device_key, check_type, entries, log):
    if device_key not in global_config.device_results:
        global_config.device_results[device_key] = {}
        log.debug(f"[{device_key}] Created new device slot in global_config.device_results")
    global_config.device_results[device_key][check_type] = entries
    print(f"[{device_key}] Stored {len(entries)} raw entries → device_results[{device_key}][{check_type}]")


# ═════════════════════════════════════════════════════════════
# STEP 3 — Run parsers over stored entries
# ═════════════════════════════════════════════════════════════
def execute_parsers(device_key, vendor, check_type, log):
    """
    Look up each command in VENDOR_REGISTRY[(vendor, cmd)],
    run the parser, write result back into entry["json_output"].
    Returns True only if ALL parsers ran without error.
    """
    registry = VENDOR_REGISTRY.get(vendor)
    if registry is None:
        print(f"[{device_key}] No registry for vendor='{vendor}' — supported: {list(VENDOR_REGISTRY.keys())}")
        return False

    entries = global_config.device_results.get(device_key, {}).get(check_type, [])
    if not entries:
        log.warning(f"[{device_key}] Nothing in device_results[{device_key}][{check_type}] to parse")
        return False

    print(f"[{device_key}] [{check_type.upper()}] Running parsers over {len(entries)} entry(ies)")
    all_ok = True

    for entry in entries:
        cmd    = entry["command"]
        output = entry["output"]

        if not output:
            log.warning(f"[{device_key}] '{cmd}' — output empty, skipping parser")
            continue

        parser_fn = registry.get((vendor, cmd))
        if parser_fn is None:
            log.warning(f"[{device_key}] No parser registered for ('{vendor}', '{cmd}') — skipping")
            continue

        print(f"[{device_key}] Running {parser_fn.__name__}() for '{cmd}'")
        try:
            result = parser_fn(output)
            entry["json_output"] = result
            keys = list(result.keys()) if isinstance(result, dict) else type(result).__name__
            print(f"[{device_key}] ✅ '{cmd}' parsed OK — result keys: {keys}")
        except Exception as e:
            print(f"[{device_key}] ❌ {parser_fn.__name__}() failed for '{cmd}': {e}")
            entry["json_output"] = {"error": str(e)}
            all_ok = False

    verdict = "all parsers OK" if all_ok else "one or more parsers FAILED"
    print(f"[{device_key}] [{check_type.upper()}] Parser run complete — {verdict}")
    return all_ok


# ═════════════════════════════════════════════════════════════
# STEP 4 — Push results into workflow_tracker
# ═════════════════════════════════════════════════════════════
def publish_results_to_tracker(device_key, check_type, entries, parse_ok, log):
    """
    Convert entries to tracker format and write to workflow_tracker commands.
    Then log the two tracker tasks: 'executing show commands' and 'Parsing the data'.
    """
    phase = "pre-checks" if check_type == "pre" else "post-checks"

    tracker_entries = [
        {"cmd": e["command"], "output": e["output"], "json": e["json_output"]}
        for e in entries
    ]
    set_commands(device_key, phase, tracker_entries)
    print(f"[{device_key}] [{check_type.upper()}] Pushed {len(tracker_entries)} entries to tracker commands")

    # Log 'executing show commands'
    cmd_ok     = "Success" if any(e["output"] for e in entries) else "Failed"
    cmd_detail = f"{len(entries)} command(s) collected"
    log_task(device_key, phase, "executing show commands", cmd_ok, cmd_detail,
            log_line=f"Collected {len(entries)} outputs [{check_type.upper()}]")
    print(f"[{device_key}] Logged 'executing show commands' → {cmd_ok}")

    # Log 'Parsing the data'
    parse_status = "Success" if parse_ok else "Failed"
    parse_detail = "All parsers OK" if parse_ok else "One or more parsers failed"
    log_task(device_key, phase, "Parsing the data", parse_status, parse_detail,
            log_line=f"Parser run — {parse_detail}")
    print(f"[{device_key}] Logged 'Parsing the data' → {parse_status}")


# ═════════════════════════════════════════════════════════════
# PUBLIC API — called from prechecks.py / main.py
# ═════════════════════════════════════════════════════════════
def dispatch_command_pipeline(device_key, vendor, commands, check_type,
                              conn, logger=None):
    """
    Main entry point.

    Args:
        device_key : e.g. 'juniper_mx204'
        vendor     : e.g. 'juniper'
        commands   : list of CLI command strings
        check_type : 'pre' | 'post'
        conn       : live Netmiko connection (required)
        logger     : caller's logger; falls back to module logger

    Returns:
        True  — collection + all parsers succeeded
        False — collection failed or one/more parsers failed
    """
    log = logger or globals()["logger"]

    print(f"[{device_key}] ── dispatch_command_pipeline START ─────────────────────────")
    print(f"[{device_key}] vendor={vendor}  check_type={check_type}  mode=LIVE")
    print(f"[{device_key}] Commands ({len(commands)}): {commands}")

    # Step 1 — collect
    if not commands:
        print(f"[{device_key}] No commands provided — aborting dispatch_command_pipeline")
        return False

    entries = collect_device_output(device_key, vendor, commands, check_type, conn, log)

    if not entries:
        print(f"[{device_key}] Collection returned no entries — aborting")
        return False

    # Step 2 — store raw
    persist_raw_output(device_key, check_type, entries, log)

    # Step 3 — parse
    parse_ok = execute_parsers(device_key, vendor, check_type, log)

    # Step 4 — push to tracker
    publish_results_to_tracker(device_key, check_type, entries, parse_ok, log)

    print(f"[{device_key}] ── dispatch_command_pipeline END — parse_ok={parse_ok} ─────")
    return parse_ok


# ═════════════════════════════════════════════════════════════
# SIMPLE WRAPPER — called from main.py as execute_commands("pre", conn)
# Reads device_key / vendor / commands from global_config
# (set by main.py before calling this)
# ═════════════════════════════════════════════════════════════
def execute_commands(check_type: str, conn, logger=None):
    """
    Thin wrapper around dispatch_command_pipeline.
    Reads device_key, vendor, and commands from global_config
    so main.py only needs one line: execute_commands("pre", conn)

    global_config must have set before calling:
        global_config.device_key  — e.g. "juniper_mx204"
        global_config.vendor      — e.g. "juniper"
        global_config.commands    — list of CLI command strings
    """
    return dispatch_command_pipeline(
        device_key = global_config.device_key,
        vendor     = global_config.vendor,
        commands   = global_config.commands,
        check_type = check_type,
        conn       = conn,
        logger     = logger,
    )
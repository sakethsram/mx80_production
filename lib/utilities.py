import logging
import sys
import os
import re
import yaml
import json
from datetime import datetime
from netmiko import ConnectHandler
from netmiko.exceptions import (
    NetmikoTimeoutException,
    NetmikoAuthenticationException
)
from paramiko.ssh_exception import SSHException
from parsers.juniper.juniper_mx204 import *

# ─────────────────────────────────────────────────────────────
# GlobalConfig
# ─────────────────────────────────────────────────────────────

class GlobalConfig:
    device_results: dict = {}
    pre_check_timestamp = ""
    vendor = ""
    model = ""
    session_log_path = ""
    device_key = ""
    commands: list = []

global_config = GlobalConfig()

# ─────────────────────────────────────────────────────────────
# Global threshold — outputs <= this length are treated as empty
# ─────────────────────────────────────────────────────────────
MIN_OUTPUT_CHARS = 5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# workflow_tracker
# ─────────────────────────────────────────────────────────────
workflow_tracker = {}


def init_device_tracker(device_key: str, host: str, vendor: str, model: str):
    workflow_tracker[device_key] = {
        "device_info": {
            "host": host, "vendor": vendor, "model": model,
            "timestamp": datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
        },
        "pre-checks": {
            "tasks": {
                "read Yaml":                     {"status": "", "error": "", "title": "Load device config from YAML",          "logs": ""},
                "start logger":                  {"status": "", "error": "", "title": "Initialise log file for session",       "logs": ""},
                "connection using credentials":  {"status": "", "error": "", "title": "Establish SSH session to device",       "logs": ""},
                "show version":                  {"status": "", "error": "", "title": "Run show version",                      "logs": ""},
                "executing show commands":       {"status": "", "error": "", "title": "Collect pre-check show command output", "logs": ""},
                "Parsing the data":              {"status": "", "error": "", "title": "Parse and validate pre-check output",   "logs": ""},
                "Backup Config":                 {"status": "", "error": "", "title": "Save running config and device logs",   "logs": ""},
                "Validate MD5 checksum":         {"status": "", "error": "", "title": "Verify image integrity via MD5",        "logs": ""},
                "Storage Check (5GB threshold)": {"status": "", "error": "", "title": "Confirm sufficient disk space",         "logs": ""},
                "Disable Filter":                {"status": "", "error": "", "title": "Remove RE protection firewall filter",  "logs": ""},
            },
            "commands": []
        },
        "upgrade": {
            "tasks": {
                "image installation": {"status": "", "error": "", "title": "Install target OS image on device",       "logs": ""},
                "reboot the device":  {"status": "", "error": "", "title": "Reboot and confirm device comes up",      "logs": ""},
                "ping the device":    {"status": "", "error": "", "title": "Verify device reachability after upgrade", "logs": ""},
            }
        },
        "post-checks": {
            "tasks": {
                "Take snapshot":            {"status": "", "error": "", "title": "Snapshot primary disk to backup disk",     "logs": ""},
                "Execute show commands":    {"status": "", "error": "", "title": "Collect post-upgrade show command output", "logs": ""},
                "parsing the commands":     {"status": "", "error": "", "title": "Parse and validate post-upgrade output",   "logs": ""},
                "Enable RE-PROTECT filter": {"status": "", "error": "", "title": "Re-apply RE protection firewall filter",   "logs": ""},
            },
            "commands": []
        }
    }
    logger.info(f"[tracker] Initialised slot for device_key='{device_key}'")


def log_task(device_key: str, phase: str, task_name: str, status: str,
             error: str = "", log_line: str = ""):
    device = workflow_tracker.get(device_key)
    if device is None:
        logger.warning(f"[log_task] device_key='{device_key}' not in workflow_tracker")
        return
    phase_data = device.get(phase)
    if phase_data is None:
        logger.warning(f"[log_task] phase='{phase}' not found for '{device_key}'")
        return
    tasks = phase_data.get("tasks", {})
    if task_name not in tasks:
        logger.warning(f"[log_task] task='{task_name}' not found under [{device_key}][{phase}]['tasks']")
        return
    tasks[task_name]["status"] = status
    if error:
        tasks[task_name]["error"] = error
    if log_line:
        existing = tasks[task_name].get("logs", "") or ""
        tasks[task_name]["logs"] = (existing + "\n" + log_line).lstrip("\n")
    logger.info(f"[tracker] {device_key} | {phase} | {task_name} -> {status}")


def set_commands(device_key: str, phase: str, entries: list):
    device = workflow_tracker.get(device_key)
    if not device:
        logger.warning(f"[set_commands] device_key='{device_key}' not in tracker")
        return
    phase_data = device.get(phase)
    if not phase_data:
        logger.warning(f"[set_commands] phase='{phase}' not found for '{device_key}'")
        return
    phase_data["commands"] = entries
    logger.info(f"[tracker] Stored {len(entries)} command entries -> [{device_key}][{phase}]['commands']")


def get_pre_results(device_key: str) -> list:
    return global_config.device_results.get(device_key, {}).get("pre", [])


# ─────────────────────────────────────────────────────────────
# normalise — canonical command string for registry lookups
#
# Rules:
#   1. Strip leading/trailing whitespace
#   2. Collapse all internal whitespace runs to a single space
#   3. Ensure exactly one space on each side of every pipe "|"
#
# Examples:
#   "show rsvp session | match DN |no-more"   → "show rsvp session | match DN | no-more"
#   "show vmhost version |no-more"             → "show vmhost version | no-more"
# ─────────────────────────────────────────────────────────────

def normalise(cmd: str) -> str:
    cmd = re.sub(r'\s+', ' ', cmd.strip())
    cmd = re.sub(r'\s*\|\s*', ' | ', cmd)
    return cmd


# ─────────────────────────────────────────────────────────────
# build_registries — all keys normalised at build time
# ─────────────────────────────────────────────────────────────

def build_registries():
    raw = {
        ("juniper", "show arp no-resolve | no-more"):                                                  parse_show_arp_no_resolve,
        ("juniper", "show vrrp summary | no-more"):                                                    parse_show_vrrp_summary,
        ("juniper", "show lldp neighbors | no-more"):                                                  parse_show_lldp_neighbors,
        ("juniper", "show bfd session | no-more"):                                                     parse_show_bfd_session,
        ("juniper", "show rsvp neighbor | no-more"):                                                   parse_show_rsvp_neighbor,
        ("juniper", "show rsvp session | no-more"):                                                    parse_show_rsvp_session,
        ("juniper", "show route table inet.0 | no-more"):                                              parse_show_route_table_inet0,
        ("juniper", "show route table inet.3 | no-more"):                                              parse_show_route_table_inet3,
        ("juniper", "show route table mpls.0 | no-more"):                                              parse_show_route_table_mpls0,
        ("juniper", "show mpls interface | no-more"):                                                  parse_show_mpls_interface,
        ("juniper", "show mpls lsp | no-more"):                                                        parse_show_mpls_lsp,
        ("juniper", "show mpls lsp p2mp | no-more"):                                                   parse_show_mpls_lsp_p2mp,
        ("juniper", "show bgp summary | no-more"):                                                     parse_show_bgp_summary,
        ("juniper", "show bgp neighbor | no-more"):                                                    parse_show_bgp_neighbor,
        ("juniper", "show isis adjacency extensive | no-more"):                                        parse_show_isis_adjacency_extensive,
        ("juniper", "show route summary | no-more"):                                                   parse_show_route_summary,
        ("juniper", "show rsvp session match DN | no-more"):                                           parse_show_rsvp_session_match_DN,
        ("juniper", "show mpls lsp unidirectional match DN | no-more"):                                parse_show_mpls_lsp_unidirectional_match_DN,
        ("juniper", "show rsvp | no-more"):                                                            parse_show_rsvp,
        ("juniper", "show mpls lsp unidirectional | no-more"):                                         parse_show_mpls_lsp_unidirectional_no_more,
        ("juniper", "show system uptime | no-more"):                                                   parse_21_show_system_uptime,
        ("juniper", "show ntp associations no-resolve | no-more"):                                     parse_22_show_ntp_associations,
        ("juniper", "show vmhost version | no-more"):                                                  parse_23_show_vmhost_version,
        ("juniper", "show vmhost snapshot | no-more"):                                                 parse_24_show_vmhost_snapshot,
        ("juniper", "show chassis hardware | no-more"):                                                parse_25_show_chassis_hardware,
        ("juniper", "show chassis fpc detail | no-more"):                                              parse_26_show_chassis_fpc_detail,
        ("juniper", "show chassis alarms | no-more"):                                                  parse_27_show_chassis_alarms,
        ("juniper", "show system alarms | no-more"):                                                   parse_28_show_system_alarms,
        ("juniper", "show chassis routing-engine | no-more"):                                          parse_29_show_chassis_routing_engine,
        ("juniper", "show chassis environment | no-more"):                                             parse_30_show_chassis_environment,
        ("juniper", "show system resource-monitor fpc | no-more"):                                     parse_31_show_system_resource_monitor_fpc,
        ("juniper", "show krt table | no-more"):                                                       parse_32_show_krt_table,
        ("juniper", "show system processes | no-more"):                                                parse_33_show_system_processes,
        ("juniper", "show interface descriptions | no-more"):                                          parse_34_show_interface_descriptions,
        ("juniper", "show oam ethernet connectivity-fault-management interfaces extensive | no-more"): parse_35_show_oam_cfm_interfaces,
        ("juniper", "show ldp neighbor | no-more"):                                                    parse_36_show_ldp_neighbor,
        ("juniper", "show connections | no-more"):                                                     parse_37_show_connections,
    }
    # Normalise every key at build time
    return {
        (vendor, normalise(cmd)): fn
        for (vendor, cmd), fn in raw.items()
    }


# ─────────────────────────────────────────────────────────────
# VENDOR_REGISTRY  — built once at module load
# ─────────────────────────────────────────────────────────────
VENDOR_REGISTRY = {
    "juniper": build_registries(),
}


# ═════════════════════════════════════════════════════════════
# PIPELINE STEP 1 — collect_outputs
#
# For each command in the list:
#   - Send command to device via conn.send_command()
#   - collected = True  only when len(output.strip()) > MIN_OUTPUT_CHARS
#   - Store entry: { cmd, output, json_output, exception }
#     exception = actual traceback if send_command raised, else ""
#
# Returns: list of entry dicts
# ═════════════════════════════════════════════════════════════

def collect_outputs(device_key: str, vendor: str, commands: list,
                    check_type: str, conn, log) -> list:

    phase = "pre-checks" if check_type == "pre" else "post-checks"

    log.info(f"[{device_key}] STEP 1 collect_outputs — "
             f"{len(commands)} command(s), phase={phase}, "
             f"MIN_OUTPUT_CHARS={MIN_OUTPUT_CHARS}")

    if device_key not in global_config.device_results:
        global_config.device_results[device_key] = {}

    entries = []

    for cmd in commands:
        log.info(f"[{device_key}] Sending: '{cmd}'")
        exception_str = ""
        output        = ""

        try:
            output = conn.send_command(cmd)
            log.debug(f"[{device_key}] '{cmd}' — {len(output)} chars received")

        except Exception:
            import traceback as tb
            exception_str = tb.format_exc()          # actual traceback string
            log.error(f"[{device_key}] '{cmd}' send_command raised:\n{exception_str}")

        stripped  = output.strip() if output else ""
        collected = len(stripped) > MIN_OUTPUT_CHARS

        entry = {
            "cmd":       cmd,
            "output":    output,
            "json":      {},
            "exception": f"send_command failed for '{cmd}'" if exception_str else "",
               }
        entries.append(entry)

        log.info(f"[{device_key}] '{cmd}' collected={collected} "
                 f"({len(stripped)} chars)")

    global_config.device_results[device_key][check_type] = entries

    log.info(f"[{device_key}] STEP 1 done — {len(entries)} entries stored")
    return entries


# ═════════════════════════════════════════════════════════════
# PIPELINE STEP 2 — parse_outputs
#
# Traverses the entries list built by collect_outputs.
# For each entry, nested-if logic determines what to do:
#
#   Level 1 — is a parser registered for this command?
#       NO  → exception = "no parser registered"
#             json stays {}
#             continue (collect-only, not a failure)
#
#       YES → Level 2 — is output > MIN_OUTPUT_CHARS?
#                 NO  → exception = "output too short (N chars)"
#                       json stays {}
#                       continue (skip silently, not a failure)
#
#                 YES → Level 3 — call the parser function
#                           RAISES   → exception = actual traceback string
#                                      json stays {}
#                                      continue (log, keep going)
#
#                           RETURNS empty → exception = "parser returned empty result"
#                                           json stays {}
#                                           continue
#
#                           RETURNS data  → json = result
#                                           exception = ""
#
# json populated  → exception = ""
# json empty      → exception = reason string (see levels above)
#
# Returns True only if every parser-registered, output-present command succeeded.
# Individual failures do NOT abort the run.
# ═════════════════════════════════════════════════════════════

def parse_outputs(device_key: str, vendor: str, check_type: str, log) -> bool:

    phase = "pre-checks" if check_type == "pre" else "post-checks"

    registry = VENDOR_REGISTRY.get(vendor)
    if registry is None:
        log.error(f"[{device_key}] STEP 2 — No registry for vendor='{vendor}'")
        return False

    entries = global_config.device_results.get(device_key, {}).get(check_type, [])
    if not entries:
        log.warning(f"[{device_key}] STEP 2 — Nothing in device_results to parse")
        return False

    log.info(f"[{device_key}] STEP 2 parse_outputs — "
             f"{len(entries)} entry(ies), vendor={vendor}")

    all_ok = True

    for entry in entries:
        cmd      = entry["cmd"]
        output   = entry["output"]
        norm_cmd = normalise(cmd)

        # ── LEVEL 1: is a parser registered? ─────────────────────────
        parser_fn = registry.get((vendor, norm_cmd))

        if parser_fn is None:
            # No parser → collect-only command, not a failure

            entry["exception"] = "no parser registered"
            log.debug(f"[{device_key}] '{cmd}' — no parser registered, collect-only")
            continue

        # ── LEVEL 2: is output long enough to parse? ─────────────────
        stripped = output.strip() if output else ""

        if len(stripped) <= MIN_OUTPUT_CHARS:
            # Parser exists but nothing useful came back — skip silently

            entry["exception"] = f"output too short )"
            log.info(f"[{device_key}] '{cmd}' — output too short ")
            continue

        # ── LEVEL 3: call the parser ──────────────────────────────────
        log.info(f"[{device_key}] Running {parser_fn.__name__}() for '{cmd}'")

        try:
            result = parser_fn(output)

            if not result or all(not v for v in result.values()):
                # Parser ran without raising but returned nothing useful

                entry["exception"] = "parser returned empty result"
                all_ok = False
                log.warning(f"[{device_key}] {parser_fn.__name__}() returned "
                             f"empty result for '{cmd}'")
                continue

            # ── SUCCESS ──────────────────────────────────────────────
            entry["json"]=result
            entry["exception"] = ""
            log.info(
                f"[{device_key}] '{cmd}' parsed OK — "
                f"keys: {list(result.keys()) if isinstance(result, dict) else type(result).__name__}"
            )

        except Exception as e :
            entry["exception"] = f"parser failed for '{cmd}'"
            all_ok = False
            log.error(f"[{device_key}] {parser_fn.__name__}() FAILED for '{cmd}': {e}")
            continue

    verdict = "all parsers OK" if all_ok else "one or more parsers FAILED (continued)"
    log.info(f"[{device_key}] STEP 2 done — {verdict}")
    return all_ok


# ═════════════════════════════════════════════════════════════
# PIPELINE STEP 3 — push_to_tracker
#
# Entries from collect_outputs are already in tracker format:
#   { "cmd", "output", "json", "exception" }
# Just calls set_commands() to write them into workflow_tracker.
# ═════════════════════════════════════════════════════════════

def push_to_tracker(device_key: str, check_type: str, entries: list,
                    parse_ok: bool, log) -> None:

    phase = "pre-checks" if check_type == "pre" else "post-checks"

    # Read from device_results — parse_outputs mutates entries in-place there.
    # This guarantees json and exception fields are fully populated before storing.
    final_entries = global_config.device_results.get(device_key, {}).get(check_type, entries)

    set_commands(device_key, phase, final_entries)

    parsed_count  = sum(1 for e in final_entries if e["json"])
    skipped_count = sum(1 for e in final_entries if not e["json"])

    log.info(
        f"[{device_key}] STEP 3 push_to_tracker — "
        f"{len(entries)} total -> [{device_key}][{phase}]['commands'] | "
        f"parsed={parsed_count}, skipped/collect-only={skipped_count}, "
        f"parse_ok={parse_ok}"
    )


# ─────────────────────────────────────────────────────────────
# setup_logger
# ─────────────────────────────────────────────────────────────

def setup_logger(name):
    log_dir = os.path.join(os.getcwd(), "logging")
    os.makedirs(log_dir, exist_ok=True)
    log_file = f"{global_config.vendor}_{global_config.model}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
    log_path = os.path.join(log_dir, log_file)
    file_logger = logging.getLogger(f"{global_config.vendor}_{global_config.model}")
    file_logger.setLevel(logging.DEBUG)
    file_logger.propagate = False
    handler = logging.FileHandler(log_path)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s",
                                  datefmt="%Y-%m-%d_%H:%M:%S")
    handler.setFormatter(formatter)
    file_logger.addHandler(handler)
    return file_logger


# ─────────────────────────────────────────────────────────────
# write_json
# ─────────────────────────────────────────────────────────────

def write_json(command_name, vendor, model, json_data):
    if not all([command_name, vendor, model]):
        logger.error("Command name, vendor, and model cannot be empty")
        raise ValueError("Invalid Parameters")
    try:
        logger.info("Writing to pre_checks JSON file ...")
        curr_dir   = os.getcwd()
        output_dir = os.path.join(curr_dir, "pre_checks")
        os.makedirs(output_dir, exist_ok=True)
        filename  = f"{vendor}_{model}_{global_config.pre_check_timestamp}.json"
        file_path = os.path.join(output_dir, filename)
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                data = json.load(f)
        else:
            data = {
                "metadata": {
                    "timestamp": global_config.pre_check_timestamp,
                    "vendor":    vendor,
                    "model":     model,
                },
                "commands": {}
            }
        data["commands"][command_name] = json_data
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"JSON file written successfully: {file_path}")
        return data
    except Exception as e:
        logger.error(f"Unexpected error while writing JSON: {e}")
        raise


# ─────────────────────────────────────────────────────────────
# login_device
# ─────────────────────────────────────────────────────────────

def login_device(host, username, password, device_type, session_log_path, logger):
    try:
        logger.info(f"Connecting to {host} using Netmiko...")
        device = {
            "device_type": device_type,
            "host":        host,
            "username":    username,
            "password":    password,
            "session_log": session_log_path,
        }
        conn = ConnectHandler(**device)
        logger.info(f"Login Successful to {host}")
        return conn
    except NetmikoTimeoutException:
        logger.error(f"{host}: Connection Timed out"); raise
    except NetmikoAuthenticationException:
        logger.error(f"{host}: Authentication Failed"); raise
    except SSHException as e:
        logger.error(f"{host}: SSH error: {e}"); raise
    except Exception as e:
        logger.error(f"{host}: Unknown error: {e}"); raise


# ─────────────────────────────────────────────────────────────
# logout_device
# ─────────────────────────────────────────────────────────────

def logout_device(conn, host, logger):
    try:
        if conn:
            conn.disconnect()
            logger.info(f"Logout successful from {host}")
        else:
            logger.warning("Logout skipped: connection object is None")
    except Exception as e:
        logger.error(f"{host if host else 'Device'}: Logout failed for vendor {global_config.vendor}: {e}")


# ─────────────────────────────────────────────────────────────
# load_yaml
# ─────────────────────────────────────────────────────────────

def load_yaml(filename):
    try:
        curr_dir  = os.getcwd()
        file_path = os.path.join(curr_dir, "inputs", filename)
        with open(file_path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load YAML {filename}: {e}")
        raise


# ─────────────────────────────────────────────────────────────
# export_device_summary
# ─────────────────────────────────────────────────────────────

def export_device_summary():
    timestamp = datetime.now().strftime("%d_%m_%y_%H_%M")
    output    = {}

    for device_key, phases in global_config.device_results.items():
        device_details = {
            "device_key":          device_key,
            "vendor":              global_config.vendor,
            "model":               global_config.model,
            "pre_check_timestamp": global_config.pre_check_timestamp,
        }

        pre_entries = phases.get("pre", [])
        pre_checks  = []
        for entry in pre_entries:
            raw_output = entry.get("output", "") or ""
            first_line = raw_output.strip().splitlines()[0] if raw_output.strip() else ""
            pre_checks.append({
                "cmd":       entry.get("cmd", ""),
                "output":    first_line,
                "json":      entry.get("json", {}),
                "exception": entry.get("exception", ""),
            })

        output[device_key] = {
            "device_details": device_details,
            "pre_checks":     pre_checks,
        }

    reports_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "precheck_jsons"
    )
    os.makedirs(reports_dir, exist_ok=True)
    file_path = os.path.join(reports_dir, f"{timestamp}.json")

    with open(file_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"[export] Summary written to {file_path}")

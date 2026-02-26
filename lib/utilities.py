import logging
import sys
import os
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
# MockConnection  — REMOVED (confirmed unused)
# ─────────────────────────────────────────────────────────────

class GlobalConfig:
    device_results: dict = {}
    pre_check_timestamp = ""
    vendor = ""
    model = ""
    session_log_path = ""
    device_key = ""       # set by main.py before calling execute_commands()
    commands: list = []   # set by main.py before calling execute_commands()

global_config = GlobalConfig()

logging.basicConfig(
    level = logging.INFO,
    format= "%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# workflow_tracker — per-device, keyed by device_key
#
# {
#   "juniper_mx204": {
#     "device_info": {"host","vendor","model","timestamp"},
#     "pre-checks":  {"tasks": {task_name: {status,error,title,logs}}, "commands": [{cmd,output,json,exception}]},
#     "upgrade":     {"tasks": {...}},
#     "post-checks": {"tasks": {...}, "commands": [...]}
#   }
# }
# ─────────────────────────────────────────────────────────────
workflow_tracker = {}


def init_device_tracker(device_key: str, host: str, vendor: str, model: str):
    """Create a fresh workflow_tracker slot for one device."""
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
                "image installation": {"status": "", "error": "", "title": "Install target OS image on device",      "logs": ""},
                "reboot the device":  {"status": "", "error": "", "title": "Reboot and confirm device comes up",     "logs": ""},
                "ping the device":    {"status": "", "error": "", "title": "Verify device reachability after upgrade","logs": ""},
            }
        },
        "post-checks": {
            "tasks": {
                "Take snapshot":            {"status": "", "error": "", "title": "Snapshot primary disk to backup disk",       "logs": ""},
                "Execute show commands":    {"status": "", "error": "", "title": "Collect post-upgrade show command output",   "logs": ""},
                "parsing the commands":     {"status": "", "error": "", "title": "Parse and validate post-upgrade output",     "logs": ""},
                "Enable RE-PROTECT filter": {"status": "", "error": "", "title": "Re-apply RE protection firewall filter",     "logs": ""},
            },
            "commands": []
        }
    }
    logger.info(f"[tracker] Initialised slot for device_key='{device_key}'")


def log_task(device_key: str, phase: str, task_name: str, status: str,
             error: str = "", log_line: str = ""):
    """Update a task entry in workflow_tracker[device_key][phase]['tasks'].

    logs is stored as a plain string — multiple calls append lines separated
    by newlines so the HTML report can render them verbatim.
    """
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
        # Append to existing string — keeps all lines if called multiple times
        existing = tasks[task_name].get("logs", "") or ""
        tasks[task_name]["logs"] = (existing + "\n" + log_line).lstrip("\n")
    logger.info(f"[tracker] {device_key} | {phase} | {task_name} -> {status}")


def set_commands(device_key: str, phase: str, entries: list):
    """Store executed command entries into workflow_tracker[device_key][phase]['commands'].

    Each entry in `entries` should be a dict with keys:
        cmd        : str   — the CLI command string
        output     : str   — raw text output from the device
        json       : dict  — parsed structured output (empty dict {} if parse failed)
        exception  : str   — traceback / error message if collection or parsing raised
                             an exception; empty string "" if all was OK
    """
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
# setup_logger — UNCHANGED
# ─────────────────────────────────────────────────────────────
def setup_logger(name):
    log_dir = os.path.join(os.getcwd(), "logging")
    os.makedirs(log_dir, exist_ok=True)
    log_file = f"{global_config.vendor}_{global_config.model}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
    log_path = os.path.join(log_dir, log_file)
    logger = logging.getLogger(f"{global_config.vendor}_{global_config.model}")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    handler = logging.FileHandler(log_path)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d_%H:%M:%S")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


# ─────────────────────────────────────────────────────────────
# build_registries
# ─────────────────────────────────────────────────────────────

def build_registries():

    JUNIPER_PARSER_REGISTRY = {
    ("juniper", "show arp no-resolve | no-more"): parse_show_arp_no_resolve,
    ("juniper", "show vrrp summary | no-more"): parse_show_vrrp_summary,
    ("juniper", "show lldp neighbors | no-more"): parse_show_lldp_neighbors,
    ("juniper", "show bfd session | no-more"): parse_show_bfd_session,
    ("juniper", "show rsvp neighbor | no-more"): parse_show_rsvp_neighbor,
    ("juniper", "show rsvp session | no-more"): parse_show_rsvp_session,
    ("juniper", "show route table inet.0 | no-more"): parse_show_route_table_inet0,
    ("juniper", "show route table inet.3 | no-more"): parse_show_route_table_inet3,
    ("juniper", "show route table mpls.0 | no-more"): parse_show_route_table_mpls0,
    ("juniper", "show mpls interface | no-more"): parse_show_mpls_interface,
    ("juniper", "show mpls lsp | no-more"): parse_show_mpls_lsp,
    ("juniper", "show mpls lsp p2mp | no-more"): parse_show_mpls_lsp_p2mp,
    ("juniper", "show bgp summary | no-more"): parse_show_bgp_summary,
    ("juniper", "show bgp neighbor | no-more"): parse_show_bgp_neighbor,
    ("juniper", "show isis adjacency extensive | no-more"): parse_show_isis_adjacency_extensive,
    ("juniper", "show route summary | no-more"): parse_show_route_summary,
    ("juniper", "show rsvp session match DN | no-more"): parse_show_rsvp_session_match_DN,
    ("juniper", "show mpls lsp unidirectional match DN | no-more"): parse_show_mpls_lsp_unidirectional_match_DN,
    ("juniper", "show rsvp | no-more"): parse_show_rsvp,
    ("juniper", "show mpls lsp unidirectional | no-more"): parse_show_mpls_lsp_unidirectional_no_more,
    ("juniper", "show system uptime | no-more"): parse_21_show_system_uptime,
    ("juniper", "show ntp associations no-resolve | no-more"): parse_22_show_ntp_associations,
    ("juniper", "show vmhost version | no-more"): parse_23_show_vmhost_version,
    ("juniper", "show vmhost snapshot | no-more"): parse_24_show_vmhost_snapshot,
    ("juniper", "show chassis hardware | no-more"): parse_25_show_chassis_hardware,
    ("juniper", "show chassis fpc detail | no-more"): parse_26_show_chassis_fpc_detail,
    ("juniper", "show chassis alarms | no-more"): parse_27_show_chassis_alarms,
    ("juniper", "show system alarms | no-more"): parse_28_show_system_alarms,
    ("juniper", "show chassis routing-engine | no-more"): parse_29_show_chassis_routing_engine,
    ("juniper", "show chassis environment | no-more"): parse_30_show_chassis_environment,
    ("juniper", "show system resource-monitor fpc | no-more"): parse_31_show_system_resource_monitor_fpc,
    ("juniper", "show krt table | no-more"): parse_32_show_krt_table,
    ("juniper", "show system processes | no-more"): parse_33_show_system_processes,
    ("juniper", "show interface descriptions | no-more"): parse_34_show_interface_descriptions,
    ("juniper", "show oam ethernet connectivity-fault-management interfaces extensive | no-more"): parse_35_show_oam_cfm_interfaces,
    ("juniper", "show ldp neighbor | no-more"): parse_36_show_ldp_neighbor,
    ("juniper", "show connections | no-more"): parse_37_show_connections,
    }
    return JUNIPER_PARSER_REGISTRY


# ─────────────────────────────────────────────────────────────
# write_json
# Writes to: pre_checks/<vendor>_<model>_<timestamp>.json
# Does NOT include hostname or version in metadata.
# ─────────────────────────────────────────────────────────────
def write_json(command_name, vendor, model, json_data):
    if not all([command_name, vendor, model]):
        logger.error("Command name, vendor, and model cannot be empty")
        raise ValueError("Invalid Parameters")
    try:
        logger.info("Writing to pre_checks JSON file ...")
        curr_dir = os.getcwd()
        output_dir = os.path.join(curr_dir, "pre_checks")
        os.makedirs(output_dir, exist_ok=True)
        filename = f"{vendor}_{model}_{global_config.pre_check_timestamp}.json"
        file_path = os.path.join(output_dir, filename)
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                data = json.load(f)
        else:
            data = {
                "metadata": {
                    "timestamp": global_config.pre_check_timestamp,
                    "vendor": vendor,
                    "model": model,
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
# login_device — UNCHANGED
# ─────────────────────────────────────────────────────────────
def login_device(host, username, password, device_type, session_log_path, logger):
    try:
        logger.info(f"Connecting to {host} using Netmiko...")
        device = {"device_type": device_type, "host": host, "username": username, "password": password, "session_log": session_log_path}
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
# logout_device — UNCHANGED
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
# load_yaml — UNCHANGED
# ─────────────────────────────────────────────────────────────
def load_yaml(filename):
    try:
        curr_dir = os.getcwd()
        file_path = os.path.join(curr_dir, "inputs", filename)
        with open(file_path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load YAML {filename}: {e}")
        raise


# ─────────────────────────────────────────────────────────────
# export_device_summary
# Does NOT include hostname or version.
# ─────────────────────────────────────────────────────────────
def export_device_summary():
    """
    Traverses all device keys in global_config.device_results and writes
    a single JSON file with device_details + pre_checks (cmd, first line of output, json).
    Saved to: reports/<DD_MM_YY_HH_MM>.json
    """
    timestamp = datetime.now().strftime("%d_%m_%y_%H_%M")
    output = {}

    for device_key, phases in global_config.device_results.items():
        # --- device_details (no hostname or version) ---
        device_details = {
            "device_key":           device_key,
            "vendor":               global_config.vendor,
            "model":                global_config.model,
            "pre_check_timestamp":  global_config.pre_check_timestamp,
        }

        # --- pre_checks ---
        pre_entries = phases.get("pre", [])
        pre_checks = []
        for entry in pre_entries:
            raw_output = entry.get("output", "") or ""
            first_line = raw_output.strip().splitlines()[0] if raw_output.strip() else ""
            pre_checks.append({
                "cmd":       entry.get("command", ""),
                "output":    first_line,
                "json":      entry.get("json_output", {}),
                "exception": entry.get("exception", ""),  # empty string if no error
            })

        output[device_key] = {
            "device_details": device_details,
            "pre_checks":     pre_checks,
        }

    # --- write file ---
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "precheck_jsons")
    os.makedirs(reports_dir, exist_ok=True)
    file_path = os.path.join(reports_dir, f"{timestamp}.json")

    with open(file_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"[export] Summary written to {file_path}")
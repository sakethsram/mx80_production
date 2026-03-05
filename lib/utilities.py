import logging
import sys
import os
import re
import yaml
import json
from netmiko import ConnectHandler
from netmiko.exceptions import (
    NetmikoTimeoutException,
    NetmikoAuthenticationException
)
from paramiko.ssh_exception import SSHException
from parsers.juniper.juniper_mx204 import *
from parsers.cisco.cisco_asr9910 import *
from datetime import datetime, timedelta
import threading
from workflow_report_generator import generate_upgrade_report
MIN_OUTPUT_CHARS = 5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Single source of truth — all live device state lives here.
# Keyed by device_key (e.g. "10_0_0_1_juniper_mx204").
# Shape per key:
#   {
#     "device_info": { host, vendor, model, hostname, version },
#     "conn":        <netmiko connection | None>,
#     "yaml":        <raw device yaml dict>,
#     "pre":         [ {cmd, output, json, exception}, ... ],
#     "post":        [ {cmd, output, json, exception}, ... ],
#     "upgrade":     {},
#   }
# ─────────────────────────────────────────────────────────────
device_results: dict = {}

# Final exportable summary (conn stripped) — written to JSON by
# export_device_summary().
all_devices_summary: dict = {}

results_lock = threading.Lock()


def init_device_results(device_key: str, host: str, vendor: str, model: str, device_yaml: dict):
    device_results[device_key] = {
        "device_info": {
            "host":     host,
            "vendor":   vendor,
            "model":    model,
            "hostname": "",
            "version":  "",
        },
        "conn":    None,
        "yaml":    device_yaml,
        "pre":     [],
        "post":    [],
        "upgrade": {},
    }


def normalise(cmd: str) -> str:
    cmd = re.sub(r'\s+', ' ', cmd.strip())
    cmd = re.sub(r'\s*\|\s*', ' | ', cmd)
    return cmd.lower()


def build_juniper_registries():
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
        ("juniper", "show rsvp session | match DN | no-more"):                                         parse_show_down_lsp_or_session,
        ("juniper", "show mpls lsp unidirectional | match dn | no-more"):                              parse_show_down_lsp_or_session,
        ("juniper", "show log messages | last 200 | no-more"):                                         parse_show_log_messages_last_200,
    }
    return {
        (vendor, normalise(cmd)): fn
        for (vendor, cmd), fn in raw.items()
    }


def build_cisco_registries():
    raw = {
        ("cisco", "show install active summary"):   show_install_active_summary,
        ("cisco", "show isis adjacency"):           show_isis_adjacency,
    }
    return {
        (vendor, normalise(cmd)): fn
        for (vendor, cmd), fn in raw.items()
    }


VENDOR_REGISTRY = {
    "juniper": build_juniper_registries(),
    "cisco":   build_cisco_registries(),
}


def collect_outputs(device_key: str, vendor: str, commands: list,
                    check_type: str, conn, log) -> list:

    log.info(f"[{device_key}] STEP 1 collect_outputs — {len(commands)} command(s), check_type={check_type}")

    if device_key not in device_results:
        device_results[device_key] = {}

    entries = []
    for cmd in commands:
        log.info(f"[{device_key}] Sending: '{cmd}'")
        exception_str = ""
        output        = ""
        try:
            output = conn.send_command(cmd)
            print(f"[{device_key}] '{cmd}' — {len(output)} chars received")
        except Exception:
            import traceback as tb
            exception_str = tb.format_exc()
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
        log.info(f"[{device_key}] '{cmd}' collected={collected} ({len(stripped)} chars)")

    device_results[device_key][check_type] = entries
    log.info(f"[{device_key}] STEP 1 done — {len(entries)} entries stored")
    return entries


def parse_outputs(device_key: str, vendor: str, check_type: str, log) -> bool:

    registry = VENDOR_REGISTRY.get(vendor)

    if registry is None:
        log.error(f"[{device_key}] STEP 2 — No registry for vendor='{vendor}'")
        return False

    entries = device_results.get(device_key, {}).get(check_type, [])

    if not entries:
        log.warning(f"[{device_key}] STEP 2 — Nothing in device_results to parse")
        return False

    all_ok = True

    for entry in entries:

        cmd      = entry.get("cmd")
        output   = entry.get("output", "")
        norm_cmd = normalise(cmd)

        parser_fn = registry.get((vendor, norm_cmd))

        if parser_fn is None:
            entry["exception"] = "no parser registered"
            continue

        stripped = output.strip() if output else ""

        if len(stripped) <= MIN_OUTPUT_CHARS:
            entry["json"]      = {}
            entry["exception"] = ""
            continue

        try:
            result = parser_fn(output)

            if not result or (
                isinstance(result, dict) and all(not v for v in result.values())
            ):
                entry["exception"] = "parser returned empty result"
                all_ok = False
                continue

            entry["json"]      = result
            entry["exception"] = ""

        except Exception:
            entry["exception"] = f"parser failed for '{cmd}'"
            all_ok = False
            continue

    return all_ok


def setup_logger(name: str, vendor: str = "", model: str = ""):
    vendor = vendor or "unknown"
    model  = model  or "unknown"

    log_dir  = os.path.join(os.getcwd(), "logging")
    os.makedirs(log_dir, exist_ok=True)
    log_file = f"{vendor}_{model}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
    log_path = os.path.join(log_dir, log_file)

    file_logger = logging.getLogger(f"{vendor}_{model}")
    file_logger.setLevel(logging.DEBUG)
    file_logger.propagate = False
    handler   = logging.FileHandler(log_path)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s",
                                  datefmt="%Y-%m-%d_%H:%M:%S")
    handler.setFormatter(formatter)
    file_logger.addHandler(handler)
    return file_logger


def write_json(command_name, vendor, model, json_data, timestamp: str = ""):
    if not all([command_name, vendor, model]):
        logger.error("Command name, vendor, and model cannot be empty")
        raise ValueError("Invalid Parameters")

    timestamp = timestamp or datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    try:
        logger.info("Writing to pre_checks JSON file ...")
        curr_dir   = os.getcwd()
        output_dir = os.path.join(curr_dir, "pre_checks")
        os.makedirs(output_dir, exist_ok=True)
        filename  = f"{vendor}_{model}_{timestamp}.json"
        file_path = os.path.join(output_dir, filename)
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                data = json.load(f)
        else:
            data = {
                "metadata": {
                    "timestamp": timestamp,
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


def login_device(host, username, password, device_type, session_log_path, logger):
    try:
        logger.info(f"Connecting to {host} using Netmiko...")
        conn = ConnectHandler(**{
            "device_type": device_type,
            "host":        host,
            "username":    username,
            "password":    password,
            "session_log": session_log_path,
        })
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


def logout_device(conn, host, logger):
    try:
        if conn:
            conn.disconnect()
            logger.info(f"Logout successful from {host}")
        else:
            logger.warning("Logout skipped: connection object is None")
    except Exception as e:
        logger.error(f"{host}: Logout failed: {e}")


def load_yaml(filename):
    try:
        file_path = os.path.join(os.getcwd(), "inputs", filename)
        with open(file_path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load YAML {filename}: {e}")
        raise


def export_device_summary(device_key: str):
    slot = device_results.get(device_key, {})
    printable = {k: v for k, v in slot.items() if k != "conn"}

    with results_lock:
        all_devices_summary[device_key] = printable

    output_dir = os.path.join(os.getcwd(), "precheck_jsons")
    os.makedirs(output_dir, exist_ok=True)
    timestamp    = (datetime.now() + timedelta(minutes=4)).strftime('%Y-%m-%d_%H-%M-%S')
    summary_file = os.path.join(output_dir, f"all_devices_summary_{timestamp}.json")
    with open(summary_file, "w") as f:
        json.dump(all_devices_summary, f, indent=2, default=str)
    print(f"[EXPORT] Summary JSON saved -> {summary_file}")

    # ── generate HTML report ──────────────────────────────────
    report_dir  = os.path.join(os.getcwd(), "reports")
    report_path = generate_upgrade_report(all_devices_summary, output_dir=report_dir)
    print(f"[REPORT] HTML report saved -> {report_path}")


def merge_thread_result(device_key: str, result: dict):
    with results_lock:
        slot = device_results.get(device_key)
        if slot is None:
            logger.warning(f"[merge] device_key='{device_key}' not in device_results — skipping")
            return
        for key in ("pre", "post", "upgrade"):
            if key in result:
                slot[key] = result[key]
        for field, value in result.get("device_info", {}).items():
            if value:
                slot["device_info"][field] = value
        logger.info(f"[merge] device_key='{device_key}' merged into device_results")

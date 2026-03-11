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
from datetime import datetime
import threading
import traceback as tb
from workflow_report_generator import *

MIN_OUTPUT_CHARS = 5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# device_results — single source of truth for all device state
# ─────────────────────────────────────────────────────────────────────────────

device_results: dict = {}
all_devices_summary: dict = {}
results_lock = threading.Lock()


def init_device_results(device_key: str, host: str, vendor: str, model: str, device_yaml: dict):
    image_details = device_yaml.get("imageDetails", [])
    initial_os    = device_yaml.get("curr_os", "")
    target_os     = image_details[-1].get("expected_os", "") if image_details else ""

    device_results[device_key] = {
        "status": "",
        "device_info": {
            "host":     host,
            "vendor":   vendor,
            "model":    model,
            "hostname": "",
            "version":  "",
        },
        "conn": None,
        "yaml": device_yaml,
        "pre": {
            "connect": {
                "ping":      "up",      # TODO: replace with real ICMP ping
                "status":    False,
                "exception": "",
            },
            "execute_show_commands": {
                "status":    "not_started",
                "exception": "",
                "commands":  [],
            },
            "show_version": {
                "status":    "not_started",
                "exception": "",
                "version":   "",
                "platform":  "",
                "hostname":  "",
            },
            "check_storage": {
                "status":        "not_started",
                "deleted_files": [],
                "exception":     "",
                "sufficient":    False,
            },
            "backup_active_filesystem": {
                "status":        "not_started",
                "exception":     "",
                "snapshot_slot": "",
                "verified":      False,
            },
            "backup_running_config": {
                "status":      "not_started",
                "exception":   "",
                "destination": "",
                "config_file": "",
            },
            "transfer_image": {
                "status":      "not_started",
                "exception":   "",
                "image":       "",
                "destination": "",
            },
            # ── verify_checksum — one slot per image in imageDetails ──────────
            "verify_checksum": [
                {
                    "image":     img.get("image", ""),
                    "status":    "not_started",
                    "exception": "",
                    "expected":  img.get("checksum", ""),
                    "computed":  "",
                    "match":     False,
                }
                for img in image_details
            ],
            "disable_re_protect_filter": {
                "status":    "not_started",
                "exception": "",
            },
        },
        "upgrade": {
            "status":     "not_started",
            "initial_os": initial_os,
            "target_os":  target_os,
            "exception":  "",
            "hops": [
                {
                    "image":     img.get("image", ""),
                    "status":    "not_started",
                    "exception": "",
                    "md5_match": False,
                }
                for img in image_details
            ],
        },
        "post": {
            "connect": {
                "status":    "not_started",
                "exception": "",
            },
            "execute_show_commands": {
                "status":    "not_started",
                "exception": "",
                "commands":  [],
            },
            "show_version": {
                "status":    "not_started",
                "exception": "",
                "version":   "",
                "platform":  "",
                "hostname":  "",
            },
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# get_show_version
# ─────────────────────────────────────────────────────────────────────────────
def get_show_version(device_key: str, conn, vendor: str, logger) -> bool:
    logger.info(f"[{device_key}] get_show_version — sending 'show version'")

    try:
        output = conn.send_command("show version")
        if not output or len(output.strip()) <= MIN_OUTPUT_CHARS:
            raise RuntimeError("'show version' returned empty output")

        hostname = ""
        model    = ""
        version  = ""

        if vendor == "juniper":
            m = re.search(r"^Hostname:\s+(\S+)", output, re.M)
            if m:
                hostname = m.group(1).strip()

            m = re.search(r"^Model:\s+(\S+)", output, re.M)
            if m:
                model = m.group(1).strip()

            m = re.search(r"^Junos:\s+(\S+)", output, re.M)
            if m:
                version = m.group(1).strip()

        elif vendor == "cisco":
            m = re.search(r"Cisco IOS XR Software.*?Version\s+(\S+)", output, re.I)
            if m:
                version = m.group(1).strip()

            m = re.search(r"^hostname\s+(\S+)", output, re.M | re.I)
            if m:
                hostname = m.group(1).strip()

        device_results[device_key]["pre"]["show_version"] = {
            "status":    "ok",
            "exception": "",
            "version":   version,
            "platform":  model,
            "hostname":  hostname,
        }

        if hostname:
            device_results[device_key]["device_info"]["hostname"] = hostname
        if version:
            device_results[device_key]["device_info"]["version"]  = version
        if model:
            device_results[device_key]["device_info"]["model"]    = model

        logger.info(
            f"[{device_key}] show_version parsed — "
            f"hostname={hostname}  model={model}  version={version}"
        )
        return True

    except Exception as e:
        logger.error(f"[{device_key}] get_show_version failed — {e}")
        device_results[device_key]["pre"]["show_version"] = {
            "status":    "failed",
            "exception": str(e),
            "version":   "",
            "platform":  "",
            "hostname":  "",
        }
        return False


# ─────────────────────────────────────────────────────────────────────────────
# normalise / registry helpers
# ─────────────────────────────────────────────────────────────────────────────
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
        ("juniper", "show oam ethernet connectivity-fault-management interfaces extensive | no-more"): parse_35_show_oam_cfm_interfaces,
        ("juniper", "show ldp neighbor | no-more"):                                                    parse_36_show_ldp_neighbor,
        ("juniper", "show connections | no-more"):                                                     parse_37_show_connections,
        ("juniper", "show log messages | last 200 | no-more"):                                         parse_show_log_messages_last_200,
        ("juniper", "show system processes extensive | match rpd | no-more"):                          parse_show_system_processes_rpd_match,
        ("juniper", "show interface terse | no-more"):                                                 parse_show_interfaces_terse,
        ("juniper", "show rsvp session | match dn | no-more"):                                        parse_show_rsvp_session_match_DN,
        ("juniper", "show mpls lsp unidirectional | match dn | no-more"):                             parse_show_mpls_lsp_unidirectional_no_more,
    }
    return {
        (vendor, normalise(cmd)): fn
        for (vendor, cmd), fn in raw.items()
    }


def build_cisco_registries():
    raw = {
        ("cisco", "show install active summary"):             show_install_active_summary,
        ("cisco", "show isis adjacency"):                     show_isis_adjacency,
        ("cisco", "show bfd session"):                        show_bfd_session,
        ("cisco", "show route summary"):                      show_route_summary,
        ("cisco", "show bgp all summary"):                    show_bgp_all_summary,
        ("cisco", "show bgp vrf all summary"):                show_bgp_vrf_all_summary,
        ("cisco", "show ipv4 vrf all interface brief"):       show_ipv4_vrf_all_interface_brief,
        ("cisco", "show mpls ldp neighbor"):                  show_mpls_ldp_neighbor,
        ("cisco", "show pim neighbor"):                       show_pim_neighbor,
        ("cisco", "show pfm location all"):                   show_pfm_location_all,
        ("cisco", "show processes cpu"):                      show_processes_cpu,
        ("cisco", "show watchdog memory-state location all"): show_watchdog_memory_state,
        ("cisco", "show redundancy"):                         show_redundancy,
        ("cisco", "show interfaces description"):             show_interfaces_description,
        ("cisco", "show filesystem"):                         show_filesystem,
        ("cisco", "show interfaces Bundle-Ether"):            show_interfaces,
        ("cisco", "show msdp peer"):                          show_msdp_peer,
        ("cisco", "show l2vpn xconnect brief"):               show_l2vpn_xconnect_brief,
        ("cisco", "show hw-module fpd"):                      show_hw_module_fpd,
        ("cisco", "show platform"):                           show_platform,
        ("cisco", "show media location 0/RSP1/CPU0"):         show_media_location,
        ("cisco", "show version"):                            show_version,
    }
    return {
        (vendor, normalise(cmd)): fn
        for (vendor, cmd), fn in raw.items()
    }


VENDOR_REGISTRY = {
    "juniper": build_juniper_registries(),
    "cisco":   build_cisco_registries(),
}


# ─────────────────────────────────────────────────────────────────────────────
# collect_outputs / parse_outputs
# ─────────────────────────────────────────────────────────────────────────────
def collect_outputs(device_key: str, vendor: str, commands: list,
                    check_type: str, conn, log) -> list:

    log.info(f"[{device_key}] collect_outputs — {len(commands)} command(s), check_type={check_type}")

    phase_key = "pre" if check_type == "pre" else "post"
    device_results[device_key][phase_key]["execute_show_commands"]["status"] = "in_progress"

    entries = []
    for cmd in commands:
        log.info(f"[{device_key}] Sending: '{cmd}'")
        exception_str = ""
        output        = ""
        try:
            output = conn.send_command(cmd)
            print(f"[{device_key}] '{cmd}' — {len(output)} chars received")
        except Exception:
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

    device_results[device_key][phase_key]["execute_show_commands"]["commands"] = entries
    log.info(f"[{device_key}] collect_outputs done — {len(entries)} entries stored")
    return entries


def parse_outputs(device_key: str, vendor: str, check_type: str, log) -> bool:

    registry = VENDOR_REGISTRY.get(vendor)
    if registry is None:
        log.error(f"[{device_key}] No registry for vendor='{vendor}'")
        return False

    phase_key = "pre" if check_type == "pre" else "post"
    entries = (
        device_results
        .get(device_key, {})
        .get(phase_key, {})
        .get("execute_show_commands", {})
        .get("commands", [])
    )
    if not entries:
        log.warning(f"[{device_key}] Nothing in {phase_key}.execute_show_commands.commands to parse")
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
            entry["json"]      = parser_fn("")
            entry["exception"] = ""
            continue

        try:
            result = parser_fn(output)
            if not result or (isinstance(result, dict) and all(not v for v in result.values())):
                entry["exception"] = "parser returned empty result"
                all_ok = False
                continue
            entry["json"]      = result
            entry["exception"] = ""
        except Exception:
            entry["json"]      = {}
            entry["exception"] = f"parser failed for '{cmd}'"
            log.error(f"[{device_key}] parser failed for '{cmd}':\n{tb.format_exc()}")
            all_ok = False
            continue

    status = "completed" if all_ok else "completed_with_errors"
    device_results[device_key][phase_key]["execute_show_commands"]["status"]    = status
    device_results[device_key][phase_key]["execute_show_commands"]["exception"] = (
        "" if all_ok else "one or more parsers failed"
    )

    return all_ok


# ─────────────────────────────────────────────────────────────────────────────
# setup_logger
# ─────────────────────────────────────────────────────────────────────────────
def setup_logger(name: str, vendor: str = "", model: str = ""):
    vendor = vendor or "unknown"
    model  = model  or "unknown"

    log_dir  = os.path.join(os.getcwd(), "logging")
    os.makedirs(log_dir, exist_ok=True)
    log_file = f"{vendor}_{model}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
    log_path = os.path.join(log_dir, log_file)

    file_logger = logging.getLogger(f"{vendor}_{model}")
    file_logger.setLevel(logging.DEBUG)
    file_logger.propagate = True
    handler   = logging.FileHandler(log_path)
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d_%H:%M:%S"
    )
    handler.setFormatter(formatter)
    file_logger.addHandler(handler)
    return file_logger


# ─────────────────────────────────────────────────────────────────────────────
# login / logout
# ─────────────────────────────────────────────────────────────────────────────
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
        logger.info(f"Login successful to {host}")
        return conn
    except NetmikoTimeoutException:
        logger.error(f"{host}: Connection timed out"); raise
    except NetmikoAuthenticationException:
        logger.error(f"{host}: Authentication failed"); raise
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


# ─────────────────────────────────────────────────────────────────────────────
# load_yaml
# ─────────────────────────────────────────────────────────────────────────────
def load_yaml(filename):
    try:
        file_path = os.path.join(os.getcwd(), "inputs", filename)
        with open(file_path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load YAML {filename}: {e}")
        raise


# ─────────────────────────────────────────────────────────────────────────────
# export_device_summary
# ─────────────────────────────────────────────────────────────────────────────
def export_device_summary(device_key: str):
    slot      = device_results.get(device_key, {})
    printable = {k: v for k, v in slot.items() if k != "conn"}

    with results_lock:
        all_devices_summary[device_key] = printable

    output_dir = os.path.join(os.getcwd(), "precheck_jsons")
    os.makedirs(output_dir, exist_ok=True)
    timestamp    = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    device_info  = slot.get("device_info", {})
    vendor       = device_info.get("vendor", "unknown")
    model        = device_info.get("model",  "unknown")
    summary_file = os.path.join(output_dir, f"{vendor}_{model}_{timestamp}.json")
    with open(summary_file, "w") as f:
        json.dump(all_devices_summary, f, indent=2, default=str)
    print(f"[EXPORT] Summary JSON saved -> {summary_file}")
    print(f"[LOGS] Device log: logging/{vendor}_{model}_*.log | Session log: outputs/{vendor}_{model}_*.log")

    # ── HTML report ───────────────────────────────────────────────────────────
    reports_dir = os.path.join(os.getcwd(), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    generated   = generate_html_report(all_devices_summary, output_dir=reports_dir)
    html_name   = f"{vendor}_{model}_{timestamp}.html"
    html_path   = os.path.join(reports_dir, html_name)
    if generated and generated != html_path:
        os.rename(generated, html_path)
    print(f"[REPORT] {html_path}")


# ─────────────────────────────────────────────────────────────────────────────
# merge_thread_result
# ─────────────────────────────────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────────────────────────
# connect / disconnect
# ─────────────────────────────────────────────────────────────────────────────
def connect(device_key: str, dev: dict, logger):
    host    = dev["host"]
    vendor  = dev["vendor"].lower()
    model   = str(dev["model"]).lower().replace("-", "")

    session_log_dir = os.path.join(os.getcwd(), "outputs")
    os.makedirs(session_log_dir, exist_ok=True)
    session_log_path = os.path.join(
        session_log_dir,
        f"{vendor}_{model}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
    )

    logger.info(f"[{device_key}] Connecting to {host}")

    try:
        conn = login_device(
            device_type      = dev["device_type"],
            host             = host,
            username         = dev["username"],
            password         = dev["password"],
            session_log_path = session_log_path,
            logger           = logger,
        )
        device_results[device_key]["conn"]                        = conn
        device_results[device_key]["pre"]["connect"]["status"]    = True
        device_results[device_key]["pre"]["connect"]["exception"] = ""
        logger.info(f"[{device_key}] Connected successfully to {host}")
        return conn

    except Exception as e:
        logger.error(f"[{device_key}] Connection failed: {e}")
        device_results[device_key]["pre"]["connect"]["status"]    = False
        device_results[device_key]["pre"]["connect"]["exception"] = str(e)
        return None


def disconnect(device_key: str, logger):
    slot = device_results.get(device_key, {})
    conn = slot.get("conn")
    host = slot.get("device_info", {}).get("host", device_key)

    if conn is None:
        logger.warning(f"[{device_key}] disconnect called but conn is None")
        return

    logout_device(conn, host, logger)
    device_results[device_key]["conn"] = None
    logger.info(f"[{device_key}] Disconnected from {host}")


# ─────────────────────────────────────────────────────────────────────────────
# load_commands
# ─────────────────────────────────────────────────────────────────────────────
def load_commands(vendor: str, model: str, logger) -> list:
    all_cmds = load_yaml("show_cmd_list.yaml")
    cmd_key  = f"{vendor}_{model}"
    if cmd_key not in all_cmds:
        logger.error(f"[load_commands] No commands found for key='{cmd_key}'")
        return []
    commands = all_cmds[cmd_key]
    logger.info(f"[load_commands] Loaded {len(commands)} commands for '{cmd_key}'")
    return commands
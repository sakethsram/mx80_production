import logging 
from netmiko import ConnectHandler 
from netmiko.exceptions import (
    NetmikoTimeoutException,
    NetmikoAuthenticationException
)
from paramiko.ssh_exception import SSHException
import sys
import time
import os
import yaml
import json
from datetime import datetime
import re
from parsers.junos import junos_mx204
from parsers.junos.junos_mx204 import *
from parsers.cisco.cisco_asr9910 import *

LOG_DIR = os.path.join(os.getcwd(), "logging")
os.makedirs(LOG_DIR, exist_ok=True)
"""
Global store for device command outputs
"""
class GlobalVariable:
    pre_output = {} 
    post_output = {}
    pre_check_timestamp = "" 
    hostname = ""
    session_log_path = ""
    device_results = []

global_variable = GlobalVariable()
 

logging.basicConfig(
    level = logging.INFO, 
    format= "%(asctime)s - %(levelname)s - %(message)s"
)
# logger = logging.getLogger(device_logs  )
logger = logging.getLogger(__name__)

#---------------------------------------------#
# Enable Logger functionality 
#---------------------------------------------#
def log_task(device_key: str, phase: str, task_name: str, status: str,
             error: str = "", log_line: str = ""):
    """Update a task entry in workflow_tracker[device_key][phase]['tasks']."""
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
        tasks[task_name]["logs"].append(log_line)
    logger.info(f"[tracker] {device_key} | {phase} | {task_name} -> {status}")




def setup_logger(name, vendor, model):
    """
    Setup logger with VENDOR and MODEL specific log file
    """
    log_dir = os.path.join(os.getcwd(), "logging")
    os.makedirs(log_dir, exist_ok=True)

    log_file = f"{vendor}_{model}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
    log_path = os.path.join(log_dir, log_file)

    logger = logging.getLogger(f"{vendor}_{model}")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    handler = logging.FileHandler(log_path)
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d_%H:%M:%S"
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)

    return logger

# ─────────────────────────────────────────────────────────────
# _build_registries — UNCHANGED
# ─────────────────────────────────────────────────────────────
def build_registries():
    print("build registries")
    JUNOS_PARSER_REGISTRY = {
#        ("juniper_mx204", "show arp no-resolve | no-more"): show_arp_no_resolve,
        #("juniper_mx204", "show lldp neighbors | no-more"): show_lldp_neighbors,
        #("juniper_mx204", "show lldp neighbors | no-more"):  parse_show_lldp_neighbors,
	#("juniper_mx204", "show version | no-more"): parse_show_version,
	#("juniper_mx204", "show system uptime | no-more"): parse_21_show_system_uptime,
	#("juniper_mx204", "show ntp associations no-resolve | no-more"): parse_22_show_ntp_associations,
	#("juniper_mx204", "show vmhost version |no-more"): parse_23_show_vmhost_version,
	#("juniper_mx204", "show vmhost snapshot |no-more"): parse_24_show_vmhost_snapshot,
	#("juniper_mx204", "show chassis hardware | no-more"): parse_25_show_chassis_hardware,
	#("juniper_mx204", "show chassis fpc detail | no-more"): parse_26_show_chassis_fpc_detail,
	#("juniper_mx204", "show chassis alarms | no-more"): parse_27_show_chassis_alarms,
	#("juniper_mx204", "show system alarms | no-more"): parse_28_show_system_alarms,
	#("juniper_mx204", "show chassis routing-engine | no-more"): parse_29_show_chassis_routing_engine,
	#("juniper_mx204", "show chassis environment | no-more"): parse_30_show_chassis_environment,
	#("juniper_mx204", "show system resource-monitor fpc | no-more"): parse_31_show_system_resource_monitor_fpc,
	##("juniper_mx204", "show krt table | match "kernel-id:  -"  |no-more"): parse_32_show_krt_table,
	#("juniper_mx204", "show system processes extensive | match rpd |no-more"): parse_33_show_system_processes,
	#("juniper_mx204", "show interfaces descriptions | no-more"): parse_34_show_interface_descriptions,
	#("juniper_mx204", "show oam ethernet connectivity-fault-management interfaces extensive | no-more"):  parse_35_show_oam_cfm_interfaces,
	#("juniper_mx204", "show arp no-resolve | no-more"): parse_show_arp_no_resolve,
	#("juniper_mx204", "show vrrp summary | no-more"): parse_show_vrrp_summary,
	#("juniper_mx204", "show lldp neighbors | no-more"): parse_show_lldp_neighbors,
	#("juniper_mx204", "show bfd session | no-more"): parse_show_bfd_session,
	#("juniper_mx204", "show rsvp neighbor | no-more"): parse_show_rsvp_neighbor,
	#("juniper_mx204", "show rsvp session | no-more"): parse_show_rsvp_session,
	#("juniper_mx204", "show route table inet.0 | no-more"): parse_show_route_table_inet0,
	#("juniper_mx204", "show route table inet.3 | no-more"): parse_show_route_table_inet3,
	#("juniper_mx204", "show route table mpls.0 | no-more"): parse_show_route_table_mpls0,
	#("juniper_mx204", "show mpls interface | no-more"): parse_show_mpls_interface,
	#("juniper_mx204", "show mpls lsp | no-more"): parse_show_mpls_lsp,
	#("juniper_mx204", "show mpls lsp p2mp | no-more"): parse_show_mpls_lsp_p2mp,
	#("juniper_mx204", "show bgp summary | no-more"): parse_show_bgp_summary,
	#("juniper_mx204", "show bgp neighbor | no-more"): parse_show_bgp_neighbor,
	#("juniper_mx204", "show isis adjacency extensive | no-more"): parse_show_isis_adjacency_extensive,
	#("juniper_mx204", "show route summary | no-more"): parse_show_route_summary,
	#("juniper_mx204", "show rsvp session | match DN |no-more"): parse_show_rsvp_session_match_DN,
	#("juniper_mx204", "show mpls lsp unidirectional | match Dn |no-more") : parse_show_mpls_lsp_unidirectional_match_DN,
	#("juniper_mx204", "show ldp neighbor | no-more"): parse_36_show_ldp_neighbor,
	#("juniper_mx204", "show connections | no-more"): parse_37_show_connections,
    }
    CISCO_PARSER_REGISTRY = {
         ("cisco_asr9910", "show install active summary"): show_install_active_summary,
        }
    print(f"JUNOS_PARSER_REGISTRY: {JUNOS_PARSER_REGISTRY}")
    return JUNOS_PARSER_REGISTRY, CISCO_PARSER_REGISTRY
#---------------------------------------------#
# Writing the output into JSON file 
#---------------------------------------------#
def write_json(vendor, model, pre_check_timestamp, json_data, json_file_path): 
    """
    Docstring for write_json
    
    :param command_name: Providing the command name
    :param json_data: Adding the command output 
    :return: Return the output JSON file along with timestamp
    """
   # if not all([command_name, vendor, model]): 
   #     logger.error("Command name, vendor, and model cannot be empty")
   #     raise ValueError("Invalid Parameters")
    
    try:
        logger.info("Writing to JSON file ...")
        curr_dir = os.getcwd()
        output_dir = os.path.join(curr_dir, json_file_path)
        os.makedirs(output_dir, exist_ok=True)
        
        filename = f"{vendor}_{model}_{pre_check_timestamp}.json"
        print(f" Filname: {filename}")

        file_path = os.path.join(output_dir, filename)
        print(f" file path: {file_path}")

        if os.path.exists(file_path): 
            with open(file_path, "r") as f: 
                data = json.load(f)
        else:
            data = {
                "metadata": {
                    "timestamp": pre_check_timestamp, 
                    "vendor": vendor, 
                    "model": model, 
                }, 
                "commands": global_variable.device_results
            }
        
        #data["commands"][command_name] = json_data
        print(f" data: {data}")
        with open(file_path, "w") as f: 
            json.dump(data, f, indent=2)

        logger.info(f"JSON file written successfully: {file_path}")
        return data
    
    except FileNotFoundError as e: 
        logger.error(f"File error: {e}")
        raise
    except PermissionError as e: 
        logger.error(f"Permission denied while writing JSON: {e}")
        raise
    except json.JSONDecodeError as e: 
        logger.error(f" Invalid JSON format in existing file: {e}")
        raise
    except Exception as e: 
        logger.error(f"Unexpected error while writing JSON: {e}")
        raise


#---------------------------------------------#
# Login into device
#---------------------------------------------#
def login_device(host, username, password, device_type, session_log_path, logger): 
    try: 
        msg = f"Connecting to {host} using Netmiko..."
        logger.info(msg) 

        device = {
            "device_type": device_type, 
            "host": host, 
            "username": username, 
            "password": password,
            "session_log": session_log_path
        }

        conn = ConnectHandler(**device)
        msg = f"Login Successful to {host}"
        logger.info(msg)
        return conn

    except NetmikoTimeoutException as e: 
        msg = f"{host}: Connection Timed out: {e}"
        logger.error(msg)
        raise
        exist
    except NetmikoAuthenticationException: 
        msg = f"{host}: Authentication Failed"
        logger.error(msg)
        raise
        exit 
    except SSHException as e: 
        msg = f"{host}: SSH error: {e}"
        logger.error(msg)
        raise
        exit 
    except Exception as e: 
        msg = f"{host}: Unknown error: {e}"
        logger.error(msg)
        raise
        exit

#---------------------------------------------#
# Logout from device
#---------------------------------------------#
def logout_device(conn, host,logger): 
    try: 
        msg = f"{host}: Logging out from device"
        if conn:
            conn.disconnect()
            msg = f"Logout successful{f' from {host}' if host else ''}"
            logger.info(msg)
        else: 
            msg = "Logout skipped: connection object is None"
            logger.warning(msg)
    except Exception as e: 
        msg = f"{host if host else 'Device'}: Logout failed for vendor {global_config.vendor}: {e}"
        logger.error(msg)
        
#---------------------------------------------#
# Parsing the data
#---------------------------------------------#
# def parser()

#---------------------------------------------#
# YAML loader
#---------------------------------------------#
def load_yaml(filename): 
    """
    Docstring for load_yaml
    
    :param file_path: Description
    """
    try:
        curr_dir = os.getcwd()
        file_path = os.path.join(curr_dir, "inputs", filename)
        with open(file_path, "r") as f: 
            return yaml.safe_load(f)
    except Exception as e: 
        logger.error(f"Failed to load YAML {filename}: {e}")
        raise

# ═════════════════════════════════════════════════════════════
# Run parsers over stored entries
# ═════════════════════════════════════════════════════════════
def execute_parser(device_name, vendor, check_type, logger):
    """
    Look up each command in VENDOR_REGISTRY[(vendor, cmd)],
    run the parser, write result back into entry["json_output"].
    Returns True only if ALL parsers ran without error.
    """
    logger.debug("started parser execution")
    JUNOS_REGISTRY, CISCO_REGISTRY = build_registries()
    print(f"registry: {JUNOS_REGISTRY}")
    vendor_registry = {
        "cisco":   CISCO_REGISTRY,
        "juniper": JUNOS_REGISTRY
    }

    registry = vendor_registry.get(vendor)
    print(f"registry:{registry}")
    logger.debug("registry:",registry)
    if registry is None:
        logger.error(f"[{device_name}] No registry for vendor='{vendor}' — supported: {list(vendor_registry.keys())}")
        return False

    entries = global_variable.device_results.get(device_name, {}).get(check_type, [])
    print(f"global entry: {entries}")
    if not entries:
        logger.warning(f"[{device_name}] Nothing in device_results[{device_name}][{check_type}] to parse")
        return False

    logger.info(f"[{device_name}] [{check_type.upper()}] Running parsers over {len(entries)} entry(ies)")
    #print(f"entries: {entries}")
    for entry in entries:
        cmd    = entry["command"]
        print(f"cmd: {cmd}")
        output = entry["output"]
        #print(f"output: {output}")

        if not output:
            logger.warning(f"[{device_name}] '{cmd}' — output empty, skipping parser")
            continue
        
        print(device_name,cmd)
        print(registry)
        parser_fn = registry.get((device_name, cmd))
        print(f"parser function: {parser_fn}")

        if parser_fn is None:
            logger.warning(f"[{device_name}] No parser registered for ('{vendor}', '{cmd}') — skipping")
            print(f"[{device_name}] No parser registered for ('{vendor}', '{cmd}') — skipping")
            continue
        
        logger.info(f"[{device_name}] Running {parser_fn}() for '{cmd}'")
        print(f"[{device_name}] Running {parser_fn}() for '{cmd}'")
        try:
            print("running parsers")
            result = parser_fn(output)
            print(f"result: {json.dumps(result, indent=2)}")
            entry["json_output"] = result
            print(f"parser: {entry}")
            keys = list(result.keys()) if isinstance(result, dict) else type(result).__name__
            logger.info(f"[{device_name}] '{cmd}' parsed OK — result type: {keys}")
        except Exception as e:
            logger.error(f"[{device_name}] {parser_fn}() failed for '{cmd}': {e}")
            entry["json_output"] = {"error": str(e)}
            return False
        
    logger.info(f"[{device_name}] [{check_type.upper()}] Parser run complete")
    return True


#-------------------------
# run the execute command 
#-------------------------

def execute_command(conn, commands, vendor, host, check_type, model, logger):
    """
    Execute show commands from YAML and store output globally
    Always logout from device on error or success
    """
    try: 
        msg = "Execute show commands from YAML and store output globally"
        logger.info(msg)
        device_name = f"{vendor}_{model}"
        if device_name not in commands: 
            msg = f"No commands found for vendor: {vendor}_{model}"
            logger.error(msg)
            logout_device(conn, host, logger)
            raise ValueError(msg)
        entries = []
        for cmd in commands.get(device_name): 
            msg = f"{host}: Executing: '{cmd}' for vendor {device_name}"
            print(msg)
            logger.info(msg)
            try: 
                output = conn.send_command(cmd)
                empty_data = output.strip().splitlines()[0][:80] if output.strip() else "<empty>"
                logger.debug(f"[{device_name}] '{cmd}' empty_data: {empty_data}") 
                parts = re.sub(r'\s*\|?\s*no-more', '', cmd)
                parts = re.sub(r'\|', ' ', parts)
                cleaned_cmd = re.sub(r'\s+', '_', parts.strip()).lower()
                #print(f"Handling whitespaces for cmd: {parts} \n final command is: {cleaned_cmd}")
                entries.append({
                  "command": cleaned_cmd,
                  "output": output, 
                  "json_output": {}
                })
                
                if check_type == "pre": 
                  global_variable.pre_output[device_name] = {"pre": entries}
                  global_variable.device_results.append(global_variable.pre_output)
                if check_type == "post": 
                  global_variable.device_results[device_name] = {"post": entries}
                
            except Exception as e: 
                msg = f"{host}: Command Failed: '{cmd}' for vendor: {vendor}: {e}"
                logger.error(msg)
                entries.append({
                  "command": cmd, 
                  "error": str(e)
                })
                logout_device(conn, host, logger)
                return False

#        parser=execute_parser(device_name,vendor,check_type,logger)
#        if not parser:
#          msg=f"{device_name} execution of parsers failed"
#          logger.info(msg)
#          return False
        print(f"device Result: {global_variable.device_results}")
        logger.info(f"[{device_name}] commands are executed — {len(entries)} entries")
        return True
    except Exception as e: 
        msg = f"{host}: Command execution Failed for vendor:{vendor}: {e}"
        logger.error(msg)
        msg = f"{host}: Please check the execute_command() fn inside lib/utilities.py file"
        logger.error(msg)
        logout_device(conn, host, logger)
        return False

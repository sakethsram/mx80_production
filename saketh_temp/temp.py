"""
temp.py — standalone test for export_device_summary()
Place this in your testing/ folder.
Reports are written to testing/reports/

Switch between scenarios by changing SCENARIO:
    SCENARIO = 1  → single device  (juniper_mx204)
    SCENARIO = 2  → two devices    (juniper_mx204 + juniper_mx80)
"""

import json
import os
from datetime import datetime

# ─────────────────────────────────────────────────────────────
# SCENARIO SWITCH
# ─────────────────────────────────────────────────────────────
SCENARIO = 2   # change to 2 for multi-device


# ─────────────────────────────────────────────────────────────
# Minimal GlobalConfig stub (mirrors lib/utilities.py)
# ─────────────────────────────────────────────────────────────
class GlobalConfig:
    device_results: dict = {}
    pre_check_timestamp  = ""
    vendor               = ""
    model                = ""
    version              = ""
    hostname             = ""
    session_log_path     = ""
    device_key           = ""
    commands: list       = []

global_config = GlobalConfig()


# ─────────────────────────────────────────────────────────────
# SCENARIO 1 — single device
# ─────────────────────────────────────────────────────────────
def load_scenario_1():
    global_config.vendor              = "juniper"
    global_config.model               = "mx204"
    global_config.hostname            = "router-test-01"
    global_config.version             = "23.4R2-S5.6"
    global_config.pre_check_timestamp = "2026-02-26_09-00-00"
    global_config.session_log_path    = "/logging/juniper_mx204.log"

    global_config.device_results = {
        "juniper_mx204": {
            "pre": [
                {
                    "command": "show arp no-resolve | no-more",
                    "output": (
                        "MAC Address       Address         Name                      Interface           Flags\n"
                        "00:00:5e:00:01:01 10.0.0.1        --                        et-0/0/0.0          none\n"
                        "00:00:5e:00:01:02 10.0.0.2        --                        et-0/0/1.0          none"
                    ),
                    "json_output": {
                        "total_entries": 2,
                        "entries": [
                            {"mac": "00:00:5e:00:01:01", "ip": "10.0.0.1", "interface": "et-0/0/0.0"},
                            {"mac": "00:00:5e:00:01:02", "ip": "10.0.0.2", "interface": "et-0/0/1.0"},
                        ]
                    }
                },
                {
                    "command": "show lldp neighbors | no-more",
                    "output": (
                        "Local Interface    Parent Interface    Chassis Id          Port info\n"
                        "et-0/0/0           -                   aa:bb:cc:dd:ee:ff   et-0/0/0"
                    ),
                    "json_output": {
                        "entries": [
                            {"local_interface": "et-0/0/0", "chassis_id": "aa:bb:cc:dd:ee:ff", "port_info": "et-0/0/0"}
                        ]
                    }
                },
                {
                    "command": "show bgp summary | no-more",
                    "output": "",          # empty output — first_line should be ""
                    "json_output": {}
                },
            ]
        }
    }


# ─────────────────────────────────────────────────────────────
# SCENARIO 2 — two devices
# ─────────────────────────────────────────────────────────────
def load_scenario_2():
    global_config.vendor              = "juniper"
    global_config.model               = "mx204"
    global_config.hostname            = "router-test-01"
    global_config.version             = "23.4R2-S5.6"
    global_config.pre_check_timestamp = "2026-02-26_09-00-00"
    global_config.session_log_path    = "/logging/juniper_mx204.log"

    global_config.device_results = {
        "juniper_mx204": {
            "pre": [
                {
                    "command": "show arp no-resolve | no-more",
                    "output": (
                        "MAC Address       Address         Name                      Interface           Flags\n"
                        "00:00:5e:00:01:01 10.0.0.1        --                        et-0/0/0.0          none"
                    ),
                    "json_output": {
                        "total_entries": 1,
                        "entries": [
                            {"mac": "00:00:5e:00:01:01", "ip": "10.0.0.1", "interface": "et-0/0/0.0"}
                        ]
                    }
                },
                {
                    "command": "show route summary | no-more",
                    "output": (
                        "Autonomous system number: 65000\n"
                        "inet.0: 120 destinations, 240 routes (118 active, 0 holddown, 2 hidden)"
                    ),
                    "json_output": {
                        "as_number": "65000",
                        "tables": [{"name": "inet.0", "destinations": 120, "routes": 240}]
                    }
                },
            ]
        },
        "juniper_mx80": {
            "pre": [
                {
                    "command": "show chassis alarms | no-more",
                    "output": "No alarms currently active",
                    "json_output": {"alarms": []}
                },
                {
                    "command": "show bgp summary | no-more",
                    "output": "",        # no output — pre_checks entry still included, output: ""
                    "json_output": {}
                },
            ]
        }
    }


# ─────────────────────────────────────────────────────────────
# The function under test
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
        # --- device_details ---
        device_details = {
            "device_key":           device_key,
            "vendor":               global_config.vendor,
            "model":                global_config.model,
            "hostname":             global_config.hostname,
            "version":              global_config.version,
            "pre_check_timestamp":  global_config.pre_check_timestamp,
        }

        # --- pre_checks ---
        pre_entries = phases.get("pre", [])
        pre_checks = []
        for entry in pre_entries:
            raw_output = entry.get("output", "") or ""
            first_line = raw_output.strip().splitlines()[0] if raw_output.strip() else ""
            pre_checks.append({
                "cmd":    entry.get("command", ""),
                "output": first_line,
                "json":   entry.get("json_output", {}),
            })

        output[device_key] = {
            "device_details": device_details,
            "pre_checks":     pre_checks,
        }

    # --- write file ---
    reports_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    file_path = os.path.join(reports_dir, f"{timestamp}.json")

    with open(file_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"[export] Summary written to {file_path}")


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if SCENARIO == 1:
        print("[temp] Loading SCENARIO 1 — single device (juniper_mx204)")
        load_scenario_1()
    elif SCENARIO == 2:
        print("[temp] Loading SCENARIO 2 — two devices (juniper_mx204 + juniper_mx80)")
        load_scenario_2()
    else:
        raise ValueError(f"Unknown SCENARIO={SCENARIO}. Use 1 or 2.")

    export_device_summary()
    print("[temp] Done.")
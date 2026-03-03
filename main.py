
import logging
import sys
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from prechecks import PreCheck
from lib.utilities import *
from parsers.junos.junos_mx80 import *
from pprint import pformat
from workflow_report_generator import generate_html_report
from parsers.junos_wrapper import *
from parsers.junos_wrapper import run_junos_parsers
import os

# NEW: use the wrapper from run_checks.py
from run_checks import execute_commands

MAX_THREADS = 5
PRECHECKS_ONLY = True   # <--- Run prechecks only; skip upgrade in main()


# ----------------------------------------------------
# Abort helper — call when any step fails
# ----------------------------------------------------

def abort(device_key, phase, subtask, error, logger):
    # Mark the failed subtask in the tracker
    log_task(device_key, phase, subtask, 'Failed', error)

    # Log + console
    logger.error(f"[{device_key}] FATAL [{phase}] '{subtask}': {error}")
    logger.error(f"[{device_key}] Aborting workflow — generating report")

    j = json.dumps(workflow_tracker, indent=2)
    logger.info(f"\n{j}")
    print("\n" + "=" * 60)
    print(f"WORKFLOW ABORTED for {device_key} — partial results (JSON):")
    print("=" * 60)
    print(j)
    print("=" * 60 + "\n")

    # Generate HTML report here (centralized on failure)
    try:
        path = generate_html_report(workflow_tracker, output_dir='reports')
        logger.info(f"[{device_key}] Report saved -> {path}")
        print(f"Report saved -> {path}")
    except Exception as e:
        logger.error(f"[{device_key}] Could not write HTML report: {e}")

    sys.exit(1)

def run_prechecks(device, logger):
    dev        = device["devices"][0]
    host       = dev["host"]
    vendor_lc  = dev["vendor"].lower()
    model_lc   = str(dev["model"]).lower().replace("-", "")
    device_key = f"{vendor_lc}_{model_lc}"
    device_type = dev.get("device_type")
    model       = dev.get("model")

    start_time = datetime.now()
    logger.info(f"[{device_key}] Prechecks started at {start_time}")

    # For filenames/JSON stamps if needed
    pre_check_timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    global_config.pre_check_timestamp = pre_check_timestamp

    # These are displayed in the report; log them here (not in main)
    log_task(device_key, 'pre-checks', 'read Yaml',    'Success', 'deviceDetails.yaml loaded successfully')
    log_task(device_key, 'pre-checks', 'start logger', 'Success', 'Logger initialised')

    precheck = PreCheck(device)

    try:
        # 1) Connect
        conn = precheck.connect(logger)
        print("CONNECTION...",conn)
        if not conn:
            abort(device_key, 'pre-checks', 'connection using credentials',
                  f'{host}: connect() returned None', logger)
        log_task(device_key, 'pre-checks', 'connection using credentials', 'Success',
                 f'{host}: Connected successfully', '')

        # 2) Show Version
        version_output = precheck.showVersion(conn, device_type, logger)
        print('version...', version_output)
        if not version_output:
            abort(device_key, 'pre-checks', 'show version',
                  f'{host}: showVersion() returned empty/False', logger)
        log_task(device_key, 'pre-checks', 'show version', 'Success',
                 f'{host}: show version retrieved','ABC')

        # 3) Execute Commands (+ parse) — via run_checks wrapper
        try:
            global_config.vendor     = vendor_lc
            global_config.device_key = device_key
            all_cmds                 = load_yaml("show_cmd_list.yaml")
            global_config.commands   = all_cmds[device_key]

            logger.info(f"[{device_key}] Executing pre-check show commands")
            exec_ok = execute_commands("pre", conn=conn, logger=logger)
            if not exec_ok:
                abort(device_key, 'pre-checks', 'executing show commands',
                      f'{host}: execute_commands() failed (collection/parsing)', logger)
            # NOTE: run_checks.push_to_tracker() logs:
            #   - 'executing show commands'
            #   - 'Parsing the data'
        except KeyError as e:
            abort(device_key, 'pre-checks', 'executing show commands',
                  f"{host}: Missing command list for vendor='{vendor_lc}' — {e}", logger)
        except Exception as e:
            abort(device_key, 'pre-checks', 'executing show commands',
                  f"{host}: execute_commands() exception — {e}", logger)
        '''
        # 4) Backup (config + logs)
        filename = f"{device_type}_{model}_{pre_check_timestamp}"
        logger.info(f"[{device_key}] Starting backup — filename: {filename}")
        prebackup = precheck.preBackup(conn, filename, logger)
        if not prebackup:
            abort(device_key, 'pre-checks', 'Backup Config',
                  f'{host}: preBackup() failed', logger)
        log_task(device_key, 'pre-checks', 'Backup Config', 'Success',
                 f'{host}: Backup complete')

        # 5) Validate MD5 checksum
        md5_ok = precheck.verifyChecksum(conn, logger)
        if not md5_ok:
            abort(device_key, 'pre-checks', 'Validate MD5 checksum',
                  f'{host}: MD5 checksum mismatch — image may be corrupted', logger)
        log_task(device_key, 'pre-checks', 'Validate MD5 checksum', 'Success',
                 f'{host}: Checksum verification PASSED')

        # 6) Storage Check
        storage = precheck.checkStorage(conn, logger)
        logger.info(f"[{device_key}] Storage result: {storage}")
        if not storage or storage.get('status') not in ('OK', 'SELECTED_FILES_DELETED'):
            abort(device_key, 'pre-checks', 'Storage Check (5GB threshold)',
                  f'{host}: Insufficient storage or cleanup failed. Result: {storage}', logger)
        log_task(device_key, 'pre-checks', 'Storage Check (5GB threshold)', 'Success',
                 f'{host}: Storage status {storage.get("status")}')

        # 7) Disable RE-PROTECT Filter
        filter_ok = precheck.disableReProtectFilter(conn, logger)
        if not filter_ok:
            abort(device_key, 'pre-checks', 'Disable Filter',
                  f'{host}: disableReProtectFilter() failed', logger)
        log_task(device_key, 'pre-checks', 'Disable Filter', 'Success',
                 f'{host}: RE-PROTECT filter disabled')
        '''
        logger.info(f"[{device_key}] All pre-checks passed")
        return True

    except SystemExit:
        raise
    except Exception as e:
        logger.error(f"[{device_key}] Precheck failed with unhandled exception: {e}")
        abort(device_key, 'pre-checks', 'unexpected error',
              f'{host}: Unhandled exception — {e}', logger)
        return False
    finally:
        precheck.disconnect(logger)
        end_time = datetime.now()
        logger.info(f"[{device_key}] Prechecks completed at {end_time}")



# ----------------------------------------------------
# Main Function — call ONLY prechecks (guarded)
# ----------------------------------------------------

def main():
    devices   = load_yaml("deviceDetails.yaml")
    dev       = devices["devices"][0]
    host      = dev["host"]
    vendor_lc = dev["vendor"].lower()
    model_lc  = str(dev["model"]).lower().replace("-", "")
    device_key = f"{vendor_lc}_{model_lc}"
    print()
    # Logger
    global_config.vendor = vendor_lc
    global_config.model  = dev["model"]
    logger = setup_logger("main")
    print("devicekey....", device_key)
    # Init tracker slot for this device
    if device_key not in workflow_tracker:
        init_device_tracker(device_key, host, vendor_lc, model_lc)
    print("workflow...",workflow_tracker)
    # Run prechecks (owns all log_task updates)
    logger.info(f"[{device_key}] Running pre-checks …")
    print("main devices...", devices)

    ok = run_prechecks(devices, logger)

    export_device_summary()

    try:
        path = generate_html_report(workflow_tracker, output_dir='reports')
        logger.info(f"[{device_key}] HTML report saved -> {path}")
        print(f"Report saved -> {path}")
    except Exception as e:
        logger.error(f"[{device_key}] Could not write HTML report: {e}")

    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
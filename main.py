(venv) colt@colt-UCSC-C220-M7S:~/Documents/MS1Automation$ cat main.py
import logging
import sys
import json
import traceback
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from prechecks import *
from lib.utilities import *
from parsers.juniper.juniper_mx204 import *
from pprint import pformat
from workflow_report_generator import generate_html_report
import os

MAX_THREADS = 5
PRECHECKS_ONLY = True   # <--- Run prechecks only; skip upgrade in main()


# ----------------------------------------------------
# Abort helper — call when any step fails
# ----------------------------------------------------

def abort(device_key, phase, subtask, error, logger, exc: Exception = None):
    log_line = ""
    if exc is not None:
        log_line = traceback.format_exc()

    log_task(device_key, phase, subtask, 'Failed', error, log_line)

    logger.error(f"[{device_key}] FATAL [{phase}] '{subtask}': {error}")
    if log_line:
        logger.error(f"[{device_key}] Traceback:\n{log_line}")
    logger.error(f"[{device_key}] Aborting workflow — generating report")

    j = json.dumps(workflow_tracker, indent=2)
    logger.info(f"\n{j}")
    print("\n" + "=" * 60)
    print(f"WORKFLOW ABORTED for {device_key} — partial results (JSON):")
    print("=" * 60)
    print(j)
    print("=" * 60 + "\n")

    try:
        path = generate_html_report(workflow_tracker, output_dir='reports')
        logger.info(f"[{device_key}] Report saved -> {path}")
        print(f"Report saved -> {path}")
    except Exception as e:
        logger.error(f"[{device_key}] Could not write HTML report:-{e}")

    sys.exit(1)


def run_prechecks(device, logger):
    dev        = device["devices"][0]
    host       = dev["host"]
    vendor_lc  = dev["vendor"].lower()
    model_lc   = str(dev["model"]).lower().replace("-", "")
    device_key = f"{vendor_lc}_{model_lc}"
    device_type = dev.get("device_type")
    model       = dev.get("model")
    print(host)
    start_time = datetime.now()
    logger.info(f"[{device_key}] Prechecks started at {start_time}")

    pre_check_timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    global_config.pre_check_timestamp = pre_check_timestamp

    log_task(device_key, 'pre-checks', 'read Yaml',    'Success', 'deviceDetails.yaml loaded successfully')
    log_task(device_key, 'pre-checks', 'start logger', 'Success', 'Logger initialised')

    precheck = PreCheck(device)

    try:
        # 1) Connect
        try:
            conn = precheck.connect(logger)
        except Exception as e:
            abort(device_key, 'pre-checks', 'connection using credentials',
                  f'{host}: connect() raised exception — {e}', logger, exc=e)

        print("CONNECTION...", conn)
        if not conn:
            abort(device_key, 'pre-checks', 'connection using credentials',
                  f'{host}: connect() returned None', logger)
        log_task(device_key, 'pre-checks', 'connection using credentials', 'Success',
                 f'{host}: Connected successfully', '')

        # 3) Execute Commands — 3-step pipeline
        try:
            global_config.vendor     = vendor_lc
            global_config.device_key = device_key
            all_cmds                 = load_yaml("show_cmd_list.yaml")
            global_config.commands   = all_cmds[device_key]

            logger.info(f"[{device_key}] Starting command pipeline — "
                        f"{len(global_config.commands)} command(s)")

            # ── STEP 1: collect raw output from device ────────────────
            entries = collect_outputs(
                device_key = device_key,
                vendor     = vendor_lc,
                commands   = global_config.commands,
                check_type = "pre",
                conn       = conn,
                log        = logger,
            )
            if not entries:
                logger.warning(f"[{device_key}] collect_outputs() returned no entries")

            # ── STEP 2: parse collected output ────────────────────────
            parse_ok = parse_outputs(
                device_key = device_key,
                vendor     = vendor_lc,
                check_type = "pre",
                log        = logger,
            )
            if not parse_ok:
                logger.warning(f"[{device_key}] one or more parsers failed — check JSON for details")

            # ── STEP 3: push results into workflow_tracker ────────────
            push_to_tracker(
                device_key = device_key,
                check_type = "pre",
                entries    = entries,
                parse_ok   = parse_ok,
                log        = logger,
            )

        except KeyError as e:
            abort(device_key, 'pre-checks', 'executing show commands',
                  f"{host}: Missing command list for device_key='{device_key}' — {e}",
                  logger, exc=e)
        except Exception as e:
            abort(device_key, 'pre-checks', 'executing show commands',
                  f"{host}: command pipeline exception — {e}", logger, exc=e)

        logger.info(f"[{device_key}] All pre-checks passed")
        return True

    except SystemExit:
        raise
    except Exception as e:
        logger.error(f"[{device_key}] Precheck failed with unhandled exception: {e}")
        abort(device_key, 'pre-checks', 'unexpected error',
              f'{host}: Unhandled exception — {e}', logger, exc=e)
        return False
    finally:
        precheck.disconnect(logger)
        end_time = datetime.now()
        logger.info(f"[{device_key}] Prechecks completed at {end_time}")


# ----------------------------------------------------
# Main Function
# ----------------------------------------------------

def main():
    devices    = load_yaml("deviceDetails.yaml")
    dev        = devices["devices"][0]
    host       = dev["host"]
    vendor_lc  = dev["vendor"].lower()
    model_lc   = str(dev["model"]).lower().replace("-", "")
    device_key = f"{vendor_lc}_{model_lc}"

    global_config.vendor = vendor_lc
    global_config.model  = dev["model"]
    logger = setup_logger("main")
    print("devicekey....", device_key)

    if device_key not in workflow_tracker:
        init_device_tracker(device_key, host, vendor_lc, model_lc)
    print("workflow...", workflow_tracker)

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
(venv) colt@colt-UCSC-C220-M7S:~/Documents/MS1Automation$ cat

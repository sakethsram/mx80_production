import logging
import sys
import json
import traceback
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from prechecks import *
from lib.utilities import *
from parsers.juniper.juniper_mx204 import *
from pprint import pformat
from workflow_report_generator import generate_html_report
import os

MAX_THREADS    = 5
PRECHECKS_ONLY = True   # <--- Run prechecks only; skip upgrade in main()


# ----------------------------------------------------
# run_prechecks — runs inside a thread
# ----------------------------------------------------

def run_prechecks(dev, device_key, logger):
    tid         = threading.get_ident()
    host        = dev["host"]
    vendor_lc   = dev["vendor"].lower()
    model_lc    = str(dev["model"]).lower().replace("-", "")
    device_type = dev.get("device_type")

    logger.info(f"[THREAD-{tid}] [{device_key}] Prechecks started at {datetime.now()}")
    global_config.pre_check_timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    log_task(device_key, 'pre-checks', 'read Yaml',    'Success', 'deviceDetails.yaml loaded successfully')
    log_task(device_key, 'pre-checks', 'start logger', 'Success', 'Logger initialised')

    precheck = PreCheck({"devices": [dev]})

    try:
        # ── STEP 1: Connect ───────────────────────────────────────────
        try:
            conn = precheck.connect(logger)
        except Exception as e:
            logger.error(f"[THREAD-{tid}] [{device_key}] FATAL connect failed: {e}")
            log_task(device_key, 'pre-checks', 'connection using credentials', 'Failed',
                     f'{host}: connect() raised exception — {e}')
            return False

        if not conn:
            logger.error(f"[THREAD-{tid}] [{device_key}] FATAL connect() returned None")
            log_task(device_key, 'pre-checks', 'connection using credentials', 'Failed',
                     f'{host}: connect() returned None')
            return False

        log_task(device_key, 'pre-checks', 'connection using credentials', 'Success',
                 f'{host}: Connected successfully', '')

        try:
            # ── STEP 2: Load commands ─────────────────────────────────
            global_config.vendor     = vendor_lc
            global_config.device_key = device_key
            all_cmds                 = load_yaml("show_cmd_list.yaml")
            global_config.commands   = all_cmds[device_key]

            logger.info(f"[THREAD-{tid}] [{device_key}] Starting command pipeline — {len(global_config.commands)} command(s)")

            # ── STEP 3: Collect outputs ───────────────────────────────
            entries = collect_outputs(
                device_key=device_key, vendor=vendor_lc,
                commands=global_config.commands, check_type="pre",
                conn=conn, log=logger,
            )
            if not entries:
                logger.warning(f"[THREAD-{tid}] [{device_key}] collect_outputs() returned no entries")
            
            # ── STEP 4: Parse outputs ─────────────────────────────────
            parse_ok = parse_outputs(
                device_key=device_key, vendor=vendor_lc,
                check_type="pre", log=logger,
            )
            if not parse_ok:
                logger.warning(f"[THREAD-{tid}] [{device_key}] one or more parsers failed — continuing")

            # ── STEP 5: Push to tracker ───────────────────────────────
            push_to_tracker(
                device_key=device_key, check_type="pre",
                entries=entries, parse_ok=parse_ok, log=logger,
            )

            # ── STEP 6: Update device info from show version ──────────
            try:
                update_device_info_from_show_version(device_key, vendor_lc, logger)
                log_task(device_key, 'pre-checks', 'show version', 'Success',
                         'hostname and version extracted from show version output')
            except Exception as e:
                logger.error(f"[THREAD-{tid}] [{device_key}] Could not extract show version info: {e}")
                log_task(device_key, 'pre-checks', 'show version', 'Failed',
                         f'Could not extract: {e}')

        except KeyError as e:
            logger.error(f"[THREAD-{tid}] [{device_key}] FATAL missing command list: {e}")
            log_task(device_key, 'pre-checks', 'executing show commands', 'Failed',
                     f"{host}: Missing command list for device_key='{device_key}' — {e}")
            return False

        except Exception as e:
            logger.error(f"[THREAD-{tid}] [{device_key}] FATAL command pipeline: {e}")
            log_task(device_key, 'pre-checks', 'executing show commands', 'Failed',
                     f"{host}: command pipeline exception — {e}")
            return False

        logger.info(f"[THREAD-{tid}] [{device_key}] All pre-checks passed")
        return True

    except Exception as e:
        logger.error(f"[THREAD-{tid}] [{device_key}] Unhandled exception: {e}")
        return False

    finally:
        precheck.disconnect(logger)
        logger.info(f"[THREAD-{tid}] [{device_key}] Prechecks completed at {datetime.now()}")


# ----------------------------------------------------
# Main Function
# ----------------------------------------------------

def main():
    devices  = load_yaml("deviceDetails.yaml")
    all_devs = devices["devices"]

    global_config.vendor = all_devs[0]["vendor"].lower()
    global_config.model  = all_devs[0]["model"]
    main_logger = setup_logger("main")

    # ── Init tracker + per-device loggers BEFORE threads ──────────────
    loggers = {}
    for dev in all_devs:
        vendor_lc  = dev["vendor"].lower()
        model_lc   = str(dev["model"]).lower().replace("-", "")
        ip_clean   = dev["host"].replace(".", "_")
        device_key = f"{ip_clean}_{vendor_lc}_{model_lc}"

        global_config.vendor = vendor_lc
        global_config.model  = dev["model"]

        if device_key not in workflow_tracker:
            init_device_tracker(device_key, dev["host"], vendor_lc, model_lc)

        loggers[device_key] = setup_logger(device_key)
        main_logger.info(f"[MAIN] Initialised tracker for [{device_key}] host={dev['host']}")

    main_logger.info(f"[MAIN] Spawning threads for {len(all_devs)} device(s)")

    # ── One thread per device ──────────────────────────────────────────
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        future_to_key = {}
        for dev in all_devs:
            vendor_lc  = dev["vendor"].lower()
            model_lc   = str(dev["model"]).lower().replace("-", "")
            ip_clean   = dev["host"].replace(".", "_")
            device_key = f"{ip_clean}_{vendor_lc}_{model_lc}"
            future = executor.submit(run_prechecks, dev, device_key, loggers[device_key])
            future_to_key[future] = device_key

        for future in as_completed(future_to_key):
            device_key = future_to_key[future]
            try:
                ok = future.result()
                main_logger.info(f"[MAIN] {device_key} -> {'passed' if ok else 'failed'}")
            except Exception as e:
                main_logger.error(f"[MAIN] {device_key} thread exception: {e}")

    # ── All devices done — generate final report ───────────────────────
    try:
        export_device_summary()
        path = generate_html_report(workflow_tracker, output_dir='reports')
        main_logger.info(f"All devices done. Report saved -> {path}")
        print(f"Report saved -> {path}")
    except Exception as e:
        main_logger.error(f"Could not write final HTML report: {e}")

    sys.exit(0)


if __name__ == "__main__":
    main()
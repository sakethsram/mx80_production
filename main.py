import logging
import sys
import json
import traceback
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
# from prechecks import *
from lib.utilities import *
from parsers.juniper.juniper_mx204 import *
import os

MAX_THREADS    = 5
PRECHECKS_ONLY = True   # <--- Run prechecks only; skip upgrade in main()


# ----------------------------------------------------
# execute_show_commands
# ----------------------------------------------------
def execute_show_commands(device_key, vendor, model, conn, check_type, logger):
    commands = load_commands(vendor, model, logger)
    if not commands:
        logger.error(f"[{device_key}] execute_show_commands — no commands loaded, aborting")
        return False
    entries  = collect_outputs(device_key, vendor, commands, check_type, conn, logger)
    if not entries:
        logger.warning(f"[{device_key}] execute_show_commands — collect_outputs returned nothing")
    parse_ok = parse_outputs(device_key, vendor, check_type, logger)
    if not parse_ok:
        logger.warning(f"[{device_key}] execute_show_commands — one or more parsers failed")
    return parse_ok


# ----------------------------------------------------
# run_prechecks — runs inside a thread
# ----------------------------------------------------
def run_prechecks(dev, device_key, logger):
    tid         = threading.get_ident()
    host        = dev["host"]
    vendor_lc   = dev["vendor"].lower()
    model_lc    = str(dev["model"]).lower().replace("-", "")
    device_type = dev.get("device_type")
    conn = None
    logger.info(f"[THREAD-{tid}] [{device_key}] Prechecks started at {datetime.now()}")

    try:
        # ── STEP 1: Connect ───────────────────────────────────────────
        try:
            conn = connect(device_key, dev, logger) 
        except Exception as e:
            logger.error(f"[THREAD-{tid}] [{device_key}] FATAL connect failed: {e}")
            merge_thread_result(device_key, device_results.get(device_key, {"pre": [], "post": [], "upgrade": {}, "device_info": {}}))
            return False

        if not conn:
            logger.error(f"[THREAD-{tid}] [{device_key}] FATAL connect() returned None")
            merge_thread_result(device_key, device_results.get(device_key, {"pre": [], "post": [], "upgrade": {}, "device_info": {}}))
            return False

        try:
            # ── STEP 2: Execute show commands ─────────────────────────
            exec_ok = execute_show_commands(device_key, vendor_lc, model_lc, conn, "pre", logger)

            # ── STEP 3: Merge results ─────────────────────────────────
            thread_result = {
                "pre":         device_results.get(device_key, {}).get("pre", []),
                "device_info": device_results.get(device_key, {}).get("device_info", {}),
                "post":        [],
                "upgrade":     {},
            }
            merge_thread_result(device_key, thread_result)

        except Exception as e:
            logger.error(f"[THREAD-{tid}] [{device_key}] FATAL command pipeline: {e}")
            merge_thread_result(device_key, device_results.get(device_key, {"pre": [], "post": [], "upgrade": {}, "device_info": {}}))
            return False

        logger.info(f"[THREAD-{tid}] [{device_key}] All pre-checks passed")
        return True

    except Exception as e:
        logger.error(f"[THREAD-{tid}] [{device_key}] Unhandled exception: {e}")
        merge_thread_result(device_key, device_results.get(device_key, {"pre": [], "post": [], "upgrade": {}, "device_info": {}}))
        return False

    finally:
        disconnect(device_key, logger)
        logger.info(f"[THREAD-{tid}] [{device_key}] Prechecks completed at {datetime.now()}")

# ----------------------------------------------------
# Main Function
# ----------------------------------------------------

def main():
    devices  = load_yaml("deviceDetails.yaml")
    all_devs = devices["devices"]

    first_vendor = all_devs[0]["vendor"].lower()
    first_model  = all_devs[0]["model"]
    main_logger  = setup_logger("main", vendor=first_vendor, model=first_model)

    # ── Init device_results + per-device loggers BEFORE threads ───────
    loggers = {}
    for dev in all_devs:
        vendor_lc  = dev["vendor"].lower()
        model_lc   = str(dev["model"]).lower().replace("-", "")
        ip_clean   = dev["host"].replace(".", "_")
        device_key = f"{ip_clean}_{vendor_lc}_{model_lc}"

        init_device_results(device_key, dev["host"], vendor_lc, model_lc, dev)
        loggers[device_key] = setup_logger(device_key, vendor=vendor_lc, model=model_lc)
        main_logger.info(f"[MAIN] Initialised device_results for [{device_key}] host={dev['host']}")

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

    # ── All devices done — export results ─────────────────────────────
    for dev in all_devs:
        vendor_lc  = dev["vendor"].lower()
        model_lc   = str(dev["model"]).lower().replace("-", "")
        ip_clean   = dev["host"].replace(".", "_")
        device_key = f"{ip_clean}_{vendor_lc}_{model_lc}"
        export_device_summary(device_key)

    main_logger.info(f"[MAIN] JSON files location -> {os.path.join(os.getcwd(), 'precheck_jsons')}")

    sys.exit(0)


if __name__ == "__main__":
    main()

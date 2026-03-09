import logging
import sys
import json
import traceback
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from lib.utilities import *
from parsers.juniper.juniper_mx204 import *
import os

MAX_THREADS    = 5
PRECHECKS_ONLY = True


# ----------------------------------------------------
# execute_show_commands
# ----------------------------------------------------
def execute_show_commands(device_key, vendor, model, conn, check_type, logger):
    commands = load_commands(vendor, model, logger)
    if not commands:
        logger.error(f"[{device_key}] execute_show_commands — no commands loaded, aborting")
        return False
    entries = collect_outputs(device_key, vendor, commands, check_type, conn, logger)
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
            if not conn:
                raise ConnectionError("connect() returned None")
        except Exception as e:
            logger.error(f"[{device_key}] STEP 1 CONNECT failed — {e}")
            device_results[device_key]["pre"]["connect"]["exception"] = str(e)
            return False

        # ── STEP 2: Execute show commands ─────────────────────────────
        try:
            exec_ok = execute_show_commands(device_key, vendor_lc, model_lc, conn, "pre", logger)
            if not exec_ok:
                raise RuntimeError("execute_show_commands returned False")
        except Exception as e:
            logger.error(f"[{device_key}] STEP 2 EXECUTE failed — {e}")
            device_results[device_key]["pre"]["execute_show_commands"]["exception"] = str(e)
            return False

        # ── STEP 3: Show version ──────────────────────────────────────
        # TODO: Run `show version` (or equivalent) on the device via conn.
        #       Parse the output to extract current OS version, platform info.
        #       Store result into:
        #           device_results[device_key]["pre"]["show_version"]
        #       If version is incompatible or parse fails, log and return False.

   
        try:
            precheck = PreCheck(dev)
            min_disk_gb=dev.get("min_disk_gb")
            storage = precheck.checkStorage(conn, min_disk_gb)
            # always store the returned dict
            device_results[device_key]["pre"]["check_storage"] = storage

            # if insufficient → fail this step
            if not storage.get("sufficient", False):
                raise RuntimeError(storage.get("exception", "Storage insufficient"))

        except Exception as e:
            logger.error(f"[{device_key}] STEP 4 STORAGE failed — {e}")
            device_results[device_key]["pre"]["check_storage"]["exception"] = str(e)
            precheck.disconnect(logger)
            return False



        # ── STEP 5: Backup active running filesystem ──────────────────
        # TODO: Identify the active boot disk/partition on the device.
        #       Check for available snapshot or backup slots across relevant disks.
        #       Trigger a snapshot/backup of the active running filesystem on-device.
        #       Verify the backup completed successfully (status, size, integrity).
        #       Store result into:
        #           device_results[device_key]["pre"]["backup_active_filesystem"]
        #       If backup fails or no valid slot found, log and return False.

        # ── STEP 6: Backup running config (device → NMS) ─────────────
        # TODO: Fetch the running configuration from the device via conn
        #       (e.g. `show configuration | no-more` for Juniper).
        #       Write / push the config to the NMS (file server, TFTP, SCP, etc.).
        #       Confirm the file arrived on the NMS side (size / md5 sanity check).
        #       Store result into:
        #           device_results[device_key]["pre"]["backup_running_config"]
        #       If transfer fails, log and return False.

        # ── STEP 7: Transfer upgrade image (NMS → device) ────────────
        # TODO: Initiate SCP / TFTP transfer of the upgrade image from NMS to device.
        #       Monitor transfer progress where possible; enforce a timeout.
        #       Confirm the file is present on the device after transfer.
        #       Store result into:
        #           device_results[device_key]["pre"]["transfer_image"]
        #       If transfer fails or times out, log and return False.

        # ── STEP 8: Validate MD5 checksum ────────────────────────────
        # TODO: Run checksum command on device for the transferred image
        #       (e.g. `file checksum md5 <path>`).
        #       Compare the computed MD5 against the known-good reference value
        #       (sourced from NMS / manifest / config).
        #       Store result into:
        #           device_results[device_key]["pre"]["validate_md5"]
        #       If checksum mismatch, log a critical error and return False.

        # ── STEP 9: Merge results ─────────────────────────────────────
        try:
            thread_result = {
                "pre":         device_results.get(device_key, {}).get("pre", {}),
                "device_info": device_results.get(device_key, {}).get("device_info", {}),
                "post":        [],
                "upgrade":     {},
            }
            merge_thread_result(device_key, thread_result)
        except Exception as e:
            logger.error(f"[{device_key}] STEP 9 STORE failed — {e}")
            return False

        logger.info(f"[THREAD-{tid}] [{device_key}] All pre-checks passed")
        return True

    except Exception as e:
        logger.error(f"[THREAD-{tid}] [{device_key}] Unhandled exception: {e}")
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
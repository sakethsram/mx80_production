import logging
import sys
import threading
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from lib.utilities import *
from prechecks import PreCheck

MAX_THREADS    = 5
PRECHECKS_ONLY = True


# ─────────────────────────────────────────────────────────────────────────────
# execute_show_commands
# ─────────────────────────────────────────────────────────────────────────────
def execute_show_commands(device_key, vendor, model, conn, check_type, logger):
    commands = load_commands(vendor, model, logger)
    if not commands:
        logger.error(f"[{device_key}] execute_show_commands — no commands loaded, aborting")
        return False

    entries = collect_outputs(device_key, vendor, commands, check_type, conn, logger)
    if not entries:
        logger.warning(f"[{device_key}] execute_show_commands — collect_outputs returned nothing")

    parse_outputs(device_key, vendor, check_type, logger)
    return True


# ─────────────────────────────────────────────────────────────────────────────
# run_prechecks — executes inside a worker thread (one per device)
# ─────────────────────────────────────────────────────────────────────────────
def run_prechecks(dev: dict, device_key: str, logger):
    tid = threading.get_ident()
    logger.info(f"[THREAD-{tid}] [{device_key}] Prechecks started at {datetime.now()}")

    vendor_lc = dev["vendor"].lower()
    model_lc  = str(dev["model"]).lower().replace("-", "")

    try:
        # ── STEP 1: Connect ───────────────────────────────────────────────────
        try:
            conn = connect(device_key, dev, logger)
            if not conn:
                raise ConnectionError("connect() returned None")
        except Exception as e:
            logger.error(f"[{device_key}] STEP 1 CONNECT failed — {e}")
            device_results[device_key]["pre"]["connect"]["exception"] = str(e)
            return False

       ## ── STEP 2: Execute show commands ─────────────────────────────────────
        try:
            exec_ok = execute_show_commands(
                device_key, vendor_lc, model_lc, conn, "pre", logger
            )
            if not exec_ok:
                raise RuntimeError("execute_show_commands returned False")
        except Exception as e:
            logger.error(f"[{device_key}] STEP 2 EXECUTE failed — {e}")
            device_results[device_key]["pre"]["execute_show_commands"]["exception"] = str(e)
            return False

       # # ── STEP 3: Show version ──────────────────────────────────────────────
        # TODO: Run `show version` (or equivalent) on the device via conn.
        #       Parse the output to extract current OS version, platform info.
        #       Store result into:
        #           device_results[device_key]["pre"]["show_version"]
        #       If version is incompatible or parse fails, log and return False.

        # ── STEP 4: Check storage ─────────────────────────────────────────────
        try:
            precheck    = PreCheck(dev)
            min_disk_gb = dev.get("min_disk_gb")

            storage = precheck.checkStorage(conn, min_disk_gb)

            # Store the returned dict verbatim
            device_results[device_key]["pre"]["check_storage"] = storage

            if not storage.get("sufficient", False):
                raise RuntimeError(
                    storage.get("exception", "Storage insufficient — see check_storage for details")
                )

        except Exception as e:
            logger.error(f"[{device_key}] STEP 4 STORAGE failed — {e}")
            device_results[device_key]["pre"]["check_storage"]["exception"] = str(e)
            return False
        try:
            t = PreCheck(dev)
            backup_disk = t.preBackupDisk(conn)
            device_results[device_key]["pre"]["backup_active_filesystem"] = backup_disk

            if backup_disk.get("status") == "failed":
                raise RuntimeError(backup_disk.get("exception", "Disk backup failed"))

        except Exception as e:
            logger.error(f"[{device_key}] STEP 5 BACKUP DISK failed — {e}")
            device_results[device_key]["pre"]["backup_active_filesystem"]["exception"] = str(e)
            return False


        # ── STEP 6: Backup running config (device → NMS) ─────────────────────
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            filename  = f"{vendor_lc}_{model_lc}_{timestamp}"
            t         = PreCheck(dev)
            backup    = t.preBackup(conn, filename)
            device_results[device_key]["pre"]["backup_running_config"] = backup

            if backup.get("status") == "failed":
                raise RuntimeError(backup.get("exception", "Config backup failed"))

        except Exception as e:
            logger.error(f"[{device_key}] STEP 6 BACKUP CONFIG failed — {e}")
            device_results[device_key]["pre"]["backup_running_config"]["exception"] = str(e)
            return False

           # ── STEP 7: Transfer upgrade image (NMS → device) ────────────────────
        try:
            image_details = dev.get("imageDetails", [])
            target        = image_details[-1]
            target_image  = target.get("image")
            image_path    = dev.get("image_path")

            t        = PreCheck(dev)
            transfer = t.transferImage(conn, image_path, target_image)
            device_results[device_key]["pre"]["transfer_image"] = transfer

            if transfer.get("status") == "failed":
                raise RuntimeError(transfer.get("exception", "Image transfer failed"))

        except Exception as e:
            logger.error(f"[{device_key}] STEP 7 TRANSFER IMAGE failed — {e}")
            device_results[device_key]["pre"]["transfer_image"]["exception"] = str(e)
            return False

        # #── STEP 8: Validate MD5 checksum ────────────────────────────────────
        try:
            expected_checksum = target.get("checksum")

            t        = PreCheck(dev)
            checksum = t.verifyChecksum(conn, target_image, expected_checksum)
            device_results[device_key]["pre"]["validate_md5"] = checksum

            if not checksum.get("match", False):
                raise RuntimeError(checksum.get("exception", "Checksum mismatch"))

        except Exception as e:
            logger.error(f"[{device_key}] STEP 8 CHECKSUM failed — {e}")
            # Safely set the result even if verifyChecksum never returned
            device_results[device_key]["pre"]["validate_md5"] = {
                "status":    "failed",
                "exception": str(e),
                "match":     False,
            }
            return False
        ## ── STEP 9: Disable RE protect filter ────────────────────────────────
        # try:
        #     t      = PreCheck(dev)
        #     result = t.disableReProtectFilter(conn, logger)
        #     device_results[device_key]["pre"]["disable_re_protect_filter"] = {
        #         "status":    "ok" if result else "failed",
        #         "exception": "" if result else "disableReProtectFilter returned False",
        #     }
        #     if not result:
        #         raise RuntimeError("disableReProtectFilter returned False")

        # except Exception as e:
        #     logger.error(f"[{device_key}] STEP 9 DISABLE RE PROTECT FILTER failed — {e}")
        #     device_results[device_key]["pre"]["disable_re_protect_filter"]["exception"] = str(e)
        #     return False
        # ── STEP 10: Merge results ─────────────────────────────────────────────
        try:
            thread_result = {
                "pre":         device_results.get(device_key, {}).get("pre", {}),
                "device_info": device_results.get(device_key, {}).get("device_info", {}),
                "post":        [],
                "upgrade":     {},
            }
            merge_thread_result(device_key, thread_result)
        except Exception as e:
            logger.error(f"[{device_key}] STEP 9 MERGE failed — {e}")
            return False

        logger.info(f"[THREAD-{tid}] [{device_key}] All pre-checks passed")
        return True

    except Exception as e:
        logger.error(f"[THREAD-{tid}] [{device_key}] Unhandled exception: {e}")
        return False

    finally:
        disconnect(device_key, logger)
        logger.info(f"[THREAD-{tid}] [{device_key}] Prechecks completed at {datetime.now()}")


# ─────────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    devices          = load_yaml("deviceDetails.yaml")
    all_devs         = devices["devices"]
    accepted_vendors = devices.get("accepted_vendors")

    for dev in all_devs:
        dev["accepted_vendors"] = accepted_vendors

    first_vendor = all_devs[0]["vendor"].lower()
    first_model  = all_devs[0]["model"]
    main_logger  = setup_logger("main", vendor=first_vendor, model=first_model)

    # ── Initialise device_results + per-device loggers (before threads) ───────
    loggers = {}
    for dev in all_devs:
        vendor_lc  = dev["vendor"].lower()
        model_lc   = str(dev["model"]).lower().replace("-", "")
        ip_clean   = dev["host"].replace(".", "_")
        device_key = f"{ip_clean}_{vendor_lc}_{model_lc}"

        init_device_results(device_key, dev["host"], vendor_lc, model_lc, dev)
        loggers[device_key] = setup_logger(device_key, vendor=vendor_lc, model=model_lc)
        main_logger.info(
            f"[MAIN] Initialised device_results for [{device_key}] host={dev['host']}"
        )

    main_logger.info(f"[MAIN] Spawning threads for {len(all_devs)} device(s)")

    # ── One thread per device ─────────────────────────────────────────────────
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
                main_logger.info(
                    f"[MAIN] {device_key} -> {'passed' if ok else 'FAILED'}"
                )
            except Exception as e:
                main_logger.error(f"[MAIN] {device_key} thread raised: {e}")

    # ── All devices done — export per-device JSON summaries ───────────────────
    for dev in all_devs:
        vendor_lc  = dev["vendor"].lower()
        model_lc   = str(dev["model"]).lower().replace("-", "")
        ip_clean   = dev["host"].replace(".", "_")
        device_key = f"{ip_clean}_{vendor_lc}_{model_lc}"
        export_device_summary(device_key)

    main_logger.info(
        f"[MAIN] JSON files location -> {os.path.join(os.getcwd(), 'precheck_jsons')}"
    )
    sys.exit(0)

if __name__ == "__main__":
    main()
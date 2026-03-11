# main.py
import logging
import sys
import threading
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from lib.utilities import *
from prechecks import PreCheck
from upgrade import Upgrade, run_upgrade, run_rollback

MAX_THREADS = 5


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
# run_prechecks
# Phase 1 — runs on the SAME thread as run_upgrade (see run_device_pipeline).
# conn is established ONCE before this is called and passed straight through.
# ─────────────────────────────────────────────────────────────────────────────
def run_prechecks(conn, dev: dict, device_key: str, logger):
    tid         = threading.get_ident()
    vendor_lc   = dev["vendor"].lower()
    model_lc    = str(dev["model"]).lower().replace("-", "")
    host        = dev.get("host")
    min_disk_gb = dev.get("min_disk_gb")

    logger.info(f"[THREAD-{tid}] [{device_key}] Prechecks started at {datetime.now()}")

    try:
        # ── STEP 1: Execute show commands (pre) ───────────────────────────────
        print(f"[{device_key}] Executing show commands")
        logger.info(f"[{device_key}] Executing show commands")

        exec_ok = execute_show_commands(device_key, vendor_lc, model_lc, conn, "pre", logger)
        if not exec_ok:
            msg = f"{host}: execute_show_commands() failed (collections/parsing)"
            logger.error(f"[{device_key}] STEP 1 EXECUTE failed — {msg}")
            device_results[device_key]["pre"]["execute_show_commands"]["exception"] = msg
            return False

        logger.info(f"[{device_key}] STEP 1 execute_show_commands OK")

        # ── STEP 2: Show version ──────────────────────────────────────────────
        try:
            ok = get_show_version(device_key, conn, vendor_lc, logger)
            if not ok:
                raise RuntimeError("get_show_version returned False")
        except Exception as e:
            logger.error(f"[{device_key}] STEP 2 SHOW VERSION failed — {e}")
            device_results[device_key]["pre"]["show_version"]["exception"] = str(e)
            logger.warning(f"[{device_key}] STEP 2 failed but continuing prechecks")

        # ── STEP 3: Check storage ─────────────────────────────────────────────
        precheck = PreCheck(dev)
        storage  = precheck.checkStorage(conn, min_disk_gb, logger)
        if not storage:
            msg = f"{host}: checkStorage() failed"
            logger.error(f"[{device_key}] STEP 3 STORAGE failed — {msg}")
            device_results[device_key]["pre"]["check_storage"]["exception"] = msg
            return False

        device_results[device_key]["pre"]["check_storage"] = storage
        logger.info(f"[{device_key}] STEP 3 storage OK")

        # ── STEP 4: Backup active filesystem (disk1 → disk2) ─────────────────
        try:
            backup_disk = precheck.preBackupDisk(conn, logger)
            device_results[device_key]["pre"]["backup_active_filesystem"] = backup_disk

            if backup_disk.get("status") == "failed":
                raise RuntimeError(backup_disk.get("exception", "Disk backup failed"))
        except Exception as e:
            logger.error(f"[{device_key}] STEP 4 BACKUP DISK failed — {e}")
            device_results[device_key]["pre"]["backup_active_filesystem"]["exception"] = str(e)
            return False

        logger.info(f"[{device_key}] STEP 4 backup disk OK")

        # ── STEP 5: Backup running config (device → NMS) ─────────────────────
        try:
            pre_check_timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            filename            = f"{vendor_lc}_{model_lc}_{pre_check_timestamp}"
            backup              = precheck.preBackup(conn, filename, logger)
            device_results[device_key]["pre"]["backup_running_config"] = backup

            if not backup:
                raise RuntimeError("preBackup returned False")
            if isinstance(backup, dict) and backup.get("status") == "failed":
                raise RuntimeError(backup.get("exception", "Config backup failed"))
        except Exception as e:
            logger.error(f"[{device_key}] STEP 5 BACKUP CONFIG failed — {e}")
            device_results[device_key]["pre"]["backup_running_config"]["exception"] = str(e)
            return False

        logger.info(f"[{device_key}] STEP 5 backup config OK")

        # ── STEP 6: Transfer upgrade image (NMS → device) ────────────────────
        try:
            image_details = dev.get("imageDetails", [])
            target        = image_details[-1]
            target_image  = target.get("image")
            image_path    = dev.get("image_path")

            transfer = precheck.transferImage(conn, image_path, target_image, logger)
            device_results[device_key]["pre"]["transfer_image"] = transfer

            if transfer.get("status") == "failed":
                raise RuntimeError(transfer.get("exception", "Image transfer failed"))
        except Exception as e:
            logger.error(f"[{device_key}] STEP 6 TRANSFER IMAGE failed — {e}")
            device_results[device_key]["pre"]["transfer_image"]["exception"] = str(e)
            return False

        logger.info(f"[{device_key}] STEP 6 transfer image OK")

        # ── STEP 7: Verify MD5 checksum for every image in imageDetails ───────
        image_details = dev.get("imageDetails", [])
        print(f"[STEP 7] image_details       = {image_details}")
        print(f"[STEP 7] number of images    = {len(image_details)}")

        for i, img_entry in enumerate(image_details):
            target_image      = img_entry.get("image")
            expected_checksum = img_entry.get("checksum")

            print(f"[STEP 7] ── image [{i}] ──────────────────────────────────")
            print(f"[STEP 7] target_image      = {target_image}")
            print(f"[STEP 7] expected_checksum = {expected_checksum}")

            try:
                checksum_result = precheck.verifyChecksum(conn, target_image, expected_checksum, logger)

                print(f"[STEP 7] checksum_result   = {checksum_result}")

                device_results[device_key]["pre"]["verify_checksum"][i].update({
                    "status":    checksum_result.get("status"),
                    "exception": checksum_result.get("exception", ""),
                    "expected":  checksum_result.get("expected", ""),
                    "computed":  checksum_result.get("computed", ""),
                    "match":     checksum_result.get("match", False),
                })

                if not checksum_result.get("match"):
                    print(f"[STEP 7] FAILED for image [{i}]: {target_image}")
                    logger.error(f"[{device_key}] STEP 7 VERIFY CHECKSUM failed — {target_image}")
                    return False

                print(f"[STEP 7] image [{i}] checksum OK — {target_image}")
                logger.info(f"[{device_key}] STEP 7 [{i}] checksum OK — {target_image}")

            except Exception as e:
                logger.error(f"[{device_key}] STEP 7 exception for image [{i}] {target_image} — {e}")
                print(f"[STEP 7] EXCEPTION image [{i}]: {e}")
                device_results[device_key]["pre"]["verify_checksum"][i]["exception"] = str(e)
                return False

        logger.info(f"[{device_key}] STEP 7 all checksums passed")

        # ── STEP 8: Merge pre results into device_results ─────────────────────
        try:
            thread_result = {
                "pre":         device_results.get(device_key, {}).get("pre", {}),
                "device_info": device_results.get(device_key, {}).get("device_info", {}),
                "post":        {},
                "upgrade":     device_results.get(device_key, {}).get("upgrade", {}),
            }
            merge_thread_result(device_key, thread_result)
        except Exception as e:
            logger.error(f"[{device_key}] STEP 8 MERGE failed — {e}")
            return False

        logger.info(f"[THREAD-{tid}] [{device_key}] All pre-checks passed")
        return True

    except Exception as e:
        logger.error(f"[THREAD-{tid}] [{device_key}] run_prechecks unhandled exception: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# run_device_pipeline
#
# ONE thread per device — owns everything from connect to report.
# Thread lifecycle:
#
#   ThreadPoolExecutor (max 5 threads)
#       └─ Thread-N  ←── ONE thread per device, never shared
#             │
#             ├─ init_device_results()       set up JSON slots
#             ├─ setup_logger()              per-device log file
#             ├─ vendor check
#             ├─ connect()                   SINGLE conn for pre-checks
#             │
#             ├─ PHASE 1: run_prechecks()    uses pre-check conn
#             │     steps 1-8 run on this thread with this conn
#             │
#             ├─ PHASE 2: run_upgrade()      receives same conn
#             │     ├─ hop 0: imageUpgrade() → systemReboot()
#             │     │           └─ reconnect_and_verify()
#             │     │                 disconnect() old conn
#             │     │                 Upgrade.connect() → new conn
#             │     │                 show version
#             │     │                 write hops[0]['connect']
#             │     ├─ hop 1: imageUpgrade() → systemReboot()
#             │     │           └─ reconnect_and_verify() (same pattern)
#             │     └─ (rollback if any hop fails)
#             │
#             └─ finally:
#                   export_device_summary()  JSON + HTML report
#                   disconnect()             clean up last conn
#
# ─────────────────────────────────────────────────────────────────────────────
def run_device_pipeline(dev: dict, accepted_vendors: list):
    vendor     = dev.get("vendor").lower()
    model      = str(dev.get("model")).lower().replace("-", "")
    host       = dev.get("host")
    ip_clean   = host.replace(".", "_")
    device_key = f"{ip_clean}_{vendor}_{model}"

    # Store accepted_vendors on dev so PreCheck / Upgrade can read it
    dev["accepted_vendors"] = accepted_vendors

    # ── init results + logger ─────────────────────────────────────────────────
    init_device_results(device_key, host, vendor, model, dev)
    logger = setup_logger(device_key, vendor=vendor, model=model)

    tid = threading.get_ident()
    logger.info(f"[THREAD-{tid}] [{device_key}] Pipeline started at {datetime.now()}")
    print(f"[{device_key}] ===== PIPELINE STARTED =====")

    conn = None

    try:
        # ── VENDOR CHECK ──────────────────────────────────────────────────────
        if vendor not in accepted_vendors:
            msg = (
                f"[{device_key}] Unsupported vendor '{vendor}' — "
                f"not in accepted_vendors {accepted_vendors}"
            )
            logger.error(msg)
            print(msg)
            device_results[device_key]["pre"]["connect"]["exception"] = msg
            raise ConnectionError(msg)

        # ── CONNECT — one connection established here, passed to both phases ──
        # Pre-checks use this conn directly.
        # Upgrade phase receives this conn but replaces it after each reboot
        # via Upgrade.reconnect_and_verify() → Upgrade.connect().
        # The finally block always disconnects whatever conn is current.
        conn = connect(device_key, dev, logger)
        if not conn:
            msg = f"[{device_key}] connect() returned None"
            logger.error(msg)
            print(msg)
            device_results[device_key]["pre"]["connect"]["exception"] = msg
            raise ConnectionError(msg)

        logger.info(f"[{device_key}] Connected to {host}")
        print(f"[{device_key}] Connected to {host}")

        # ── PHASE 1: PRE-CHECKS ───────────────────────────────────────────────
        logger.info(f"[{device_key}] ── PHASE 1 PRE-CHECKS starting")
        print(f"[{device_key}] ── PHASE 1 PRE-CHECKS starting")

        precheck_ok = run_prechecks(conn, dev, device_key, logger)
        if not precheck_ok:
            msg = f"[{device_key}] Phase 1 FAILED — skipping upgrade"
            logger.error(msg)
            print(msg)
            return False

        logger.info(f"[{device_key}] ── PHASE 1 COMPLETE — starting Phase 2")
        print(f"[{device_key}] ── PHASE 1 COMPLETE — starting Phase 2")

        # ── PHASE 2: UPGRADE ─────────────────────────────────────────────────
        # Same thread continues here with the same conn from Phase 1.
        # run_upgrade() will replace conn internally after each reboot.
        # We get the final conn back so finally can disconnect it cleanly.
        conn, upgrade_ok = run_upgrade(conn, dev, device_key, accepted_vendors, logger)

        # Always sync device_results['conn'] with whatever conn we got back
        device_results[device_key]["conn"] = conn

        if not upgrade_ok:
            msg = f"[{device_key}] Phase 2 FAILED (rollback attempted) — stopping device"
            logger.error(msg)
            print(msg)
            return False

        logger.info(f"[{device_key}] ── PHASE 2 COMPLETE — upgrade successful")
        print(f"[{device_key}] ── PHASE 2 COMPLETE — upgrade successful")
        return True

    finally:
        # Always runs — success, failure, or exception
        try:
            export_device_summary(device_key)
            logger.info(f"[{device_key}] HTML report exported")
        except Exception as e:
            logger.error(f"[{device_key}] export_device_summary failed: {e}")

        disconnect(device_key, logger)
        logger.info(f"[THREAD-{tid}] [{device_key}] Pipeline finished at {datetime.now()}")
        print(f"[{device_key}] ===== PIPELINE FINISHED =====")


# ─────────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    devices          = load_yaml("deviceDetails.yaml")
    all_devs         = devices["devices"]
    accepted_vendors = devices.get("accepted_vendors")

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {
            executor.submit(run_device_pipeline, dev, accepted_vendors): dev
            for dev in all_devs
        }
        for future in as_completed(futures):
            dev = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"[MAIN] Thread error for {dev.get('host')}: {e}")

    sys.exit(0)


if __name__ == "__main__":
    main()
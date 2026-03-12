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
# Phase 1
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
            ok = get_show_version(device_key, conn, vendor_lc, logger, check_type="pre")
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
# run_postchecks
# Phase 3 — same thread, conn handed over from run_upgrade.
#
# Uses the EXACT same utility calls as run_prechecks.
# The only difference from pre is check_type="post" — results land in
#   device_results[key]["post"][...] instead of ["pre"][...]
#
# Steps:
#   1. show version         — non-fatal (same rule as pre STEP 2)
#   2. execute show commands — fatal    (same rule as pre STEP 1)
#   3. enable_re_protect_filter — stub slot, set aside for future
# ─────────────────────────────────────────────────────────────────────────────
def run_postchecks(conn, dev: dict, device_key: str, logger):
    tid       = threading.get_ident()
    vendor_lc = dev["vendor"].lower()
    model_lc  = str(dev["model"]).lower().replace("-", "")
    host      = dev.get("host")

    logger.info(f"[THREAD-{tid}] [{device_key}] Postchecks started at {datetime.now()}")

    try:
        # ── STEP 1: Show version (post) ───────────────────────────────────────
        # Same call as pre STEP 2 — only check_type differs.
        # Non-fatal: log error, write exception, continue to STEP 2.
        print(f"[{device_key}] POST STEP 1: show version")
        logger.info(f"[{device_key}] POST STEP 1: show version")

        try:
            ok = get_show_version(device_key, conn, vendor_lc, logger, check_type="post")
            if not ok:
                raise RuntimeError("get_show_version returned False")
            logger.info(
                f"[{device_key}] POST STEP 1 show_version OK — "
                f"version={device_results[device_key]['post']['show_version'].get('version', '?')}"
            )
        except Exception as e:
            logger.error(f"[{device_key}] POST STEP 1 SHOW VERSION failed — {e}")
            device_results[device_key]["post"]["show_version"]["exception"] = str(e)
            logger.warning(f"[{device_key}] POST STEP 1 failed but continuing postchecks")

        # ── STEP 2: Execute show commands (post) ──────────────────────────────
        # Same call as pre STEP 1 — only check_type="post" differs.
        # Fatal: Phase 4 diff needs post command outputs to exist.
        print(f"[{device_key}] POST STEP 2: executing show commands")
        logger.info(f"[{device_key}] POST STEP 2: executing show commands")

        exec_ok = execute_show_commands(device_key, vendor_lc, model_lc, conn, "post", logger)
        if not exec_ok:
            msg = f"{host}: execute_show_commands() failed during postchecks"
            logger.error(f"[{device_key}] POST STEP 2 failed — {msg}")
            device_results[device_key]["post"]["execute_show_commands"]["exception"] = msg
            return False

        logger.info(f"[{device_key}] POST STEP 2 execute_show_commands OK")

        # ── STEP 3: Enable RE protect filter — stub, set aside for future ─────
        # Slot already in device_results["post"]["enable_re_protect_filter"]
        # as {"status": "", "exception": ""} from init_device_results.
        # Nothing written here until implemented.
        logger.info(f"[{device_key}] POST STEP 3: enable_re_protect_filter stub — skipping")

        logger.info(f"[THREAD-{tid}] [{device_key}] All post-checks complete")
        return True

    except Exception as e:
        logger.error(f"[THREAD-{tid}] [{device_key}] run_postchecks unhandled exception: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# run_device_pipeline
#
# Phases are STRICTLY sequential on one thread.
# Each phase must fully return before the next one starts.
#
#   Phase 1 returns True   →  Phase 2 starts
#   Phase 2 returns True   →  Phase 3 starts
#   Phase 3 returns        →  Phase 4 starts
#   Phase 4 returns        →  finally{} runs
# ─────────────────────────────────────────────────────────────────────────────
def run_device_pipeline(dev: dict, accepted_vendors: list):
    vendor     = dev.get("vendor").lower()
    model      = str(dev.get("model")).lower().replace("-", "")
    host       = dev.get("host")
    ip_clean   = host.replace(".", "_")
    device_key = f"{ip_clean}_{vendor}_{model}"

    dev["accepted_vendors"] = accepted_vendors

    init_device_results(device_key, host, vendor, model, dev)
    logger = setup_logger(device_key, vendor=vendor, model=model, host=host)

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

        # ── CONNECT ───────────────────────────────────────────────────────────
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

        # Phase 1 fully returned True — Phase 2 now starts
        logger.info(f"[{device_key}] ── PHASE 1 COMPLETE — starting Phase 2")
        print(f"[{device_key}] ── PHASE 1 COMPLETE — starting Phase 2")

        # ── PHASE 2: UPGRADE ──────────────────────────────────────────────────
        conn, upgrade_ok = run_upgrade(conn, dev, device_key, accepted_vendors, logger)
        device_results[device_key]["conn"] = conn

        if not upgrade_ok:
            msg = f"[{device_key}] Phase 2 FAILED (rollback attempted) — stopping device"
            logger.error(msg)
            print(msg)
            return False

        # Phase 2 fully returned True — Phase 3 now starts
        logger.info(f"[{device_key}] ── PHASE 2 COMPLETE — starting Phase 3")
        print(f"[{device_key}] ── PHASE 2 COMPLETE — starting Phase 3")

        # ── PHASE 3: POST-CHECKS ──────────────────────────────────────────────
        postcheck_ok = run_postchecks(conn, dev, device_key, logger)
        if not postcheck_ok:
            logger.warning(f"[{device_key}] Phase 3 completed with errors — check post section")
        else:
            logger.info(f"[{device_key}] ── PHASE 3 COMPLETE")
        print(f"[{device_key}] ── PHASE 3 COMPLETE")

        # Phase 3 fully returned — Phase 4 now starts.
        # pre.execute_show_commands and post.execute_show_commands are both
        # fully written into device_results at this point.

        # ── PHASE 4: DIFF ─────────────────────────────────────────────────────
        print(f"[{device_key}] ── PHASE 4 DIFF starting")
        logger.info(f"[{device_key}] ── PHASE 4 DIFF starting")

        try:
            from diff import diff_devices
            diff_input  = {device_key: device_results.get(device_key, {})}
            diff_result = diff_devices(data=diff_input)
            device_results[device_key]["diff"] = diff_result.get(device_key, {})
            changed = len(device_results[device_key]["diff"])
            logger.info(f"[{device_key}] ── PHASE 4 COMPLETE — {changed} command(s) with changes")
            print(f"[{device_key}] ── PHASE 4 COMPLETE — {changed} command(s) with changes")
        except Exception as e:
            logger.error(f"[{device_key}] PHASE 4 DIFF failed — {e}")
            device_results[device_key]["diff"] = {}

        # Phase 4 fully returned — finally{} now runs
        return True

    finally:
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
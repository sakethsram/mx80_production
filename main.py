import logging
import sys
import threading
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from lib.utilities import *
from prechecks import PreCheck
from upgrade import Upgrade

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

        # ── STEP 2: Execute show commands ─────────────────────────────────────
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

        # ── STEP 3: Show version ──────────────────────────────────────────────
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
            device_results[device_key]["pre"]["check_storage"] = storage

            if not storage.get("sufficient", False):
                raise RuntimeError(
                    storage.get("exception", "Storage insufficient — see check_storage for details")
                )
        except Exception as e:
            logger.error(f"[{device_key}] STEP 4 STORAGE failed — {e}")
            device_results[device_key]["pre"]["check_storage"]["exception"] = str(e)
            return False

        # ── STEP 5: Backup active filesystem (disk1 → disk2) ─────────────────
        try:
            t           = PreCheck(dev)
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

        # ── STEP 8: Validate MD5 checksum ─────────────────────────────────────
        # try:
        #     expected_checksum = target.get("checksum")
        #     t        = PreCheck(dev)
        #     checksum = t.verifyChecksum(conn, target_image, expected_checksum)
        #     device_results[device_key]["pre"]["validate_md5"] = checksum
        #     if not checksum.get("match", False):
        #         raise RuntimeError(checksum.get("exception", "Checksum mismatch"))
        # except Exception as e:
        #     logger.error(f"[{device_key}] STEP 8 CHECKSUM failed — {e}")
        #     device_results[device_key]["pre"]["validate_md5"] = {
        #         "status":    "failed",
        #         "exception": str(e),
        #         "match":     False,
        #     }
        #     return False

        # ── STEP 9: Disable RE protect filter ────────────────────────────────
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

        # ── STEP 10: Merge results ────────────────────────────────────────────
        try:
            thread_result = {
                "pre":         device_results.get(device_key, {}).get("pre", {}),
                "device_info": device_results.get(device_key, {}).get("device_info", {}),
                "post":        [],
                "upgrade":     device_results.get(device_key, {}).get("upgrade", {}),
            }
            merge_thread_result(device_key, thread_result)
        except Exception as e:
            logger.error(f"[{device_key}] STEP 10 MERGE failed — {e}")
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
# run_rollback
# ─────────────────────────────────────────────────────────────────────────────
def run_rollback(conn, dev, device_key, rollback_image, logger):
    host             = dev.get("host")
    vendor           = dev.get("vendor").lower()
    model            = str(dev.get("model")).lower().replace("-", "")
    device_name      = f"{vendor}_{model}"
    accepted_vendors = dev.get("accepted_vendors")

    logger.info(f"[{device_key}] Rollback started at {datetime.now()}")
    print(f"[{device_key}] ===== ROLLBACK STARTED =====")

    upgrade = Upgrade(dev, accepted_vendors)

    try:
        reversed_list = rollback_image[::-1]

        print(f"[{device_key}] Rollback chain (reversed order):")
        logger.info(f"[{device_key}] Rollback chain (reversed order):")
        for i, entry in enumerate(reversed_list, start=1):
            print(f"[{device_key}]   {i}. image={entry.get('image')}  expected_os={entry.get('expected_os')}")
            logger.info(f"[{device_key}]   {i}. image={entry.get('image')}  expected_os={entry.get('expected_os')}")

        hops = device_results[device_key]["upgrade"]["hops"]

        for details in reversed_list:
            rb_image    = details.get("image")
            expected_os = details.get("expected_os")

            print(f"[{device_key}] Rolling back using: {rb_image} -> expected OS: {expected_os}")
            logger.info(f"[{device_key}] Rolling back: {rb_image} -> {expected_os}")

            if not rb_image or not expected_os:
                msg = f"[{device_key}] Missing image or expected_os in rollback entry — aborting"
                logger.error(msg)
                print(msg)
                device_results[device_key]["upgrade"]["status"]    = "rollback_failed"
                device_results[device_key]["upgrade"]["exception"] = msg
                return conn, False

            hop_idx = next((j for j, h in enumerate(hops) if h["image"] == rb_image), None)

            try:
                print(f"[{device_key}] Calling imageUpgrade for rollback hop: {rb_image}")
                conn, is_rollback = upgrade.imageUpgrade(conn, expected_os, rb_image, device_name, logger)
                print(f"[{device_key}] imageUpgrade (rollback) returned: {is_rollback}  conn={conn}")
                logger.info(f"[{device_key}] imageUpgrade (rollback) result: {is_rollback}")
            except Exception as e:
                msg = f"[{device_key}] imageUpgrade raised exception during rollback for {rb_image}: {e}"
                logger.error(msg)
                print(msg)
                if hop_idx is not None:
                    hops[hop_idx]["status"]    = "rollback_failed"
                    hops[hop_idx]["exception"] = str(e)
                device_results[device_key]["upgrade"]["status"]    = "rollback_failed"
                device_results[device_key]["upgrade"]["exception"] = str(e)
                return conn, False

            if not is_rollback:
                msg = f"[{device_key}] Rollback hop failed for {rb_image}"
                logger.error(msg)
                print(msg)
                if hop_idx is not None:
                    hops[hop_idx]["status"]    = "rollback_failed"
                    hops[hop_idx]["exception"] = msg
                device_results[device_key]["upgrade"]["status"]    = "rollback_failed"
                device_results[device_key]["upgrade"]["exception"] = msg
                return conn, False

            print(f"[{device_key}] Rollback hop succeeded: {rb_image}")
            logger.info(f"[{device_key}] Rollback hop succeeded: {rb_image}")
            if hop_idx is not None:
                hops[hop_idx]["status"] = "rolled_back"

            if expected_os == dev.get("curr_os"):
                msg = f"[{device_key}] Original OS {dev.get('curr_os')} restored — rollback complete"
                logger.info(msg)
                print(msg)
                device_results[device_key]["upgrade"]["status"] = "rolled_back"
                return conn, True

        logger.info(f"[{device_key}] Rollback completed")
        print(f"[{device_key}] Rollback completed")
        device_results[device_key]["upgrade"]["status"] = "rolled_back"
        return conn, True

    except Exception as e:
        msg = f"[{device_key}] Rollback — unhandled exception: {e}"
        logger.error(msg)
        print(msg)
        device_results[device_key]["upgrade"]["status"]    = "rollback_failed"
        device_results[device_key]["upgrade"]["exception"] = str(e)
        return conn, False


# ─────────────────────────────────────────────────────────────────────────────
# run_upgrade — executes inside a worker thread (one per device)
# ─────────────────────────────────────────────────────────────────────────────
def run_upgrade(dev: dict, device_key: str, logger):
    tid              = threading.get_ident()
    host             = dev.get("host")
    vendor           = dev.get("vendor").lower()
    model            = str(dev.get("model")).lower().replace("-", "")
    device_name      = f"{vendor}_{model}"
    image_details    = dev.get("imageDetails", [])
    accepted_vendors = dev.get("accepted_vendors")

    logger.info(f"[THREAD-{tid}] [{device_key}] Upgrade started at {datetime.now()}")
    print(f"[{device_key}] ===== UPGRADE STARTED =====")

    # ── vendor check ──────────────────────────────────────────────────────────
    if vendor not in accepted_vendors:
        msg = f"[{device_key}] Unsupported vendor: {vendor}"
        logger.error(msg)
        print(msg)
        device_results[device_key]["upgrade"]["status"]    = "failed"
        device_results[device_key]["upgrade"]["exception"] = msg
        return False

    # rollback_image starts with current state — grows after each successful hop
    rollback_image = [{
        "image":       dev.get("curr_image"),
        "expected_os": dev.get("curr_os"),
    }]

    upgrade  = Upgrade(dev, accepted_vendors)
    precheck = PreCheck(dev)

    try:
        # ── STEP 1: Connect ───────────────────────────────────────────────────
        try:
            conn = connect(device_key, dev, logger)
            if not conn:
                raise ConnectionError("connect() returned None")
            print(f"[{device_key}] Connected to {host}")
            logger.info(f"[{device_key}] Connected to {host}")
        except Exception as e:
            msg = f"[{device_key}] UPGRADE STEP 1 CONNECT failed: {e}"
            logger.error(msg)
            print(msg)
            device_results[device_key]["upgrade"]["status"]    = "failed"
            device_results[device_key]["upgrade"]["exception"] = str(e)
            return False

        device_results[device_key]["upgrade"]["status"] = "in_progress"
        hops = device_results[device_key]["upgrade"]["hops"]

        for i, details in enumerate(image_details):
            image       = details.get("image")
            expected_os = details.get("expected_os")
            checksum    = details.get("checksum")

            print(f"[{device_key}] ── HOP {i+1}/{len(image_details)}: {image} -> {expected_os} ──")
            logger.info(f"[{device_key}] HOP {i+1}/{len(image_details)}: {image} -> {expected_os}")

            # ── validate yaml fields ──────────────────────────────────────────
            if not image or not expected_os or not checksum:
                msg = f"[{device_key}] HOP {i+1}: missing image/expected_os/checksum in imageDetails"
                logger.error(msg)
                print(msg)
                hops[i]["status"]    = "failed"
                hops[i]["exception"] = msg
                device_results[device_key]["upgrade"]["status"]    = "failed"
                device_results[device_key]["upgrade"]["exception"] = msg
                return False

            # ── MD5 checksum ──────────────────────────────────────────────────
            print(f"[{device_key}] HOP {i+1}: verifying MD5 for {image}")
            print(f"[{device_key}] HOP {i+1}: expected checksum = {checksum}")
            logger.info(f"[{device_key}] HOP {i+1}: verifying MD5 — expected={checksum}")

            try:
                checksum_result = precheck.verifyChecksum(conn, image, checksum)
                print(f"[{device_key}] HOP {i+1}: verifyChecksum returned: {checksum_result}")
                logger.info(f"[{device_key}] HOP {i+1}: verifyChecksum result: {checksum_result}")
            except Exception as e:
                msg = f"[{device_key}] HOP {i+1}: verifyChecksum raised exception: {e}"
                logger.error(msg)
                print(msg)
                hops[i]["status"]    = "failed"
                hops[i]["exception"] = str(e)
                hops[i]["md5_match"] = False
                device_results[device_key]["upgrade"]["status"]    = "failed"
                device_results[device_key]["upgrade"]["exception"] = str(e)
                return False

            hops[i]["md5_match"] = checksum_result.get("match", False)
            print(f"[{device_key}] HOP {i+1}: md5_match = {hops[i]['md5_match']}")
            print(f"[{device_key}] HOP {i+1}: computed  = {checksum_result.get('computed', 'N/A')}")
            print(f"[{device_key}] HOP {i+1}: expected  = {checksum_result.get('expected', 'N/A')}")

            if not checksum_result.get("match", False):
                msg = (
                    f"[{device_key}] HOP {i+1}: MD5 MISMATCH for {image} — "
                    f"expected={checksum_result.get('expected')} "
                    f"computed={checksum_result.get('computed')}"
                )
                logger.error(msg)
                print(msg)
                hops[i]["status"]    = "failed"
                hops[i]["exception"] = msg
                device_results[device_key]["upgrade"]["status"]    = "failed"
                device_results[device_key]["upgrade"]["exception"] = msg
                return False

            print(f"[{device_key}] HOP {i+1}: MD5 OK")
            logger.info(f"[{device_key}] HOP {i+1}: MD5 OK")

            # ── imageUpgrade ──────────────────────────────────────────────────
            print(f"[{device_key}] HOP {i+1}: starting imageUpgrade")
            logger.info(f"[{device_key}] HOP {i+1}: calling imageUpgrade")

            try:
                conn, is_upgrade = upgrade.imageUpgrade(conn, expected_os, image, device_name, logger)
                print(f"[{device_key}] HOP {i+1}: imageUpgrade returned: {is_upgrade}  conn={conn}")
                logger.info(f"[{device_key}] HOP {i+1}: imageUpgrade result: {is_upgrade}")
            except Exception as e:
                msg = f"[{device_key}] HOP {i+1}: imageUpgrade raised exception: {e}"
                logger.error(msg)
                print(msg)
                hops[i]["status"]    = "failed"
                hops[i]["exception"] = str(e)
                device_results[device_key]["upgrade"]["status"]    = "failed"
                device_results[device_key]["upgrade"]["exception"] = str(e)
                print(f"[{device_key}] HOP {i+1}: initiating rollback")
                logger.info(f"[{device_key}] HOP {i+1}: initiating rollback")
                run_rollback(conn, dev, device_key, rollback_image, logger)
                return False

            if not is_upgrade:
                msg = f"[{device_key}] HOP {i+1}: imageUpgrade failed for {image}"
                logger.error(msg)
                print(msg)
                hops[i]["status"]    = "failed"
                hops[i]["exception"] = msg
                device_results[device_key]["upgrade"]["status"]    = "failed"
                device_results[device_key]["upgrade"]["exception"] = msg
                print(f"[{device_key}] HOP {i+1}: initiating rollback")
                logger.info(f"[{device_key}] HOP {i+1}: initiating rollback")
                run_rollback(conn, dev, device_key, rollback_image, logger)
                return False

            # hop succeeded
            hops[i]["status"] = "ok"
            rollback_image.append({"image": image, "expected_os": expected_os})
            print(f"[{device_key}] HOP {i+1}: succeeded. rollback_chain now: {rollback_image}")
            logger.info(f"[{device_key}] HOP {i+1}: succeeded. rollback_chain: {rollback_image}")

        # ── all hops done ─────────────────────────────────────────────────────
        device_results[device_key]["upgrade"]["status"] = "completed"
        msg = f"[{device_key}] Upgrade completed successfully"
        logger.info(msg)
        print(msg)
        return conn, True

    except Exception as e:
        msg = f"[THREAD-{tid}] [{device_key}] Upgrade — unhandled exception: {e}"
        logger.error(msg)
        print(msg)
        device_results[device_key]["upgrade"]["status"]    = "failed"
        device_results[device_key]["upgrade"]["exception"] = str(e)
        return False

    finally:
        disconnect(device_key, logger)
        logger.info(f"[THREAD-{tid}] [{device_key}] Upgrade thread finished at {datetime.now()}")
        print(f"[{device_key}] ===== UPGRADE THREAD FINISHED =====")

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
        main_logger.info(f"[MAIN] Initialised device_results for [{device_key}] host={dev['host']}")

    main_logger.info(f"[MAIN] Spawning threads for {len(all_devs)} device(s)")

    # ── One thread per device — prechecks then upgrade in same thread ─────────
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        future_to_key = {}
        for dev in all_devs:
            vendor_lc  = dev["vendor"].lower()
            model_lc   = str(dev["model"]).lower().replace("-", "")
            ip_clean   = dev["host"].replace(".", "_")
            device_key = f"{ip_clean}_{vendor_lc}_{model_lc}"

            def device_thread(d=dev, dk=device_key, lg=loggers[device_key]):
                ok = run_prechecks(d, dk, lg)
                if not ok:
                    lg.error(f"[{dk}] Prechecks failed — skipping upgrade")
                    return False
                if PRECHECKS_ONLY:
                    lg.info(f"[{dk}] PRECHECKS_ONLY=True — skipping upgrade")
                    return True
                return run_upgrade(d, dk, lg)

            future = executor.submit(device_thread)
            future_to_key[future] = device_key

    #     for future in as_completed(future_to_key):
    #         device_key = future_to_key[future]
    #         try:
    #             ok = future.result()
    #             main_logger.info(f"[MAIN] {device_key} -> {'passed' if ok else 'FAILED'}")
    #         except Exception as e:
    #             main_logger.error(f"[MAIN] {device_key} thread raised: {e}")

    # # ── All devices done — export per-device JSON summaries ───────────────────
    # for dev in all_devs:
    #     vendor_lc  = dev["vendor"].lower()
    #     model_lc   = str(dev["model"]).lower().replace("-", "")
    #     ip_clean   = dev["host"].replace(".", "_")
    #     device_key = f"{ip_clean}_{vendor_lc}_{model_lc}"
    #     export_device_summary(device_key)

    main_logger.info(f"[MAIN] JSON files location -> {os.path.join(os.getcwd(), 'precheck_jsons')}")
    sys.exit(0)


if __name__ == "__main__":
    main()
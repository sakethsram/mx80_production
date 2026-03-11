import logging
import sys
import threading
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from lib.utilities import *
from prechecks import PreCheck
from upgrade import Upgrade

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

        # ── STEP 7: Merge results ─────────────────────────────────────────────
        try:
            thread_result = {
                "pre":         device_results.get(device_key, {}).get("pre", {}),
                "device_info": device_results.get(device_key, {}).get("device_info", {}),
                "post":        {},
                "upgrade":     device_results.get(device_key, {}).get("upgrade", {}),
            }
            merge_thread_result(device_key, thread_result)
        except Exception as e:
            logger.error(f"[{device_key}] STEP 7 MERGE failed — {e}")
            return False

        logger.info(f"[THREAD-{tid}] [{device_key}] All pre-checks passed")
        return True

    except Exception as e:
        logger.error(f"[THREAD-{tid}] [{device_key}] run_prechecks unhandled exception: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# run_rollback
# ─────────────────────────────────────────────────────────────────────────────
def run_rollback(conn, dev, device_key, rollback_image, logger):
    vendor      = dev.get("vendor").lower()
    model       = str(dev.get("model")).lower().replace("-", "")
    device_name = f"{vendor}_{model}"

    logger.info(f"[{device_key}] Rollback started at {datetime.now()}")
    print(f"[{device_key}] ===== ROLLBACK STARTED =====")

    upgrade = Upgrade(dev)

    try:
        if vendor == "juniper":
            reversed_list = rollback_image[::-1]

            log_lines = ["\n===== ROLLBACK CHAIN (REVERSED) ====="]
            for i, entry in enumerate(reversed_list, start=1):
                log_lines.append(
                    f"{i}. image = {entry.get('image')}, expected_os = {entry.get('expected_os')}"
                )
            log_lines.append("=====================================\n")
            logger.info("\n".join(log_lines))
            print("\n".join(log_lines))

            original_os = dev.get("curr_os")
            hops        = device_results[device_key]["upgrade"]["hops"]

            for details in reversed_list:
                rb_image    = details.get("image")
                expected_os = details.get("expected_os")

                if not rb_image or not expected_os:
                    msg = "Please provide the image details you want to rollback to"
                    logger.info(msg)
                    print(msg)
                    device_results[device_key]["upgrade"]["status"]    = "rollback_failed"
                    device_results[device_key]["upgrade"]["exception"] = msg
                    return conn, False

                step_msg = f"Rollback Step → Installing: {rb_image}, expecting OS: {expected_os}"
                print(step_msg)
                logger.info(step_msg)

                hop_idx = next((j for j, h in enumerate(hops) if h["image"] == rb_image), None)

                try:
                    conn, is_rollback = upgrade.imageUpgrade(
                        conn, expected_os, rb_image, device_name, logger
                    )
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
                    msg = f"Rollback is not successful for {device_name}"
                    logger.info(msg)
                    print(msg)
                    if hop_idx is not None:
                        hops[hop_idx]["status"]    = "rollback_failed"
                        hops[hop_idx]["exception"] = msg
                    device_results[device_key]["upgrade"]["status"]    = "rollback_failed"
                    device_results[device_key]["upgrade"]["exception"] = msg
                    return conn, False

                if hop_idx is not None:
                    hops[hop_idx]["status"] = "rolled_back"

                if expected_os == original_os:
                    done_msg = f"{device_name}: Original OS {original_os} restored. Rollback complete."
                    logger.info(done_msg)
                    print(done_msg)
                    device_results[device_key]["upgrade"]["status"] = "rolled_back"
                    return conn, True

        logger.info(f"{device_name}: Multi-step rollback completed.")
        msg = f"Rollback is successful for {device_name}"
        logger.info(msg)
        print(msg)
        device_results[device_key]["upgrade"]["status"] = "rolled_back"
        return conn, True

    except Exception as e:
        msg = f"[{device_key}] Rollback failed for {device_name} due to {e}"
        logger.error(msg)
        print(msg)
        device_results[device_key]["upgrade"]["status"]    = "rollback_failed"
        device_results[device_key]["upgrade"]["exception"] = str(e)
        return conn, False


# ─────────────────────────────────────────────────────────────────────────────
# run_upgrade
# ─────────────────────────────────────────────────────────────────────────────
def run_upgrade(conn, dev: dict, device_key: str, logger):
    vendor        = dev.get("vendor").lower()
    model         = str(dev.get("model")).lower().replace("-", "")
    device_name   = f"{vendor}_{model}"
    image_details = dev.get("imageDetails", [])

    logger.info(f"[{device_key}] Upgrade started at {datetime.now()}")
    print(f"[{device_key}] ===== UPGRADE STARTED =====")

    rollback_image = [{
        "image":       dev.get("curr_image"),
        "expected_os": dev.get("curr_os"),
    }]

    upgrade  = Upgrade(dev)
    precheck = PreCheck(dev)

    try:
        device_results[device_key]["upgrade"]["status"] = "in_progress"
        hops = device_results[device_key]["upgrade"]["hops"]

        for i, details in enumerate(image_details):
            image       = details["image"]
            expected_os = details["expected_os"]
            checksum    = details["checksum"]

            if not image or not expected_os or not checksum:
                msg = (
                    f"{device_name}: Please provide image details correctly — "
                    f"one of image, checksum, expected_os is missing"
                )
                logger.info(msg)
                print(msg)
                hops[i]["status"]    = "failed"
                hops[i]["exception"] = msg
                device_results[device_key]["upgrade"]["status"]    = "failed"
                device_results[device_key]["upgrade"]["exception"] = msg
                return conn, False

            msg = f"{device_name}: Upgrading the devices using {image} and {expected_os}"
            logger.info(msg)
            print(msg)

            # ── MD5 checksum ──────────────────────────────────────────────────
            verify_checksum = precheck.verifyChecksum(conn, checksum, image, logger)
            if not verify_checksum.get("match"):
                msg = "Checksum verification failed"
                logger.info(msg)
                hops[i]["status"]    = "failed"
                hops[i]["exception"] = msg
                hops[i]["md5_match"] = False
                device_results[device_key]["upgrade"]["status"]    = "failed"
                device_results[device_key]["upgrade"]["exception"] = msg
                device_results[device_key]["upgrade"]["validate_md5"] = {
                    "status":    verify_checksum.get("status"),
                    "exception": verify_checksum.get("exception"),
                    "expected":  verify_checksum.get("expected"),
                    "computed":  verify_checksum.get("computed"),
                    "match":     verify_checksum.get("match"),
                }
                return conn, False

            hops[i]["md5_match"] = True
            device_results[device_key]["upgrade"]["validate_md5"]["match"]  = True
            device_results[device_key]["upgrade"]["validate_md5"]["status"] = "ok"

            # ── imageUpgrade ──────────────────────────────────────────────────
            conn, is_upgrade = upgrade.imageUpgrade(conn, expected_os, image, device_name, logger)

            if not is_upgrade:
                msg = f"Upgrade is not successful for {device_name}"
                logger.info(msg)
                print(msg)
                msg2 = f"Rolling back to the old image for {device_name}"
                logger.info(msg2)
                print(msg2)
                hops[i]["status"]    = "failed"
                hops[i]["exception"] = msg
                device_results[device_key]["upgrade"]["status"]    = "failed"
                device_results[device_key]["upgrade"]["exception"] = msg

                conn, rollback_ok = run_rollback(conn, dev, device_key, rollback_image, logger)
                if not rollback_ok:
                    msg = "Rollback failed"
                    logger.info(msg)
                    print(msg)
                return conn, False

            hops[i]["status"] = "ok"
            rollback_image.append({"image": image, "expected_os": expected_os})
            logger.info(f"[{device_key}] HOP {i+1} succeeded. rollback_chain: {rollback_image}")

        device_results[device_key]["upgrade"]["status"] = "completed"
        msg = f"Image installation is successful for {device_name}"
        logger.info(msg)
        print(msg)
        return conn, True

    except Exception as e:
        msg = f"[{device_key}] Upgrade failed for {device_name} due to {e}"
        logger.error(msg)
        print(msg)
        device_results[device_key]["upgrade"]["status"]    = "failed"
        device_results[device_key]["upgrade"]["exception"] = str(e)
        return conn, False


# ─────────────────────────────────────────────────────────────────────────────
# run_device_pipeline
# Owns: init results/logger, vendor check, single connect, pre, upgrade, report.
# Called once per device in its own thread.
# ─────────────────────────────────────────────────────────────────────────────
def run_device_pipeline(dev: dict, accepted_vendors: list):
    vendor     = dev.get("vendor").lower()
    model      = str(dev.get("model")).lower().replace("-", "")
    host       = dev.get("host")
    ip_clean   = host.replace(".", "_")
    device_key = f"{ip_clean}_{vendor}_{model}"

    # Store accepted_vendors on dev so PreCheck/Upgrade can read it from device dict
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

        # ── SINGLE CONNECTION — passed through all phases ─────────────────────
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
        logger.info(f"[{device_key}] Starting pre-checks")
        print(f"[{device_key}] Starting pre-checks")

        precheck_ok = run_prechecks(conn, dev, device_key, logger)
        if not precheck_ok:
            msg = f"[{device_key}] Pre-checks failed — skipping upgrade"
            logger.error(msg)
            print(msg)
            return False

        logger.info(f"[{device_key}] Pre-checks passed — starting upgrade")
        print(f"[{device_key}] Pre-checks passed — starting upgrade")

        # ── PHASE 2: UPGRADE ──────────────────────────────────────────────────
        conn, upgrade_ok = run_upgrade(conn, dev, device_key, logger)
        if not upgrade_ok:
            msg = f"[{device_key}] Upgrade failed"
            logger.error(msg)
            print(msg)
            return False

        logger.info(f"[{device_key}] Upgrade succeeded")
        print(f"[{device_key}] Upgrade succeeded")
        return True

    except ConnectionError:
        return False

    except Exception as e:
        msg = f"[THREAD-{tid}] [{device_key}] Pipeline unhandled exception: {e}"
        logger.error(msg)
        print(msg)
        return False

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
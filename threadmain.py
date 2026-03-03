import logging
import sys
import json
import traceback
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from prechecks import *
from lib.utilities import *
from parsers.junos.junos_mx204 import *
from parsers.cisco.cisco_asr9910 import *
from upgrade import Upgrade
from pprint import pformat
from workflow_report_generator import generate_html_report
import os

MAX_THREADS = 5
PRECHECKS_ONLY = True  # <--- Run prechecks only; skip upgrade in main()

# ----------------------------------------------------
# Abort helper — call when any step fails
# ----------------------------------------------------

def abort(device_key, phase, subtask, error, logger, exc: Exception = None):
    log_line = ""
    if exc is not None:
        log_line = traceback.format_exc()

    log_task(device_key, phase, subtask, 'Failed', error, log_line)

    # Log + console
    logger.error(f"[{device_key}] FATAL [{phase}] '{subtask}': {error}")
    if log_line:
        logger.error(f"[{device_key}] Traceback:\n{log_line}")
    logger.error(f"[{device_key}] Aborting device — generating partial report")

    '''
    j = json.dumps(workflow_tracker, indent=2)
    logger.info(f"\n{j}")
    print("\n" + "=" * 60)
    print(f"WORKFLOW ABORTED for {device_key} — partial results (JSON):")
    print("=" * 60)
    print(j)
    print("=" * 60 + "\n")'''

    # Generate HTML report here (centralized on failure)
    try:
        report_timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        path = generate_html_report(workflow_tracker, f'workflow_report_{report_timestamp}.html')
        logger.info(f"[{device_key}] Report saved -> {path}")
        print(f"Report saved -> {path}")
    except Exception as e:
        logger.error(f"[{device_key}] Could not write HTML report: {e}")

    sys.exit(1)

# ----------------------------------------------------
# Worker Function (Runs per device)
# ----------------------------------------------------

def run_prechecks(conn, device, device_key, accepted_vendors, commands, logger):
    print("Running Prechecks..")

    host = device.get("host")
    vendor = device.get("vendor").lower()
    model = str(device.get("model")).lower().replace("-","")
    device_type = device.get('device_type')
    username = device.get("username")
    password = device.get("password")
    checksum = device.get('md5checksum_file')
    target_image = device.get('target_image')
    min_disk_gb = device.get('min_disk_gb')
    image_path = device.get('image_path')

    start_time = datetime.now()
    logger.info(f"{host} — Prechecks started at {start_time}")

    ##pre_check_timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    global_config.pre_check_timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    log_task(device_key, 'pre-checks', 'read Yaml',    'Success', 'deviceDetails.yaml loaded successfully')
    log_task(device_key, 'pre-checks', 'start logger', 'Success', 'Logger initialised')

    precheck = PreCheck(device)
    check_type = "pre"
    print(f" device details: \n host: {host}")
    phase = "pre-checks"
    device_key = f"{vendor}_{model}"

    try:

        # Step1 - execute show commands
        if not conn:
            abort(device_key, 'pre-checks', 'connection using credentials',
                  f'{host}: connect() returned None', logger)
        log_task(device_key, 'pre-checks', 'connection using credentials', 'Success', f'{host}: Connected successfully', '')
        global_config.vendor     = vendor
        global_config.device_key = device_key
        all_cmds                 = commands
        global_config.commands   = all_cmds[device_key]


        logger.info(f"[{device_key}] Starting command pipeline — {len(global_config.commands)} command(s)")

        entries = collect_outputs(
                device_key=device_key, vendor=vendor_lc,
                commands=global_config.commands, check_type="pre",
                conn=conn, log=logger,
            )

        if not entries:
            logger.warning(f"[{device_key}] collect_outputs() returned no entries")

        parse_ok = parse_outputs(
            device_key=device_key, vendor=vendor_lc,
            check_type="pre", log=logger,
        )
        if not parse_ok:
            logger.warning(f"[{device_key}] one or more parsers failed — continuing")

        push_to_tracker(
            device_key=device_key, check_type="pre",
            entries=entries, parse_ok=parse_ok, log=logger,
        )

        # ── NEW: populate hostname + version into device_info ──────
        try:
            update_device_info_from_show_version(device_key, vendor_lc, logger)
            log_task(device_key, 'pre-checks', 'show version', 'Success',
                     'hostname and version extracted from show version output')
        except Exception as e:
            logger.error(f"[{device_key}] Could not extract show version info: {e}")
            log_task(device_key, 'pre-checks', 'show version', 'Failed',
                     f'Could not extract: {e}')
        logger.info(f"[{device_key}] All pre-checks passed")
        return True

    except KeyError as e:
        abort(device_key, 'pre-checks', 'executing show commands',
              f"{host}: Missing command list for device_key='{device_key}' — {e}", logger, exc=e)
    except Exception as e:
        abort(device_key, 'pre-checks', 'executing show commands',
              f"{host}: command pipeline exception — {e}", logger, exc=e)
    except Exception as e:
        logger.error(f"[{device_key}] Unhandled exception: {e}")
        abort(device_key, 'pre-checks', 'unexpected error',
              f'{host}: Unhandled exception — {e}', logger, exc=e)
        return False
    finally:
        precheck.disconnect(logger)
        logger.info(f"[{device_key}] Prechecks completed at {datetime.now()}")

def run_upgrade(conn, device, accepted_vendors, logger):
    print("Running Upgrade..")
    host = device.get("host")
    vendor = device.get("vendor")
    model = device.get("model")
    expected_os = device.get('expected_os')
    target_image = device.get("target_image")
    device_name = f"{vendor}_{model}"

    start_time = datetime.now()
    logger.info(f"{host} — Upgrade started at {start_time}")

    upgrade = Upgrade(device, accepted_vendors)
    try:
        conn, isUpgrade = upgrade.imageUpgrade(conn, expected_os, target_image, device_name, logger)

        if not isUpgrade:
            msg = f"Upgrade is not successful for {device_name}"
            logger.info(msg)
            print(msg)
            msg = f"Rolling back to the old image for {device_name}"
            logger.info(msg)
            print(msg)
            rollback = run_rollback(conn, device, accepted_vendors, vendor, model, host, logger)
            if not rollback:
              msg = f"Rollback failed"
              logger.info(msg)
              print(msg)
              return False
            return True
        msg = f"Upgrade is successful for {device_name}"
        logger.info(msg)
        print(msg)
        return conn, True

    except Exception as e:
        msg = f"{host}: Upgrade failed for {device_name} due to {e}"
        logger.error(msg)
        print(msg)
        return False


def run_rollback(conn, device, accepted_vendors, vendor, model, host, logger):
  print("Running Rollback...")
  rollback_image = device.get("current_image")
  device_name = f"{vendor}_{model}"

  msg = f"{host} - Rollback started at {datetime.now}"
  logger.info(msg)

  rollback = Rollback(decice, accepted_vendors, rollback_image)
  try:
    isRollback = rollback.imageRollback(conn, device_name, logger)

    if not isRollback:
      msg = f"Rollback is not successful for {device_name}"
      logger.info(msg)
      print(msg)

    msg = f"Rollback is successfull for {device_name}"
    logger.info(msg)
    print(msg)
    return True
  except Exception as e:
    msg = f"{host}: Rollback failed for {device_name} due to {e}"
    logger.error(msg)
    print(msg)
    return False


def run_device_pipeline(device, accepted_vendors,commands):
    vendor = device.get("vendor").lower()
    model = device.get("model").lower().replace("-","")
    host = device.get("host")
    device_name = f"{vendor}_{model}"
    global_config.vendor = vendor
    global_config.model  = model

    print(f"vendor: {vendor} and model: {model}")
    logger = setup_logger("main", vendor, model)
    logger.info(f"[{device_key}] Starting workflow")

    if device_key not in workflow_tracker:
        init_device_tracker(device_key, dev["host"], vendor_lc, model_lc)

    try:
        msg = f"Starting pipeline for {vendor} {model}"
        logger.info(msg)

        # Step 1: Precheck
        precheck = PreCheck(device, accepted_vendors)
        conn = precheck.connect(logger)

        msg = "Running pre-checks"
        logger.info(msg)
        print(msg)
        precheck_success = run_prechecks(conn, device, accepted_vendors,commands, logger)

        if not precheck_success:
            msg = "skipping upgrade due to failed prechecks"
            logger.info(msg)
            print(msg)
            sys.exit(1)

    except Exception as e:
        msg = f"Device Upgrade failed for {vendor}_{model}: {e}"
        logger.error(msg)
        print(msg)



# ----------------------------------------------------
# Main Function
# ----------------------------------------------------
def main():
    device_details = load_yaml("deviceDetails.yaml")
    devices = device_details.get("devices")
    print(f" device detials \n: {devices}")

    vendors = device_details.get("accepted_vendors")

    print(f" Accepted vendor \n: {vendors}")
    commands=load_yaml("show_cmd_list.yaml")
    print(f"list of commands \n: {commands}")

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = [
            executor.submit(run_device_pipeline, device, vendors,commands)
            for device in devices
        ]
        print(f" futures: {futures}")

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Thread execution error: {e}")

    # All devices done — generate final report
    try:
        export_device_summary()
        path = generate_html_report(workflow_tracker, output_dir='reports')
        logger.info(f"All devices done. Report saved -> {path}")
        print(f"Report saved -> {path}")
    except Exception as e:
        logger.error(f"Could not write final HTML report: {e}")

    sys.exit(0)

if __name__ == "__main__":
    main()
#store the ouput in a text file


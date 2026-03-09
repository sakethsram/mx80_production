import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from prechecks import PreCheck
from lib.utilities import *
from parsers.junos.junos_mx80 import *
from parsers.cisco.cisco_asr9910 import * 
from upgrade import Upgrade
from pprint import pformat
MAX_THREADS = 5

# ----------------------------------------------------
# Abort helper — call when any step fails
# ----------------------------------------------------

def abort(device_key, phase, subtask, error, logger):
    # Mark the failed subtask in the tracker
    log_task(device_key, phase, subtask, 'Failed', error)

    # Log + console
    logger.error(f"[{device_key}] FATAL [{phase}] '{subtask}': {error}")
    logger.error(f"[{device_key}] Aborting workflow — generating report")

    j = json.dumps(workflow_tracker, indent=2)
    logger.info(f"\n{j}")
    print("\n" + "=" * 60)
    print(f"WORKFLOW ABORTED for {device_key} — partial results (JSON):")
    print("=" * 60)
    print(j)
    print("=" * 60 + "\n")

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

def run_prechecks(conn, device,accepted_vendors,commands, logger):
    print("Running Prechecks..")
    host = device.get("host")
    vendor = device.get("vendor")
    model = device.get("model")
    device_type = device.get('device_type')
    username = device.get("username")
    password = device.get("password")
    min_disk_gb = device.get('min_disk_gb')
    start_time = datetime.now()
    logger.info(f"{host} — Prechecks started at {start_time}")

    pre_check_timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    precheck = PreCheck(device, accepted_vendors)
    check_type = "pre"
    print(f" device details: \n host: {host}")
    phase = "pre-checks" 
    device_name = f"{vendor}_{model}"    

    try:

        # Step1 - execute show commands   

        print(f"Executing show commands: {commands}")
        logger.info("Executing show commands")
	
        device_res = execute_command(conn, commands,vendor, host, check_type, model, logger)
        if not device_res: 
          msg= f'{host}: execute_commands() failed (collections/parsing)'
          logger.info(msg)
#          log_task(device_name, 'pre-checks', 'Executing show commands', 'Failed', msg ,logger)
          return False 

        msg= f'{host}: execute_commands() success (collections/parsing)'
        logger.info(msg)
#        output_file = write_json(
#          vendor=vendor,
#          model=model,
#          pre_check_timestamp = pre_check_timestamp,
#          json_data=device_res,
#          json_file_path="precheck_jsons/"
#         )
#        log_task(device_name, 'pre-checks', 'Executing show commands', 'Success',msg,logger)

#        # Step 2 — Backup Config
        filename = f"{device_type}_{model}_{pre_check_timestamp}"
        print(f" filename: {filename}")
        
#        if vendor == "cisco": 
#          validateFPDs = precheck.validateFPDs(conn, logger, device_name)
#          if not validateFPDs:
#            msg = f"{host}: Failed to validate FPDs"
#            logger.info(msg)
#            print(msg) 
#            return False

        # step - check disk space
        storage = precheck.checkStorage(conn,min_disk_gb, logger)
        if not storage: 
          msg = f"Precheck check storage failed"
          logger.info(msg)
          print(msg)
          return False
 
#        prebackup = precheck.preBackup(conn, filename, logger)
#        if not prebackup:
#          msg = 'Precheck failed for backup'
#          logger.info(msg)
#          print(msg)
#          return False
#        print(f" prebackup success: {prebackup}")
#        logger.info(f"Running config: {prebackup}")
#        print("CONNECTION", conn)
#        
        
        # Step6: Disable RE-PROTECT filter 
#        filter = precheck.disableReProtectFilter(conn, logger)
#        if not filter: 
#          msg = "PRECHECK - Disable RE Protect Filter failed. \n Please check the disableReProtectFilter()"
#          logger.info(msg) 
#          print(msg) 
#          msg = "Please check execution logs /logging and session-log /outputs for more information"
#          logger.info(msg)
#          print(msg) 
#          return False
        return True
    except Exception as e:
        logger.error(f"{host} — Precheck failed: {e}")
        return False





def run_upgrade(conn, device, accepted_vendors, logger): 
    print("Running Upgrade..")
    host = device.get("host")
    vendor = device.get("vendor")
    imageDetails = device.get("imageDetails")
    model = device.get("model")
    device_name = f"{vendor}_{model}"
    image_path = device.get('image_path')
    curr_image = device.get('curr_image')
    curr_os = device.get('curr_os')
    
    rollback_image = [{
      "image": curr_image, 
      "expected_os": curr_os
    }]

    start_time = datetime.now()
    logger.info(f"{host} — Upgrade started at {start_time}")

    upgrade = Upgrade(device, accepted_vendors)
    precheck = PreCheck(device, accepted_vendors)
    try: 
        for details in imageDetails:
            image = details['image'] 
            expected_os = details['expected_os']
            checksum = details['checksum']
            
            if (not image or 
              not expected_os or 
              not checksum
            ):
              msg = f"{device_name}: Please provide image details correctly "
              logger.info(msg) 
              print(msg) 
              msg = f"one of the value is missinge for these 3 keys: image, checksum, and expected_os "
              logger.info(msg) 
              print(msg) 
              precheck.disconnect(logger)
              return False
            
            msg = f"{device_name}: Upgrading the devices using {image} and {expected_os}"
            logger.info(msg) 
            print(msg)
            # Transfering file from  remoter to router
#            image_deployed = precheck.transferImage(conn,image_path, image, logger)
#            if not image_deployed:
#              msg = f"{image} transfer failed"
#              logger.exception(msg)
#              print(msg)
#              return False
#
#            # Step4: Md5 checksum
#            verify_checksum = precheck.verifyChecksum(conn, checksum, image, logger)
#            if not verify_checksum:
#              msg = "Checksum verification failed"
#              logger.info(msg)
#              return False
#
            conn, isUpgrade = upgrade.imageUpgrade(conn,expected_os, image, device_name, logger) 

        
            if not isUpgrade: 
              msg = f"Upgrade is not successful for {device_name}"
              logger.info(msg)
              print(msg)
              msg = f"Rolling back to the old image for {device_name}"
              logger.info(msg)
              print(msg)
              rollback_image.append({
                "image": image, 
                "expected_os": expected_os
              })
              rollback = run_rollback(conn, device, vendor, device_name, rollback_image, host, logger,accepted_vendors)
              if not rollback:
                msg = f"Rollback failed"
                logger.info(msg)
                print(msg)
                precheck.disconnect(logger)
                return False
        msg = f"Upgrade is successful for {device_name}"
        logger.info(msg)
        print(msg)
        return conn, True

    except Exception as e: 
        msg = f"{host}: Upgrade failed for {device_name} due to {e}"
        logger.error(msg)
        print(msg)
        precheck.disconnect(logger)
        return False
  

def run_rollback(conn, device,vendor, device_name, imageDetails, host, logger, accepted_vendors): 
  print("Running Rollback...") 

  msg = f"{host} - Rollback started at {datetime.now()}"
  logger.info(msg) 
  
#  rollback = Rollback(decice, accepted_vendors, rollback_image)
  upgrade = Upgrade(device, accepted_vendors)
  precheck = PreCheck(device, accepted_vendors)
  try: 
    if vendor == "juniper": 
      for details in imageDetails[-1:]:
        rollback_image = details.get('image')
        expected_os = details.get("expected_os") 

        if (
          not rollback_image or 
          not expected_os
        ):
          msg = f"Please provide the image details you want to rollback to"
          logger.info(msg) 
          print(msg) 
          precheck.disconnect(logger)
          return conn, False

        conn, isRollback = upgrade.imageUpgrade(conn,expected_os, rollback_image, device_name, logger)
        if not isRollback:
          msg = f"Rollback is not successful for {device_name}"
          logger.info(msg)
          print(msg)
          precheck.disconnect(logger)
          return conn, False

#    if vendor == "cisco": 
#      isRollback = rollback.imageRollback(conn, device_name, logger)
    
#    if not isRollback: 
#      msg = f"Rollback is not successful for {device_name}" 
#      logger.info(msg) 
#      print(msg) 
#      precheck.disconnect(logger)
#      return False

    msg = f"Rollback is successfull for {device_name}" 
    logger.info(msg) 
    print(msg) 
    return conn, True 
  except Exception as e: 
    msg = f"{host}: Rollback failed for {device_name} due to {e}" 
    logger.error(msg) 
    print(msg) 
    return conn ,False


 
def run_postcheck(conn, device,accepted_vendors,commands, logger):
    print("Running Prechecks..")
    host = device.get("host")
    vendor = device.get("vendor")
    model = device.get("model")
    device_type = device.get('device_type')
    username = device.get("username")
    password = device.get("password")
    min_disk_gb = device.get('min_disk_gb')
    start_time = datetime.now()
    logger.info(f"{host} — Prechecks started at {start_time}")

    post_check_timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    precheck = PreCheck(device, accepted_vendors)
    check_type = "post"
    print(f" device details: \n host: {host}")
    phase = "post-checks"
    device_name = f"{vendor}_{model}"

    try:

        # Step1 - execute show commands

        print(f"Executing show commands: {commands}")
        logger.info("Executing show commands")

        device_res = execute_command(conn, commands,vendor, host, check_type, model, logger)
        if not device_res:
          msg= f'{host}: execute_commands() failed (collections/parsing)'
          logger.info(msg)
#          log_task(device_name, 'pre-checks', 'Executing show commands', 'Failed', msg ,logger)
          return False

        msg= f'{host}: execute_commands() success (collections/parsing)'
        logger.info(msg)

        # Taking  backup of the upated device.
        postbackup = precheck.preBackup(conn, filename, logger)
        if not postbackup:
          msg = 'Postcheck failed for backup'
          logger.info(msg)
          print(msg)
          return False
        print(f" postbackup success: {postbackup}")
        logger.info(f"Running config: {postbackup}")
        print("CONNECTION", conn)

        # Enable RE-PROTECT FILTER
#         filter = precheck.enableReProtectFilter(conn, logger)
#        if not filter:
#          msg = "POSTCHECK - Enable RE Protect Filter failed. \n Please check the enableReProtectFilter()"
#          logger.info(msg)
#          print(msg)
#          msg = "Please check execution logs /logging and session-log /outputs for more information"
#          logger.info(msg)
#          print(msg)
#          return False
        return True 
    except Exception as e:
        msg = f"{host}: Rollback failed for {device_name} due to {e}"
        logger.error(msg)
        print(msg)
        return False

def run_device_pipeline(device, accepted_vendors,commands): 
    vendor = device.get("vendor")
    model = device.get("model")
    host = device.get("host")
    device_name = f"{vendor}_{model}"

    print(f"vendor: {vendor} and model: {model}")
#    log_task(device_name, 'pre-checks', 'read Yaml', 'Success', log_line = 'deviceDetails.yaml loaded successfully')
#    log_task(device_name, 'pre-checks', 'start logger', 'Success', log_line = 'Logger initialised')

    logger = setup_logger("main", vendor, model)

    try: 
        msg = f"Starting pipeline for {vendor} {model}"
        logger.info(msg)
#        log_task(device_name, 'pre-checks', 'pipeline started', 'Success', msg)

        # Step 1: Precheck 
        precheck = PreCheck(device, accepted_vendors)
        conn = precheck.connect(logger)

        if not conn: 
            msg = "Not connecting to the device"
            logger.error(msg)
#            log_task(device_key, 'pre-checks', 'connection using credentials', 'Failed',
#                 f'{host}: {msg}')
#            abort(device_key, 'pre-checks', 'connection using credentials', f'{host}: connect() returned None', logger)
            sys.exit(1)

#        log_task(device_key, 'pre-checks', 'connection using credentials', 'Success',
#                 f'{host}: Connected successfully')
        msg = "Running pre-checks"
        logger.info(msg)
        print(msg)
        precheck_sucess = run_prechecks(conn, device, accepted_vendors,commands, logger)

        if not precheck_sucess: 
            msg = "skipping upgrade due to failed prechecks"
            logger.info(msg)
            print(msg)
            sys.exit(1)
        
        msg = f"{host}: Prechecks passed, starting upgrade"
        logger.info(msg)
        print(msg)
        conn, upgrade_success = run_upgrade(conn, device, accepted_vendors, logger) 
       
        if not upgrade_success: 
          msg = f"Upgrade Failed" 
          logger.info(msg) 
          print(msg)
#          rollback = run_rollback(conn, device, accepted_vendors, vendor, model, host, logger)
#          if not rollback: 
#            msg = f"Rollback failed" 
#            logger.info(msg) 
#            print(msg) 

        msg = f"{host}: Upgrade Success, starting postchecks"
        logger.info(msg) 
        print(msg)
        
        postcheck_success = run_postcheck(conn, device, accepted_vendors, logger)
        if not postcheck_success: 
          msg = f"Postcheck Failed" 
          logger.info(msg) 
          print(msg) 
          precheck.disconnect(logger) 
          sys.exit(1) 
       
        msg = f"{host}: Post check success. The device is upgraded successfully. " 
        logger.info(msg) 
        print(msg) 
        

    except Exception as e: 
:        msg = f"Device Upgrade failed for {vendor}_{model}: {e}"
        logger.error(msg)
        print(msg)

    finally:
        msg = f"Execution flow is completed for {vendor}_{model}"
        logger.info(msg)
        prechecks.disconnect(logger)
        sys.exit(1)



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


if __name__ == "__main__":
    main()
#store the ouput in a text file 


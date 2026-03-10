colt@colt-UCSC-C220-M7S:~/Desktop/UpgradeAutomation/venv$ cat upgrade.py
import logging
from netmiko import ConnectHandler
from lib.utilities import *
from prechecks import PreCheck
import subprocess
import re
# logger = logging.getLogger(__name__)
#----------------------------------------------------#
# Upgrade class
#----------------------------------------------------#
class Upgrade:

    """
    Handles configuration and log backups from devices.
    Currently support JUNOS devices

    """

    def __init__(self, device, accepted_vendors):
        self.host = device.get("host")
        self.vendor = device.get('vendor')
        self.accepted_vendor = accepted_vendors
        self.prechecks = PreCheck(device,accepted_vendors)

    def reconnect_and_verify(self, logger, max_retries=6, wait_time=20):
      """
      Disconnect stale session, reconnect, and verify 'show version'.
      """
      self.prechecks.disconnect(logger)  # kill old session
      for attempt in range(max_retries):
        try:
            logger.info(f"{self.host}: Reconnect attempt {attempt+1}")
            conn = self.prechecks.connect(logger)
            if conn:
                output = conn.send_command("show version")
                if output:
                    logger.info(f"{self.host}: SSH ready, got version output")
                    return conn, output
        except Exception as e:
            logger.warning(f"{self.host}: attempt {attempt+1} failed: {e}")
        time.sleep(wait_time)
      raise RuntimeError(f"{self.host}: SSH not ready after {max_retries} retries")
    # -------------------------------
    # Intiating the image upgradation
    # -------------------------------
    def imageUpgrade(self,conn, expected_os,target_image,device_name, logger):
        try:
            logger.info(f"{self.host}: Starting image upgrade process\n")

            if not conn:
                msg = f"Not connected to device for vendor: {self.vendor}"
                logger.error(msg)
                raise RuntimeError("Not connected to device")
            #-----------------------------
            # Get current version
            #-----------------------------
            if (
                self.vendor not in self.accepted_vendor
            ):
                logger.error(f"Unsupported vendor: {self.vendor}")
                self.prechecks.disconnect(logger)
                raise ValueError(f"Unsupported vendor: {self.vendor}")

            curr_version = ""
            output = conn.send_command("show version")
            print(f"device result: {global_variable.device_results}")
            for device_entry in global_variable.device_results:
                if device_name in device_entry:
                    curr_version = output
                    print(f"curr_version: {curr_version}")
                    if self.vendor == "juniper":
                      curr_version = re.search(r"Junos:\s*(?P<version>\S+)", curr_version, re.IGNORECASE)
                    curr_version = curr_version.group('version')
                else:
                    msg = f"No such device in pre_output variable. Please make sure you run the execute_command() for {device_name}"
                    logger.info(msg)
                    print(msg)
                    self.prechecks.disconnect(logger)
                    return conn, False

            print(f"current version: {curr_version}")
            logger.info(f"{self.host}: current version -> {curr_version}")

            if expected_os == curr_version:
                logger.info(f"{self.host}: Already running expected version\n")
                msg = {"status": "Already_Upgraded"}
                logger.info(msg)
#                self.prechecks.disconnect(logger)
                return conn, True


            logger.info(f"{self.host}: Installing device image: {target_image}\n")

            if self.vendor == "juniper":
                cmd = f"request vmhost software add /var/tmp/{target_image} no-validate"
                output = conn.send_command(cmd,read_timeout=900)
                print(f"image installing: {output}")


                if not output:
                    msg = f"{target_image} is not installed. Please check the imageUpgrade()"
                    logger.error(msg)
                    print(msg)
                    return conn, False

            if self.vendor == "cisco":
                conn.send_command(
                    f"install add file {target_image} activate commit",
                    read_timeout=900
                )
            reboot_system = self.systemReboot(conn, logger)
            logger.info(f"{self.host}: Waiting for reboot after final upgrade")
            # time.sleep(900)

            # ---------------------------
            # Verify Version
            # ---------------------------
            if reboot_system:
#                conn = self.prechecks.connect(logger)
#                time.sleep(10)
#                print(f"conn: {conn}")
#                if not conn:
#                  msg = f"{self.host}: Not connected to a device"
#                  logger.info(msg)
#                  print(msg)
#                  msg = f"{self.host}: Connecting to device after reboot"
#                  logger.info(msg)
#                  print(msg)
#                  conn = self.prechecks.connect(logger)
#                print("Running show version command",conn)
#                output = conn.send_command("show version")
#                print(f"Output: {output}")
                logger.info(f"{self.host}: Device rebooted, waiting for SSH to come back")
                conn, output = self.reconnect_and_verify(logger)
                print(f"Output: {output}")
                if self.vendor == "juniper":
                    version_pattern = re.search(r"Junos:\s*(?P<version>\S+)", output, re.IGNORECASE)
                if self.vendor == "cisco":
                    version_pattern = re.search(r"Cisco:\s*(?P<version>\S+)", output, re.IGNORECASE)

                if version_pattern:
                    new_version = version_pattern.group("version")
                else:
                    logger.warning("No device name and version found. Check the output file")
                    self.prechecks.disconnect(logger)
                    raise ValueError("No device name and version found. Check the output file")


                logger.info(f"{self.host}: Version information retrieved\n")
                logger.info(f"{self.host}: New Version -> {new_version}")

                if expected_os == new_version:
                    msg = {
                        "status": "SUCCESS",
                        "version": new_version
                    }
                    logger.info(msg)
                    print(msg)
                    return conn, True
                else:
                    logger.error(f"{self.host}: Version mismatch after upgrade\n")
                    msg = {
                        "status": "FAILED",
                        "expected_version": expected_os,
                        "current_version": new_version
                    }
                    logger.info(msg)
                    return conn, False

        except Exception as e:
            logger.exception(f"{self.host}: Image upgrade failed: {e}\n")
            logger.info(f"{self.host}: Please check the imageUpdrade function or rollback to the {curr_version}")
            self.prechecks.disconnect(logger)
            return conn, False

    def pingDevice(self, logger, packet_size=5, count=2, timeout=2):
        """
        Ping device with custom packet size.
        Returns True if ping succeeds.
        """
        try:
            command = [
                "ping",
                "-c", str(count),
                "-s", str(packet_size),
                "-W", str(timeout),
                self.host
            ]

            result = subprocess.run(
                command,
                stdout = subprocess.DEVNULL,
                stderr = subprocess.DEVNULL
            )

            return result.returncode == 0
        except Exception as e:
            msg = f"Ping failed with error: {e}"
            print(msg)
            logger.error(f"{self.host}: Ping failed with error: {e}")
            msg = "Host is not reachable"
            print(msg)
            logger.info(f"{self.host}: Host is not reachable")
            return False

    def systemReboot(self, conn, logger):
        """
        Reboot device and verify reachability using ping.
        Return true if device responds to ping after reboot
        """
        try:
            logger.info(f"{self.host}: Rebooting the system...\n")

            if self.vendor == 'juniper':
                command = [
                    "request vmhost reboot",
                    "yes",
                    "\n"
                ]
            elif self.vendor == 'cisco':
                command = [
                    "reload",
                    "\n",
                    "yes"
                ]
            else:
                msg = f"Unsupported vendor: {self.vendor}\n Supported Vendors:\n{self.accepted_vendor}"
                logger.error(msg)
                print(msg)
                self.prechecks.disconnect(logger)
                raise ValueError(msg)

            msg = f"{self.host}: Running {command}..."
            logger.info(msg)
            print(msg)
            output = conn.send_multiline_timing(command)

            print(f"reboot: {output}")

            msg = f"{self.host}: Waiting for device to reboot..\n"
            logger.info(msg)
            print(msg)

            msg = f"{self.host}: starting ping check after reboot"
            logger.info(msg)
            print(msg)
            time.sleep(1200)
            if self.pingDevice(logger):
                msg = "Device is reachable after reboot"
                print(msg)
                logger.info(f"{self.host}: Device is reachable after reboot")
                return True
            msg = "Device is not reachable after reboot"
            print(msg)
            logger.error(f"{self.host}: Device is not reachable after reboot")
            return False
        except Exception as e:
            logger.error(f"{self.host}: Not able to reboot the device: {e}.\n")
            logger.error(f"check the systemReboot function\n")
            self.prechecks.disconnect(logger)
            return False



colt@colt-UCSC-C220-M7S:~/Desktop/UpgradeAutomation/venv$ ^C
colt@colt-UCSC-C220-M7S:~/Desktop/UpgradeAutomation/venv$ cat main.py
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
        filename = f"{device_name}_{pre_check_timestamp}-pre"
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

            # Step4: Md5 checksum
            verify_checksum = precheck.verifyChecksum(conn, checksum, image, logger)
            if not verify_checksum:
              msg = "Checksum verification failed"
              logger.info(msg)
              return False
#
            conn, isUpgrade = upgrade.imageUpgrade(conn,expected_os, image, device_name, logger)


            if not isUpgrade:
              msg = f"Upgrade is not successful for {device_name}"
              logger.info(msg)
              print(msg)
              msg = f"Rolling back to the old image for {device_name}"
              logger.info(msg)
              print(msg)
              rollback = run_rollback(conn, device, vendor, device_name, rollback_image, host, logger,accepted_vendors)
              if not rollback:
                msg = f"Rollback failed"
                logger.info(msg)
                print(msg)
                precheck.disconnect(logger)
                return False
              break
            rollback_image.append({
                "image": image,
                "expected_os": expected_os
            })

        msg = f"Image installation is successful for {device_name}"
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
      reversed_list = imageDetails[::-1]
      log_lines = ["\n===== ROLLBACK CHAIN (REVERSED) ====="]
      for i, entry in enumerate(reversed_list, start=1):
          log_lines.append(f"{i}. image = {entry.get('image')}, expected_os = {entry.get('expected_os')}")
          log_lines.append("=====================================\n")
          log_text = "\n".join(log_lines)
          print(log_text)
          logger.info(log_text)
          original_os = device.get("curr_os")

      for details in reversed_list:
        rollback_image = details.get('image')
        expected_os = details.get("expected_os")


        if (
          not rollback_image or
          not expected_os
        ):
          msg = "Please provide the image details you want to rollback to"
          logger.info(msg)
          print(msg)
          precheck.disconnect(logger)
          return conn, False

        step_msg = f"Rollback Step → Installing: {rollback_image}, expecting OS: {expected_os}"
        print(step_msg)
        logger.info(step_msg)


        conn, isRollback = upgrade.imageUpgrade(conn,expected_os, rollback_image, device_name, logger)
        if not isRollback:
          msg = f"Rollback is not successful for {device_name}"
          logger.info(msg)
          print(msg)
          precheck.disconnect(logger)
          return conn, False

        if expected_os == original_os:
          done_msg = f"{device_name}: Original OS {original_os} restored. Rollback complete."
          logger.info(done_msg)
          print(done_msg)
          return conn, True


#    if vendor == "cisco":
#      isRollback = rollback.imageRollback(conn, device_name, logger)

#    if not isRollback:
#      msg = f"Rollback is not successful for {device_name}"
#      logger.info(msg)
#      print(msg)
#      precheck.disconnect(logger)
#      return False
    logger.info(f"{device_name}: Multi-step rollback completed.")
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
        filename = f"{device_name}_{post_check_timestamp}-post"
        print(f" filename: {filename}")

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
          rollback = run_rollback(conn, device, accepted_vendors, vendor, model, host, logger)
          if not rollback:
            msg = f"Rollback failed"
            logger.info(msg)
            print(msg)
            sys.exit(1)

        msg = f"{host}: Upgrade Success, starting postchecks"
        logger.info(msg)
        print(msg)

#        postcheck_success = run_postcheck(conn, device, accepted_vendors,commands, logger)
#        if not postcheck_success:
#          msg = f"Postcheck Failed"
#          logger.info(msg)
#          print(msg)
#          precheck.disconnect(logger)
#          sys.exit(1)
#
#        msg = f"{host}: Post check success. The device is upgraded successfully. "
#        logger.info(msg)
#        print(msg)


    except Exception as e:
        msg = f"Device Upgrade failed for {vendor}_{model}: {e}"
        logger.error(msg)
        print(msg)

    finally:
        msg = f"Execution flow is completed for {vendor}_{model}"
        logger.info(msg)
        precheck.disconnect(logger)
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


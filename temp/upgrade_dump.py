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


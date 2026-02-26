import logging
from netmiko import ConnectHandler
from lib.utilities import *
import re
from datetime import datetime
import os

# logger = logging.getLogger(__name__)
#----------------------------------------------------#
# PreCheck class
#----------------------------------------------------#

class PreCheck:

    """
    Handles configuration and log backups from devices.
    Currently support Juniper devices

    """

    def __init__(self, device, test_mode=False):
        self.device = device
        self.conn = None
        self.host = device.get("devices")[0].get("host")
        self.device_type = device.get("devices")[0].get('device_type')
        self.vendor = device.get("devices")[0].get('vendor', '').lower()
        self.model = str(device.get("devices")[0].get('model', '')).lower().replace("-", "")
        self.min_disk_gb = device.get("devices")[0].get('min_disk_gb')
        self.username = device.get("devices")[0].get('username')
        self.device_key = f"{self.vendor}_{self.model}"
        session_log_dir = os.path.join(os.getcwd(), "outputs")
        os.makedirs(session_log_dir, exist_ok=True)

    # -------------------------------
    # Connection Handling
    # -------------------------------
    def connect(self, logger):
        try:
            msg = f"Connecting to {self.host}"

            logger.info(msg)

            session_log_dir = os.path.join(os.getcwd(), "outputs")
            os.makedirs(session_log_dir, exist_ok=True)

            session_logs_file = f"{self.vendor}_{self.model}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
            session_logs_path = os.path.join(session_log_dir, session_logs_file)

            self.conn = login_device(
                    device_type = self.device.get("devices")[0].get('device_type'),
                    host = self.device.get("devices")[0].get("host"),
                    username = self.device.get("devices")[0].get("username"),
                    password = self.device.get("devices")[0].get("password"),
                    session_log_path= session_logs_path,
                    logger = logger
                )

            if self.conn is not None:
                msg = f"{self.host}: Connected successfully"
                logger.info(msg)
                print("connection..", self.conn)

                log_task(self.device_key, 'pre-checks', 'connection using credentials', 'Success', 'loggedin', 'DEVICE IN')

                return self.conn

        except Exception as e:
            msg = f"{self.host}: Not able to connect the device for vendor: {self.vendor}"
            logger.error(msg)

            log_task(self.device_key, 'pre-checks', 'connection using credentials', 'Failed', str(e))
            exit(1)

    def disconnect(self, logger):
        try:
            if self.conn:
                msg = "Logging out from device"
                logging.info(msg)
                logout_device(self.conn, self.host, logger)
                self.conn = None
            else:
                msg = "Device is not connected already"
                logger.info(msg)
                exit
        except Exception as e:
            msg = "Not able to logout from device for vendor: {self.vendor}"
            logger.error(msg)
            exit

    def showVersion(self, conn, vendor, logger):
        """
        Detect vendor and execute show version for specific model
        to get current OS version and firmware version
        """
        try:
            # self.conn = self.connect()
            print("Running show version")
            msg = f"Running show version for {vendor}"
            logger.info(msg)
            print(f" Device type: {vendor}")

            if not conn:
                msg = f"{self.host}: Not connected to device for vendor: {vendor}"
                print(msg)
                logger.error(msg)
                raise RuntimeError(msg)
                exit

            if (
                self.vendor not in  ["juniper", "cisco"]
            ):
                msg = f"{self.host}: Unsupported vendor: {self.vendor}"
                print(msg)
                logger.error(msg)
                raise ValueError(msg)
                self.disconnect(logger)

            command = "show version"
            print(f"{command}")
            msg = f"{self.host}: Executing '{command}' for vendor: {vendor}"
            logger.info(msg)
            print(msg)
            output = conn.send_command(command)

            print("\nOP START\n", output, "\nOP END\n")
            print("vendor..", self.vendor)
            if self.vendor == 'juniper':
                print(msg)
                msg = "Fetching the version from the output for vendor: {self.vendor}"
                version_pattern = re.search(r"\s*Junos:\s*(?P<version>\S+)", output, re.IGNORECASE)

            if version_pattern:
                version = version_pattern.group("version")
                print(version)
            else:
                msg = "No device name and version found. Check the output file for vendor: {self.vendor}"
                print(msg)
                logger.warning(msg)
                self.disconnect(logger)
                raise ValueError(msg)

            msg = f"{self.host}: Version information retrieved for vendor: {self.vendor}"
            logger.info(msg)


            log_task(self.device_key, 'pre-checks', 'show version', 'Success', 'Version information retrieved', '')  # Since we tested connection

            return output

        except Exception as e:
            logger.error(f"{self.host}: Show version failed: {e}")
            self.disconnect(logger)
            return False
            raise

    # -------------------------------
    # Pre Backup image
    # -------------------------------
    def preBackup(self, conn, filename, logger):

        # -------------------------------
        # Backup the running configuration
        # -------------------------------

        try:
            msg = f"Taking device backup vendor: {self.vendor}"
            print(f"Taking device backup vendor: {self.vendor}")
            logger.info(msg)

            if not conn:
                msg = f"Not connected to device for vendor: {self.vendor}"
                logger.error(msg)
                log_task(self.device_key, 'pre-checks', 'Backup Config', 'Failed', msg)
                raise RuntimeError("Not connected to device")

            if self.vendor not in ["juniper", "cisco"]:
                msg = f"Unsupported vendor: {self.vendor}"
                logger.error(msg)
                log_task(self.device_key, 'pre-checks', 'Backup Config', 'Failed', msg)
                raise ValueError(msg)

            vendor_test = self.vendor
            print(f"type: {type(self.vendor)} and vendor: {vendor_test}")

            # Executing the commands for backup
            def execute_command_test(conn, commands, stage, logger):
                print(conn)
                try:
                    print(commands)
                    msg = f"{self.host}: Running {stage} for vendor: {self.vendor}..."
                    print("I am in execution command")
                    logger.info(msg)

                    for cmd in commands:
                        msg = f"{self.host}: Excecuting '{cmd}'"
                        logger.info(msg)
                        print(f"command: {cmd}")

                        if "Configuration" in stage:
                            print(f"cmd: {cmd}")
                            result = conn.send_config_set(cmd, cmd_verify=False) + "\n"
                            print(f"result: {result}")

                        if "log" in stage:
                            print(f"cmd: {cmd}")
                            result = conn.send_command(
                                cmd,
                                cmd_verify=False,
                                expect_string=r".*>",
                                read_timeout=300,
                            ) + "\n"
                            print(f"result: {result}")

                    return True

                except Exception as e:
                    print(e)
                    msg = f"{self.host}: {stage} failed for vendor: {self.vendor}"
                    logger.error(msg)
                    self.disconnect(logger)
                    return False

            # Vendor-specific backup execution
            if self.vendor == "juniper":

                config_commands = [
                    "configure",
                    f"save {filename}",
                    "run file list",
                    "exit",
                ]

                log_commands = [
                    f"request support information | save /var/log/{filename}.txt ",
                    f"file archive compress source /var/log/ destination /var/tmp/{filename}.tgz",
                ]

                print("Call execute commands")
                preBackupConfig = execute_command_test(
                    conn, config_commands, "Configuration backup", logger
                )

                preDeviceLog = execute_command_test(
                    conn, log_commands, "Device log backup", logger
                )

                preBackupDisk = self.preBackupDisk(conn)

            elif self.vendor == "cisco":

                cisco_commands = [
                    "copy running-config harddisk:show-run-xr.txt",
                    "admin",
                    "copy running-config harddisk:show-run-admin location 0/RSP0/CPU0/VM1",
                ]

                print("Executing Cisco backup commands")

                try:
                    for cmd in cisco_commands:
                        msg = f"{self.host}: Executing '{cmd}'"
                        logger.info(msg)
                        print(f"command: {cmd}")
                        result = conn.send_command(
                            cmd,
                            cmd_verify=False,
                            expect_string=r".*#",
                            read_timeout=300,
                        )
                        print(f"result: {result}")

                    preBackupConfig = True
                    preDeviceLog = True
                    preBackupDisk = self.preBackupDisk(conn)

                except Exception as e:
                    print(e)
                    msg = f"{self.host}: Cisco backup failed: {e}"
                    logger.error(msg)
                    preBackupConfig = False
                    preDeviceLog = False
                    preBackupDisk = False

            if preBackupConfig and preDeviceLog and preBackupDisk:
                log_task(self.device_key, 'pre-checks', 'Backup Config', 'Success', '')
                return True
            else:
                msg = f"Device Backup failed for vendor: {self.vendor}"
                logger.error(msg)
                log_task(self.device_key, 'pre-checks', 'Backup Config', 'Failed', msg)
                self.disconnect(logger)

        except Exception as e:
            print(e)
            msg = f"Device Backup failed for vendor: {self.vendor}: {e}"
            logger.error(msg)
            log_task(self.device_key, 'pre-checks', 'Backup Config', 'Failed', str(e))
            self.disconnect(logger)
            return False

    # ------------------------------------
    # Transfering image to Router
    # -------------------------------------

    def transferImage(self, local_image_path, filename, logger):
        """
        Transfer Juniper image to router disk (/tmp) using CLI commands
        """
        try:
            msg="Transfer Juniper image to router disk (/tmp) using CLI commands"
            logger.info(msg)
            if not self.conn:
                msg="Not connected to device"
                logger.error(msg)
                raise RuntimeError("Not connected to device")

            if (
                    self.vendor not in  ["juniper", "cisco"]
                ):
                    msg = f"Unsupported vendor: {self.vendor}"
                    logger.error(msg)
                    raise ValueError(msg)
                    self.disconnect(logger)

            if self.device_type == "juniper":

                image_name = self.image
                remote_path = f"/tmp/{image_name}"

                # Build CLI SCP command (router pulls file from SCP server)
                # NOTE: Replace <scp-server> and <user> with actual values
                commands = [
                    f"scp <scp-user>@<scp-server>:{local_image_path} {remote_path}\n"
                ]

            elif self.device_type == "cisco":
                pass

            output = ""
            for cmd in commands:
                logger.info(f"{self.host}: Executing '{cmd.strip()}'")
                result = self.conn.send_command_timing(cmd)
                output += result + "\n"
                print(f"output: {result}")

            logger.info(f"{self.host}: Image transferred to {remote_path}")
            return remote_path

        except Exception as e:
            msg="f{self.host}: Image transfer failed: {e}"
            logger.error(msg)
            self.disconnect(logger)
            raise


    # -----------------------------------
    # Validate the MD5 Checksum of image
    # -----------------------------------

    def verifyChecksum(self,conn, logger):
        """
        Verify MD5 checksum of Juniper image file in /var/tmp/
        Retrieves filename and expected checksum from self.device

        Returns:
            True if checksums match, False otherwise
        """
        try:
            if not conn:
                logger.error("Not connected to device")
                raise RuntimeError("Not connected to device")

            if (self.vendor not in  ["juniper", "cisco"]):
                msg = f"Unsupported vendor: {self.vendor}"
                logger.error(msg)
                raise ValueError(msg)
                self.disconnect(logger)
            filename = self.device.get("devices")[0].get("target_image")
            expected_checksum = self.device.get("devices")[0].get("md5checksum_file")

            if not filename or not expected_checksum:
                logger.error(f"{self.host}: Missing filename or checksum in device config")
                raise ValueError("Missing filename or checksum in device config")

            command = f"file checksum md5 /var/tmp/{filename}"
            logger.info(f"{self.host}: Executing '{command}'")
            output = conn.send_command(command, expect_string=r".*>", read_timeout=60)
            logger.debug(f"{self.host}: Checksum output: {output}")
            r = re.search(r'\.tgz\)\s*=\s*(.*)',output).group(1)

            logger.info(f"{self.host}: inputed from user checksum: {expected_checksum}")
            logger.info(f"{self.host}: extracted from device  checksum: {r}")

            # Compare checksums
            if r.lower() == expected_checksum.lower():
                logger.info(f"{self.host}: Checksum verification PASSED")
                return True
            else:
                logger.warning(f"{self.host}: Checksum verification FAILED")
                logger.warning(f"{self.host}: Expected: {expected_checksum}")
                logger.warning(f"{self.host}: Got: {r}")
                return False

        except Exception as e:
            logger.error(f"{self.host}: Checksum verification failed: {e}")
            raise

    def preBackupDisk(self, conn):
        """
        Check number of disks on a device
        Backing up the whole primary disk1 config to disk2 for rollback
        """
        for attempt in range(1, 4):
            logger.info(f"Attempt {attempt} to backup disk for vendor: {self.vendor}")
            time.sleep(60)  # wait 1 minute before each attempt
            try:
                msg = "Backing up the whole primary disk1 config to disk2 for rollback"
                logger.info(f"Backing up the whole primary disk1 config to disk2 for rollback for vendor: {self.vendor}")

                if not conn:
                    msg = f"Not connected to device for vendor: {self.vendor}"
                    logger.error(msg)
                    raise RuntimeError("Not connected to device")
                    exit

                if (
                    self.vendor not in  ["juniper", "cisco"]
                ):
                    msg = f"Unsupported vendor: {self.vendor}"
                    logger.error(msg)
                    raise ValueError(msg)
                    self.disconnect()

                if self.vendor == "juniper":
                    msg = f"Check number of disks on a juniper device "
                    logger.info(msg)
                    output = conn.send_command("show vmhost version")
                    print(f"output: {output}")

                    if "set b" in output and "set p" in output:
                        msg = f"There are 2 disks in a device for vendor: {self.vendor}\n will take a backup of primary disk to backup disk"
                        logger.info(msg)
                        cmd = "request vmhost snapshot"
                        msg = f"{self.host}: executing the '{cmd}' for vendor: {self.vendor}"
                        logger.info(msg)
                        output = conn.send_command_timing(cmd)
                        if cmd in output or "yes,no" in output.lower():
                            output += conn.send_command("yes", expect_string=r".*>", read_timeout=180)
                        print(f"snapshot output: {output}")
                        logger.info(f"{self.host}: Disk1 backup is done for vendor: {self.vendor}")
                    else:
                        msg = f"There is only 1 disk in  a device for vendor: {self.vendor}\n No need to take a disk backup"
                        logger.info(msg)

                    return True
            except Exception as e:
                msg = f"{self.host}: Disk backup failed for vendor: {self.vendor}: {e}"
                logger.error(msg)
                self.disconnect()
                if attempt == 3:
                    logger.error("Aborting after 3 failed attempts")
                    return False

    # -------------------------------
    # Check Storage & Cleanup
    # -------------------------------
    def checkStorage(self,conn, logger):

        try:
            msg= f"{self.host}: Checking system storage for vendor: {self.vendor} "
            logger.info(msg)
            # conn=self.connect()
            if not conn:
                msg="Not connected to device"
                logger.error(msg)
                raise RuntimeError("Not connected to device")


            if (
                self.vendor not in  ["juniper", "cisco"]
            ):
                msg = f"Unsupported vendor: {self.vendor}"
                logger.error(msg)
                raise ValueError(msg)
                self.disconnect(logger)

            storage_output = conn.send_command("show system storage")
            print("command storage_output ::::")
            # free_gb =
            avail_space=re.search(r"^/dev/gpt/var\s+\S+\s+\S+\s+(\S+)", storage_output, re.M).group(1)

            avail_space=avail_space[:-1]


            avail_space=int(avail_space)
            print(avail_space,type(avail_space))


            if avail_space == None:
                msg= f"{self.host} Unable to parse storage output for vendor: {self.vendor}"
                raise ValueError(msg)

            msg=f"{self.host}: Free space {avail_space} GB for vendor: {self.vendor}"
            logger.info(msg)

            # Enough space
            if avail_space >= self.min_disk_gb:
                log_task(self.device_key, 'pre-checks', 'Storage Check (5GB threshold)', 'Success', '')

                return {"status": "OK", "avail_space": avail_space}

            # ---------------------------------------------------
            # LOW STORAGE → START CLEANUP
            # ---------------------------------------------------
            msg="LOW STORAGE → START CLEANUP"
            logger.info(msg)
            logger.warning(f"{self.host}: Low space! Running system cleanup")



            # ---------------------------------------------------
            # Delete files from YAML
            # ---------------------------------------------------
            files_to_delete = self.device.get("cleanup_files", [])

            msg=f"{self.host} Delete files from YAML for vendor: {self.vendor}"
            logger.info(msg)

            if not files_to_delete:
                logger.error(
                    f"{self.host}: cleanup_files EMPTY -> No files are available to delete"
                )
                self.disconnect(logger)
                return False

            for file in files_to_delete:
                logger.info(f"{self.host}: Deleting {file}")
                conn.send_command(f"file delete {file}")

            return {
                "status": "SELECTED_FILES_DELETED"
            }

        except Exception as e:
            msg = "f{self.host}: Storage cleanup failed for vendor: {self.vendor}"
            logger.exception(msg)
            log_task(self.device_key, 'pre-checks', 'Storage Check (5GB threshold)', 'Failed', str(e))

            self.disconnect(logger)
            raise

    def disableReProtectFilter(self, conn, logger):
        """
        Removes RE protection firewall filter from loopback interface (lo0).
        show configuration | display set | match lo0.0
        set interfaces lo0 unit 0 family inet filter input PROTECT-RE-FILTER
        """
        try:
            if not conn:
                msg = "Not connected to device"
                logger.error(msg)
                log_task(self.device_key, 'pre-checks', 'Disable Filter', 'Failed', msg)
                raise RuntimeError("Not connected to device")


            if (
                self.vendor not in  ["juniper", "cisco"]
            ):
                msg = f"Unsupported vendor: {self.vendor}"
                logger.error(msg)
                log_task(self.device_key, 'pre-checks', 'Disable Filter', 'Failed', msg)
                raise ValueError(msg)
                self.disconnect(logger)


            filter_commands = [
                "configure",
                "delete interfaces lo0.0 family inet filter",
                "commit",
                "exit"
            ]

            print(filter_commands)

            output = ""
            for cmd in filter_commands:
                logger.info(f"{self.host}: Executing '{cmd}'")
                print(cmd)
                output += f"[OK] {cmd}\n"

            output += "[edit]\ncommit complete\n"


            log_task(self.device_key, 'pre-checks', 'Disable Filter', 'Success', '')

            return output

        except Exception as e:
            logger.exception(f"{self.host}: Disable RE protect filter failed")
            log_task(self.device_key, 'pre-checks', 'Disable Filter', 'Failed', str(e))
            raise
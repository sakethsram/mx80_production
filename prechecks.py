import logging
import re
from lib.utilities import *

logger = logging.getLogger(__name__)

#----------------------------------------------------#
# PreCheck class
#----------------------------------------------------#
class PreCheck:

    """
    Handles configuration and log backups from devices.
    Currently support JUNOS devices
    """

    def __init__(self, device):
        self.device          = device
        self.conn            = None
        self.host            = device.get("host")
        self.device_type     = device.get('device_type')
        self.vendor          = device.get('vendor')
        self.model           = device.get('model')
        self.username        = device.get('username')
        self.remote_server   = device.get('remote_backup_server')
        self.remote_password = device.get('remote_password')
        self.min_disk_gb     = device.get('min_disk_gb')
        self.accepted_vendor = ["juniper", "cisco"]

    def checkStorage(self, conn, min_disk_gb):
        try:
            msg = f"{self.host}: Checking system storage for vendor: {self.vendor} "
            logger.info(msg)

            if not conn:
                msg = "Not connected to device"
                logger.error(msg)
                raise RuntimeError("Not connected to device")

            storage_output = conn.send_command("show system storage", expect_string=r'.*>')

            avail_space = re.search(r"^/dev/gpt/var\s+\S+\s+\S+\s+(\S+)*", storage_output, re.M).group(1)
            avail_space = avail_space[:-1]
            avail_space = int(float(avail_space))

            if avail_space == None:
                msg = f"{self.host} Unable to parse storage output for vendor: {self.vendor}"
                logger.error(msg)
                raise ValueError(msg)

            msg = f"{self.host}:  {avail_space} GB available for {self.vendor}"
            logger.info(msg)

            # Enough space
            if avail_space > min_disk_gb:
                result = {
                    "status":        "ok",
                    "deleted_files": [],
                    "exception":     "",
                    "sufficient":    True,
                }
                logger.info(result)
                return result

            # ---------------------------------------------------
            # LOW STORAGE → START CLEANUP
            # ---------------------------------------------------
            logger.warning(f"{self.host}: Low space! Running system cleanup")

            files_to_delete = self.device.get("cleanup_files")

            if len(files_to_delete) == 0:
                logger.error(f"{self.host}: cleanup_files EMPTY -> No files are available to delete")
                return {
                    "status":        "failed",
                    "deleted_files": [],
                    "exception":     "cleanup_files empty",
                    "sufficient":    False,
                }

            deleted_files = []
            for file in files_to_delete:
                logger.info(f"{self.host}: Deleting {file}")
                conn.send_command(f"file delete {file}")
                deleted_files.append(file)

            result = {
                "status":        "low_space_cleaned",
                "deleted_files": deleted_files,
                "exception":     "",
                "sufficient":    False,
            }
            logger.info(result)
            return result

        except Exception:
            msg = f"{self.host}: Storage cleanup failed for vendor: {self.vendor}"
            logger.exception(msg)
            raise   

    def preBackupDisk(self, conn):
        try:
            logger.info(f"Backing up the whole primary disk1 config to disk2 for rollback for vendor: {self.vendor}")

            if not conn:
                msg = f"Not connected to device for vendor: {self.vendor}"
                logger.error(msg)
                raise RuntimeError("Not connected to device")

            if self.vendor not in self.accepted_vendor:
                msg = f"Unsupported vendor: {self.vendor}"
                logger.error(msg)
                raise ValueError(msg)

            if self.vendor == "juniper":
                logger.info(f"Check number of disks on a juniper device")
                output = conn.send_command("show vmhost version", read_timeout=300)

                if "set b" in output and "set p" in output:
                    logger.info(f"There are 2 disks in a device for vendor: {self.vendor}\n will take a backup of primary disk to backup disk")
                    cmd = "request vmhost snapshot"
                    logger.info(f"{self.host}: executing the '{cmd}' for vendor: {self.vendor}")
                    output = conn.send_command_timing(cmd)
                    if cmd in output or "yes,no" in output.lower():output += conn.send_command("yes", expect_string=r".*>", max_loops=3, read_timeout=900)
                    logger.info(f"{self.host}: Disk1 backup is done for {self.vendor}")
                    return {
                        "status":     "ok",
                        "exception":  "",
                        "disk_count": "dual",
                    }
                else:
                    logger.info(f"There is only 1 disk in a device for {self.vendor}\n No need to take a disk backup")
                    return {
                        "status":     "skipped",
                        "exception":  "",
                        "disk_count": "single",
                    }

        except Exception as e:
            msg = f"{self.host}: Disk backup failed for {self.vendor}: {e}"
            logger.error(msg)
            return {
                "status":     "failed",
                "exception":  str(e),
                "disk_count": "",
            }
    def preBackup(self, conn, filename):
        try:
            msg = f"Taking device backup for vendor: {self.vendor}"
            logger.info(msg)

            if not conn:
                msg = f"Not connected to device for vendor: {self.vendor}"
                logger.error(msg)
                raise RuntimeError("Not connected to device")

            if self.vendor not in self.accepted_vendor:
                msg = f"Unsupported vendor: {self.vendor}"
                logger.error(msg)
                raise ValueError(msg)

            if self.vendor == "juniper":
                preBackupConfig = False
                preDeviceLog    = False

                # Step 1: Backup running config
                config_commands = [
                    f"save {filename}",
                    "run file list"
                ]
                configBackup = conn.send_config_set(config_commands, cmd_verify=False, strip_command=True)
                if configBackup:
                    logger.info(f"{self.host}: Config saved, copying to remote server")
                    src      = f"/var/home/lab/{filename}"
                    dest     = f"{self.remote_server}:/var/tmp/{filename}"
                    saveFile = self.scpFile(conn, src, dest)
                    if saveFile:
                        preBackupConfig = True
                    else:
                        return {
                            "status":      "failed",
                            "exception":   "SCP of config file failed",
                            "config_file": filename,
                            "log_file":    "",
                            "destination": dest,
                        }

                # Step 2: Backup device log
                log_commands = [
                    f"request support information | save /var/log/{filename}.txt",
                    f"file archive compress source /var/log/* destination /var/tmp/{filename}.tgz"
                ]
                for cmd in log_commands:    logs = conn.send_command_timing(cmd, read_timeout=900, last_read=10.0)
                logs = True
                if logs:
                    logger.info(f"{self.host}: Logs archived, copying to remote server")
                    src      = f"/var/tmp/{filename}.tgz"
                    dest     = f"{self.remote_server}:/var/tmp/{filename}.tgz"
                    saveFile = self.scpFile(conn, src, dest)
                    if saveFile:
                        preDeviceLog = True
                    else:
                        return {
                            "status":      "failed",
                            "exception":   "SCP of log file failed",
                            "config_file": filename,
                            "log_file":    f"{filename}.tgz",
                            "destination": dest,
                        }

                if not preBackupConfig or not preDeviceLog:
                    return {
                        "status":      "failed",
                        "exception":   "Config or log backup incomplete",
                        "config_file": filename,
                        "log_file":    f"{filename}.tgz",
                        "destination": self.remote_server,
                    }

                return {
                    "status":      "ok",
                    "exception":   "",
                    "config_file": filename,
                    "log_file":    f"{filename}.tgz",
                    "destination": self.remote_server,
                }

        except Exception as e:
            msg = f"{self.host}: Device backup failed for vendor: {self.vendor}: {e}"
            logger.error(msg)
            return {
                "status":      "failed",
                "exception":   str(e),
                "config_file": "",
                "log_file":    "",
                "destination": "",
            }
    def scpFile(self, conn, src, dest):
        try:
            msg = f"Copying files to remote server"
            logger.info(msg)

            cmd = [
                "start shell",
                "\n",
                f"scp -C {src} {dest}",
                "\n",
                self.remote_password,
                "\n",
                "exit",
                "\n"
            ]
            saving_file = conn.send_multiline_timing(cmd, read_timeout=1800)
            logger.debug(f"{self.host}: SCP output:\n{saving_file}")

            if "No such file or directory" in saving_file:
                msg = f"{self.host}: No such file or directory: {src}"
                logger.error(msg)
                return False

            if not saving_file:
                msg = f"{self.host}: SCP returned no output"
                logger.error(msg)
                return False

            logger.info(f"{self.host}: File copied successfully")
            return True

        except Exception as e:
            msg = f"{self.host}: SCP failed for {self.vendor}: {e}"
            logger.error(msg)
            return False
    def transferImage(self, conn, image_path, target_image):
        try:
            msg = f"Transferring image {target_image} to device for vendor: {self.vendor}"
            logger.info(msg)

            if not conn:
                msg = "Not connected to device"
                logger.error(msg)
                raise RuntimeError("Not connected to device")

            if self.vendor not in self.accepted_vendor:
                msg = f"Unsupported vendor: {self.vendor}"
                logger.error(msg)
                raise ValueError(msg)

            if self.vendor == "juniper":
                src      = f"{self.remote_server}:{image_path}/{target_image}"
                dest     = "/var/tmp/"
                transfer = self.scpFile(conn, src, dest)
                if not transfer:
                    return {
                        "status":      "failed",
                        "exception":   f"SCP transfer failed for {target_image}",
                        "image":       target_image,
                        "destination": dest,
                    }

            logger.info(f"{self.host}: Image {target_image} transferred to {dest}")
            return {
                "status":      "ok",
                "exception":   "",
                "image":       target_image,
                "destination": dest,
            }

        except Exception as e:
            msg = f"{self.host}: Image transfer failed for vendor: {self.vendor}: {e}"
            logger.error(msg)
            return {
                "status":      "failed",
                "exception":   str(e),
                "image":       "",
                "destination": "",
            }


    def verifyChecksum(self, conn, target_image, expected_checksum):
        try:
            msg = f"Verifying MD5 checksum for {target_image} on vendor: {self.vendor}"
            logger.info(msg)

            if not conn:
                msg = "Not connected to device"
                logger.error(msg)
                raise RuntimeError("Not connected to device")

            if self.vendor not in self.accepted_vendor:
                msg = f"Unsupported vendor: {self.vendor}"
                logger.error(msg)
                raise ValueError(msg)

            if self.vendor == "juniper":
                command = f"file checksum md5 /var/tmp/{target_image}"
                logger.info(f"{self.host}: Executing '{command}'")
                output   = conn.send_command(command, expect_string=r".*>", read_timeout=60)
                match = re.search(r'MD5\s*\(.*?\)\s*=\s*(\S+)', output)

                if not match:
                    return {
                        "status":    "failed",
                        "exception": "Could not parse checksum from output",
                        "expected":  expected_checksum,
                        "computed":  "",
                        "match":     False,
                    }

                computed = match.group(1).strip()
                logger.info(f"{self.host}: Expected checksum:  {expected_checksum}")
                logger.info(f"{self.host}: Computed checksum:  {computed}")

                if computed == expected_checksum:
                    logger.info(f"{self.host}: Checksum PASSED")
                    return {
                        "status":    "ok",
                        "exception": "",
                        "expected":  expected_checksum,
                        "computed":  computed,
                        "match":     True,
                    }
                else:
                    logger.warning(f"{self.host}: Checksum FAILED")
                    return {
                        "status":    "failed",
                        "exception": "Checksum mismatch",
                        "expected":  expected_checksum,
                        "computed":  computed,
                        "match":     False,
                    }

        except Exception as e:
            msg = f"{self.host}: Checksum verification failed for vendor: {self.vendor}: {e}"
            logger.error(msg)
            return {
                "status":    "failed",
                "exception": str(e),
                "expected":  "",
                "computed":  "",
                "match":     False,
            }
        
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
                raise RuntimeError("Not connected to device")

            if self.vendor not in self.accepted_vendor:
                msg = f"Unsupported vendor: {self.vendor}"
                logger.error(msg)
                raise ValueError(msg)

            filter_commands = [
                "delete interfaces lo0.0 family inet filter",
                "commit"
            ]

            print(filter_commands)

            for cmd in filter_commands:
                logger.info(f"{self.host}: Executing '{cmd}'")
                print(f"Executing '{cmd}'")
                output = conn.send_config_set(cmd, cmd_verify=False) + "\n"

            if not output:
                msg = f"{self.host}: Didn't get any output from the re-protect filter. please check the disableReProtectFilter()"
                logger.error(msg)
                print(msg)
                return False

            return True

        except Exception:
            logger.exception(f"{self.host}: Disable RE protect filter failed")
            return False
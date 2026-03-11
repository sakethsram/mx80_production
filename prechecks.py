import re
from lib.utilities import *


# ─────────────────────────────────────────────────────────────────────────────
# PreCheck class
# ─────────────────────────────────────────────────────────────────────────────
class PreCheck:
    """
    Handles pre-upgrade checks: storage, disk backup, config backup, image transfer.
    Supports vendors defined in deviceDetails.yaml → accepted_vendors.
    conn and logger are always passed in from run_device_pipeline().
    """

    def __init__(self, device):
        self.device          = device
        self.host            = device.get("host")
        self.device_type     = device.get("device_type")
        self.vendor          = device.get("vendor")
        self.model           = device.get("model")
        self.username        = device.get("username")
        self.remote_server   = device.get("remote_backup_server")
        self.remote_password = device.get("remote_password")
        self.min_disk_gb     = device.get("min_disk_gb")
        # accepted_vendors comes from the YAML, stored on dev by run_device_pipeline
        self.accepted_vendors = device.get("accepted_vendors", [])

    # ─────────────────────────────────────────────────────────────────────────
    def checkStorage(self, conn, min_disk_gb, logger):
        try:
            logger.info(f"[{self.host}] checkStorage — vendor: {self.vendor}")

            storage_output = conn.send_command("show system storage", expect_string=r'.*>')

            match = re.search(r"^/dev/gpt/var\s+\S+\s+\S+\s+(\S+)", storage_output, re.M)
            if not match:
                raise ValueError(f"[{self.host}] Could not parse storage output")

            raw        = match.group(1).rstrip("%")
            size_match = re.match(r"^([\d.]+)\s*([GMTK]?)B?$", raw, re.IGNORECASE)
            if not size_match:
                raise ValueError(f"[{self.host}] Unrecognised storage value: '{raw}'")
            size_val   = float(size_match.group(1))
            size_unit  = size_match.group(2).upper()
            unit_to_gb = {"T": 1024, "G": 1, "M": 1 / 1024, "K": 1 / 1048576, "": 1}
            avail_space = size_val * unit_to_gb.get(size_unit, 1)
            logger.info(f"[{self.host}] checkStorage — {avail_space:.2f} GB available")

            # Enough space
            if avail_space > min_disk_gb:
                result = {
                    "status":        "ok",
                    "deleted_files": [],
                    "exception":     "",
                    "sufficient":    True,
                }
                logger.info(f"[{self.host}] checkStorage — sufficient space: {result}")
                return result

            # ── LOW STORAGE → CLEANUP ─────────────────────────────────────────
            logger.warning(f"[{self.host}] checkStorage — low space, running cleanup")

            files_to_delete = self.device.get("cleanup_files", [])
            if not files_to_delete:
                msg = f"[{self.host}] checkStorage — cleanup_files empty, cannot free space"
                logger.error(msg)
                return {
                    "status":        "failed",
                    "deleted_files": [],
                    "exception":     "cleanup_files empty",
                    "sufficient":    False,
                }

            deleted_files = []
            for f in files_to_delete:
                logger.info(f"[{self.host}] checkStorage — deleting {f}")
                conn.send_command(f"file delete {f}")
                deleted_files.append(f)

            result = {
                "status":        "low_space_cleaned",
                "deleted_files": deleted_files,
                "exception":     "",
                "sufficient":    False,
            }
            logger.info(f"[{self.host}] checkStorage — cleanup done: {result}")
            return result

        except Exception as e:
            msg = f"[{self.host}] checkStorage failed: {e}"
            logger.exception(msg)
            raise

    # ─────────────────────────────────────────────────────────────────────────
    def preBackupDisk(self, conn, logger):
        try:
            logger.info(f"[{self.host}] preBackupDisk — vendor: {self.vendor}")

            if self.vendor not in self.accepted_vendors:
                raise ValueError(f"[{self.host}] preBackupDisk — unsupported vendor: {self.vendor}")

            if self.vendor == "juniper":
                output = conn.send_command("show vmhost version", read_timeout=300)

                if "set b" in output and "set p" in output:
                    logger.info(f"[{self.host}] preBackupDisk — dual disk, taking snapshot")
                    cmd    = "request vmhost snapshot"
                    output = conn.send_command_timing(cmd)
                    if cmd in output or "yes,no" in output.lower():
                        output += conn.send_command("yes", expect_string=r".*>", max_loops=3, read_timeout=900)
                    logger.info(f"[{self.host}] preBackupDisk — snapshot complete")
                    return {
                        "status":     "ok",
                        "exception":  "",
                        "disk_count": "dual",
                    }
                else:
                    logger.info(f"[{self.host}] preBackupDisk — single disk, skipping snapshot")
                    return {
                        "status":     "skipped",
                        "exception":  "",
                        "disk_count": "single",
                    }

        except Exception as e:
            msg = f"[{self.host}] preBackupDisk failed: {e}"
            logger.error(msg)
            return {
                "status":     "failed",
                "exception":  str(e),
                "disk_count": "",
            }

    # ─────────────────────────────────────────────────────────────────────────
    def preBackup(self, conn, filename, logger):
        try:
            logger.info(f"[{self.host}] preBackup — vendor: {self.vendor}")

            if self.vendor not in self.accepted_vendors:
                raise ValueError(f"[{self.host}] preBackup — unsupported vendor: {self.vendor}")

            if self.vendor == "juniper":
                pre_backup_config = False
                pre_device_log    = False

                # Step 1: Backup running config
                config_commands = [f"save {filename}", "run file list"]
                config_backup   = conn.send_config_set(config_commands, cmd_verify=False, strip_command=True)
                if config_backup:
                    logger.info(f"[{self.host}] preBackup — config saved, SCP to remote server")
                    src      = f"/var/home/lab/{filename}"
                    dest     = f"{self.remote_server}:/var/tmp/{filename}"
                    if self.scpFile(conn, src, dest, logger):
                        pre_backup_config = True
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
                    f"file archive compress source /var/log/* destination /var/tmp/{filename}.tgz",
                ]
                for cmd in log_commands:
                    conn.send_command_timing(cmd, read_timeout=900, last_read=10.0)

                logger.info(f"[{self.host}] preBackup — logs archived, SCP to remote server")
                src  = f"/var/tmp/{filename}.tgz"
                dest = f"{self.remote_server}:/var/tmp/{filename}.tgz"
                if self.scpFile(conn, src, dest, logger):
                    pre_device_log = True
                else:
                    return {
                        "status":      "failed",
                        "exception":   "SCP of log file failed",
                        "config_file": filename,
                        "log_file":    f"{filename}.tgz",
                        "destination": dest,
                    }

                if not pre_backup_config or not pre_device_log:
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
            msg = f"[{self.host}] preBackup failed: {e}"
            logger.error(msg)
            return {
                "status":      "failed",
                "exception":   str(e),
                "config_file": "",
                "log_file":    "",
                "destination": "",
            }

    # ─────────────────────────────────────────────────────────────────────────
    def scpFile(self, conn, src, dest, logger):
        try:
            logger.info(f"[{self.host}] scpFile — {src} → {dest}")

            cmd = [
                "start shell", "\n",
                f"scp -C {src} {dest}", "\n",
                self.remote_password, "\n",
                "exit", "\n",
            ]
            output = conn.send_multiline_timing(cmd, read_timeout=1800)
            if "No such file or directory" in output:
                logger.error(f"[{self.host}] scpFile — no such file: {src}")
                return False

            if not output:
                logger.error(f"[{self.host}] scpFile — no output returned")
                return False

            logger.info(f"[{self.host}] scpFile — transfer complete")
            return True

        except Exception as e:
            logger.error(f"[{self.host}] scpFile failed: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    def transferImage(self, conn, image_path, target_image, logger):
        try:
            logger.info(f"[{self.host}] transferImage — {target_image}, vendor: {self.vendor}")

            if self.vendor not in self.accepted_vendors:
                raise ValueError(f"[{self.host}] transferImage — unsupported vendor: {self.vendor}")

            if self.vendor == "juniper":
                src  = f"{self.remote_server}:{image_path}/{target_image}"
                dest = "/var/tmp/"
                if not self.scpFile(conn, src, dest, logger):
                    return {
                        "status":      "failed",
                        "exception":   f"SCP transfer failed for {target_image}",
                        "image":       target_image,
                        "destination": dest,
                    }

            logger.info(f"[{self.host}] transferImage — {target_image} transferred to {dest}")
            return {
                "status":      "ok",
                "exception":   "",
                "image":       target_image,
                "destination": dest,
            }

        except Exception as e:
            logger.error(f"[{self.host}] transferImage failed: {e}")
            return {
                "status":      "failed",
                "exception":   str(e),
                "image":       "",
                "destination": "",
            }
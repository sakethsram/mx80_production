# ─────────────────────────────────────────────────────────────────────────────
# upgrade.py  —  Upgrade class
# ─────────────────────────────────────────────────────────────────────────────
import logging
import time
import subprocess
import re
from lib.utilities import *
from prechecks import PreCheck


class Upgrade:
    """
    Handles image upgrade and rollback for network devices.
    Currently supports JUNOS and Cisco devices.
    """

    def __init__(self, device):
        self.host      = device.get("host")
        self.vendor    = device.get("vendor")
        self.prechecks = PreCheck(device)

    def reconnect_and_verify(self, logger, max_retries=6, wait_time=20):
        """
        Disconnect stale session, reconnect, and verify 'show version'.
        """
        self.prechecks.disconnect(logger)
        for attempt in range(max_retries):
            try:
                logger.info(f"{self.host}: Reconnect attempt {attempt + 1}/{max_retries}")
                conn = self.prechecks.connect(logger)
                if conn:
                    output = conn.send_command("show version")
                    if output:
                        logger.info(f"{self.host}: SSH ready, got version output")
                        return conn, output
            except Exception as e:
                logger.warning(f"{self.host}: attempt {attempt + 1} failed: {e}")
            time.sleep(wait_time)
        raise RuntimeError(f"{self.host}: SSH not ready after {max_retries} retries")

    # ─────────────────────────────────────────────────────────────────────────
    # imageUpgrade
    # ─────────────────────────────────────────────────────────────────────────
    def imageUpgrade(self, conn, expected_os, target_image, device_name, logger):
        curr_version = ""
        try:
            logger.info(f"{self.host}: Starting image upgrade process")

            if not conn:
                msg = f"Not connected to device for vendor: {self.vendor}"
                logger.error(msg)
                raise RuntimeError("Not connected to device")

            # ── get current version ───────────────────────────────────────────
            output       = conn.send_command("show version")
            curr_version = output

            if self.vendor == "juniper":
                match = re.search(r"Junos:\s*(?P<version>\S+)", curr_version, re.IGNORECASE)
                if match:
                    curr_version = match.group("version")
                else:
                    msg = f"{self.host}: could not parse version from show version output"
                    logger.error(msg)
                    print(msg)
                    return conn, False

            if self.vendor == "cisco":
                match = re.search(r"Cisco IOS.*Version\s+(?P<version>\S+)", curr_version, re.IGNORECASE)
                if match:
                    curr_version = match.group("version")
                else:
                    msg = f"{self.host}: could not parse version from show version output"
                    logger.error(msg)
                    print(msg)
                    return conn, False

            logger.info(f"{self.host}: current version -> {curr_version}")
            print(f"{self.host}: current version: {curr_version}")

            # ── already on expected OS ────────────────────────────────────────
            if expected_os == curr_version:
                logger.info(f"{self.host}: Already running expected version")
                return conn, True

            # ── install image ─────────────────────────────────────────────────
            logger.info(f"{self.host}: Installing device image: {target_image}")

            if self.vendor == "juniper":
                cmd    = f"request vmhost software add /var/tmp/{target_image} no-validate"
                output = conn.send_command(cmd, read_timeout=900)
                print(f"{self.host}: image installing: {output}")

                if not output:
                    msg = f"{target_image} is not installed. Please check the imageUpgrade()"
                    logger.error(msg)
                    print(msg)
                    return conn, False

            if self.vendor == "cisco":
                conn.send_command(
                    f"install add file {target_image} activate commit",
                    read_timeout=900,
                )

            # ── reboot ────────────────────────────────────────────────────────
            reboot_ok = self.systemReboot(conn, logger)
            logger.info(f"{self.host}: Waiting for reboot after final upgrade")

            # ── reconnect and verify version ──────────────────────────────────
            if reboot_ok:
                logger.info(f"{self.host}: Device rebooted, waiting for SSH to come back")
                conn, output = self.reconnect_and_verify(logger)
                print(f"{self.host}: Output: {output}")

                if self.vendor == "juniper":
                    version_pattern = re.search(r"Junos:\s*(?P<version>\S+)", output, re.IGNORECASE)
                if self.vendor == "cisco":
                    version_pattern = re.search(r"Cisco:\s*(?P<version>\S+)", output, re.IGNORECASE)

                if not version_pattern:
                    logger.warning(f"{self.host}: No device name and version found. Check the output file")
                    raise ValueError("No device name and version found. Check the output file")

                new_version = version_pattern.group("version")
                logger.info(f"{self.host}: New Version -> {new_version}")

                if expected_os == new_version:
                    msg = {"status": "SUCCESS", "version": new_version}
                    logger.info(msg)
                    print(msg)
                    return conn, True
                else:
                    logger.error(f"{self.host}: Version mismatch after upgrade")
                    msg = {
                        "status":           "FAILED",
                        "expected_version": expected_os,
                        "current_version":  new_version,
                    }
                    logger.info(msg)
                    return conn, False

            return conn, False

        except Exception as e:
            logger.exception(f"{self.host}: Image upgrade failed: {e}")
            logger.info(f"{self.host}: Please check imageUpgrade() or rollback to {curr_version}")
            return conn, False

    # ─────────────────────────────────────────────────────────────────────────
    # verifyChecksum
    # ─────────────────────────────────────────────────────────────────────────
    def verifyChecksum(self, conn, checksum, target_image, logger):
        try:
            print(f"{self.host}: ── verifyChecksum START ──")
            print(f"{self.host}: target_image      = {target_image}")
            print(f"{self.host}: expected_checksum = {checksum}")

            if not conn:
                raise RuntimeError(f"{self.host}: Not connected to device")

            if self.vendor == "juniper":
                command = f"file checksum md5 /var/tmp/{target_image}"
                output  = conn.send_command(
                    command,
                    expect_string=r".*>",
                    read_timeout=300,
                    strip_prompt=True,
                    strip_command=True,
                )
                print(f"{self.host}: raw MD5 output:\n{output}")

                match = re.search(r'MD5\s*\(.*?\)\s*=\s*(\S+)', output)
                if not match:
                    return {
                        "status":    "failed",
                        "exception": "Could not parse checksum from output",
                        "expected":  checksum,
                        "computed":  "",
                        "match":     False,
                    }

                computed = match.group(1).strip()
                print(f"{self.host}: computed={computed}  expected={checksum}  match={computed == checksum}")

                if computed == checksum:
                    print(f"{self.host}: MD5 PASSED")
                    return {
                        "status":    "ok",
                        "exception": "",
                        "expected":  checksum,
                        "computed":  computed,
                        "match":     True,
                    }
                else:
                    print(f"{self.host}: MD5 FAILED — mismatch")
                    return {
                        "status":    "failed",
                        "exception": "Checksum mismatch",
                        "expected":  checksum,
                        "computed":  computed,
                        "match":     False,
                    }

        except Exception as e:
            msg = f"{self.host}: verifyChecksum raised exception: {e}"
            print(msg)
            return {
                "status":    "failed",
                "exception": str(e),
                "expected":  checksum,
                "computed":  "",
                "match":     False,
            }

    # ─────────────────────────────────────────────────────────────────────────
    # pingDevice
    # ─────────────────────────────────────────────────────────────────────────
    def pingDevice(self, logger, packet_size=5, count=2, timeout=2):
        try:
            command   = ["ping", "-c", str(count), "-s", str(packet_size), "-W", str(timeout), self.host]
            result    = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            reachable = result.returncode == 0
            print(f"{self.host}: ping result: {'reachable' if reachable else 'NOT reachable'}")
            logger.info(f"{self.host}: ping {'succeeded' if reachable else 'failed'}")
            return reachable
        except Exception as e:
            logger.error(f"{self.host}: Ping failed with error: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # systemReboot
    # ─────────────────────────────────────────────────────────────────────────
    def systemReboot(self, conn, logger):
        try:
            logger.info(f"{self.host}: Rebooting the system...")

            if self.vendor == "juniper":
                command = ["request vmhost reboot", "yes", "\n"]
            elif self.vendor == "cisco":
                command = ["reload", "\n", "yes"]
            else:
                msg = f"Unsupported vendor: {self.vendor}"
                logger.error(msg)
                print(msg)
                raise ValueError(msg)

            msg = f"{self.host}: Running {command}..."
            logger.info(msg)
            print(msg)
            output = conn.send_multiline_timing(command)
            print(f"{self.host}: reboot output: {output}")

            msg = f"{self.host}: Waiting for device to reboot... (default 1200s)"
            logger.info(msg)
            print(msg)
            time.sleep(1200)

            msg = f"{self.host}: starting ping check after reboot"
            logger.info(msg)
            print(msg)

            if self.pingDevice(logger):
                logger.info(f"{self.host}: Device is reachable after reboot")
                return True
            logger.error(f"{self.host}: Device is not reachable after reboot")
            return False

        except Exception as e:
            logger.error(f"{self.host}: Not able to reboot the device: {e}")
            return False
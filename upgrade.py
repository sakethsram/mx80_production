import logging
import time
import subprocess
import re
from lib.utilities import *
from prechecks import PreCheck


# ─────────────────────────────────────────────────────────────────────────────
# Upgrade class
# ─────────────────────────────────────────────────────────────────────────────
class Upgrade:

    """
    Handles image upgrade and rollback for network devices.
    Currently supports JUNOS and Cisco devices.
    """

    def __init__(self, device, accepted_vendors):
        self.host            = device.get("host")
        self.vendor          = device.get("vendor")
        self.accepted_vendor = accepted_vendors
        self.prechecks       = PreCheck(device, accepted_vendors)

    def reconnect_and_verify(self, logger, max_retries=6, wait_time=20):
        """
        Disconnect stale session, reconnect, and verify 'show version'.
        """
        print(f"{self.host}: reconnect_and_verify — killing old session")
        self.prechecks.disconnect(logger)

        for attempt in range(max_retries):
            try:
                print(f"{self.host}: Reconnect attempt {attempt + 1}/{max_retries}")
                logger.info(f"{self.host}: Reconnect attempt {attempt + 1}/{max_retries}")
                conn = self.prechecks.connect(logger)
                if conn:
                    print(f"{self.host}: Connection re-established, sending show version")
                    output = conn.send_command("show version")
                    print(f"{self.host}: show version output length: {len(output) if output else 0}")
                    if output:
                        logger.info(f"{self.host}: SSH ready, got version output")
                        print(f"{self.host}: SSH ready")
                        return conn, output
                    else:
                        print(f"{self.host}: show version returned empty — retrying")
            except Exception as e:
                logger.warning(f"{self.host}: Reconnect attempt {attempt + 1} failed: {e}")
                print(f"{self.host}: Reconnect attempt {attempt + 1} failed: {e}")
            time.sleep(wait_time)

        raise RuntimeError(f"{self.host}: SSH not ready after {max_retries} retries")

    # ─────────────────────────────────────────────────────────────────────────
    # imageUpgrade
    # ─────────────────────────────────────────────────────────────────────────
    def imageUpgrade(self, conn, expected_os, target_image, device_name, logger):
        curr_version = ""
        try:
            print(f"{self.host}: ── imageUpgrade START ──")
            print(f"{self.host}: target_image={target_image}  expected_os={expected_os}  device_name={device_name}")
            logger.info(f"{self.host}: imageUpgrade START — target={target_image} expected_os={expected_os}")

            if not conn:
                msg = f"{self.host}: Not connected to device"
                logger.error(msg)
                print(msg)
                raise RuntimeError(msg)

            if self.vendor not in self.accepted_vendor:
                msg = f"{self.host}: Unsupported vendor: {self.vendor}"
                logger.error(msg)
                print(msg)
                raise ValueError(msg)

            # ── get current version ───────────────────────────────────────────
            print(f"{self.host}: sending 'show version' to get current OS")
            logger.info(f"{self.host}: sending 'show version'")
            output = conn.send_command("show version")
            print(f"{self.host}: show version raw output:\n{output}")
            logger.info(f"{self.host}: show version output length: {len(output) if output else 0}")

            # look up device_name in device_results (our global)
            matched = False
            for device_entry in device_results:
                print(f"{self.host}: checking device_entry key: {device_entry}")
                if device_name in device_entry:
                    matched      = True
                    curr_version = output
                    print(f"{self.host}: matched device_entry — parsing version from output")
                    if self.vendor == "juniper":
                        version_match = re.search(r"Junos:\s*(?P<version>\S+)", curr_version, re.IGNORECASE)
                        print(f"{self.host}: juniper version regex match: {version_match}")
                    if version_match:
                        curr_version = version_match.group("version")
                    else:
                        msg = f"{self.host}: could not parse version from show version output"
                        logger.error(msg)
                        print(msg)
                        return conn, False
                    break

            if not matched:
                msg = f"{self.host}: {device_name} not found in device_results — run prechecks first"
                logger.error(msg)
                print(msg)
                return conn, False

            print(f"{self.host}: current version = {curr_version}")
            logger.info(f"{self.host}: current version = {curr_version}")

            # ── already on expected OS ────────────────────────────────────────
            if expected_os == curr_version:
                msg = f"{self.host}: Already running expected OS {expected_os} — skipping install"
                logger.info(msg)
                print(msg)
                return conn, True

            # ── install image ─────────────────────────────────────────────────
            print(f"{self.host}: installing image {target_image}")
            logger.info(f"{self.host}: installing image {target_image}")

            if self.vendor == "juniper":
                cmd = f"request vmhost software add /var/tmp/{target_image} no-validate"
                print(f"{self.host}: sending command: {cmd}")
                logger.info(f"{self.host}: sending: {cmd}")
                output = conn.send_command(cmd, read_timeout=900)
                print(f"{self.host}: install output:\n{output}")
                logger.info(f"{self.host}: install output length: {len(output) if output else 0}")

                if not output:
                    msg = f"{self.host}: install command returned no output for {target_image}"
                    logger.error(msg)
                    print(msg)
                    return conn, False

            if self.vendor == "cisco":
                cmd = f"install add file {target_image} activate commit"
                print(f"{self.host}: sending command: {cmd}")
                logger.info(f"{self.host}: sending: {cmd}")
                conn.send_command(cmd, read_timeout=900)

            # ── reboot ────────────────────────────────────────────────────────
            print(f"{self.host}: calling systemReboot")
            logger.info(f"{self.host}: calling systemReboot")
            reboot_ok = self.systemReboot(conn, logger)
            print(f"{self.host}: systemReboot returned: {reboot_ok}")
            logger.info(f"{self.host}: systemReboot returned: {reboot_ok}")

            if not reboot_ok:
                msg = f"{self.host}: systemReboot failed"
                logger.error(msg)
                print(msg)
                return conn, False

            # ── reconnect and verify version ──────────────────────────────────
            print(f"{self.host}: reconnecting and verifying version after reboot")
            logger.info(f"{self.host}: reconnecting after reboot")
            conn, output = self.reconnect_and_verify(logger)
            print(f"{self.host}: post-reboot show version output:\n{output}")

            if self.vendor == "juniper":
                version_pattern = re.search(r"Junos:\s*(?P<version>\S+)", output, re.IGNORECASE)
                print(f"{self.host}: juniper version regex on post-reboot output: {version_pattern}")
            if self.vendor == "cisco":
                version_pattern = re.search(r"Cisco:\s*(?P<version>\S+)", output, re.IGNORECASE)
                print(f"{self.host}: cisco version regex on post-reboot output: {version_pattern}")

            if not version_pattern:
                msg = f"{self.host}: could not parse version from post-reboot show version"
                logger.warning(msg)
                print(msg)
                raise ValueError(msg)

            new_version = version_pattern.group("version")
            print(f"{self.host}: post-reboot version = {new_version}")
            print(f"{self.host}: expected version    = {expected_os}")
            logger.info(f"{self.host}: post-reboot version={new_version}  expected={expected_os}")

            if expected_os == new_version:
                msg = f"{self.host}: version verified — upgrade SUCCESS ({new_version})"
                logger.info(msg)
                print(msg)
                return conn, True
            else:
                msg = f"{self.host}: version MISMATCH — expected={expected_os} got={new_version}"
                logger.error(msg)
                print(msg)
                return conn, False

        except Exception as e:
            msg = f"{self.host}: imageUpgrade raised exception: {e}"
            logger.exception(msg)
            print(msg)
            print(f"{self.host}: curr_version at time of exception: {curr_version}")
            return conn, False

    # ─────────────────────────────────────────────────────────────────────────
    # verifyChecksum
    # ─────────────────────────────────────────────────────────────────────────
    def verifyChecksum(self, conn, target_image, expected_checksum):
        try:
            print(f"{self.host}: ── verifyChecksum START ──")
            print(f"{self.host}: target_image      = {target_image}")
            print(f"{self.host}: expected_checksum = {expected_checksum}")
            print(f"{self.host}: vendor            = {self.vendor}")
            print(f"{self.host}: conn              = {conn}")

            if not conn:
                msg = f"{self.host}: Not connected to device"
                print(msg)
                raise RuntimeError(msg)

            if self.vendor not in self.accepted_vendor:
                msg = f"{self.host}: Unsupported vendor: {self.vendor}"
                print(msg)
                raise ValueError(msg)

            if self.vendor == "juniper":
                command = f"file checksum md5 /var/tmp/{target_image}"
                print(f"{self.host}: sending command: {command}")

                output = conn.send_command(
                    command,
                    expect_string=r".*>",
                    read_timeout=300,
                    strip_prompt=True,
                    strip_command=True,
                )
                print(f"{self.host}: raw MD5 command output:\n{output}")
                print(f"{self.host}: output length: {len(output) if output else 0}")

                match = re.search(r'MD5\s*\(.*?\)\s*=\s*(\S+)', output)
                print(f"{self.host}: MD5 regex match: {match}")

                if not match:
                    print(f"{self.host}: MD5 regex found no match — check the output above")
                    return {
                        "status":    "failed",
                        "exception": "Could not parse checksum from output",
                        "expected":  expected_checksum,
                        "computed":  "",
                        "match":     False,
                    }

                computed = match.group(1).strip()
                print(f"{self.host}: computed  checksum = {computed}")
                print(f"{self.host}: expected  checksum = {expected_checksum}")
                print(f"{self.host}: checksums match    = {computed == expected_checksum}")

                if computed == expected_checksum:
                    print(f"{self.host}: MD5 PASSED")
                    return {
                        "status":    "ok",
                        "exception": "",
                        "expected":  expected_checksum,
                        "computed":  computed,
                        "match":     True,
                    }
                else:
                    print(f"{self.host}: MD5 FAILED — mismatch")
                    return {
                        "status":    "failed",
                        "exception": "Checksum mismatch",
                        "expected":  expected_checksum,
                        "computed":  computed,
                        "match":     False,
                    }

        except Exception as e:
            msg = f"{self.host}: verifyChecksum raised exception: {e}"
            print(msg)
            return {
                "status":    "failed",
                "exception": str(e),
                "expected":  expected_checksum,
                "computed":  "",
                "match":     False,
            }

    # ─────────────────────────────────────────────────────────────────────────
    # pingDevice
    # ─────────────────────────────────────────────────────────────────────────
    def pingDevice(self, logger, packet_size=5, count=2, timeout=2):
        try:
            print(f"{self.host}: pinging device")
            command = ["ping", "-c", str(count), "-s", str(packet_size), "-W", str(timeout), self.host]
            result  = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            reachable = result.returncode == 0
            print(f"{self.host}: ping result: {'reachable' if reachable else 'NOT reachable'}")
            logger.info(f"{self.host}: ping {'succeeded' if reachable else 'failed'}")
            return reachable
        except Exception as e:
            print(f"{self.host}: pingDevice exception: {e}")
            logger.error(f"{self.host}: Ping failed with error: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # systemReboot
    # ─────────────────────────────────────────────────────────────────────────
    def systemReboot(self, conn, logger):
        try:
            print(f"{self.host}: ── systemReboot START ──")
            logger.info(f"{self.host}: systemReboot START")

            if self.vendor == "juniper":
                command = ["request vmhost reboot", "yes", "\n"]
            elif self.vendor == "cisco":
                command = ["reload", "\n", "yes"]
            else:
                msg = f"{self.host}: Unsupported vendor for reboot: {self.vendor}"
                logger.error(msg)
                print(msg)
                raise ValueError(msg)

            print(f"{self.host}: sending reboot command: {command}")
            logger.info(f"{self.host}: sending reboot command")
            output = conn.send_multiline_timing(command)
            print(f"{self.host}: reboot command output:\n{output}")

            print(f"{self.host}: sleeping 1200s for device to reboot")
            logger.info(f"{self.host}: waiting 1200s for reboot")
            time.sleep(1200)

            print(f"{self.host}: starting ping check")
            logger.info(f"{self.host}: starting ping check after reboot")
            if self.pingDevice(logger):
                print(f"{self.host}: device is reachable after reboot")
                logger.info(f"{self.host}: device reachable after reboot")
                return True
            else:
                print(f"{self.host}: device NOT reachable after reboot")
                logger.error(f"{self.host}: device not reachable after reboot")
                return False

        except Exception as e:
            msg = f"{self.host}: systemReboot exception: {e}"
            logger.error(msg)
            print(msg)
            return False
# upgrade.py
import re
import os
import time
import logging
import subprocess
import threading
from datetime import datetime
from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException
from paramiko.ssh_exception import SSHException
from lib.utilities import device_results, disconnect


# ─────────────────────────────────────────────────────────────────────────────
# Upgrade class
# ─────────────────────────────────────────────────────────────────────────────

class Upgrade:

    def __init__(self, device_key: str, device: dict, accepted_vendors: list):
        self.device_key      = device_key
        self.device          = device
        self.host            = device.get("host")
        self.vendor          = device.get("vendor")
        self.accepted_vendor = accepted_vendors

    # ─────────────────────────────────────────────────────────────────────────
    # connect
    # ─────────────────────────────────────────────────────────────────────────
    def connect(self, logger):
        try:
            logger.info(f"{self.host}: [Upgrade.connect] Connecting to device")
            logger.debug(
                f"{self.host}: [Upgrade.connect] device_type={self.device.get('device_type')}, "
                f"username={self.device.get('username')}"
            )

            session_log_dir = os.path.join(os.getcwd(), "outputs")
            os.makedirs(session_log_dir, exist_ok=True)
            session_log_file = (
                f"{self.vendor}_{self.device.get('model', 'unknown')}_"
                f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_upgrade.log"
            )
            session_log_path = os.path.join(session_log_dir, session_log_file)
            logger.debug(f"{self.host}: [Upgrade.connect] Session log → {session_log_path}")

            conn = ConnectHandler(
                device_type = self.device.get("device_type"),
                host        = self.host,
                username    = self.device.get("username"),
                password    = self.device.get("password"),
                session_log = session_log_path,
            )

            # Store into device_results so the rest of the pipeline sees it
            device_results[self.device_key]["conn"]                            = conn
            device_results[self.device_key]["upgrade"]["connect"]["status"]    = True
            device_results[self.device_key]["upgrade"]["connect"]["exception"] = ""

            logger.info(f"{self.host}: [Upgrade.connect] Connected successfully")
            return conn

        except NetmikoTimeoutException as e:
            logger.error(f"{self.host}: [Upgrade.connect] Timeout — {e}")
            device_results[self.device_key]["upgrade"]["connect"]["status"]    = False
            device_results[self.device_key]["upgrade"]["connect"]["exception"] = str(e)
            return None
        except NetmikoAuthenticationException as e:
            logger.error(f"{self.host}: [Upgrade.connect] Auth failed — {e}")
            device_results[self.device_key]["upgrade"]["connect"]["status"]    = False
            device_results[self.device_key]["upgrade"]["connect"]["exception"] = str(e)
            return None
        except SSHException as e:
            logger.error(f"{self.host}: [Upgrade.connect] SSH error — {e}")
            device_results[self.device_key]["upgrade"]["connect"]["status"]    = False
            device_results[self.device_key]["upgrade"]["connect"]["exception"] = str(e)
            return None
        except Exception as e:
            logger.error(f"{self.host}: [Upgrade.connect] Unknown error — {e}")
            device_results[self.device_key]["upgrade"]["connect"]["status"]    = False
            device_results[self.device_key]["upgrade"]["connect"]["exception"] = str(e)
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # reconnect_and_verify
    # ─────────────────────────────────────────────────────────────────────────
    def reconnect_and_verify(self, hop_index: int, logger, max_retries=6, wait_time=20):
        logger.info(
            f"{self.host}: [reconnect_and_verify] Starting — "
            f"hop_index={hop_index}, max_retries={max_retries}, wait_time={wait_time}s"
        )
        disconnect(self.device_key, logger)          # kill stale session

        for attempt in range(max_retries):
            try:
                logger.info(f"{self.host}: Reconnect attempt {attempt + 1}/{max_retries}")
                conn = self.connect(logger)
                if conn:
                    output = conn.send_command("show version")
                    if output:
                        logger.info(f"{self.host}: SSH ready, got version output")

                        # ── write per-hop connect result ──────────────────────
                        if hop_index >= 0:
                            device_results[self.device_key]["upgrade"]["hops"][hop_index]["connect"].update({
                                "status":    True,
                                "attempt":   attempt + 1,
                                "exception": "",
                            })

                        return conn, output
                    else:
                        logger.warning(
                            f"{self.host}: [reconnect_and_verify] Connection up but "
                            f"'show version' returned empty output on attempt {attempt + 1}"
                        )
                else:
                    logger.warning(
                        f"{self.host}: [reconnect_and_verify] connect() returned None "
                        f"on attempt {attempt + 1}"
                    )

            except Exception as e:
                logger.warning(f"{self.host}: attempt {attempt + 1} failed: {e}")

                if hop_index >= 0:
                    device_results[self.device_key]["upgrade"]["hops"][hop_index]["connect"].update({
                        "status":    False,
                        "attempt":   attempt + 1,
                        "exception": str(e),
                    })

            time.sleep(wait_time)

        # ── exhausted all retries ─────────────────────────────────────────────
        logger.error(
            f"{self.host}: [reconnect_and_verify] All {max_retries} reconnect attempts exhausted"
        )
        if hop_index >= 0:
            device_results[self.device_key]["upgrade"]["hops"][hop_index]["connect"].update({
                "status":    False,
                "attempt":   max_retries,
                "exception": f"SSH not ready after {max_retries} retries",
            })
        raise RuntimeError(f"{self.host}: SSH not ready after {max_retries} retries")

    # ─────────────────────────────────────────────────────────────────────────
    # imageUpgrade
    # ─────────────────────────────────────────────────────────────────────────
    def imageUpgrade(self, conn, expected_os, target_image, hop_index, logger):
        logger.info(
            f"{self.host}: [imageUpgrade] Starting — "
            f"hop_index={hop_index}, target_image={target_image}, expected_os={expected_os}"
        )

        try:
            if not conn:
                msg = f"Not connected to device for vendor: {self.vendor}"
                logger.error(msg)
                raise RuntimeError("Not connected to device")

            if self.vendor not in self.accepted_vendor:
                logger.error(f"Unsupported vendor: {self.vendor}")
                raise ValueError(f"Unsupported vendor: {self.vendor}")

            # ── Get current version from device_results (set by get_show_version) ──
            curr_version = device_results[self.device_key]["device_info"]["version"]
            print(f"[imageUpgrade] current version: {curr_version}")
            logger.info(f"{self.host}: current version -> {curr_version}")
            logger.debug(
                f"{self.host}: [imageUpgrade] Version check — "
                f"curr={curr_version}, expected={expected_os}"
            )

            # hop_index == -1 means this is a rollback call — never write into hops[]
            def _write_hop(update: dict):
                if hop_index >= 0:
                    device_results[self.device_key]["upgrade"]["hops"][hop_index].update(update)

            if expected_os == curr_version:
                logger.info(f"{self.host}: Already running expected version")
                _write_hop({"status": "already_upgraded", "exception": "", "md5_match": True})
                return conn, True

            logger.info(f"{self.host}: Installing device image: {target_image}")

            if self.vendor == "juniper":
                cmd    = f"request vmhost software add /var/tmp/{target_image} no-validate"
                logger.debug(f"{self.host}: [imageUpgrade] Sending: {cmd} (read_timeout=900s)")
                output = conn.send_command(cmd, read_timeout=900)
                print(f"[imageUpgrade] install output: {output}")

                if not output:
                    msg = f"{target_image} is not installed. Please check imageUpgrade()"
                    logger.error(msg)
                    _write_hop({"status": "failed", "exception": msg, "md5_match": False})
                    return conn, False

            if self.vendor == "cisco":
                conn.send_command(
                    f"install add file {target_image} activate commit",
                    read_timeout=900
                )

            logger.info(f"{self.host}: [imageUpgrade] Install completed, initiating reboot")
            reboot_system = self.systemReboot(conn, logger)
            logger.info(f"{self.host}: Waiting for reboot after upgrade")

            if reboot_system:
                logger.info(f"{self.host}: Device rebooted, waiting for SSH to come back")
                conn, output = self.reconnect_and_verify(hop_index, logger)
                print(f"[imageUpgrade] post-reboot output: {output}")

                if self.vendor == "juniper":
                    version_pattern = re.search(r"Junos:\s*(?P<version>\S+)", output, re.IGNORECASE)
                if self.vendor == "cisco":
                    version_pattern = re.search(r"Cisco:\s*(?P<version>\S+)", output, re.IGNORECASE)

                if version_pattern:
                    new_version = version_pattern.group("version")
                    logger.debug(
                        f"{self.host}: [imageUpgrade] Version regex matched — new_version={new_version}"
                    )
                else:
                    msg = "No version found in show version output after reboot"
                    logger.warning(msg)
                    _write_hop({"status": "failed", "exception": msg, "md5_match": False})
                    raise ValueError(msg)

                # ── Update device_info version so next hop reads the right value ──
                device_results[self.device_key]["device_info"]["version"] = new_version
                logger.info(f"{self.host}: Version information retrieved")
                logger.info(f"{self.host}: New Version -> {new_version}")

                if expected_os == new_version:
                    logger.info(f"{self.host}: Upgrade hop SUCCESS — {new_version}")
                    _write_hop({"status": "success", "exception": "", "md5_match": True})
                    return conn, True
                else:
                    msg = (
                        f"Version mismatch after upgrade — "
                        f"expected={expected_os}, got={new_version}"
                    )
                    logger.error(f"{self.host}: {msg}")
                    _write_hop({"status": "failed", "exception": msg, "md5_match": False})
                    return conn, False

            else:
                logger.error(
                    f"{self.host}: [imageUpgrade] systemReboot() returned False — "
                    f"device did not come back for image {target_image}"
                )

        except Exception as e:
            msg = f"{self.host}: Image upgrade failed: {e}"
            logger.exception(msg)
            _write_hop({"status": "failed", "exception": str(e), "md5_match": False})
            return conn, False

    # ─────────────────────────────────────────────────────────────────────────
    # pingDevice
    # ─────────────────────────────────────────────────────────────────────────
    def pingDevice(self, logger, packet_size=5, count=2, timeout=2):
        logger.debug(
            f"{self.host}: [pingDevice] count={count}, packet_size={packet_size}, timeout={timeout}s"
        )
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
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            reachable = result.returncode == 0
            if reachable:
                logger.info(f"{self.host}: [pingDevice] Host is reachable (rc={result.returncode})")
            else:
                logger.warning(f"{self.host}: [pingDevice] Host did not respond (rc={result.returncode})")
            return reachable
        except Exception as e:
            logger.error(f"{self.host}: Ping failed with error: {e}")
            logger.info(f"{self.host}: Host is not reachable")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # systemReboot
    # ─────────────────────────────────────────────────────────────────────────
    def systemReboot(self, conn, logger):
        logger.info(f"{self.host}: [systemReboot] Initiating reboot — vendor={self.vendor}")

        try:
            if self.vendor == "juniper":
                command = ["request vmhost reboot", "yes", "\n"]
            elif self.vendor == "cisco":
                command = ["reload", "\n", "yes"]
            else:
                msg = f"Unsupported vendor: {self.vendor}"
                logger.error(msg)
                raise ValueError(msg)

            logger.info(f"{self.host}: Rebooting the system...")
            print(f"[systemReboot] Running {command}...")
            output = conn.send_multiline_timing(command)
            print(f"[systemReboot] reboot output: {output}")

            logger.info(f"{self.host}: Waiting for device to reboot... (900s)")
            print(f"[systemReboot] sleeping 900s...")
            time.sleep(900)

            logger.info(f"{self.host}: Starting ping check after reboot")
            if self.pingDevice(logger):
                logger.info(f"{self.host}: Device is reachable after reboot")
                return True

            logger.error(f"{self.host}: Device is NOT reachable after reboot")
            return False

        except Exception as e:
            logger.error(f"{self.host}: Not able to reboot the device: {e}")
            return False


# ─────────────────────────────────────────────────────────────────────────────
# run_upgrade
# ─────────────────────────────────────────────────────────────────────────────
def run_upgrade(conn, device: dict, device_key: str, accepted_vendors: list, logger):
    host          = device.get("host")
    vendor        = device.get("vendor")
    model         = str(device.get("model")).lower().replace("-", "")
    image_details = device.get("imageDetails", [])
    curr_image    = device.get("curr_image")
    curr_os       = device.get("curr_os")

    tid = threading.get_ident()
    logger.info(f"[THREAD-{tid}] [{device_key}] Upgrade started at {datetime.now()}")
    logger.info(
        f"[{device_key}] run_upgrade — host={host}, vendor={vendor}, model={model}, "
        f"curr_os={curr_os}, total_hops={len(image_details)}"
    )
    print(f"[{device_key}] Running Upgrade...")

    # Seed rollback chain with the original image/OS from YAML
    rollback_image = [{"image": curr_image, "expected_os": curr_os}]
    logger.debug(f"[{device_key}] Rollback chain seeded — image={curr_image}, os={curr_os}")

    device_results[device_key]["upgrade"]["status"] = "in_progress"

    upgrade = Upgrade(device_key, device, accepted_vendors)

    try:
        for i, details in enumerate(image_details):
            image       = details.get("image")
            expected_os = details.get("expected_os")
            checksum    = details.get("checksum")

            logger.info(
                f"[{device_key}] ── Hop [{i}/{len(image_details)-1}] ── "
                f"image={image}, expected_os={expected_os}"
            )

            if not image or not expected_os or not checksum:
                msg = (
                    f"{host}: imageDetails[{i}] missing one of: "
                    f"image, expected_os, checksum"
                )
                logger.error(f"[{device_key}] {msg}")
                device_results[device_key]["upgrade"]["status"]    = "failed"
                device_results[device_key]["upgrade"]["exception"] = msg
                return conn, False

            logger.info(f"[{device_key}] Hop [{i}] — image={image}, expected_os={expected_os}")
            print(f"[{device_key}] Hop [{i}] upgrading with {image}")

            conn, is_upgrade = upgrade.imageUpgrade(conn, expected_os, image, i, logger)
            logger.debug(f"[{device_key}] Hop [{i}] imageUpgrade returned is_upgrade={is_upgrade}")

            if not is_upgrade:
                msg = f"Upgrade hop [{i}] failed for {image}"
                logger.error(f"[{device_key}] {msg}")
                device_results[device_key]["upgrade"]["status"]    = "failed"
                device_results[device_key]["upgrade"]["exception"] = msg

                logger.info(f"[{device_key}] Triggering rollback...")
                logger.debug(
                    f"[{device_key}] Rollback chain at failure: "
                    + str([e.get("image") for e in rollback_image])
                )
                print(f"[{device_key}] Upgrade failed — starting rollback")

                conn, rollback_ok = run_rollback(
                    conn, device, device_key, vendor, rollback_image,
                    accepted_vendors, logger
                )
                logger.info(f"[{device_key}] run_rollback completed — rollback_ok={rollback_ok}")

                if not rollback_ok:
                    msg = f"Rollback also failed for {device_key} — stopping device"
                    logger.error(f"[{device_key}] {msg}")
                    device_results[device_key]["upgrade"]["exception"] = (
                        device_results[device_key]["upgrade"]["exception"]
                        + " | ROLLBACK ALSO FAILED"
                    )
                return conn, False

            # Hop succeeded — add to rollback chain so we can unwind to here if needed
            rollback_image.append({"image": image, "expected_os": expected_os})
            logger.info(f"[{device_key}] Hop [{i}] succeeded — rollback chain now {len(rollback_image)} entries")

        msg = f"All {len(image_details)} upgrade hop(s) successful"
        logger.info(f"[{device_key}] {msg}")
        print(f"[{device_key}] {msg}")
        device_results[device_key]["upgrade"]["status"]    = "success"
        device_results[device_key]["upgrade"]["exception"] = ""
        return conn, True

    except Exception as e:
        msg = f"run_upgrade unhandled exception: {e}"
        logger.error(f"[{device_key}] {msg}")
        device_results[device_key]["upgrade"]["status"]    = "failed"
        device_results[device_key]["upgrade"]["exception"] = str(e)
        return conn, False


# ─────────────────────────────────────────────────────────────────────────────
# run_rollback
# ─────────────────────────────────────────────────────────────────────────────
def run_rollback(conn, device: dict, device_key: str, vendor: str,
                 rollback_image: list, accepted_vendors: list, logger):
    host        = device.get("host")
    original_os = device.get("curr_os")

    logger.info(f"[{device_key}] Rollback started at {datetime.now()}")
    logger.info(
        f"[{device_key}] run_rollback — host={host}, vendor={vendor}, "
        f"original_os={original_os}, chain_length={len(rollback_image)}"
    )
    print(f"[{device_key}] Running Rollback...")

    upgrade = Upgrade(device_key, device, accepted_vendors)

    try:
        if vendor == "juniper":
            reversed_list = rollback_image[::-1]

            log_lines = ["\n===== ROLLBACK CHAIN (REVERSED) ====="]
            for i, entry in enumerate(reversed_list, start=1):
                log_lines.append(
                    f"{i}. image={entry.get('image')}, expected_os={entry.get('expected_os')}"
                )
            log_lines.append("=====================================\n")
            logger.info("\n".join(log_lines))

            for step_idx, details in enumerate(reversed_list):
                rollback_img = details.get("image")
                expected_os  = details.get("expected_os")

                logger.info(
                    f"[{device_key}] Rollback step [{step_idx+1}/{len(reversed_list)}] — "
                    f"image={rollback_img}, expected_os={expected_os}"
                )

                if not rollback_img or not expected_os:
                    msg = "Rollback entry missing image or expected_os — aborting rollback"
                    logger.error(f"[{device_key}] {msg}")
                    return conn, False

                step_msg = f"Rollback Step → Installing: {rollback_img}, expecting OS: {expected_os}"
                logger.info(f"[{device_key}] {step_msg}")
                print(f"[{device_key}] {step_msg}")

                conn, is_rollback = upgrade.imageUpgrade(
                    conn, expected_os, rollback_img, -1, logger
                )
                logger.debug(
                    f"[{device_key}] Rollback step [{step_idx+1}] imageUpgrade returned "
                    f"is_rollback={is_rollback}"
                )

                if not is_rollback:
                    msg = f"Rollback step failed for {rollback_img}"
                    logger.error(f"[{device_key}] {msg}")
                    return conn, False

                if expected_os == original_os:
                    done_msg = (
                        f"{device_key}: Original OS {original_os} restored. "
                        f"Rollback complete."
                    )
                    logger.info(done_msg)
                    print(f"[{device_key}] {done_msg}")
                    return conn, True

        logger.info(f"[{device_key}] Multi-step rollback completed")
        print(f"[{device_key}] Rollback successful")
        return conn, True

    except Exception as e:
        msg = f"run_rollback unhandled exception: {e}"
        logger.error(f"[{device_key}] {msg}")
        return conn, False
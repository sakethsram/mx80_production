import logging
import re
from lib.utilities import device_results

logger = logging.getLogger(__name__)

ACCEPTED_VENDORS = ["juniper", "cisco"]


# ────────────────────────────────────────────────────────────────────────────
# PreCheck
# Instantiated once per device thread.  All methods return a plain dict that
# the orchestrator (main.py) stores directly into device_results.
# ────────────────────────────────────────────────────────────────────────────
class PreCheck:
    """
    Per-device pre-upgrade checks.
    Supported vendors: juniper, cisco
    """

    def __init__(self, device: dict):
        self.device        = device
        self.host          = device.get("host")
        self.vendor        = device.get("vendor", "").lower()
        self.model         = device.get("model")
        self.device_type   = device.get("device_type")
        self.username      = device.get("username")
        self.min_disk_gb   = device.get("min_disk_gb", 5)
        self.cleanup_files = device.get("cleanup_files") or []

    # ── disconnect helper ────────────────────────────────────────────────────
    def disconnect(self, log):
        """Thin wrapper so callers can still call precheck.disconnect(logger)."""
        from lib.utilities import disconnect
        ip_clean   = self.host.replace(".", "_")
        model_lc   = str(self.model).lower().replace("-", "")
        device_key = f"{ip_clean}_{self.vendor}_{model_lc}"
        disconnect(device_key, log)

    # ── checkStorage ─────────────────────────────────────────────────────────
    def checkStorage(self, conn, min_disk_gb=None):
        try:
            msg = f"{self.host}: Checking system storage for vendor: {self.vendor}"
            logger.info(msg)

            if not conn:
                msg = "Not connected to device"
                logger.error(msg)
                raise RuntimeError("Not connected to device")

            storage_output = conn.send_command("show system storage", expect_string=r'.*>')

            avail_space = re.search(
                r"^/dev/gpt/var\s+\S+\s+\S+\s+(\S+)*",
                storage_output,
                re.M
            ).group(1)
            avail_space = avail_space[:-1]          # strip trailing unit char e.g. 'G'
            avail_space = int(float(avail_space))

            if avail_space is None:
                msg = f"{self.host} Unable to parse storage output for vendor: {self.vendor}"
                logger.error(msg)
                self.disconnect(logger)
                raise ValueError(msg)

            msg = f"{self.host}: {avail_space} GB available for {self.vendor}"
            logger.info(msg)

            # ── Enough space ─────────────────────────────────────────────────
            if avail_space > (min_disk_gb or self.min_disk_gb):
                result = {
                    "sufficient":    True,
                    "available_gb":  avail_space,
                    "files_deleted": [],
                    "exception":     "",
                }
                logger.info(result)
                return result

            # ── Low storage → cleanup ────────────────────────────────────────
            logger.warning(f"{self.host}: Low space! Running system cleanup")

            files_to_delete = self.device.get("cleanup_files") or []

            if len(files_to_delete) == 0:
                logger.error(
                    f"{self.host}: cleanup_files EMPTY -> No files are available to delete"
                )
                self.disconnect(logger)
                return {
                    "sufficient":    False,
                    "available_gb":  avail_space,
                    "files_deleted": [],
                    "exception":     "cleanup_files empty",
                }

            files_deleted = []
            for file in files_to_delete:
                logger.info(f"{self.host}: Deleting {file}")
                conn.send_command(f"file delete {file}")
                files_deleted.append(file)

            result = {
                "sufficient":    False,
                "available_gb":  avail_space,
                "files_deleted": files_deleted,
                "exception":     "",
            }
            logger.info(result)
            return result

        except Exception:
            msg = f"{self.host}: Storage check failed for vendor: {self.vendor}"
            logger.exception(msg)
            self.disconnect(logger)
            raise
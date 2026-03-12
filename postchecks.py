# postchecks.py
from lib.utilities import *


# ─────────────────────────────────────────────────────────────────────────────
# PostCheck class
# ─────────────────────────────────────────────────────────────────────────────
class PostCheck:
    """
    Handles post-upgrade checks.
    Mirrors the PreCheck interface — conn and logger are always passed in
    from run_postchecks() after the upgrade phase completes.

    Current steps (called from run_postchecks in main.py):
        1. show version  → get_show_version(..., check_type="post")
        2. show commands → execute_show_commands(..., check_type="post")

    Add vendor-specific post-check methods here as needed, following the same
    pattern as PreCheck (e.g. verifyRoutes, checkAlarms, compareProtocols).
    """

    def __init__(self, device: dict):
        self.device           = device
        self.host             = device.get("host")
        self.device_type      = device.get("device_type")
        self.vendor           = device.get("vendor")
        self.model            = device.get("model")
        self.username         = device.get("username")
        self.accepted_vendors = device.get("accepted_vendors", [])
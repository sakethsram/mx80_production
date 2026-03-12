"""
fetch_reports.py
─────────────────────────────────────────────────────────────────────────────
File location:  ~/Documents/MS1Automation/fetch_reports.py

Folder structure (all relative to this script):
  ~/Documents/MS1Automation/
  ├── fetch_reports.py          ← this file
  ├── reports/                  ← local reports folder (listed at startup)
  └── precheck_jsons/           ← local precheck folder (listed at startup)

Remote (on 10.80.71.55):
  /home/colt/Documents/MS1Automation/reports/
  /home/colt/Documents/MS1Automation/precheck_jsons/

What the script does:
  1. Lists both LOCAL sibling folders (reports + precheck_jsons)
  2. Deletes ALL contents of  ~/Desktop/   (only files/folders dropped there
     by a previous run — see DESKTOP_PREFIX to scope deletions if needed)
  3. Connects to 10.80.71.55 via Netmiko
  4. Scans both REMOTE folders, compares mtimes, picks the SINGLE latest file
  5. SCPs that one file to  ~/Desktop/

Requirements
────────────
    pip install netmiko paramiko scp
"""

import os
import sys
import shutil
import pathlib
from datetime import datetime

try:
    from netmiko import ConnectHandler
    import paramiko
    from scp import SCPClient
except ImportError as exc:
    sys.exit(
        f"[ERROR] Missing dependency: {exc}\n"
        "Run:  pip install netmiko paramiko scp"
    )

# ─────────────────────────────────────────────────────────────────────────────
#  PATHS  — derived from this script's own location, no hardcoding needed
# ─────────────────────────────────────────────────────────────────────────────

# Directory that contains this script  →  ~/Documents/MS1Automation/
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent

# Sibling folders living next to this script
LOCAL_REPORTS_DIR   = SCRIPT_DIR / "reports"
LOCAL_PRECHECK_DIR  = SCRIPT_DIR / "precheck_jsons"

# Destination: the user's Desktop
LOCAL_DESKTOP = pathlib.Path.home() / "Desktop"

# ─────────────────────────────────────────────────────────────────────────────
#  DEVICE CONFIG
# ─────────────────────────────────────────────────────────────────────────────

DEVICE = {
    "host":        "10.80.71.55",
    "username":    "lab",
    "password":    "lab123",
    "device_type": "juniper",
    "port":        22,
    "timeout":     30,
}

# Remote directories (mirroring the local structure on the device)
REMOTE_DIRS = [
    "/home/colt/Documents/MS1Automation/reports",
    "/home/colt/Documents/MS1Automation/precheck_jsons",
]

# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def banner(msg: str) -> None:
    print(f"\n{'─' * 68}\n  {msg}\n{'─' * 68}")


def list_local_folder(folder: pathlib.Path) -> None:
    """Print contents of a local folder sorted newest-first."""
    banner(f"Local folder: {folder}")
    if not folder.exists():
        print(f"  [WARNING] Folder does not exist: {folder}")
        return
    items = sorted(folder.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)
    if not items:
        print("  (empty)")
        return
    for item in items:
        mtime = datetime.fromtimestamp(item.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        tag   = "[DIR] " if item.is_dir() else "      "
        print(f"  {tag}{item.name:<52}  {mtime}")


def clear_desktop(desktop: pathlib.Path) -> None:
    """
    Removes ALL files and folders directly inside ~/Desktop.
    Skips items it cannot remove and reports them.
    """
    banner(f"Clearing Desktop: {desktop}")
    if not desktop.exists():
        print("  Desktop folder not found — nothing to clear.")
        return
    removed = 0
    for item in desktop.iterdir():
        try:
            shutil.rmtree(item) if item.is_dir() else item.unlink()
            removed += 1
        except Exception as e:
            print(f"  [SKIP] Could not remove {item.name}: {e}")
    print(f"  → Removed {removed} item(s).")


def get_file_mtime(conn, remote_path: str) -> int:
    """Return Unix mtime of a remote file via SSH (GNU then BSD stat fallback)."""
    out = conn.send_command(
        f"stat --format=%Y {remote_path} 2>/dev/null || stat -f%m {remote_path}"
    )
    try:
        return int(out.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return 0


def find_single_latest_remote_file(conn) -> str:
    """
    Walk every directory in REMOTE_DIRS, stat each file, and return the
    full remote path of the single most-recently-modified file.
    """
    banner("Scanning remote directories …")
    best_path  = None
    best_mtime = -1

    for remote_dir in REMOTE_DIRS:
        print(f"\n  {remote_dir}")
        raw = conn.send_command(f"ls -tp {remote_dir} 2>&1")

        if "No such file" in raw or "cannot access" in raw:
            print("    [WARNING] Not found or inaccessible — skipping.")
            continue

        # Filter out sub-directories (ls -p appends / to them)
        files = [l.strip() for l in raw.splitlines()
                 if l.strip() and not l.strip().endswith("/")]

        if not files:
            print("    (no files)")
            continue

        for fname in files:
            full_path = f"{remote_dir}/{fname}"
            mtime     = get_file_mtime(conn, full_path)
            ts        = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S") if mtime else "unknown"
            marker    = ""
            if mtime > best_mtime:
                best_mtime = mtime
                best_path  = full_path
                marker     = "  ← newest so far"
            print(f"    {fname:<52}  {ts}{marker}")

    if best_path is None:
        raise FileNotFoundError("No files found in any remote directory.")

    print(f"\n  ✔  Winner → {best_path}")
    return best_path


def scp_download(host: str, username: str, password: str,
                 remote_path: str, local_dir: pathlib.Path) -> pathlib.Path:
    """Download a single remote file to local_dir via SCP."""
    filename   = os.path.basename(remote_path)
    local_dest = local_dir / filename

    banner(f"Downloading: {filename}")
    print(f"  From : {host}:{remote_path}")
    print(f"  To   : {local_dest}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=username, password=password, timeout=30)
    with SCPClient(ssh.get_transport()) as scp:
        scp.get(remote_path, str(local_dest))
    ssh.close()

    size = local_dest.stat().st_size
    print(f"  → Done  ({size:,} bytes)")
    return local_dest


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:

    # STEP 0 – show local sibling folders before touching anything remote
    list_local_folder(LOCAL_REPORTS_DIR)
    list_local_folder(LOCAL_PRECHECK_DIR)

    # STEP 1 – wipe the Desktop
    clear_desktop(LOCAL_DESKTOP)

    # STEP 2 – connect to the Juniper device
    banner(f"Connecting to {DEVICE['host']} …")
    conn = ConnectHandler(**DEVICE)
    print(f"  → Connected  (prompt: {conn.find_prompt().strip()})")

    try:
        # STEP 3 – find the single latest file across both remote dirs
        latest_remote = find_single_latest_remote_file(conn)
    finally:
        conn.disconnect()
        print("\n  → Disconnected.")

    # STEP 4 – SCP it to the Desktop
    saved = scp_download(
        host        = DEVICE["host"],
        username    = DEVICE["username"],
        password    = DEVICE["password"],
        remote_path = latest_remote,
        local_dir   = LOCAL_DESKTOP,
    )

    banner("All done")
    print(f"  File saved to: {saved}\n")


if __name__ == "__main__":
    main()
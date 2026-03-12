"""
downloader.py
─────────────────────────────────────────────────────────────────────────────
Location:  ~/Documents/MS1Automation/downloader.py

The reports and precheck_jsons folders are LOCAL (on this same machine).
No SSH/SCP/Netmiko needed — this script just copies files locally.

What it does:
  1. Lists both sibling folders (reports/ and precheck_jsons/)
  2. Finds the single latest file across both folders (by filename timestamp)
  3. Prints what it found — does NOT copy anything yet
─────────────────────────────────────────────────────────────────────────────
"""

import pathlib
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
#  PATHS  — relative to this script's own location
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR          = pathlib.Path(__file__).resolve().parent
LOCAL_REPORTS_DIR   = SCRIPT_DIR / "reports"
LOCAL_PRECHECK_DIR  = SCRIPT_DIR / "precheck_jsons"
LOCAL_DESKTOP       = pathlib.Path.home() / "Desktop"

# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def banner(msg: str) -> None:
    print(f"\n{'─' * 68}\n  {msg}\n{'─' * 68}")


def list_local_folder(folder: pathlib.Path) -> None:
    """Print all files in a folder, newest first."""
    banner(f"Local folder: {folder}")
    if not folder.exists():
        print(f"  [WARNING] Folder does not exist: {folder}")
        return
    files = sorted(
        [f for f in folder.iterdir() if f.is_file()],
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )
    if not files:
        print("  (empty)")
        return
    for f in files:
        mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"  {f.name:<60}  {mtime}")


def find_latest_file(*folders: pathlib.Path) -> pathlib.Path:
    """Return the single most-recently-modified file across all given folders."""
    all_files = []
    for folder in folders:
        if folder.exists():
            all_files.extend(f for f in folder.iterdir() if f.is_file())

    if not all_files:
        raise FileNotFoundError("No files found in any of the source folders.")

    latest = max(all_files, key=lambda f: f.stat().st_mtime)
    return latest


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:

    # STEP 1 — list both local sibling folders
    list_local_folder(LOCAL_REPORTS_DIR)
    list_local_folder(LOCAL_PRECHECK_DIR)

    # STEP 2 — find the single latest file across both folders
    banner("Finding latest file across both folders …")
    latest = find_latest_file(LOCAL_REPORTS_DIR, LOCAL_PRECHECK_DIR)
    mtime  = datetime.fromtimestamp(latest.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    size   = latest.stat().st_size

    print(f"  ✔  Latest file : {latest.name}")
    print(f"     Full path   : {latest}")
    print(f"     Modified    : {mtime}")
    print(f"     Size        : {size:,} bytes")
    print(f"\n  Would copy to  : {LOCAL_DESKTOP / latest.name}")

    banner("Done (print-only mode — nothing was copied)")


if __name__ == "__main__":
    main()
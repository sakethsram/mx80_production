import sys
from lib.utilities import load_yaml, connect, disconnect, setup_logger, get_show_version

def main():
    devices          = load_yaml("deviceDetails.yaml")
    all_devs         = devices["devices"]
    accepted_vendors = devices.get("accepted_vendors", [])

    for dev in all_devs:
        vendor     = dev.get("vendor", "").lower()
        model      = str(dev.get("model", "")).lower().replace("-", "")
        host       = dev.get("host")
        ip_clean   = host.replace(".", "_")
        device_key = f"{ip_clean}_{vendor}_{model}"

        if vendor not in accepted_vendors:
            print(f"[{host}] Skipping — unsupported vendor '{vendor}'")
            continue

        logger = setup_logger(device_key, vendor=vendor, model=model, host=host)

        print(f"\n[{host}] Connecting...")
        conn = connect(device_key, dev, logger)
        if not conn:
            print(f"[{host}] ERROR: connect() returned None")
            continue

        print(f"[{host}] Connected. Fetching show version...")
        ok = get_show_version(device_key, conn, vendor, logger, check_type="pre")
        if ok:
            print(f"[{host}] show version result: {ok}")
        else:
            print(f"[{host}] ERROR: get_show_version() returned False")

        disconnect(device_key, logger)
        print(f"[{host}] Done.")

if __name__ == "__main__":
    main()
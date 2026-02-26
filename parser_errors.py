import json

CMD_MIN_LEN = 10

def audit_pre_checks(file_path: str) -> list:
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"[audit] ERROR — file not found: {file_path}")
        return []
    except json.JSONDecodeError as e:
        print(f"[audit] ERROR — could not parse JSON: {e}")
        return []
    except Exception as e:
        print(f"[audit] ERROR — unexpected error loading file: {e}")
        return []

    results = []

    for device_key, device_data in data.items():
        pre_checks = device_data.get("pre_checks", [])

        for entry in pre_checks:
            cmd        = entry.get("cmd", "")
            json_data  = entry.get("json", {})
            cmd_number = entry.get("cmd_number", "?")

            has_cmd  = len(cmd) >= CMD_MIN_LEN
            has_json = bool(json_data)

            if not has_cmd and not has_json:
                status = "no_command_no_output"
                detail = "Command is empty/short and no JSON — skipped, expected."
            elif has_cmd and not has_json:
                status = "parse_failed"
                detail = "Command ran but JSON is empty — parser likely failed."
            else:
                status = "ok"
                detail = "Command ran and JSON was produced successfully."

            result = {
                "device_key": device_key,
                "cmd_number": cmd_number,
                "cmd":        cmd,
                "status":     status,
                "detail":     detail,
            }

            line = (
                f"[audit] {device_key} | "
                f"cmd #{cmd_number:>3} | "
                f"cmd: '{cmd}' | "
                f"{status:<22} | "
                f"{detail}"
            )

            print(line)
            results.append({**result, "_line": line})

    # --- write to text file ---
    output_txt = file_path.replace(".json", "_audit.txt")
    try:
        with open(output_txt, "w") as f:
            for r in results:
                f.write(r["_line"] + "\n")
            # clean up the temp _line key
        results = [{k: v for k, v in r.items() if k != "_line"} for r in results]
        print(f"[audit] Results written to {output_txt}")
    except Exception as e:
        print(f"[audit] ERROR — could not write text file: {e}")

    return results


file_path = "26_02_26_16_10.json"
audit_pre_checks(file_path)
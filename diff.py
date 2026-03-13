import json
import difflib
from pathlib import Path

MOCK_FILE = Path(__file__).parent / "mock.json"

def diff_devices(data: dict = None) -> dict:
    """
    Production function.

    Reads mock.json from the same directory by default.
    For every device, diffs pre vs post execute_show_commands by 'cmd' key.

    Returns:
        {
            device_key: {
                cmd: [
                    {"pre": "...", "post": "...", "change": "" | ["before-[removed]+[added]after", ...]},
                    ...
                ],
                ...   # only commands that have at least one change
            },
            ...
        }
    """
    if data is None:
        with open(MOCK_FILE) as f:
            data = json.load(f)

    def _extract_token(line, i1, i2):
        """Extract the whole word/token containing the change at i1:i2."""
        start = i1
        while start > 0 and line[start - 1] not in (" ", "\t"):
            start -= 1
        end = i2
        while end < len(line) and line[end] not in (" ", "\t"):
            end += 1
        return line[start:end]

    def _trim(line, i1, i2):
        """Return full line if <=10 chars, else the token containing the change."""
        if len(line) <= 10:
            return line
        return _extract_token(line, i1, i2)

    def _change_parts(pre_line, post_line):
        """
        Returns a list of dicts, one per differing opcode:
          {"change": "-[removed]+[added]", "pre": ..., "post": ...}
        pre/post are trimmed to the token if the line exceeds 10 chars.
        """
        matcher = difflib.SequenceMatcher(None, pre_line, post_line, autojunk=False)
        parts   = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            removed = pre_line[i1:i2]  if tag in ("replace", "delete") else ""
            added   = post_line[j1:j2] if tag in ("replace", "insert") else ""
            parts.append({
                "change": [removed, added],
                "pre":    _trim(pre_line,  i1, i2),
                "post":   _trim(post_line, j1, j2),
            })
        return parts

    def _diff_outputs(pre_out, post_out):
        pre_lines  = pre_out.splitlines()
        post_lines = post_out.splitlines()
        matcher    = difflib.SequenceMatcher(None, pre_lines, post_lines, autojunk=False)
        entries    = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            elif tag == "replace":
                pre_blk, post_blk = pre_lines[i1:i2], post_lines[j1:j2]
                pairs = min(len(pre_blk), len(post_blk))
                for k in range(pairs):
                    entries.extend(_change_parts(pre_blk[k], post_blk[k]))
                for k in range(pairs, len(pre_blk)):
                    entries.append({"pre": pre_blk[k], "post": "N/A", "change": ""})
                for k in range(pairs, len(post_blk)):
                    entries.append({"pre": "N/A", "post": post_blk[k], "change": ""})
            elif tag == "delete":
                for ln in pre_lines[i1:i2]:
                    entries.append({"pre": ln, "post": "N/A", "change": ""})
            elif tag == "insert":
                for ln in post_lines[j1:j2]:
                    entries.append({"pre": "N/A", "post": ln, "change": ""})

        return entries

    results = {}

    for device_key, device in data.items():
        pre_cmds  = device.get("pre",  {}).get("execute_show_commands", {}).get("commands", [])
        post      = device.get("post", {})
        post_cmds = post.get("execute_show_commands", {}).get("commands", []) if isinstance(post, dict) else []

        pre_map  = {c["cmd"]: c for c in pre_cmds}
        post_map = {c["cmd"]: c for c in post_cmds}

        cmd_results = {}
        for cmd in sorted(set(pre_map) | set(post_map)):
            pre_out  = pre_map[cmd].get("output",  "") if cmd in pre_map  else ""
            post_out = post_map[cmd].get("output", "") if cmd in post_map else ""
            entries  = _diff_outputs(pre_out, post_out)
            if entries:
                cmd_results[cmd] = entries

        if cmd_results:
            results[device_key] = cmd_results

    return results


# ─── production JSON reader ───────────────────────────────────────────────────

PROD_JSON = Path(__file__).parent / "10_80_71_55_juniper_mx204_2026-03-12_22-27-01.json"

def load_production_json(json_path: Path = None) -> dict:
    """
    Reads a production-level device JSON file (same schema as mock.json).
    Defaults to PROD_JSON (10_80_71_55_juniper_mx204_2026-03-12_22-27-01.json)
    in the same directory as this script.

    The JSON may be either:
      • A single device dict  → wrapped into {"<filename_stem>": data}
      • A multi-device dict   → used as-is

    Returns the normalised multi-device dict.
    """
    path = Path(json_path) if json_path else PROD_JSON
    if not path.exists():
        raise FileNotFoundError(f"Production JSON not found: {path}")

    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    # If the top-level keys look like device keys (have "pre"/"upgrade"/"post"),
    # treat it as a multi-device dict already.
    if isinstance(raw, dict):
        first_val = next(iter(raw.values()), None)
        if isinstance(first_val, dict) and any(k in first_val for k in ("pre", "upgrade", "post")):
            return raw  # already multi-device format

    # Otherwise wrap it as a single device using the filename stem as key.
    device_key = path.stem
    return {device_key: raw}


def run_diff_and_generate_report(json_path: Path = None, output_dir: str = ".") -> str:
    """
    1. Load the production JSON (defaults to PROD_JSON).
    2. Run diff_devices() to compute pre→post diffs.
    3. Inject the diff results back into the device data under ["diff"].
    4. Call generate_html_report() to produce the HTML file.

    Returns the path to the generated HTML file.
    """
    from workflow_report_generator import generate_html_report   # local import to avoid circular deps

    # Load data
    workflow_data = load_production_json(json_path)

    # Compute diffs and inject
    diff_results = diff_devices(workflow_data)
    for device_key, cmd_diffs in diff_results.items():
        if device_key in workflow_data:
            workflow_data[device_key]["diff"] = cmd_diffs

    # Generate HTML
    html_path = generate_html_report(workflow_data, output_dir=output_dir)
    return html_path


def print_diff(results: dict = None):
    """NOT FOR PRODUCTION."""
    if results is None:
        results = diff_devices()
    print(json.dumps(results, indent=2))


# ─── entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    # Usage:
    #   python diff.py                          → diff + HTML from default PROD_JSON
    #   python diff.py path/to/other.json       → diff + HTML from a custom JSON file
    #   python diff.py --print-only             → just print diff JSON to stdout (mock)

    if "--print-only" in sys.argv:
        print_diff()
    else:
        json_path = None
        for arg in sys.argv[1:]:
            if not arg.startswith("--"):
                json_path = Path(arg)
                break

        try:
            html_path = run_diff_and_generate_report(json_path=json_path, output_dir=".")
            print(f"Report written: {html_path}")
        except FileNotFoundError as e:
            print(f"ERROR: {e}")
            print("Place the JSON file next to diff.py or pass the path as an argument:")
            print("  python diff.py path/to/your_device.json")
            sys.exit(1)
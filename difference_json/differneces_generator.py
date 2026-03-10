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


def print_diff(results: dict = None):
    """NOT FOR PRODUCTION."""
    if results is None:
        results = diff_devices()
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    print_diff()
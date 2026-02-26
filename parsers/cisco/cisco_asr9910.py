import re
import os
import sys
import json
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
 
 
def parse_show_bfd_session(folder_path: str) -> Dict[str, Any]:
    """
    Parse 'show bfd session' output (from COMMAND_OUTPUT_STORE) and write JSON.
    
    :param folder_path: (unused) Kept for signature compatibility. Input comes from COMMAND_OUTPUT_STORE.
    :type folder_path: str
    :return: JSON-like dict (whatever write_json returns) for 'show bfd session'
    :rtype: Dict[str, Any]
    """
    try:
        print(" show bfd session ...")

        cmd = "show bfd session"
        content = COMMAND_OUTPUT_STORE.get(cmd).get("output").get('output')
        content = content.strip() if content else ""
        print(f" Content: {content!r}")

        if not content or "empty" in content.lower():
            return {"status": "empty", "file": None}

        result: List[Dict[str, Any]] = []
        lines = content.splitlines()
        i = 0

        # Helper to parse a timer token "45ms(15ms*3)" or "0s" or "n/a"
        def parse_timer(token: str):
            token = token.strip()
            m = re.match(r'^(\d+(?:ms|s))\((\d+(?:ms|s))\*(\d+)\)$', token, flags=re.IGNORECASE)
            if m:
                return m.group(1), m.group(2), m.group(3)
            if token.lower() in ("n/a", "na", "-"):
                return "n/a", "n/a", "n/a"
            simple = re.match(r'^(\d+(?:ms|s))$', token, flags=re.IGNORECASE)
            if simple:
                return simple.group(1), "0s", "0"
            return token, "0s", "0"

        while i < len(lines):
            raw_line = lines[i]
            line = raw_line.strip()

            # Skip blanks, headers, separators
            if (
                not line
                or line.lower().startswith("interface")
                or line.startswith("---")
                or ("echo" in line.lower() and "async" in line.lower())
            ):
                i += 1
                continue

            # Split by 2+ spaces – typical for XR/XE tabular outputs
            cols = re.split(r'\s{2,}', line)
            if len(cols) < 3:
                i += 1
                continue

            interface = cols[0].strip()
            dest_addr = cols[1].strip()
            echo_full = cols[2].strip()
            async_full = cols[3].strip() if len(cols) >= 4 else "n/a"
            state = cols[4].strip() if len(cols) >= 5 else ""

            echo_time, echo_interval, echo_multiplier = parse_timer(echo_full)
            async_time, async_interval, async_multiplier = parse_timer(async_full)

            hardware = "n/a"
            npu = "n/a"

            # Optional continuation line with "Yes/No <npu>" and/or state details
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                # Continuation heuristic: if it doesn't look like a new session (no IP)
                if next_line and not re.search(r'\d{1,3}(?:\.\d{1,3}){3}', next_line):
                    if not state:
                        m_yes_no = re.search(r'\b(Yes|No)\b', next_line, flags=re.IGNORECASE)
                        if m_yes_no:
                            hardware = m_yes_no.group(1).title()
                            parts = next_line.split()
                            idx = parts.index(m_yes_no.group(1))
                            if idx + 1 < len(parts):
                                npu = parts[idx + 1]
                            state = " ".join(parts[:idx]).strip() or state
                        else:
                            state = next_line if not state else state
                    else:
                        parts = next_line.split()
                        if parts and parts[0].lower() in ("yes", "no"):
                            hardware = parts[0].title()
                            if len(parts) > 1:
                                npu = parts[1]
                    i += 1  # consume continuation

            entry = BFDSession(
                interface=interface,
                dest_addr=dest_addr,
                echo_time=echo_time,
                echo_interval=echo_interval,
                echo_multiplier=echo_multiplier,
                async_time=async_time,
                async_interval=async_interval,
                async_multiplier=async_multiplier,
                state=state,
                hardware=hardware,
                npu=npu
            )
            result.append(asdict(entry))
            i += 1

        output_file = write_json(
            command_name="show_bfd_session",
            vendor="cisco",
            model="asr9910",
            json_data=result,
            json_file_path="precheck_jsons/"
        )

        
        return output_file

    except Exception as e:
        return {"error": f"Error reading/parsing command output: {str(e)}"}




def show_install_active_summary(folder_path: str) -> Dict[str, Any]:
    """
    Docstring for show_install_active_summary
    
    :param folder_path: (unused) Kept for signature compatibility. Input comes from COMMAND_OUTPUT_STORE.
    :type folder_path: str
    :return: JSON-like dict (whatever write_json returns) for 'show install active summary'
    :rtype: Dict[str, Any]
    """
    try:
        print(" Show install active summary ....")

        cmd = "show install active summary"
        content = COMMAND_OUTPUT_STORE.get(cmd).get("output")
        print(f" Content: {content!r}")

        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        # Label (optional on some platforms)
        label_match = re.search(r'^\s*Label\s*:\s*(.+?)\s*$', content, flags=re.MULTILINE)
        label = label_match.group(1).strip() if label_match else "Unknown"

        # Active packages count (optional fallback to 0)
        m_count = re.search(r'Active Packages:\s*(?P<count>\d+)', content)
        activePackages = int(m_count.group("count")) if m_count else 0
        print(f" Active Packages: {activePackages}")

        # Package lines: lines starting with indentation but not headers
        # Excludes lines beginning with 'Active' or 'Mon' to avoid header bleed
        package_lines = re.findall(
            r'^(?:[ \t]+)(?!Active)(?!Mon)(.+\S)\s*$',
            content,
            flags=re.MULTILINE
        )
        packages = [line.strip() for line in package_lines if line.strip()]

        # Build result with your field names
        result = [asdict(ShowInstallActiveSummary(
            Label=label,
            AcivePackages=activePackages,
            Packages=packages
        ))]

        # Write JSON via your helper
        output_file = write_json(
            command_name="show_install_active_summary",
            vendor="cisco",
            model="asr9910",
            json_data=result,
            json_file_path="precheck_jsons/"
        )

        return output_file

    except Exception as e:
        return {"error": f"Error reading command output: {str(e)}"}
 
 
def show_route_summary(folder_path: str): 
    """
    Docstring for show_route_summary
    
    :param folder_path: Description
    :type folder_path: str
    """
    try: 
        print(" show route summary ...")
        
        cmd = "show route summary"
        content = COMMAND_OUTPUT_STORE.get(cmd).get("output")
        print(f" Content: {content}")
        if not content: 
            raise ValueError(f"No output found for command: {cmd}")

        result = [] 

        for line in content.splitlines(): 
            line = line.strip() 
            print(f" Line: {line}")

            if ( 
                not line 
                or line.startswith("Route")
            ): 
                continue 

            cols = re.split(r'\s{2,}', line)
            print(f" cols: {cols}")

            entry = ShowRouteSummary(
                routeSource=cols[0],
                routes= cols[1],
                backup=cols[2],
                deleted=cols[3], 
                memory=cols[4]
            )
            result.append(asdict(entry))
        
            # Creating json file 
            output_file = write_json(
                command_name="show_platform", 
                vendor="cisco",
                model="asr9910",
                json_data=result,
                json_file_path="precheck_jsons/"
            )

            return output_file
    except Exception as e: 
        return {"error": f"Error reading file: {str(e)}"}


def show_pim_neighbor(folder_path: str) -> Dict[str, Any]:
    """
    Docstring for show_pim_neighbor

    :param folder_path: (unused) Kept for signature compatibility. Input comes from COMMAND_OUTPUT_STORE.
    :type folder_path: str
    :return: JSON-like dict (whatever write_json returns) for 'show pim neighbor'
    :rtype: Dict[str, Any]
    """
    try:
        print(" show pim neighbor ...")

        cmd = "show pim neighbor"
        content = COMMAND_OUTPUT_STORE.get(cmd).get("output")
        print(f" Content: {content!r}")

        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        # VRF (optional)
        vrf_match = re.search(r'PIM neighbors in VRF\s+(\S+)', content, flags=re.IGNORECASE)
        vrf = vrf_match.group(1) if vrf_match else "default"

        result: List[Dict[str, Any]] = []

        for raw_line in content.splitlines():
            line = raw_line.rstrip("\n")
            stripped = line.strip()
            print(f" Line: {stripped}")

            if not stripped:
                continue

            lower = stripped.lower()
            # Skip non-data lines / headers
            if (
                lower.startswith("pim neighbors in vrf")
                or lower.startswith("flag:")
                or lower.startswith("* indicates the neighbor")
                or lower.startswith("neighbor address")
                or lower.startswith("---")
            ):
                continue

            # XR/XE table row pattern
            m = re.match(
                r'^\s*'
                r'(?P<addr>\d{1,3}(?:\.\d{1,3}){3})'
                r'(?P<self>\*)?'
                r'\s+'
                r'(?P<intf>\S+)'
                r'\s+'
                r'(?P<uptime>\S+)'
                r'\s+'
                r'(?P<expires>\S+)'
                r'\s+'
                r'(?P<drpri>\d+)'
                r'\s+'
                r'(?P<flags>.+?)'
                r'\s*$',
                stripped
            )
            if not m:
                # Not a matching row; continue safely
                continue

            neighbor_addr = m.group("addr")
            is_self = bool(m.group("self"))
            intf = m.group("intf")
            uptime = m.group("uptime")
            expires = m.group("expires")

            try:
                drpri = int(m.group("drpri"))
            except Exception:
                drpri = 0

            flags_raw = m.group("flags").strip()
            is_dr = "(dr)" in flags_raw.lower()

            # Extract letter flags (B/E/P/S) without duplicates
            letters: List[str] = []
            for token in flags_raw.replace("(", " ").replace(")", " ").split():
                t = token.strip()
                if t in ("B", "E", "P", "S") and t not in letters:
                    letters.append(t)

            entry = PimNeighbor(
                vrf=vrf,
                neighborAddress=neighbor_addr,
                isSelf=is_self,
                interface=intf,
                uptime=uptime,
                expires=expires,
                drPriority=drpri,
                isDR=is_dr,
                flags=letters,
                flagsRaw=flags_raw
            )
            result.append(asdict(entry))

        # Creating json file
        output_file = write_json(
            command_name="show_pim_neighbor",
            vendor="cisco",
            model="asr9910",
            json_data=result,
            json_file_path="precheck_jsons/"
        )

        return output_file

    except Exception as e:
        return {"error": f"Error reading/parsing command output: {str(e)}"}


def show_filesystem(folder_path: str) -> Dict[str, Any]:
    """
    Docstring for show_filesystem

    :param folder_path: (unused) Kept for signature compatibility. Input comes from COMMAND_OUTPUT_STORE.
    :type folder_path: str
    :return: JSON-like dict (whatever write_json returns) for 'show filesystem'
    :rtype: Dict[str, Any]
    """
    try:
        print(" show filesystem ...")

        cmd = "show filesystem"
        content = COMMAND_OUTPUT_STORE.get(cmd).get("output")
        print(f" Content: {content!r}")

        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        result: List[Dict[str, Any]] = []

        for raw_line in content.splitlines():
            line = raw_line.strip()

            if not line:
                continue

            lower = line.lower()
            # Skip headers/separators commonly seen on XR/XE/IOS
            if (
                lower.startswith("file systems:")
                or lower.startswith("size(b)")
                or lower.startswith("file systems")  # defensive
                or lower.startswith("---")           # separators
            ):
                continue

            # Expect 5 columns separated by 2+ spaces:
            # Size(b) | Free(b) | Type | Flags | Prefixes
            cols = re.split(r'\s{2,}', line)

            if len(cols) < 5:
                # Not enough columns; skip safely
                continue

            size_str, free_str, fs_type, flags, prefixes_raw = cols[:5]

            # Parse numeric fields (bytes)
            try:
                size_bytes = int(size_str.replace(",", ""))
                free_bytes = int(free_str.replace(",", ""))
            except ValueError:
                # Non-numeric; skip the row
                continue

            # Normalize prefixes into a list (tokens keep trailing colons)
            prefixes = [p for p in prefixes_raw.split() if p]

            entry = ShowFileSystemEntry(
                sizeBytes=size_bytes,
                freeBytes=free_bytes,
                fsType=fs_type,
                flags=flags,
                prefixesRaw=prefixes_raw,
                prefixes=prefixes
            )
            result.append(asdict(entry))

        # Write JSON artifact via your shared helper
        output_file = write_json(
            command_name="show_filesystem",
            vendor="cisco",
            model="asr9910",
            json_data=result,
            json_file_path="precheck_jsons/"
        )

        return output_file

    except Exception as e:
        return {"error": f"Error reading/parsing command output: {str(e)}"}


def show_watchdog_memory_state_asr9910(folder_path: str) -> Dict[str, Any]:
    """
    Parse 'show watchdog memory-state location all' output for Cisco ASR9910 from COMMAND_OUTPUT_STORE
    and write JSON via write_json(vendor='cisco', model='ASR9910').

    :param folder_path: (unused) Kept for signature compatibility.
    :return: Whatever write_json returns, or an error dict.
    """
    try:
        print("show watchdog memory-state location all (ASR9910)")

        cmd = "show watchdog memory-state location all"
        content = COMMAND_OUTPUT_STORE.get(cmd).get("output")
        print(f" Content: {content!r}")
        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        result: List[Dict[str, Any]] = []

        pattern = re.compile(
            r"----\s*(?P<section>[^-]+?)\s*----\s*"
            r"Memory information:\s*"
            r"\s*Physical\s+Memory\s*:\s*(?P<physical>[\d.]+)\s*(?:MB|Gb|GB|mb)?\s*"
            r"\s*Free\s+Memory\s*:\s*(?P<free>[\d.]+)\s*(?:MB|Gb|GB|mb)?\s*"
            r"\s*Memory\s+State\s*:\s*(?P<state>\w+)\s*",
            flags=re.IGNORECASE | re.MULTILINE
        )

        matches = pattern.finditer(content)

        for m in matches:
            # Build memoryInfo using your ASR9910 dataclass
            mem_info = cisco_asr9910.memoryInfo(
                physicalMem=m.group("physical"),
                freeMem=m.group("free"),
                memoryState=m.group("state").upper()
            )

            node_state = cisco_asr9910.ShowWatchdogMemoryState(
                nodeName=m.group("section").strip(),
                memoryInfo=[mem_info]
            )

            result.append(asdict(node_state))

        # If no matches found, return empty result gracefully
        if not result:
            print(" No matching sections found; returning empty result.")
        
        output_file = write_json(
            command_name="show_watchdog_memory_state",
            vendor="cisco",
            model="asr9910",
            json_data=result,
            json_file_path="precheck_jsons/"
        )

        return output_file

    except Exception as e:
        return {"error": f"Error reading/parsing command output: {str(e)}"}

def show_hw_module_fpd(folder_path: str): 
    """
    Docstring for show_hw_module_fpd
    
    :param folder_path: Description
    :type folder_path: str
    """
    try: 
        print("show hw_module fpd ...")
        
        cmd = "show hw-module fpd"
        content = COMMAND_OUTPUT_STORE.get(cmd).get("output")
        print(f" Content: {content}")
        if not content: 
            raise ValueError(f"No output found for command: {cmd}")

        auto_upgrade_pattern = re.search(
            r'^Auto-upgrade\s*:\s*(?P<AutoUpgrade>\S+)',
            content,
            re.MULTILINE
        )

        auto_upgrade = auto_upgrade_pattern.group("AutoUpgrade") if auto_upgrade_pattern else ""
        fpds, result = [], []

        for line in content.splitlines(): 
            line  = line.strip() 
            print(f" Line: {line}")

            if (
                not line 
                or line.startswith("Auto") 
                or line.startswith("Location") 
                or line.startswith("-") 
                or line.startswith("=") 
                or line.startswith("FPD")
            ): 
                continue 

            cols = re.split(r'\s{1,}', line)
            # print(f" cols: {cols}")

            # card_type, hwver, fpd_device = cols[1].split()

            print(f" cols: {cols}")
            # print(f"cardType: {card_type}, hwver: {hwver}, and fpddevice: {fpd_device}")
            fpd_version = { 
                "Running": float(cols[5]), 
                "Programd": float(cols[6])
            }

            # print(f" fpd versions: {fpd_version}")
            
            fpd = FPDEntry( 
                Location=cols[0], 
                CardType=cols[1], 
                HWver=cols[2], 
                FPDdevice=cols[3], 
                ATRstatus=cols[4], 
                FPDVersions=fpd_version
            )

            fpds.append(asdict(fpd))
            # print(f" FPD Entry: {fpds}")
        
        result.append(
            {
                "AutoUpgrade": auto_upgrade, 
                "FPDs": fpds
            }
        )
        print(f" Result: {result}")
        # Creating json file 
        output_file = write_json(
            command_name="show_hw_module_fpd", 
            vendor="cisco",
            model="asr9910",
            json_data=result,
            json_file_path="precheck_jsons/"
        )

        return output_file
    except Exception as e: 
        return {"error": f"Error reading file: {str(e)}"}



ef show_l2vpn_xconnect_brief(folder_path: str) -> Dict[str, Any]:
    """
    Parse 'show l2vpn xconnect brief' output from COMMAND_OUTPUT_STORE and write JSON.

    Output shape:
    {
      "rows": [ L2vpnXconnectBriefRow-as-dict, ... ],
      "summary": L2vpnXconnectBriefSummary-as-dict
    }
    """
    try:
        print(" show l2vpn xconnect brief ...")

        cmd = "show l2vpn xconnect brief"
        content = COMMAND_OUTPUT_STORE.get(cmd).get("output")
        print(f" Content: {content!r}")

        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        rows: List[Dict[str, Any]] = []
        # Initialize summary (will be updated by the grand total line if present)
        summary_obj = L2vpnXconnectBriefSummary(totalUp=0, totalDown=0, totalUnresolved=0)

        current_domain: str = ""
        current_category: str = ""

        for raw_line in content.splitlines():
            line = raw_line.rstrip("\n")
            stripped = line.strip()

            if not stripped:
                continue

            # Detect a domain (e.g., "EVPN VPWS"). Heuristic: left-aligned printable text
            # that doesn't contain column headers keywords and has no colon.
            if (
                re.match(r'^[A-Za-z].*$', stripped)
                and "UP" not in stripped
                and "DOWN" not in stripped
                and "UNR" not in stripped
                and "UNRESOLVED" not in stripped
                and ":" not in stripped
            ):
                current_domain = stripped
                current_category = ""  # reset category when domain changes
                # print(f" Domain -> {current_domain}")
                continue

            # Detect category/header lines (contain header columns)
            # Example: "Like-to-Like                        UP       DOWN        UNR"
            if ("UP" in stripped and "DOWN" in stripped) and ("UNR" in stripped or "UNRESOLVED" in stripped):
                # Category is text before "UP"
                category = stripped.split("UP")[0].strip()
                if category:
                    current_category = category
                # print(f" Category -> {current_category}")
                continue

            # Match row lines: "<name> <up> <down> <unr>"
            # Examples:
            #   "PW-Ether                         392         18          0"
            #   "Total                            392         18          0"
            m = re.match(
                r'^\s*(?P<name>[\S ]*?\S)\s+(?P<up>\d+)\s+(?P<down>\d+)\s+(?P<unr>\d+)\s*$',
                line
            )
            if m and current_domain:
                name = m.group("name").strip()
                up = int(m.group("up"))
                down = int(m.group("down"))
                unr = int(m.group("unr"))

                row = L2vpnXconnectBriefRow(
                    domain=current_domain,
                    category=current_category or "Unknown",
                    typeName=name,
                    up=up,
                    down=down,
                    unresolved=unr
                )
                rows.append(asdict(row))
                continue

            # Match grand total line: "Total: 392 UP, 18 DOWN, 0 UNRESOLVED"
            mg = re.search(
                r'Total:\s*(?P<up>\d+)\s*UP,\s*(?P<down>\d+)\s*DOWN,\s*(?P<unr>\d+)\s*(?:UNRESOLVED|UNR)',
                stripped,
                flags=re.IGNORECASE
            )
            if mg:
                summary_obj.totalUp = int(mg.group("up"))
                summary_obj.totalDown = int(mg.group("down"))
                summary_obj.totalUnresolved = int(mg.group("unr"))
                continue

        # Build final payload
        payload = {
            "rows": rows,
            "summary": asdict(summary_obj)
        }

        # Write JSON via your shared writer
        output_file = write_json(
            command_name="show_l2vpn_xconnect_brief",
            vendor="cisco",
            model="asr9910",
            json_data=payload,
            json_file_path="precheck_jsons/"
        )

        return output_file

    except Exception as e:
        return {"error": f"Error reading/parsing command output: {str(e)}"}


def show_isis_colt_adjacencies(folder_path: str) -> Dict[str, Any]:
    """
    Parse 'show isis adjacency' style output for IS-IS COLT Level-1/Level-2 adjacencies and write JSON.
    
    :param folder_path: (unused) Kept for signature compatibility. Input comes from COMMAND_OUTPUT_STORE.
    :type folder_path: str
    :return: JSON-like dict (whatever write_json returns) for 'show isis colt adjacencies'
    :rtype: Dict[str, Any]
    """
    try:
        print(" Show IS-IS COLT adjacencies ....")

        # Prefer a fixed command key, but accept common variants as fallback
        cmd_candidates = [
            "show isis colt adjacencies",
            "show isis adjacencies",
            "show isis adjacency",
        ]
        content = None
        cmd_used = None
        for c in cmd_candidates:
            v = COMMAND_OUTPUT_STORE.get(c)
            if v:
                content = v
                cmd_used = c
                break

        print(f" Using command key: {cmd_used!r}")
        print(f" Content: {content!r}")

        if not content:
            raise ValueError(f"No output found for any of: {', '.join(cmd_candidates)}")

        # --- Regex to find Level sections ---
        # Example header lines:
        #   IS-IS COLT Level-1 adjacencies:
        #   IS-IS COLT Level-2 adjacencies:
        section_re = re.compile(r"^\s*IS-IS\s+COLT\s+(Level-\d)\s+adjacencies:\s*$", re.MULTILINE)
        total_re   = re.compile(r"^\s*Total\s+adjacency\s+count:\s*(\d+)\s*$", re.MULTILINE)

        # Row regex for columns:
        # System Id, Interface, SNPA, State, Hold, Changed, NSF, IPv4 BFD, IPv6 BFD
        # 'Changed' can be "not up" (two tokens) or durations like "1y39w", etc.
        row_re = re.compile(
            r"^(?P<SystemId>\S+)\s+"
            r"(?P<Interface>\S+)\s+"
            r"(?P<SNPA>\S+)\s+"
            r"(?P<State>\S+)\s+"
            r"(?P<Hold>\d+)\s+"
            r"(?P<Changed>.+?)\s+"
            r"(?P<NSF>\S+)\s+"
            r"(?P<IPv4BFD>\S+)\s+"
            r"(?P<IPv6BFD>\S+)\s*$"
        )

        # --- Split into sections by Level ---
        matches = list(section_re.finditer(content))
        if not matches:
            return {"error": "No 'IS-IS COLT Level-x adjacencies' sections found in command output."}

        results: List[Dict[str, Any]] = []

        for idx, m in enumerate(matches):
            level = m.group(1)  # Level-1 / Level-2
            start = m.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
            section_text = content[start:end]

            adjacencies: List[Dict[str, Any]] = []
            total_count = 0

            for raw_line in section_text.splitlines():
                line = raw_line.rstrip()
                if not line:
                    continue

                # Skip header/noise lines typical in tabular CLI output
                hdr_line = line.strip()
                if (
                    hdr_line.startswith("System Id")
                    or hdr_line.startswith("Interface")
                    or "SNPA" in hdr_line
                    or hdr_line.startswith("BFD")
                    or hdr_line.startswith("IPv4")
                    or hdr_line.startswith("IPv6")
                ):
                    continue

                # Total adjacency count
                mt = total_re.match(line)
                if mt:
                    total_count = int(mt.group(1))
                    continue

                # Try match a data row
                mr = row_re.match(line)
                if not mr:
                    # ignore non-data lines silently
                    continue

                row = mr.groupdict()

                # Normalize types / whitespace
                row["Hold"] = int(row["Hold"])
                row["Changed"] = row["Changed"].strip()

                adjacencies.append(row)

            # If total_count missing, infer it
            if total_count == 0:
                total_count = len(adjacencies)

            level_obj = {
                "Level": level,
                "TotalAdjacencyCount": total_count,
                "Adjacencies": adjacencies,
            }
            results.append(level_obj)

        # Write JSON via your helper
        output_file = write_json(
            command_name="show_isis_colt_adjacencies",
            vendor="cisco",
            model="asr9910",
            json_data=results,
            json_file_path="precheck_jsons/"
        )

        return output_file

    except Exception as e:
        return {"error": f"Error reading command output: {str(e)}"}


def show_memory_summary(folder_path: str) -> Dict[str, Any]:
    """
    Docstring for show_memory_summary

    :param folder_path: (unused) Kept for signature compatibility. Input comes from COMMAND_OUTPUT_STORE.
    :type folder_path: str
    :return: JSON-like dict (whatever write_json returns) for 'show memory summary'
    :rtype: Dict[str, Any]
    """
    try:
        print(" Show memory summary ....")

        cmd = "show memory summary"
        content = COMMAND_OUTPUT_STORE.get(cmd).get("output")
        print(f" Content: {content!r}")

        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        # Regex patterns (tolerant of extra spaces/case)
        re_node = re.compile(r'^\s*node:\s*(?P<node>\S+)\s*$', re.IGNORECASE | re.MULTILINE)

        # "Physical Memory: 27309M total (12820M available)" — some XR images omit 'total'
        re_phys = re.compile(
            r'^\s*Physical\s+Memory:\s*(?P<total>\S+)\s+(?:total\s*)?\(\s*(?P<avail>\S+)\s+available\)\s*$',
            re.IGNORECASE | re.MULTILINE
        )

        # "Application Memory : 27309M (12820M available)"
        re_app = re.compile(
            r'^\s*Application\s+Memory\s*:\s*(?P<total>\S+)\s*\(\s*(?P<avail>\S+)\s+available\)\s*$',
            re.IGNORECASE | re.MULTILINE
        )

        # "Image: 4M (bootram: 0M)"
        re_img = re.compile(
            r'^\s*Image:\s*(?P<image>\S+)\s*\(\s*bootram:\s*(?P<bootram>\S+)\s*\)\s*$',
            re.IGNORECASE | re.MULTILINE
        )

        # "Reserved: 0M, IOMem: 0M, flashfsys: 0M"
        # (Allow minor variants in key casing/spaces)
        re_resv = re.compile(
            r'^\s*Reserved:\s*(?P<reserved>\S+)\s*,\s*IO\s*Mem:\s*(?P<iomem>\S+)\s*,\s*flashf?sys:\s*(?P<flashfsys>\S+)\s*$',
            re.IGNORECASE | re.MULTILINE
        )

        # "Total shared window: 1G"
        re_shared = re.compile(
            r'^\s*Total\s+shared\s+window:\s*(?P<shared>\S+)\s*$',
            re.IGNORECASE | re.MULTILINE
        )

        lines = content.splitlines()
        records: List[Dict[str, str]] = []
        cur: Dict[str, str] | None = None

        def flush_current():
            nonlocal cur
            if cur is None:
                return
            defaults = {
                "node": "",
                "physical_total": "",
                "physical_available": "",
                "app_total": "",
                "app_available": "",
                "image": "",
                "bootram": "",
                "reserved": "",
                "iomem": "",
                "flashfsys": "",
                "shared_window": "",
            }
            for k, v in defaults.items():
                cur.setdefault(k, v)
            records.append(cur.copy())
            cur = None

        # Parse line-by-line
        for line in lines:
            m = re_node.match(line)
            if m:
                flush_current()
                cur = {"node": m.group("node")}
                continue

            if cur is None:
                continue

            m = re_phys.match(line)
            if m:
                cur["physical_total"] = m.group("total")
                cur["physical_available"] = m.group("avail")
                continue

            m = re_app.match(line)
            if m:
                cur["app_total"] = m.group("total")
                cur["app_available"] = m.group("avail")
                continue

            m = re_img.match(line)
            if m:
                cur["image"] = m.group("image")
                cur["bootram"] = m.group("bootram")
                continue

            m = re_resv.match(line)
            if m:
                cur["reserved"] = m.group("reserved")
                cur["iomem"] = m.group("iomem")
                cur["flashfsys"] = m.group("flashfsys")
                continue

            m = re_shared.match(line)
            if m:
                cur["shared_window"] = m.group("shared")
                continue

        # Capture the last block
        flush_current()

        # Fallback: parse a single block even if 'node:' header is missing
        if not records:
            cur = {"node": "Unknown"}
            for line in lines:
                m = re_phys.match(line)
                if m:
                    cur["physical_total"] = m.group("total")
                    cur["physical_available"] = m.group("avail")
                    continue
                m = re_app.match(line)
                if m:
                    cur["app_total"] = m.group("total")
                    cur["app_available"] = m.group("avail")
                    continue
                m = re_img.match(line)
                if m:
                    cur["image"] = m.group("image")
                    cur["bootram"] = m.group("bootram")
                    continue
                m = re_resv.match(line)
                if m:
                    cur["reserved"] = m.group("reserved")
                    cur["iomem"] = m.group("iomem")
                    cur["flashfsys"] = m.group("flashfsys")
                    continue
                m = re_shared.match(line)
                if m:
                    cur["shared_window"] = m.group("shared")
                    continue
            if any(cur.get(k) for k in ["physical_total", "app_total", "image", "reserved", "iomem", "flashfsys", "shared_window"]):
                records.append(cur)

        # Build result via your dataclass
        result: List[Dict[str, Any]] = []
        for r in records:
            obj = ShowMemorySummary(
                node=r.get("node", ""),
                physical_total=r.get("physical_total", ""),
                physical_available=r.get("physical_available", ""),
                app_total=r.get("app_total", ""),
                app_available=r.get("app_available", ""),
                image=r.get("image", ""),
                bootram=r.get("bootram", ""),
                reserved=r.get("reserved", ""),
                iomem=r.get("iomem", ""),
                flashfsys=r.get("flashfsys", ""),
                shared_window=r.get("shared_window", "")
            )
            result.append(asdict(obj))

        output_file = write_json(
            command_name="show_memory_summary",
            vendor="cisco",
            model="asr9910",
            json_data=result,
            json_file_path="precheck_jsons/"
        )
        
        return output_file

    except Exception as e:
        return {"error": f"Error reading command output: {str(e)}"}



def show_redundancy(folder_path: str) -> Dict[str, Any]:
    """
    Docstring for show_redundancy

    :param folder_path: (unused) Kept for signature compatibility. Input comes from COMMAND_OUTPUT_STORE.
    :type folder_path: str
    :return: JSON-like dict (whatever write_json returns) for 'show redundancy'
    :rtype: Dict[str, Any]
    """
    try:
        print(" Show redundancy ....")

        cmd = "show redundancy"
        content = COMMAND_OUTPUT_STORE.get(cmd).get("output")
        print(f" Content: {content!r}")

        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        # ---------------- Regex patterns ----------------
        # Section header
        re_header = re.compile(
            r'^\s*Redundancy\s+information\s+for\s+node\s+(?P<node>[^:]+):\s*$',
            re.IGNORECASE | re.MULTILINE
        )

        # Roles
        re_node_role = re.compile(
            r'^\s*Node\s+(?P<node>\S+)\s+is\s+in\s+(?P<role>\S+)\s+role\s*$',
            re.IGNORECASE
        )
        re_partner_role = re.compile(
            r'^\s*Partner\s+node\s+\((?P<partner>[^)]+)\)\s+is\s+in\s+(?P<role>\S+)\s+role\s*$',
            re.IGNORECASE
        )

        # Standby readiness
        re_stby_ready = re.compile(
            r'^\s*Standby\s+node\s+in\s+(?P<standby>\S+)\s+is\s+ready\s*$',
            re.IGNORECASE
        )
        re_stby_nsr_ready = re.compile(
            r'^\s*Standby\s+node\s+in\s+(?P<standby>\S+)\s+is\s+NSR-ready\s*$',
            re.IGNORECASE
        )

        # Reload/boot lines (keep as-is for traceability)
        re_controller_reload = re.compile(
            r'^\s*(?P<line>.+\sreloaded\s+.+)$', re.IGNORECASE
        )
        re_active_boot = re.compile(
            r'^\s*(?P<line>Active\s+node\s+booted\s+.+)$', re.IGNORECASE
        )
        re_standby_boot = re.compile(
            r'^\s*(?P<line>Standby\s+node\s+boot\s+.+)$', re.IGNORECASE
        )
        re_stby_last_not_ready = re.compile(
            r'^\s*(?P<line>Standby\s+node\s+last\s+went\s+not\s+ready\s+.+)$', re.IGNORECASE
        )
        re_stby_last_ready = re.compile(
            r'^\s*(?P<line>Standby\s+node\s+last\s+went\s+ready\s+.+)$', re.IGNORECASE
        )
        re_stby_last_not_nsr_ready = re.compile(
            r'^\s*(?P<line>Standby\s+node\s+last\s+went\s+not\s+NSR-ready\s+.+)$', re.IGNORECASE
        )
        re_stby_last_nsr_ready = re.compile(
            r'^\s*(?P<line>Standby\s+node\s+last\s+went\s+NSR-ready\s+.+)$', re.IGNORECASE
        )

        # Switchovers
        re_switchovers = re.compile(
            r'^\s*There\s+have\s+been\s+(?P<count>\d+)\s+switch-overs\s+since\s+reload\s*$', re.IGNORECASE
        )

        # Reload reasons
        re_active_reason = re.compile(
            r'^\s*Active\s+node\s+reload\s+"(?P<reason>[^"]*)"\s*$', re.IGNORECASE
        )
        re_standby_reason = re.compile(
            r'^\s*Standby\s+node\s+reload\s+"(?P<reason>[^"]*)"\s*$', re.IGNORECASE
        )

        # ---------------- Parse across multiple node sections ----------------
        lines = content.splitlines()
        records: List[Dict[str, Any]] = []

        cur: Dict[str, Any] | None = None

        def new_empty_record(node_name: str) -> Dict[str, Any]:
            return {
                "node": node_name.strip(),
                "node_role": "",
                "partner_node": "",
                "partner_role": "",
                "standby_node": "",
                "standby_ready": False,
                "standby_nsr_ready": False,
                "switchovers_since_reload": 0,
                "active_node_reload_reason": "",
                "standby_node_reload_reason": "",
                "reload_boot_info": {
                    "controller_reload": "",
                    "active_boot": "",
                    "standby_boot": "",
                    "standby_last_not_ready": "",
                    "standby_last_ready": "",
                    "standby_last_not_nsr_ready": "",
                    "standby_last_nsr_ready": "",
                },
            }

        def flush_current():
            nonlocal cur
            if cur is not None:
                records.append(cur)
                cur = None

        # Main scan
        for line in lines:
            # Section header → start a new record
            mh = re_header.match(line)
            if mh:
                flush_current()
                cur = new_empty_record(mh.group("node"))
                print(f" New redundancy section: node={cur['node']}")
                continue

            if cur is None:
                continue  # ignore lines until a section begins

            # Roles
            m = re_node_role.match(line)
            if m:
                cur["node_role"] = m.group("role").strip().upper()
                continue

            m = re_partner_role.match(line)
            if m:
                cur["partner_node"] = m.group("partner").strip()
                cur["partner_role"] = m.group("role").strip().upper()
                continue

            # Standby readiness
            m = re_stby_ready.match(line)
            if m:
                cur["standby_node"] = m.group("standby").strip()
                cur["standby_ready"] = True
                continue

            m = re_stby_nsr_ready.match(line)
            if m:
                cur["standby_node"] = m.group("standby").strip()
                cur["standby_nsr_ready"] = True
                continue

            # Reload/Boot lines (store entire line as-is)
            m = re_controller_reload.match(line)
            if m and not cur["reload_boot_info"]["controller_reload"]:
                cur["reload_boot_info"]["controller_reload"] = m.group("line").strip()
                continue

            m = re_active_boot.match(line)
            if m and not cur["reload_boot_info"]["active_boot"]:
                cur["reload_boot_info"]["active_boot"] = m.group("line").strip()
                continue

            m = re_standby_boot.match(line)
            if m and not cur["reload_boot_info"]["standby_boot"]:
                cur["reload_boot_info"]["standby_boot"] = m.group("line").strip()
                continue

            m = re_stby_last_not_ready.match(line)
            if m and not cur["reload_boot_info"]["standby_last_not_ready"]:
                cur["reload_boot_info"]["standby_last_not_ready"] = m.group("line").strip()
                continue

            m = re_stby_last_ready.match(line)
            if m and not cur["reload_boot_info"]["standby_last_ready"]:
                cur["reload_boot_info"]["standby_last_ready"] = m.group("line").strip()
                continue

            m = re_stby_last_not_nsr_ready.match(line)
            if m and not cur["reload_boot_info"]["standby_last_not_nsr_ready"]:
                cur["reload_boot_info"]["standby_last_not_nsr_ready"] = m.group("line").strip()
                continue

            m = re_stby_last_nsr_ready.match(line)
            if m and not cur["reload_boot_info"]["standby_last_nsr_ready"]:
                cur["reload_boot_info"]["standby_last_nsr_ready"] = m.group("line").strip()
                continue

            # Switchovers
            m = re_switchovers.match(line)
            if m:
                try:
                    cur["switchovers_since_reload"] = int(m.group("count"))
                except Exception:
                    pass
                continue

            # Reload reasons
            m = re_active_reason.match(line)
            if m:
                cur["active_node_reload_reason"] = m.group("reason").strip()
                continue

            m = re_standby_reason.match(line)
            if m:
                cur["standby_node_reload_reason"] = m.group("reason").strip()
                continue

        # Flush last record
        flush_current()

        if not records:
            raise ValueError("No 'Redundancy information for node ...' sections found.")

        # Convert to dataclass dicts
        result: List[Dict[str, Any]] = []
        for r in records:
            info = RedundancyReloadBootInfo(**r["reload_boot_info"])
            obj = ShowRedundancySummary(
                node=r["node"],
                node_role=r.get("node_role", ""),
                partner_node=r.get("partner_node", ""),
                partner_role=r.get("partner_role", ""),
                standby_node=r.get("standby_node", ""),
                standby_ready=bool(r.get("standby_ready", False)),
                standby_nsr_ready=bool(r.get("standby_nsr_ready", False)),
                switchovers_since_reload=int(r.get("switchovers_since_reload", 0)),
                active_node_reload_reason=r.get("active_node_reload_reason", ""),
                standby_node_reload_reason=r.get("standby_node_reload_reason", ""),
                reload_boot_info=info,
            )
            result.append(asdict(obj))

        # Write JSON via your helper
        output_file = write_json(
            command_name="show_redundancy",
            vendor="cisco",
            model="asr9910",
            json_data=result,
            json_file_path="precheck_jsons/"
        )
        }

        return output_file

    except Exception as e:
        return {"error": f"Error reading command output: {str(e)}"}

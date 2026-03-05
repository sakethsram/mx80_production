from typing import List, Dict, Any
import re
import sys
from dataclasses import dataclass, asdict, field
import logging

# Import models
from models.cisco.cisco_asr9910 import (
    ShowInstallActiveSummary,
    ISISAdjacencies,
    ShowRouteSummary,
    PimNeighbor,
    ShowFileSystemEntry,
    FPDEntry,
    ShowPlatform,
    ShowInterfacesDescription,
    ShowInterfacesBundleEther,
    BundleMember,
    ShowbfdSession,
    ShowBgpAllSummary,
    BgpProcessVersion,
    BgpNeighbor,
    ShowBgpVrfAllSummary,
    ShowIpv4VrfAllInterfaceBrief,
    ShowMplsLdpNeighbor,
    ShowPfmLocationAll,
    ShowWatchdogMemoryState,
    memoryInfo,
    ShowL2vpnXconnectBrief,
    ShowMsdpPeer,
    ShowRedundancy,
    ShowVersion,
    ShowMediaLocation,
    ShowProcessesCpu,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# show redundancy
# ---------------------------------------------------------------------------
def show_redundancy(content: str) -> List[Dict[str, Any]]:
    """
    Parse 'show redundancy' output.

    :param content: Raw command output string.
    :return: List of parsed dicts.
    """
    try:
        cmd = "show redundancy"

        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        active_match = re.search(r'Active node:\s+(\S+)', content)
        standby_match = re.search(r'Standby node:\s+(\S+)', content)
        state_match = re.search(r'Redundancy state:\s+(.+)', content)
        mode_match = re.search(r'Redundancy mode:\s+(.+)', content)
        last_sw_match = re.search(r'Last switchover:\s+(.+)', content)

        result = [asdict(ShowRedundancy(
            ActiveNode=active_match.group(1).strip() if active_match else "",
            StandbyNode=standby_match.group(1).strip() if standby_match else "",
            RedundancyState=state_match.group(1).strip() if state_match else "",
            RedundancyMode=mode_match.group(1).strip() if mode_match else "",
            LastSwitchover=last_sw_match.group(1).strip() if last_sw_match else ""
        ))]

        return result

    except Exception as e:
        return [{"error": f"Error parsing command output: {str(e)}"}]

# ---------------------------------------------------------------------------
# show bfd session
# ---------------------------------------------------------------------------
def show_bfd_session(content: str) -> List[Dict[str, Any]]:
    try:
        cmd = "show bfd session"
        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        result = []

        # Matches any interface name (BE1, Te0/0/0/1, Gi0/0/0/0, etc.)
        # Echo and Async columns can be "n/a" or "value(interval*mult)"
        bfd_pattern = re.compile(
            r'(?m)^(?P<interface>\S+)\s+'
            r'(?P<destAddr>\S+)\s+'
            r'(?P<echo>\S+)\s+'
            r'(?P<async_val>\S+)\s+'
            r'(?P<state>\S+)\s*\n\s+'
            r'(?P<hw>\S+)\s+(?P<npu>\S+)'
        )

        for match in bfd_pattern.finditer(content):
            # Skip the header line if accidentally matched
            if match.group("interface") in ("Interface", "---"):
                continue
            entry = ShowbfdSession(
                interface=match.group("interface"),
                destAddr=match.group("destAddr"),
                localDettime=[{
                    "echo": match.group("echo"),
                    "async": match.group("async_val")
                }],
                hw=match.group("hw"),
                npu=match.group("npu"),
                state=match.group("state")
            )
            result.append(asdict(entry))

        return result

    except Exception as e:
        return [{"error": f"Error parsing command output: {str(e)}"}]

# ---------------------------------------------------------------------------
# show processes cpu
# ---------------------------------------------------------------------------
def show_processes_cpu(content: str) -> List[Dict[str, Any]]:
    try:
        cmd = "show processes cpu"
        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        # XR format: "CPU utilization for one minute: 2%; five minutes: 2%; fifteen minutes: 2%"
        cpu_match = re.search(
            r'CPU utilization for one minute:\s*(\d+)%;\s*five minutes:\s*(\d+)%;\s*fifteen minutes:\s*(\d+)%',
            content
        )

        one_min  = cpu_match.group(1) if cpu_match else ""
        five_min = cpu_match.group(2) if cpu_match else ""
        fifteen  = cpu_match.group(3) if cpu_match else ""

        # XR per-process format: "PID    1Min    5Min    15Min Process"
        # e.g.  "1        0%      0%       0% init"
        process_pattern = re.compile(
            r'^\s*(\d+)\s+'
            r'(\d+)%\s+'
            r'(\d+)%\s+'
            r'(\d+)%\s+'
            r'(.+)$',
            re.MULTILINE
        )

        processes = []
        for m in process_pattern.finditer(content):
            processes.append(asdict(ShowProcessesCpu(
                PID=m.group(1),
                Runtime="",      # not present in XR format
                Invoked="",      # not present in XR format
                uSecs="",        # not present in XR format
                FiveSec="",      # not present in XR format
                OneMin=m.group(2),
                FiveMin=m.group(3),
                TTY="",          # not present in XR format
                Process=m.group(5).strip()
            )))

        result = [{
            "CPUUtilization": {
                "FiveSeconds": "",      # XR does not report 5-sec
                "OneMinute":   one_min,
                "FiveMinutes": five_min,
                "FifteenMinutes": fifteen
            },
            "Processes": processes
        }]

        return result

    except Exception as e:
        return [{"error": f"Error parsing command output: {str(e)}"}]
# ---------------------------------------------------------------------------
# show install active summary
# ---------------------------------------------------------------------------
def show_install_active_summary(content: str) -> List[Dict[str, Any]]:
    """
    Parse 'show install active summary' output.

    :param content: Raw command output string.
    :return: List of parsed dicts.
    """
    try:
        cmd = "show install active summary"

        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        label_match = re.search(r'^\s*Label\s*:\s*(.+?)\s*$', content, flags=re.MULTILINE)
        label = label_match.group(1).strip() if label_match else "Unknown"

        m_count = re.search(r'Active Packages:\s*(?P<count>\d+)', content)
        activePackages = int(m_count.group("count")) if m_count else 0

        package_lines = re.findall(
            r'^(?:[ \t]+)(?!Active)(?!Label)(.+\S)',
            content,
            re.MULTILINE
        )
        packages = [line.strip() for line in package_lines if line.strip()]

        result = [asdict(ShowInstallActiveSummary(
            Label=label,
            AcivePackages=activePackages,
            Packages=packages
        ))]

        return result

    except Exception as e:
        return [{"error": f"Error parsing command output: {str(e)}"}]


# ---------------------------------------------------------------------------
# show isis adjacency
# ---------------------------------------------------------------------------
def show_isis_adjacency(content: str) -> List[Dict[str, Any]]:
    """
    Parse 'show isis adjacency' output.

    :param content: Raw command output string.
    :return: List of parsed dicts.
    """
    try:
        cmd = "show isis adjacency"

        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        result, adjacencies = [], []

        match = re.search(
            r'^IS-IS\s\S+\sLevel-(?P<adjacencyLevel>\d+)',
            content,
            re.MULTILINE
        )
        adjacencyLevel = int(match.group("adjacencyLevel")) if match else 0

        for line in content.splitlines():
            line = line.strip()

            if (
                not line
                or line.startswith("System")
                or line.startswith("IS-IS")
                or line.startswith("Total")
                or line.startswith("BFD")
            ):
                continue

            cols = re.split(r'\s{1,}', line)
            if len(cols) < 9:
                continue

            entry = ISISAdjacencies(
                systemID=cols[0],
                interface=cols[1],
                SNPA=cols[2],
                state=cols[3],
                hold=cols[4],
                changed=cols[5],
                NSF=cols[6],
                ipv4BFD=cols[7],
                ipv6BFD=cols[8]
            )
            adjacencies.append(asdict(entry))

        total_match = re.search(
            r'^Total\s+adjacency\s+count:\s*(?P<adjacencyCount>\d+)',
            content,
            re.MULTILINE
        )
        adjacencyCount = int(total_match.group("adjacencyCount")) if total_match else 0

        result.append({
            "ISISColtAdjacencyLevel": adjacencyLevel,
            "adjacencies": adjacencies,
            "totalAdjacency": adjacencyCount
        })

        return result

    except Exception as e:
        return [{"error": f"Error parsing command output: {str(e)}"}]




# ---------------------------------------------------------------------------
# show route summary
# ---------------------------------------------------------------------------
def show_route_summary(content: str) -> List[Dict[str, Any]]:
    """
    Parse 'show route summary' output.

    :param content: Raw command output string.
    :return: List of parsed dicts.
    """
    try:
        cmd = "show route summary"

        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        result = []

        for line in content.splitlines():
            line = line.strip()

            if not line or line.startswith("Route"):
                continue

            cols = re.split(r'\s{2,}', line)
            if len(cols) < 5:
                continue

            entry = ShowRouteSummary(
                routeSource=cols[0],
                routes=cols[1],
                backup=cols[2],
                deleted=cols[3],
                memory=cols[4]
            )
            result.append(asdict(entry))

        return result

    except Exception as e:
        return [{"error": f"Error parsing command output: {str(e)}"}]


# ---------------------------------------------------------------------------
# show bgp all summary
# ---------------------------------------------------------------------------
def show_bgp_all_summary(content: str) -> List[Dict[str, Any]]:
    """
    Parse 'show bgp all summary' output.

    :param content: Raw command output string.
    :return: List of parsed dicts.
    """
    try:
        cmd = "show bgp all summary"

        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        router_id = re.search(r'router identifier\s+(\S+)', content)
        local_as = re.search(r'local AS number\s+(\d+)', content)
        table_state = re.search(r'BGP table state:\s+(\S+)', content)
        main_table_version = re.search(r'main routing table version\s+(\d+)', content)

        process_pattern = (
            r'(\S+)\s+'
            r'(\d+)\s+'
            r'(\d+)\s+'
            r'(\d+)\s+'
            r'(\d+)\s+'
            r'(\d+)\s+'
            r'(\d+)'
        )

        process_versions = [
            asdict(BgpProcessVersion(
                Process=m[0],
                RcvTblVer=m[1],
                BRibRib=m[2],
                LabelVer=m[3],
                ImportVer=m[4],
                SendTblVer=m[5],
                StandbyVer=m[6],
            ))
            for m in re.findall(process_pattern, content)
        ]

        neighbor_pattern = (
            r'(\d+\.\d+\.\d+\.\d+)\s+'
            r'(\d+)\s+'
            r'(\d+)\s+'
            r'(\d+)\s+'
            r'(\d+)\s+'
            r'(\d+)\s+'
            r'(\d+)\s+'
            r'(\d+)\s+'
            r'(\S+)\s+'
            r'(\d+)'
        )

        neighbors = [
            asdict(BgpNeighbor(
                Neighbor=m[0],
                Spk=m[1],
                RemoteAS=m[2],
                MsgRcvd=m[3],
                MsgSent=m[4],
                TblVer=m[5],
                InQ=m[6],
                OutQ=m[7],
                UpDown=m[8],
                StatePfxRcd=m[9],
            ))
            for m in re.findall(neighbor_pattern, content)
        ]

        result = [asdict(ShowBgpAllSummary(
            RouterID=router_id.group(1) if router_id else "",
            LocalAS=local_as.group(1) if local_as else "",
            TableState=table_state.group(1) if table_state else "",
            MainTableVersion=main_table_version.group(1) if main_table_version else "",
            ProcessVersions=process_versions,
            Neighbors=neighbors,
        ))]

        return result

    except Exception as e:
        return [{"error": f"Error parsing command output: {str(e)}"}]


# ---------------------------------------------------------------------------
# show bgp vrf all summary
# ---------------------------------------------------------------------------
def show_bgp_vrf_all_summary(content: str) -> List[Dict[str, Any]]:
    """
    Parse 'show bgp vrf all summary' output.

    :param content: Raw command output string.
    :return: List of parsed dicts.
    """
    try:
        cmd = "show bgp vrf all summary"

        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        vrf_match = re.search(r'VRF:\s+(\S+)', content)
        state_match = re.search(r'BGP VRF \S+, state:\s+(\S+)', content)
        rd_match = re.search(r'BGP Route Distinguisher:\s+(\S+)', content)
        vrf_id_match = re.search(r'VRF ID:\s+(\S+)', content)

        router_match = re.search(
            r'BGP router identifier\s+(\S+), local AS number\s+(\d+)',
            content
        )

        table_state_match = re.search(r'BGP table state:\s+(\S+)', content)
        main_tbl_match = re.search(r'BGP main routing table version\s+(\d+)', content)

        process_pattern = r'^(\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)'
        process_matches = re.findall(process_pattern, content, re.MULTILINE)

        process_list = [
            asdict(BgpProcessVersion(
                Process=p[0],
                RcvTblVer=p[1],
                BRibRib=p[2],
                LabelVer=p[3],
                ImportVer=p[4],
                SendTblVer=p[5],
                StandbyVer=p[6],
            ))
            for p in process_matches
        ]

        result = [asdict(ShowBgpVrfAllSummary(
            VRF=vrf_match.group(1) if vrf_match else "",
            VRFState=state_match.group(1) if state_match else "",
            RouteDistinguisher=rd_match.group(1) if rd_match else "",
            VRFID=vrf_id_match.group(1) if vrf_id_match else "",
            RouterID=router_match.group(1) if router_match else "",
            LocalAS=router_match.group(2) if router_match else "",
            TableState=table_state_match.group(1) if table_state_match else "",
            MainTableVersion=main_tbl_match.group(1) if main_tbl_match else "",
            ProcessVersions=process_list
        ))]

        return result

    except Exception as e:
        return [{"error": f"Error parsing command output: {str(e)}"}]


# ---------------------------------------------------------------------------
# show ipv4 vrf all interface brief
# ---------------------------------------------------------------------------
def show_ipv4_vrf_all_interface_brief(content: str) -> List[Dict[str, Any]]:
    """
    Parse 'show ipv4 vrf all interface brief' output.

    :param content: Raw command output string.
    :return: List of parsed dicts.
    """
    try:
        cmd = "show ipv4 vrf all interface brief"

        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        pattern = r'^(\S+)\s+(\S+)\s+(Up|Down|Shutdown|up|down)\s+(Up|Down|up|down)\s+(\S+)'
        matches = re.findall(pattern, content, re.MULTILINE)

        result = [
            asdict(ShowIpv4VrfAllInterfaceBrief(
                Interface=m[0],
                IPAddress=m[1],
                Status=m[2],
                Protocol=m[3],
                VrfName=m[4]
            ))
            for m in matches
        ]

        return result

    except Exception as e:
        return [{"error": f"Error parsing command output: {str(e)}"}]


# ---------------------------------------------------------------------------
# show mpls ldp neighbor
# ---------------------------------------------------------------------------
def show_mpls_ldp_neighbor(content: str) -> List[Dict[str, Any]]:
    """
    Parse 'show mpls ldp neighbor' output.

    :param content: Raw command output string.
    :return: List of parsed dicts.
    """
    try:
        cmd = "show mpls ldp neighbor"

        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        peer_match = re.search(r'Peer LDP Identifier:\s+(\S+)', content)
        tcp_match = re.search(r'TCP connection:\s+(\S+)\s*-\s*(\S+)', content)
        state_match = re.search(r'State:\s+(\S+)', content)
        uptime_match = re.search(r'Up time:\s+(\S+)', content)
        msgs_match = re.search(r'Msgs sent/rcvd:\s+(\d+)/(\d+)', content)

        discovery_matches = re.findall(r'(TenGigE\S+)', content)
        bound_ipv4 = re.findall(r'\b\d+\.\d+\.\d+\.\d+\b', content)

        result = [asdict(ShowMplsLdpNeighbor(
            PeerLdpIdentifier=peer_match.group(1) if peer_match else "",
            LocalTCP=tcp_match.group(1) if tcp_match else "",
            RemoteTCP=tcp_match.group(2) if tcp_match else "",
            SessionState=state_match.group(1) if state_match else "",
            Uptime=uptime_match.group(1) if uptime_match else "",
            MsgsSent=msgs_match.group(1) if msgs_match else "",
            MsgsReceived=msgs_match.group(2) if msgs_match else "",
            DiscoveryInterfaces=discovery_matches,
            BoundIPv4Addresses=bound_ipv4
        ))]

        return result

    except Exception as e:
        return [{"error": f"Error parsing command output: {str(e)}"}]


# ---------------------------------------------------------------------------
# show pim neighbor
# ---------------------------------------------------------------------------
def show_pim_neighbor(content: str) -> List[Dict[str, Any]]:
    """
    Parse 'show pim neighbor' output.

    :param content: Raw command output string.
    :return: List of parsed dicts.
    """
    try:
        cmd = "show pim neighbor"

        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        vrf_match = re.search(r'PIM neighbors in VRF\s+(\S+)', content, flags=re.IGNORECASE)
        vrf = vrf_match.group(1) if vrf_match else "default"

        result: List[Dict[str, Any]] = []

        for raw_line in content.splitlines():
            stripped = raw_line.strip()

            if not stripped:
                continue

            lower = stripped.lower()
            if (
                lower.startswith("pim neighbors in vrf")
                or lower.startswith("flag:")
                or lower.startswith("* indicates the neighbor")
                or lower.startswith("neighbor address")
                or lower.startswith("---")
            ):
                continue

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
                continue

            try:
                drpri = int(m.group("drpri"))
            except Exception:
                drpri = 0

            flags_raw = m.group("flags").strip()
            is_dr = "(dr)" in flags_raw.lower()

            letters: List[str] = []
            for token in flags_raw.replace("(", " ").replace(")", " ").split():
                t = token.strip()
                if t in ("B", "E", "P", "S") and t not in letters:
                    letters.append(t)

            entry = PimNeighbor(
                vrf=vrf,
                neighborAddress=m.group("addr"),
                isSelf=bool(m.group("self")),
                interface=m.group("intf"),
                uptime=m.group("uptime"),
                expires=m.group("expires"),
                drPriority=drpri,
                isDR=is_dr,
                flags=letters,
                flagsRaw=flags_raw
            )
            result.append(asdict(entry))

        return result

    except Exception as e:
        return [{"error": f"Error parsing command output: {str(e)}"}]


# ---------------------------------------------------------------------------
# show pfm location all
# ---------------------------------------------------------------------------
def show_pfm_location_all(content: str) -> List[Dict[str, Any]]:
    """
    Parse 'show pfm location all' output.

    :param content: Raw command output string.
    :return: List of parsed dicts.
    """
    try:
        cmd = "show pfm location all"

        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        node_blocks = re.split(r'node:\s+', content)
        results = []

        for block in node_blocks[1:]:
            node_name = block.splitlines()[0].strip()

            time_match = re.search(r'CURRENT TIME:\s+(.+)', block)
            total_match = re.search(r'PFM TOTAL:\s+(\d+)', block)
            ea_match = re.search(r'EMERGENCY/ALERT\(E/A\):\s+(\d+)', block)
            cr_match = re.search(r'CRITICAL\(CR\):\s+(\d+)', block)
            er_match = re.search(r'ERROR\(ER\):\s+(\d+)', block)
            raised_time_match = re.search(r'Raised Time\s*\n\s*(.+)', block)

            fault_pattern = (
                r'\|\s*(\d+)\s*\|'
                r'\s*([^|]+)\s*\|'
                r'\s*(E/A|CR|ER)\s*\|'
                r'\s*(\d+)\s*\|'
                r'\s*([^|]+)\s*\|'
                r'\s*(0x[0-9A-Fa-f]+)\s*\|'
            )
            fault_match = re.search(fault_pattern, block)

            results.append(asdict(ShowPfmLocationAll(
                Node=node_name,
                CurrentTime=time_match.group(1).strip() if time_match else "",
                PFMTotal=int(total_match.group(1)) if total_match else 0,
                EmergencyAlert=int(ea_match.group(1)) if ea_match else 0,
                Critical=int(cr_match.group(1)) if cr_match else 0,
                Error=int(er_match.group(1)) if er_match else 0,
                RaisedTime=raised_time_match.group(1).strip() if raised_time_match else "",
                SNumber=fault_match.group(1) if fault_match else "",
                FaultName=fault_match.group(2).strip() if fault_match else "",
                Severity=fault_match.group(3) if fault_match else "",
                ProcessID=fault_match.group(4) if fault_match else "",
                DevicePath=fault_match.group(5).strip() if fault_match else "",
                Handle=fault_match.group(6) if fault_match else ""
            )))

        return results

    except Exception as e:
        return [{"error": f"Error parsing command output: {str(e)}"}]


# ---------------------------------------------------------------------------
# show watchdog memory-state location all
# ---------------------------------------------------------------------------
def show_watchdog_memory_state(content: str) -> List[Dict[str, Any]]:
    """
    Parse 'show watchdog memory-state location all' output.

    :param content: Raw command output string.
    :return: List of parsed dicts.
    """
    try:
        cmd = "show watchdog memory-state location all"

        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        result = []

        pattern = re.compile(
            r"----\s*(?P<section>[^-]+?)\s*----\s*"
            r"Memory information:\s*"
            r"\s*Physical Memory\s*:\s*(?P<physical>[\d.]+)\s*MB\s*"
            r"\s*Free Memory\s*:\s*(?P<free>[\d.]+)\s*MB\s*"
            r"\s*Memory State\s*:\s*(?P<state>\w+)",
            re.MULTILINE
        )

        for match in pattern.finditer(content):
            mem_info = memoryInfo(
                physicalMem=match.group("physical"),
                freeMem=match.group("free"),
                memoryState=match.group("state")
            )
            node_state = ShowWatchdogMemoryState(
                nodeName=match.group("section").strip(),
                memoryInfo=[mem_info]
            )
            result.append(asdict(node_state))

        return result

    except Exception as e:
        return [{"error": f"Error parsing command output: {str(e)}"}]



# ---------------------------------------------------------------------------
# show interfaces description
# ---------------------------------------------------------------------------
def show_interfaces_description(content: str) -> List[Dict[str, Any]]:
    """
    Parse 'show interfaces description' output.

    :param content: Raw command output string.
    :return: List of parsed dicts.
    """
    try:
        cmd = "show interfaces description"

        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        pattern = r'^(\S+)\s+(up|down|admin-down)\s+(up|down)\s+(.+)$'
        matches = re.findall(pattern, content, re.MULTILINE)

        result = [
            asdict(ShowInterfacesDescription(
                Interface=match[0],
                Status=match[1],
                Protocol=match[2],
                Description=match[3].strip()
            ))
            for match in matches
        ]

        return result

    except Exception as e:
        return [{"error": f"Error parsing command output: {str(e)}"}]


# ---------------------------------------------------------------------------
# show filesystem
# ---------------------------------------------------------------------------
def show_filesystem(content: str) -> List[Dict[str, Any]]:
    """
    Parse 'show filesystem' output.

    :param content: Raw command output string.
    :return: List of parsed dicts.
    """
    try:
        cmd = "show filesystem"

        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        result: List[Dict[str, Any]] = []

        for raw_line in content.splitlines():
            line = raw_line.strip()

            if not line:
                continue

            lower = line.lower()
            if (
                lower.startswith("file systems:")
                or lower.startswith("size(b)")
                or lower.startswith("file systems")
                or lower.startswith("---")
            ):
                continue

            cols = re.split(r'\s{2,}', line)
            if len(cols) < 5:
                continue

            size_str, free_str, fs_type, flags, prefixes_raw = cols[:5]

            try:
                size_bytes = int(size_str.replace(",", ""))
                free_bytes = int(free_str.replace(",", ""))
            except ValueError:
                continue

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

        return result

    except Exception as e:
        return [{"error": f"Error parsing command output: {str(e)}"}]


# ---------------------------------------------------------------------------
# show interfaces (Bundle-Ether)
# ---------------------------------------------------------------------------
def show_interfaces(content: str) -> List[Dict[str, Any]]:
    """
    Parse 'show interfaces Bundle-Ether' output.

    :param content: Raw command output string.
    :return: List of parsed dicts.
    """
    try:
        cmd = "show interfaces Bundle-Ether"

        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        results = []
        bundle_blocks = re.split(r'(?=^Bundle-Ether)', content, flags=re.MULTILINE)

        for block in bundle_blocks:
            if not block.strip():
                continue

            members = []

            header_match = re.search(
                r'^(Bundle-Ether\S+) is (\w+), line protocol is (\w+)', block
            )
            mac_match = re.search(r'address is (\S+)', block)
            desc_match = re.search(r'Description:\s+(.+)', block)
            ip_match = re.search(r'Internet address is (\S+)', block)
            mtu_bw_match = re.search(r'MTU (\d+) bytes, BW (\d+) Kbit', block)
            flap_match = re.search(r'Last link flapped (.+)', block)
            arp_match = re.search(r'ARP timeout (\S+)', block)
            member_count_match = re.search(r'No\. of members in this bundle:\s+(\d+)', block)

            member_pattern = re.findall(
                r'^(HundredGigE\S+)\s+(Full-duplex|Half-duplex)\s+(\S+)\s+(\S+)',
                block,
                re.MULTILINE
            )

            for iface, duplex, speed, state in member_pattern:
                members.append(asdict(BundleMember(
                    Interface=iface,
                    Duplex=duplex,
                    Speed=speed,
                    State=state
                )))

            results.append(asdict(ShowInterfacesBundleEther(
                Interface=header_match.group(1) if header_match else "",
                AdminState=header_match.group(2) if header_match else "",
                LineProtocol=header_match.group(3) if header_match else "",
                MacAddress=mac_match.group(1) if mac_match else "",
                Description=desc_match.group(1).strip() if desc_match else "",
                InternetAddress=ip_match.group(1) if ip_match else "",
                MTU=mtu_bw_match.group(1) if mtu_bw_match else "",
                Bandwidth=mtu_bw_match.group(2) if mtu_bw_match else "",
                LastLinkFlapped=flap_match.group(1).strip() if flap_match else "",
                ArpTimeout=arp_match.group(1) if arp_match else "",
                MemberCount=int(member_count_match.group(1)) if member_count_match else 0,
                Members=members
            )))

        return results

    except Exception as e:
        return [{"error": f"Error parsing Bundle-Ether output: {str(e)}"}]


# ---------------------------------------------------------------------------
# show msdp peer
# ---------------------------------------------------------------------------
def show_msdp_peer(content: str) -> List[Dict[str, Any]]:
    """
    Parse 'show msdp peer' output.

    :param content: Raw command output string.
    :return: List of parsed dicts.
    """
    try:
        cmd = "show msdp peer"

        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        result = []

        # Split on peer blocks
        peer_blocks = re.split(r'(?=MSDP Peer\s+\S+)', content)

        for block in peer_blocks:
            if not block.strip():
                continue

            peer_match = re.search(r'MSDP Peer\s+(\S+),', block)
            as_match = re.search(r'AS\s+(\d+)', block)
            state_match = re.search(r'State:\s+(\S+)', block)
            uptime_match = re.search(r'Uptime/Reset-time:\s+(\S+)', block)
            sa_count_match = re.search(r'SA Count:\s+(\d+)', block)
            conn_match = re.search(r'Connection Source:\s+(\S+)', block)
            rpf_match = re.search(r'RPF Peer:\s+(\S+)', block)

            result.append(asdict(ShowMsdpPeer(
                PeerAddress=peer_match.group(1) if peer_match else "",
                AS=as_match.group(1) if as_match else "",
                State=state_match.group(1) if state_match else "",
                UptimeResetTime=uptime_match.group(1) if uptime_match else "",
                SACount=int(sa_count_match.group(1)) if sa_count_match else 0,
                ConnectionSource=conn_match.group(1) if conn_match else "",
                RPFPeer=rpf_match.group(1) if rpf_match else ""
            )))

        return result

    except Exception as e:
        return [{"error": f"Error parsing command output: {str(e)}"}]


# ---------------------------------------------------------------------------
# show l2vpn xconnect brief
# ---------------------------------------------------------------------------
def show_l2vpn_xconnect_brief(content: str) -> List[Dict[str, Any]]:
    """
    Parse 'show l2vpn xconnect brief' output.

    :param content: Raw command output string.
    :return: List of parsed dicts.
    """
    try:
        cmd = "show l2vpn xconnect brief"

        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        like_match = re.search(r'Like-to-Like\s+(\d+)\s+(\d+)\s+(\d+)', content)
        pw_match = re.search(r'PW-Ether\s+(\d+)\s+(\d+)\s+(\d+)', content)
        total_match = re.search(r'Total:\s+(\d+)\s+UP,\s+(\d+)\s+DOWN,\s+(\d+)\s+UNRESOLVED', content)

        result = [asdict(ShowL2vpnXconnectBrief(
            LikeToLike_UP=int(like_match.group(1)) if like_match else 0,
            LikeToLike_DOWN=int(like_match.group(2)) if like_match else 0,
            LikeToLike_UNR=int(like_match.group(3)) if like_match else 0,
            PwEther_UP=int(pw_match.group(1)) if pw_match else 0,
            PwEther_DOWN=int(pw_match.group(2)) if pw_match else 0,
            PwEther_UNR=int(pw_match.group(3)) if pw_match else 0,
            Total_UP=int(total_match.group(1)) if total_match else 0,
            Total_DOWN=int(total_match.group(2)) if total_match else 0,
            Total_UNRESOLVED=int(total_match.group(3)) if total_match else 0,
        ))]

        return result

    except Exception as e:
        return [{"error": f"Error parsing command output: {str(e)}"}]


# ---------------------------------------------------------------------------
# show hw-module fpd
# ---------------------------------------------------------------------------
def show_hw_module_fpd(content: str) -> List[Dict[str, Any]]:
    """
    Parse 'show hw-module fpd' output.

    :param content: Raw command output string.
    :return: List of parsed dicts.
    """
    try:
        cmd = "show hw-module fpd"

        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        auto_upgrade_pattern = re.search(
            r'^Auto-upgrade\s*:\s*(?P<AutoUpgrade>\S+)',
            content,
            re.MULTILINE
        )
        auto_upgrade = auto_upgrade_pattern.group("AutoUpgrade") if auto_upgrade_pattern else ""

        fpds = []

        for line in content.splitlines():
            line = line.strip()

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
            if len(cols) < 7:
                continue

            try:
                fpd_version = {
                    "Running": float(cols[5]),
                    "Programd": float(cols[6])
                }
            except (ValueError, IndexError):
                fpd_version = {"Running": 0.0, "Programd": 0.0}

            fpd = FPDEntry(
                Location=cols[0],
                CardType=cols[1],
                HWver=cols[2],
                FPDdevice=cols[3],
                ATRstatus=cols[4],
                FPDVersions=fpd_version
            )
            fpds.append(asdict(fpd))

        result = [{"AutoUpgrade": auto_upgrade, "FPDs": fpds}]

        return result

    except Exception as e:
        return [{"error": f"Error parsing command output: {str(e)}"}]


# ---------------------------------------------------------------------------
# show platform
# ---------------------------------------------------------------------------
def show_platform(content: str) -> List[Dict[str, Any]]:
    """
    Parse 'show platform' output.

    :param content: Raw command output string.
    :return: List of parsed dicts.
    """
    try:
        cmd = "show platform"

        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        pattern = r'^(\S+)\s+(\S+)\s+(.+?)\s+(NSHUT|SHUT|N/A)'
        matches = re.findall(pattern, content, re.MULTILINE)

        result = [
            asdict(ShowPlatform(
                Node=m[0],
                Type=m[1],
                State=m[2].strip(),
                ConfigState=m[3]
            ))
            for m in matches
        ]

        return result

    except Exception as e:
        return [{"error": f"Error parsing command output: {str(e)}"}]


# ---------------------------------------------------------------------------
# show media location (e.g. show media location 0/RSP1/CPU0)
# ---------------------------------------------------------------------------
def show_media_location(content: str) -> List[Dict[str, Any]]:
    """
    Parse 'show media location 0/RSP1/CPU0' output.

    :param content: Raw command output string.
    :return: List of parsed dicts.
    """
    try:
        cmd = "show media location 0/RSP1/CPU0"

        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        result = []

        # Each disk entry block
        disk_pattern = re.compile(
            r'(?P<disk>\S+disk\S*|harddisk\S*|compactflash\S*|usb\S*)'
            r'.*?Size\s*:\s*(?P<size>[\d.]+\s*\S+)'
            r'.*?Used\s*:\s*(?P<used>[\d.]+\s*\S+)'
            r'.*?Free\s*:\s*(?P<free>[\d.]+\s*\S+)',
            re.IGNORECASE | re.DOTALL
        )

        for m in disk_pattern.finditer(content):
            result.append(asdict(ShowMediaLocation(
                Disk=m.group("disk"),
                Size=m.group("size").strip(),
                Used=m.group("used").strip(),
                Free=m.group("free").strip()
            )))

        # Fallback: parse simple table rows
        if not result:
            row_pattern = re.compile(
                r'^(\S+)\s+([\d.]+\s*\w+)\s+([\d.]+\s*\w+)\s+([\d.]+\s*\w+)',
                re.MULTILINE
            )
            for m in row_pattern.finditer(content):
                result.append(asdict(ShowMediaLocation(
                    Disk=m.group(1),
                    Size=m.group(2),
                    Used=m.group(3),
                    Free=m.group(4)
                )))

        return result

    except Exception as e:
        return [{"error": f"Error parsing command output: {str(e)}"}]


# ---------------------------------------------------------------------------
# show version
# ---------------------------------------------------------------------------
def show_version(content: str) -> List[Dict[str, Any]]:
    """
    Parse 'show version' output.

    :param content: Raw command output string.
    :return: List of parsed dicts.
    """
    try:
        cmd = "show version"

        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        version_match = re.search(r'Version\s+:\s+(.+)', content)
        if not version_match:
            version_match = re.search(r'Cisco IOS XR Software.*?Version\s+(\S+)', content)

        uptime_match = re.search(r'uptime is\s+(.+)', content)
        image_match = re.search(r'image file is\s+"?(\S+)"?', content, re.IGNORECASE)
        processor_match = re.search(r'processor\s+with\s+(.+)', content, re.IGNORECASE)
        serial_match = re.search(r'[Ss]erial\s+[Nn]umber\s*:\s*(\S+)', content)
        chassis_match = re.search(r'[Cc]hassis\s+[Ss]N\s*:\s*(\S+)', content)
        rom_match = re.search(r'ROM:\s+(.+)', content)
        build_info_match = re.search(r'Built\s+:\s+(.+)', content)

        result = [asdict(ShowVersion(
            Version=version_match.group(1).strip() if version_match else "",
            Uptime=uptime_match.group(1).strip() if uptime_match else "",
            ImageFile=image_match.group(1).strip() if image_match else "",
            Processor=processor_match.group(1).strip() if processor_match else "",
            SerialNumber=serial_match.group(1).strip() if serial_match else (
                chassis_match.group(1).strip() if chassis_match else ""
            ),
            ROM=rom_match.group(1).strip() if rom_match else "",
            BuildInfo=build_info_match.group(1).strip() if build_info_match else ""
        ))]

        return result

    except Exception as e:
        return [{"error": f"Error parsing command output: {str(e)}"}]
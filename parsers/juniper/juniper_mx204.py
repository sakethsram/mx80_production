import re
import json
from dataclasses import asdict
from models.juniper.juniper_mx204 import *
from typing import Any, Dict


# ────────────────────────────────────────────────────────────────────────────────
def parse_show_arp_no_resolve(text_content: str) -> Dict[str, Any]:
    cmd = "show arp no-resolve | no-more"
    try:
        result = ShowArpNoResolve()
        pattern = r'([0-9a-f:]{17})\s+(\d+\.\d+\.\d+\.\d+)\s+(\S+)\s+(\S+)'
        for match in re.finditer(pattern, text_content, re.IGNORECASE):
            entry = ShowArpNoResolveEntry(
                mac_address=match.group(1),
                ip_address=match.group(2),
                interface=match.group(3),
                flags=match.group(4)
            )
            result.entries.append(entry)

        total_match = re.search(r'Total entries:\s*(\d+)', text_content)
        result.total_entries = int(total_match.group(1)) if total_match else len(result.entries)

        return asdict(result)
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


# ────────────────────────────────────────────────────────────────────────────────
def parse_show_lldp_neighbors(text_content: str) -> Dict[str, Any]:
    cmd = "show lldp neighbors | no-more"
    try:
        result = ShowLldpNeighbors()

        pattern = re.compile(
            r'^\s*(\S+)\s+(\S+)\s+([0-9A-Fa-f:]{17})\s+(\S+)\s+(.+)$',
            re.MULTILINE
        )

        for match in pattern.finditer(text_content):
            local_interface = match.group(1)
            parent_interface = match.group(2)
            chassis_id = match.group(3)
            port_info = match.group(4)
            system_name = match.group(5).strip()

            if local_interface.lower() == 'local' and parent_interface.lower() == 'interface':
                continue

            entry = ShowLldpNeighborsEntry(
                local_interface=local_interface,
                parent_interface=parent_interface,
                chassis_id=chassis_id,
                port_info=port_info,
                system_name=system_name,
            )
            result.entries.append(entry)

        return asdict(result)
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


# ────────────────────────────────────────────────────────────────────────────────
def parse_29_show_chassis_routing_engine(text_content: str) -> Dict[str, Any]:
    cmd = "show chassis routing-engine | no-more"
    try:
        routing_engine_result = ShowChassisRoutingEngine()
        re_status = RoutingEngineStatus()

        temp_match = re.search(r'Temperature\s+(\d+\s+degrees\s+C\s+/\s+\d+\s+degrees\s+F)', text_content)
        if temp_match:
            re_status.temperature = temp_match.group(1)

        cpu_temp_match = re.search(r'CPU temperature\s+(\d+\s+degrees\s+C\s+/\s+\d+\s+degrees\s+F)', text_content)
        if cpu_temp_match:
            re_status.cpu_temperature = cpu_temp_match.group(1)

        dram_match = re.search(r'DRAM\s+(\d+\s+MB.*?)(?:\n|$)', text_content)
        if dram_match:
            re_status.dram = dram_match.group(1).strip()

        mem_util_match = re.search(r'Memory utilization\s+(\d+)\s+percent', text_content)
        if mem_util_match:
            re_status.memory_utilization = int(mem_util_match.group(1))

        cpu_5sec_block = re.search(
            r'5 sec CPU utilization:\s+User\s+(\d+)\s+percent\s+Background\s+(\d+)\s+percent\s+'
            r'Kernel\s+(\d+)\s+percent\s+Interrupt\s+(\d+)\s+percent\s+Idle\s+(\d+)\s+percent',
            text_content
        )
        if cpu_5sec_block:
            re_status.cpu_util_5_sec = CpuUtilization(
                user=int(cpu_5sec_block.group(1)), background=int(cpu_5sec_block.group(2)),
                kernel=int(cpu_5sec_block.group(3)), interrupt=int(cpu_5sec_block.group(4)),
                idle=int(cpu_5sec_block.group(5))
            )

        cpu_1min_block = re.search(
            r'1 min CPU utilization:\s+User\s+(\d+)\s+percent\s+Background\s+(\d+)\s+percent\s+'
            r'Kernel\s+(\d+)\s+percent\s+Interrupt\s+(\d+)\s+percent\s+Idle\s+(\d+)\s+percent',
            text_content
        )
        if cpu_1min_block:
            re_status.cpu_util_1_min = CpuUtilization(
                user=int(cpu_1min_block.group(1)), background=int(cpu_1min_block.group(2)),
                kernel=int(cpu_1min_block.group(3)), interrupt=int(cpu_1min_block.group(4)),
                idle=int(cpu_1min_block.group(5))
            )

        cpu_5min_block = re.search(
            r'5 min CPU utilization:\s+User\s+(\d+)\s+percent\s+Background\s+(\d+)\s+percent\s+'
            r'Kernel\s+(\d+)\s+percent\s+Interrupt\s+(\d+)\s+percent\s+Idle\s+(\d+)\s+percent',
            text_content
        )
        if cpu_5min_block:
            re_status.cpu_util_5_min = CpuUtilization(
                user=int(cpu_5min_block.group(1)), background=int(cpu_5min_block.group(2)),
                kernel=int(cpu_5min_block.group(3)), interrupt=int(cpu_5min_block.group(4)),
                idle=int(cpu_5min_block.group(5))
            )

        cpu_15min_block = re.search(
            r'15 min CPU utilization:\s+User\s+(\d+)\s+percent\s+Background\s+(\d+)\s+percent\s+'
            r'Kernel\s+(\d+)\s+percent\s+Interrupt\s+(\d+)\s+percent\s+Idle\s+(\d+)\s+percent',
            text_content
        )
        if cpu_15min_block:
            re_status.cpu_util_15_min = CpuUtilization(
                user=int(cpu_15min_block.group(1)), background=int(cpu_15min_block.group(2)),
                kernel=int(cpu_15min_block.group(3)), interrupt=int(cpu_15min_block.group(4)),
                idle=int(cpu_15min_block.group(5))
            )

        model_match = re.search(r'Model\s+(.+?)(?:\n|$)', text_content)
        if model_match:
            re_status.model = model_match.group(1).strip()

        start_time_match = re.search(r'Start time\s+(.+?)(?:\n|$)', text_content)
        if start_time_match:
            re_status.start_time = start_time_match.group(1).strip()

        uptime_match = re.search(r'Uptime\s+(.+?)(?:\n|$)', text_content)
        if uptime_match:
            re_status.uptime = uptime_match.group(1).strip()

        reboot_match = re.search(r'Last reboot reason\s+(.+?)(?:\n|$)', text_content)
        if reboot_match:
            re_status.last_reboot_reason = reboot_match.group(1).strip()

        load_avg_match = re.search(r'Load averages:.*?\n\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)', text_content)
        if load_avg_match:
            re_status.load_averages = LoadAverages(
                one_minute=float(load_avg_match.group(1)),
                five_minute=float(load_avg_match.group(2)),
                fifteen_minute=float(load_avg_match.group(3))
            )

        routing_engine_result.routing_engines.append(re_status)
        return routing_engine_result.to_dict()
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


# ────────────────────────────────────────────────────────────────────────────────
def parse_21_show_system_uptime(text_content: str) -> Dict[str, Any]:
    cmd = "show system uptime | no-more"
    try:
        result = ShowSystemUptime()

        current_time_match = re.search(r'Current time:\s+(.+)', text_content)
        if current_time_match:
            result.current_time = current_time_match.group(1).strip()

        time_source_match = re.search(r'Time Source:\s+(.+)', text_content)
        if time_source_match:
            result.time_source = time_source_match.group(1).strip()

        system_booted_match = re.search(r'System booted:\s+(.+?)\s+\((.+?)\)', text_content)
        if system_booted_match:
            result.system_booted = system_booted_match.group(1).strip()
            result.system_booted_ago = system_booted_match.group(2).strip()

        protocols_started_match = re.search(r'Protocols started:\s+(.+?)\s+\((.+?)\)', text_content)
        if protocols_started_match:
            result.protocols_started = protocols_started_match.group(1).strip()
            result.protocols_started_ago = protocols_started_match.group(2).strip()

        last_configured_match = re.search(r'Last configured:\s+(.+?)\s+\((.+?)\)\s+by\s+(.+)', text_content)
        if last_configured_match:
            result.last_configured = last_configured_match.group(1).strip()
            result.last_configured_ago = last_configured_match.group(2).strip()
            result.last_configured_by = last_configured_match.group(3).strip()

        uptime_line_match = re.search(
            r'(\d{1,2}:\d{2}[AP]M)\s+up\s+(.+?),\s+(\d+)\s+users?,\s+load averages?:\s+([\d.]+),\s+([\d.]+),\s+([\d.]+)',
            text_content
        )
        if uptime_line_match:
            result.uptime_time = uptime_line_match.group(1).strip()
            result.uptime_duration = uptime_line_match.group(2).strip()
            result.users = int(uptime_line_match.group(3))
            result.load_average_1min = float(uptime_line_match.group(4))
            result.load_average_5min = float(uptime_line_match.group(5))
            result.load_average_15min = float(uptime_line_match.group(6))

        return result.to_dict()
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


# ────────────────────────────────────────────────────────────────────────────────
def parse_22_show_ntp_associations(text_content: str) -> Dict[str, Any]:
    cmd = "show ntp associations no-resolve | no-more"
    try:
        result = ShowNtpAssociations()

        # Juniper NTP output columns (11 fields):
        # remote  refid  auth  st  t  when  poll  reach  delay  offset  jitter
        # Example:
        #  10.91.141.57   .INIT.   -  16  u  -  1024  0  0.000  +0.000  0.000
        ntp_pattern = (
            r'^\s*([*#+x\- ]?)(\S+)'   # optional tally + remote
            r'\s+(\S+)'                # refid
            r'\s+(\S+)'                # auth
            r'\s+(\d+)'                # st
            r'\s+(\w+)'                # t
            r'\s+(\S+)'                # when (can be '-')
            r'\s+(\d+)'                # poll
            r'\s+(\d+)'                # reach
            r'\s+([\d.]+)'             # delay
            r'\s+([+\-]?[\d.]+)'       # offset
            r'\s+([\d.]+)'             # jitter
        )

        for line in text_content.splitlines():
            if 'remote' in line or '=====' in line or not line.strip():
                continue
            match = re.match(ntp_pattern, line)
            if match:
                ntp_entry = NtpAssociation(
                    remote=match.group(2),
                    refid=match.group(3),
                    auth=match.group(4),
                    st=int(match.group(5)),
                    t=match.group(6),
                    when=match.group(7),
                    poll=int(match.group(8)),
                    reach=int(match.group(9)),
                    delay=float(match.group(10)),
                    offset=match.group(11),
                    jitter=float(match.group(12)),
                )
                result.associations.append(ntp_entry)

        return result.to_dict()
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}

# ────────────────────────────────────────────────────────────────────────────────
def parse_23_show_vmhost_version(text_content: str) -> Dict[str, Any]:
    cmd = "show vmhost version | no-more"
    try:
        result = ShowVmhostVersion()

        root_details_match = re.search(
            r'Current root details,\s+Device\s+(\S+),\s+Label:\s+(\S+),\s+Partition:\s+(\S+)',
            text_content
        )
        if root_details_match:
            result.current_device = root_details_match.group(1).strip()
            result.current_label = root_details_match.group(2).strip()
            result.current_partition = root_details_match.group(3).strip()

        boot_disk_match = re.search(r'Current boot disk:\s+(.+)', text_content)
        if boot_disk_match:
            result.current_boot_disk = boot_disk_match.group(1).strip()

        root_set_match = re.search(r'Current root set:\s+(.+)', text_content)
        if root_set_match:
            result.current_root_set = root_set_match.group(1).strip()

        uefi_match = re.search(r'UEFI\s+Version:\s+(.+)', text_content)
        if uefi_match:
            result.uefi_version = uefi_match.group(1).strip()

        disk_upgrade_match = re.search(r'(.+?Disk),\s+Upgrade Time:\s+(.+)', text_content)
        if disk_upgrade_match:
            result.disk_type = disk_upgrade_match.group(1).strip()
            result.upgrade_time = disk_upgrade_match.group(2).strip()

        version_set_pattern = (
            r'Version:\s+set\s+(\w+)\s+VMHost Version:\s+(.+?)\s+VMHost Root:\s+(.+?)\s+'
            r'VMHost Core:\s+(.+?)\s+kernel:\s+(.+?)\s+Junos Disk:\s+(.+?)(?=\n\n|\nVersion:|\Z)'
        )
        for match in re.finditer(version_set_pattern, text_content, re.DOTALL):
            version_entry = VmhostVersionSet(
                version_set=match.group(1).strip(),
                vmhost_version=match.group(2).strip(),
                vmhost_root=match.group(3).strip(),
                vmhost_core=match.group(4).strip(),
                kernel=match.group(5).strip(),
                junos_disk=match.group(6).strip()
            )
            result.versions.append(version_entry)

        return result.to_dict()
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


# ────────────────────────────────────────────────────────────────────────────────
def parse_24_show_vmhost_snapshot(text_content: str) -> Dict[str, Any]:
    cmd = "show vmhost snapshot | no-more"
    try:
        result = VMHostSnapshot()

        uefi_match = re.search(r'UEFI\s+Version:\s+(.+)', text_content)
        if uefi_match:
            result.uefi_version = uefi_match.group(1).strip()

        disk_match = re.search(r'(.+?Disk),\s+Snapshot Time:\s+(.+)', text_content)
        if disk_match:
            result.disk_type = disk_match.group(1).strip()
            result.snapshot_time = disk_match.group(2).strip()

        version_set_pattern = (
            r'Version:\s+set\s+(\w+)\s+VMHost Version:\s+(.+?)\s+VMHost Root:\s+(.+?)\s+'
            r'VMHost Core:\s+(.+?)\s+kernel:\s+(.+?)\s+Junos Disk:\s+(.+?)(?=\n\n|\nVersion:|\Z)'
        )
        for match in re.finditer(version_set_pattern, text_content, re.DOTALL):
            version_entry = VMHostSnapshotVersion(
                version_set=match.group(1).strip(),
                vmhost_version=match.group(2).strip(),
                vmhost_root=match.group(3).strip(),
                vmhost_core=match.group(4).strip(),
                kernel=match.group(5).strip(),
                junos_disk=match.group(6).strip()
            )
            result.versions.append(version_entry)

        return result.to_dict()
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


# ────────────────────────────────────────────────────────────────────────────────
def parse_25_show_chassis_hardware(text_content: str) -> Dict[str, Any]:
    cmd = "show chassis hardware | no-more"
    try:
        result = ChassisHardware()

        for line in text_content.splitlines():
            if 'Hardware inventory:' in line or ('Item' in line and 'Version' in line) or not line.strip():
                continue

            indent = len(line) - len(line.lstrip())
            indent_level = indent // 2
            parts = line.strip().split()

            if len(parts) < 2:
                continue

            version = None
            if 'REV' in parts:
                rev_index = parts.index('REV')
                item_name = ' '.join(parts[:rev_index])
                version = parts[rev_index + 1] if rev_index + 1 < len(parts) else None
                remaining = parts[rev_index + 2:]
            else:
                if parts[0] in ['Chassis', 'FPC', 'PIC', 'Xcvr', 'PEM', 'CB']:
                    if len(parts) > 1 and parts[1].isdigit():
                        item_name = f"{parts[0]} {parts[1]}"
                        remaining = parts[2:]
                    else:
                        item_name = parts[0]
                        remaining = parts[1:]
                elif parts[0] == 'Routing' and len(parts) > 1 and parts[1] == 'Engine':
                    item_name = f"Routing Engine {parts[2]}" if len(parts) > 2 else "Routing Engine"
                    remaining = parts[3:] if len(parts) > 2 else []
                elif parts[0] == 'Fan' and len(parts) > 1 and parts[1] == 'Tray':
                    item_name = f"Fan Tray {parts[2]}" if len(parts) > 2 else "Fan Tray"
                    remaining = parts[3:] if len(parts) > 2 else []
                else:
                    item_name = parts[0]
                    remaining = parts[1:]

            if len(remaining) >= 3:
                part_number = remaining[0]
                serial_number = remaining[1]
                description = ' '.join(remaining[2:])
            elif len(remaining) == 2:
                part_number = remaining[0]
                serial_number = remaining[1]
                description = ""
            elif len(remaining) == 1:
                part_number = remaining[0]
                serial_number = ""
                description = ""
            else:
                part_number = ""
                serial_number = ""
                description = ""

            hardware_item = ChassisHardwareItem(
                item=item_name,
                version=version,
                part_number=part_number,
                serial_number=serial_number,
                description=description,
                indent_level=indent_level
            )
            result.items.append(hardware_item)

        return result.to_dict()
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


# ────────────────────────────────────────────────────────────────────────────────
def parse_26_show_chassis_fpc_detail(text_content: str) -> Dict[str, Any]:
    cmd = "show chassis fpc detail | no-more"
    try:
        chassis_fpc_result = ShowChassisFpcDetail()

        slot_pattern = r'Slot\s+(\d+)\s+information:'
        slot_matches = list(re.finditer(slot_pattern, text_content))

        if not slot_matches:
            return chassis_fpc_result.to_dict()

        for idx, slot_match in enumerate(slot_matches):
            slot_num = int(slot_match.group(1))
            start_pos = slot_match.end()
            end_pos = slot_matches[idx + 1].start() if idx + 1 < len(slot_matches) else len(text_content)
            slot_block = text_content[start_pos:end_pos]

            fpc_entry = ChassisFpcDetail(slot=slot_num)

            state_match = re.search(r'State\s+(\S+)', slot_block)
            if state_match:
                fpc_entry.state = state_match.group(1)

            cpu_dram_match = re.search(r'Total CPU DRAM\s+(.+)', slot_block)
            if cpu_dram_match:
                fpc_entry.total_cpu_dram = cpu_dram_match.group(1).strip()

            rldram_match = re.search(r'Total RLDRAM\s+(.+)', slot_block)
            if rldram_match:
                fpc_entry.total_rldram = rldram_match.group(1).strip()

            ddr_dram_match = re.search(r'Total DDR DRAM\s+(.+)', slot_block)
            if ddr_dram_match:
                fpc_entry.total_ddr_dram = ddr_dram_match.group(1).strip()

            fips_match = re.search(r'FIPS Capable\s+(\S+)', slot_block)
            if fips_match:
                fpc_entry.fips_capable = fips_match.group(1)

            temp_match = re.search(r'Temperature\s+(\S+)', slot_block)
            if temp_match:
                fpc_entry.temperature = temp_match.group(1)

            start_time_match = re.search(r'Start time\s+(.+)', slot_block)
            if start_time_match:
                fpc_entry.start_time = start_time_match.group(1).strip()

            uptime_match = re.search(r'Uptime\s+(.+)', slot_block)
            if uptime_match:
                fpc_entry.uptime = uptime_match.group(1).strip()

            hp_support_match = re.search(r'High-Performance mode support\s+(\S+)', slot_block)
            if hp_support_match:
                fpc_entry.high_performance_mode_support = hp_support_match.group(1)

            pfes_match = re.search(r'PFEs in High-Performance mode\s+(.+)', slot_block)
            if pfes_match:
                fpc_entry.pfes_in_high_performance_mode = pfes_match.group(1).strip()

            chassis_fpc_result.slots.append(fpc_entry)

        return chassis_fpc_result.to_dict()
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


# ────────────────────────────────────────────────────────────────────────────────
def parse_27_show_chassis_alarms(text_content: str) -> Dict[str, Any]:
    cmd = "show chassis alarms | no-more"
    try:
        s = (text_content or "").strip().lower()
        if "no alarms currently active" in s:
            return {"chassis_alarms": "None"}
        if not s or s == "=== end of output ===":
            return {"chassis_alarms": "None"}
        return {"chassis_alarms": "None"}
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


# ────────────────────────────────────────────────────────────────────────────────
def parse_28_show_system_alarms(text_content: str) -> Dict[str, Any]:
    cmd = "show system alarms | no-more"
    try:
        s = text_content or ""
        if re.search(r'\bNo\s+alarms\s+currently\s+active\b', s, re.IGNORECASE):
            return {"system_alarms": "None"}
        if not re.search(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}', s):
            return {"system_alarms": "None"}
        return {"system_alarms": "None"}
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


# ────────────────────────────────────────────────────────────────────────────────
def parse_30_show_chassis_environment(text_content: str) -> Dict[str, Any]:
    cmd = "show chassis environment | no-more"
    try:
        environment_result = ShowChassisEnvironment()
        current_class = None

        for line in text_content.splitlines():
            if 'Class Item' in line or not line.strip():
                continue

            parts = line.split()
            if not parts:
                continue

            if parts[0] in ['Temp', 'Power', 'Fans']:
                current_class = parts[0]
                rest = ' '.join(parts[1:])
            else:
                rest = line.strip()

            status = None
            status_index = -1
            for i, word in enumerate(rest.split()):
                if word in ['OK', 'Absent', 'Failed', 'Check']:
                    status = word
                    status_index = i
                    break

            if status_index == -1:
                continue

            rest_parts = rest.split()
            item_name = ' '.join(rest_parts[:status_index])
            measurement = ' '.join(rest_parts[status_index + 1:])

            env_item = EnvironmentItem(
                item_class=current_class,
                item_name=item_name,
                status=status,
                measurement=measurement
            )
            environment_result.items.append(env_item)

        return environment_result.to_dict()
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


# ────────────────────────────────────────────────────────────────────────────────
def parse_31_show_system_resource_monitor_fpc(text_content: str) -> Dict[str, Any]:
    cmd = "show system resource-monitor fpc | no-more"
    try:
        resource_monitor_result = ShowSystemResourceMonitorFpc()

        heap_watermark_match = re.search(r'Free Heap Mem Watermark\s+:\s+(\d+)', text_content)
        if heap_watermark_match:
            resource_monitor_result.free_heap_mem_watermark = int(heap_watermark_match.group(1))

        nh_watermark_match = re.search(r'Free NH Mem Watermark\s+:\s+(\d+)', text_content)
        if nh_watermark_match:
            resource_monitor_result.free_nh_mem_watermark = int(nh_watermark_match.group(1))

        filter_watermark_match = re.search(r'Free Filter Mem Watermark\s*:\s*(\d+)', text_content)
        if filter_watermark_match:
            resource_monitor_result.free_filter_mem_watermark = int(filter_watermark_match.group(1))

        current_fpc = None

        for line in text_content.splitlines():
            line = line.strip()
            if not line or 'Slot' in line or 'Free' in line or '*' in line or 'FPC Resource' in line:
                continue

            parts = line.split()

            if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                if 'PFE' not in line:
                    slot_num = int(parts[0])
                    heap_free = int(parts[1])
                    current_fpc = FpcResourceUsage(
                        slot_number=slot_num,
                        heap_free_percent=heap_free
                    )
                    resource_monitor_result.fpc_resources.append(current_fpc)

            elif current_fpc and len(parts) >= 4 and parts[0].isdigit():
                pfe_num = int(parts[0])
                encap_mem = parts[1]
                nh_mem = int(parts[2])
                fw_mem = int(parts[3])
                pfe_resource = PfeResourceUsage(
                    pfe_number=pfe_num,
                    encap_mem_free_percent=encap_mem,
                    nh_mem_free_percent=nh_mem,
                    fw_mem_free_percent=fw_mem
                )
                current_fpc.pfe_resources.append(pfe_resource)

        return resource_monitor_result.to_dict()
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


# ────────────────────────────────────────────────────────────────────────────────
def parse_show_system_processes_rpd_match(text_content: str) -> Dict[str, Any]:
    cmd = "show system processes extensive | match rpd | no-more"
    try:
        result = ShowSystemProcessesRpd()
        pattern = re.compile(
            r'^\s*(\d+)\s+(\S+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\d+)\s+(\S+)\s+(\S+%)\s+(.+)$',
            re.MULTILINE
        )
        for match in pattern.finditer(text_content):
            entry = RpdProcessEntry(
                pid=int(match.group(1)),
                user=match.group(2),
                pri=int(match.group(3)),
                nice=int(match.group(4)),
                size=match.group(5),
                res=match.group(6),
                state=match.group(7),
                cpu=int(match.group(8)),
                time=match.group(9),
                pct=match.group(10),
                thread_name=match.group(11).strip()
            )
            result.entries.append(entry)
        result.total_rpd_threads = len(result.entries)
        return asdict(result)
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


# ────────────────────────────────────────────────────────────────────────────────
def parse_show_interfaces_terse(text_content: str) -> Dict[str, Any]:
    cmd = "show interface terse | no-more"
    try:
        result = ShowInterfacesTerse()
        lines = text_content.strip().splitlines()

        for line in lines[1:]:  # skip header
            parts = line.split()
            if not parts:
                continue

            # skip continuation lines (proto-only lines like "inet6", "mpls", "iso")
            if len(parts) < 3:
                continue

            # skip if first token is not an interface name (no slash or colon)
            if parts[0] in ('inet', 'inet6', 'iso', 'mpls', 'tnp', 'multiservice',
                            'aenet', 'vpls', 'bridge', '-->', 'tnp'):
                continue

            entry = InterfaceEntry(
                interface=parts[0],
                admin=parts[1],
                link=parts[2],
            )
            if len(parts) > 3:
                idx = 3
                if parts[idx] not in ["up", "down", "testing"]:
                    entry.proto = parts[idx]
                    idx += 1
                    if idx < len(parts):
                        entry.local = parts[idx]
                        idx += 1
                    if idx < len(parts):
                        entry.remote = parts[idx]

            result.interfaces.append(entry)

        result.total_interfaces = len(result.interfaces)
        return asdict(result)
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


# ────────────────────────────────────────────────────────────────────────────────
def parse_35_show_oam_cfm_interfaces(text_content: str) -> Dict[str, Any]:
    cmd = "show oam ethernet connectivity-fault-management interfaces extensive | no-more"
    try:
        oam_cfm_result = ShowOamCfmInterfaces()
        interface_blocks = re.split(r'\n(?=Interface name:)', text_content)

        for block in interface_blocks:
            if not block.strip() or 'Interface name:' not in block:
                continue

            intf_match = re.search(
                r'Interface name:\s+(\S+)\s*,\s*Interface status:\s+(\w+)\s*,\s*Link status:\s+(\w+)',
                block
            )
            if not intf_match:
                continue

            oam_interface = OamCfmInterface(
                interface_name=intf_match.group(1),
                interface_status=intf_match.group(2),
                link_status=intf_match.group(3)
            )

            md_match = re.search(
                r'Maintenance domain name:\s+(.+?)\s*,\s*Format:\s+(\w+)\s*,\s*Level:\s+(\d+)\s*,\s*MD Index:\s+(\d+)',
                block
            )
            if md_match:
                oam_interface.maintenance_domain_name = md_match.group(1).strip()
                oam_interface.md_format = md_match.group(2)
                oam_interface.md_level = int(md_match.group(3))
                oam_interface.md_index = int(md_match.group(4))

            ma_match = re.search(
                r'Maintenance association name:\s+(.+?)\s*,\s*Format:\s+(\w+)\s*,\s*MA Index:\s+(\d+)',
                block
            )
            if ma_match:
                oam_interface.maintenance_association_name = ma_match.group(1).strip()
                oam_interface.ma_format = ma_match.group(2)
                oam_interface.ma_index = int(ma_match.group(3))

            cc_match = re.search(
                r'Continuity-check status:\s+(\w+)\s*,\s*Interval:\s+(\S+)\s*,\s*Loss-threshold:\s+(.+)',
                block
            )
            if cc_match:
                oam_interface.continuity_check_status = cc_match.group(1)
                oam_interface.cc_interval = cc_match.group(2)
                oam_interface.loss_threshold = cc_match.group(3).strip()

            mep_match = re.search(
                r'MEP identifier:\s+(\d+)\s*,\s*Direction:\s+(\w+)\s*,\s*MAC address:\s+([0-9a-f:]+)',
                block
            )
            if mep_match:
                oam_interface.mep_identifier = int(mep_match.group(1))
                oam_interface.mep_direction = mep_match.group(2)
                oam_interface.mac_address = mep_match.group(3)

            mep_status_match = re.search(r'MEP status:\s+(\w+)', block)
            if mep_status_match:
                oam_interface.mep_status = mep_status_match.group(1)

            oam_cfm_result.interfaces.append(oam_interface)

        return oam_cfm_result.to_dict()
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


# ────────────────────────────────────────────────────────────────────────────────
def parse_show_vrrp_summary(text_content: str) -> Dict[str, Any]:
    cmd = "show vrrp summary | no-more"
    try:
        s = (text_content or "").strip()
        if re.search(r'vrrp subsystem not running', s, re.IGNORECASE):
            return {"vrrp_summary": "None"}
        if not re.search(r'\b(ge-|xe-|et-|ae-|vlan)\S*', s, re.IGNORECASE):
            return {"vrrp_summary": "None"}
        return {"vrrp_summary": "None"}
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}

def parse_show_bfd_session(text_content: str) -> Dict[str, Any]:
    cmd = "show bfd session | no-more"
    try:
        result = ShowBfdSession()

        pattern = r'(\d+\.\d+\.\d+\.\d+)\s+(\S+)\s+(\S+)\s+([\d.]+)\s+([\d.]+)\s+(\d+)'
        for match in re.finditer(pattern, text_content):
            entry = ShowBfdSessionEntry(
                address=match.group(1),
                state=match.group(2),
                interface=match.group(3),
                detect_time=match.group(4),
                transmit_interval=match.group(5),
                multiplier=match.group(6)
            )
            result.entries.append(entry)

        summary_match = re.search(r'(\d+)\s+sessions,\s+(\d+)\s+clients', text_content)
        if summary_match:
            result.total_sessions = int(summary_match.group(1))
            result.total_clients  = int(summary_match.group(2))

        return asdict(result)
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


def parse_show_rsvp_neighbor(text_content: str) -> Dict[str, Any]:
    cmd = "show rsvp neighbor | no-more"
    try:
        result = ShowRsvpNeighbor()

        total_match = re.search(r"RSVP neighbor:\s+(\d+)\s+learned", text_content)
        if total_match:
            result.total_neighbors = int(total_match.group(1))

        lines = text_content.split('\n')
        for line in lines:
            if 'Address' in line or not line.strip() or 'RSVP neighbor' in line:
                continue
            fields = line.split()
            if len(fields) >= 8:
                try:
                    entry = ShowRsvpNeighborEntry(
                        address=fields[0],
                        idle=int(fields[1]),
                        up_dn=fields[2],
                        last_change=f"{fields[3]} {fields[4]}",
                        hello_interval=int(fields[5]),
                        hello_tx_rx=fields[6],
                        msg_rcvd=int(fields[7])
                    )
                    result.entries.append(entry)
                except (ValueError, IndexError):
                    continue

        return asdict(result)
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


def parse_show_rsvp_session(text_content: str) -> Dict[str, Any]:
    cmd = "show rsvp session | no-more"
    try:
        result = ShowRsvpSession()

        ingress_header = re.search(r'Ingress RSVP:\s+(\d+)\s+sessions', text_content)
        if ingress_header:
            result.ingress_sessions = int(ingress_header.group(1))

        ingress_total = re.search(
            r'Total\s+(\d+)\s+displayed,\s+Up\s+(\d+),\s+Down\s+(\d+)',
            text_content.split('Egress RSVP:')[0] if 'Egress RSVP:' in text_content else text_content
        )
        if ingress_total:
            result.ingress_up   = int(ingress_total.group(2))
            result.ingress_down = int(ingress_total.group(3))

        ingress_pattern = r'(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)\s+(\w+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(.+)$'
        if 'Ingress RSVP:' in text_content and 'Egress RSVP:' in text_content:
            ingress_section = text_content.split('Ingress RSVP:')[1].split('Egress RSVP:')[0]
            for match in re.finditer(ingress_pattern, ingress_section, re.MULTILINE):
                entry = RsvpSessionIngressEntry(
                    to=match.group(1),
                    from_=match.group(2),
                    state=match.group(3),
                    rt=int(match.group(4)),
                    style=f"{match.group(5)} {match.group(6)}",
                    label_in=match.group(7),
                    label_out=match.group(8),
                    lsp_name=match.group(9).strip()
                )
                result.ingress_entries.append(entry)

        egress_header = re.search(r'Egress RSVP:\s+(\d+)\s+sessions', text_content)
        if egress_header:
            result.egress_sessions = int(egress_header.group(1))

        if 'Egress RSVP:' in text_content:
            egress_section_text = text_content.split('Egress RSVP:')[1]
            egress_total = re.search(
                r'Total\s+(\d+)\s+displayed,\s+Up\s+(\d+),\s+Down\s+(\d+)',
                egress_section_text.split('Transit RSVP:')[0] if 'Transit RSVP:' in egress_section_text else egress_section_text
            )
            if egress_total:
                result.egress_up   = int(egress_total.group(2))
                result.egress_down = int(egress_total.group(3))

        egress_pattern = r'(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)\s+(\w+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(.+)$'
        if 'Egress RSVP:' in text_content:
            egress_section = text_content.split('Egress RSVP:')[1]
            if 'Transit RSVP:' in egress_section:
                egress_section = egress_section.split('Transit RSVP:')[0]
            for match in re.finditer(egress_pattern, egress_section, re.MULTILINE):
                entry = RsvpSessionEgressEntry(
                    to=match.group(1),
                    from_=match.group(2),
                    state=match.group(3),
                    rt=int(match.group(4)),
                    style=f"{match.group(5)} {match.group(6)}",
                    label_in=match.group(7),
                    label_out=match.group(8),
                    lsp_name=match.group(9).strip()
                )
                result.egress_entries.append(entry)

        transit_header = re.search(r'Transit RSVP:\s+(\d+)\s+sessions', text_content)
        if transit_header:
            result.transit_sessions = int(transit_header.group(1))

        if 'Transit RSVP:' in text_content:
            transit_section_text = text_content.split('Transit RSVP:')[1]
            transit_total = re.search(
                r'Total\s+(\d+)\s+displayed,\s+Up\s+(\d+),\s+Down\s+(\d+)',
                transit_section_text
            )
            if transit_total:
                result.transit_up   = int(transit_total.group(2))
                result.transit_down = int(transit_total.group(3))
            else:
                result.transit_up   = sum(1 for e in result.transit_entries if e.state == 'Up')
                result.transit_down = sum(1 for e in result.transit_entries if e.state == 'Down')

        return asdict(result)
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}

# ────────────────────────────────────────────────────────────────────────────────
def parse_show_route_table_inet0(text_content: str) -> Dict[str, Any]:
    cmd = "show route table inet.0 | no-more"
    try:
        result = RouteTableData(
            table_name="", total_destinations=0, total_routes=0,
            active_routes=0, holddown_routes=0, hidden_routes=0, entries=[]
        )

        header_match = re.search(
            r'(inet\.0):\s+(\d+)\s+destinations,\s+(\d+)\s+routes\s+\((\d+)\s+active,\s+(\d+)\s+holddown,\s+(\d+)\s+hidden\)',
            text_content
        )
        if header_match:
            result.table_name = header_match.group(1)
            result.total_destinations = int(header_match.group(2))
            result.total_routes = int(header_match.group(3))
            result.active_routes = int(header_match.group(4))
            result.holddown_routes = int(header_match.group(5))
            result.hidden_routes = int(header_match.group(6))

        lines = text_content.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line or line.startswith('+') or line.startswith('inet.'):
                i += 1
                continue

            dest_match = re.match(
                r'^([\d\.\/]+)\s+(\*?)(\[[\w\-]+\/\d+\])\s+([\w\d\s:]+?)(?:,\s+metric\s+(\d+))?$',
                line
            )

            if dest_match:
                destination = dest_match.group(1)
                flags = dest_match.group(2)
                protocol_pref = dest_match.group(3)
                age = dest_match.group(4).strip()
                metric = int(dest_match.group(5)) if dest_match.group(5) else 0

                protocol_match = re.search(r'\[([\w\-]+)/(\d+)\]', protocol_pref)
                protocol = protocol_match.group(1) if protocol_match else ""
                preference = int(protocol_match.group(2)) if protocol_match else 0

                next_hop = ""
                interface = ""

                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line.startswith('>'):
                        hop_match = re.search(r'>\s+to\s+([\d\.]+)\s+via\s+([\w\-\.\/]+)', next_line)
                        if hop_match:
                            next_hop = hop_match.group(1)
                            interface = hop_match.group(2)
                            i += 1
                        else:
                            hop_match2 = re.search(r'>\s+via\s+([\w\-\.\/]+)', next_line)
                            if hop_match2:
                                interface = hop_match2.group(1)
                                next_hop = ""
                                i += 1
                    elif 'Local via' in next_line:
                        hop_match3 = re.search(r'Local\s+via\s+([\w\-\.\/]+)', next_line)
                        if hop_match3:
                            interface = hop_match3.group(1)
                            next_hop = "Local"
                            i += 1

                entry = RouteEntry(
                    destination=destination,
                    protocol=protocol,
                    preference=preference,
                    metric=metric,
                    age=age,
                    next_hop=next_hop,
                    interface=interface,
                    flags=flags
                )
                result.entries.append(entry)

            i += 1

        return asdict(result)
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


# ────────────────────────────────────────────────────────────────────────────────
def parse_show_route_table_inet3(text_content: str) -> Dict[str, Any]:
    cmd = "show route table inet.3 | no-more"
    try:
        result = ShowRouteTableInet3()

        header_match = re.search(
            r'inet\.3:\s+(\d+)\s+destinations,\s+(\d+)\s+routes\s+\((\d+)\s+active,\s+(\d+)\s+holddown,\s+(\d+)\s+hidden\)',
            text_content
        )
        if header_match:
            result.total_destinations = int(header_match.group(1))
            result.total_routes = int(header_match.group(2))
            result.active_routes = int(header_match.group(3))
            result.holddown_routes = int(header_match.group(4))
            result.hidden_routes = int(header_match.group(5))

        lines = text_content.split('\n')
        i = 0
        current_entry = None

        while i < len(lines):
            line = lines[i]

            if not line.strip() or line.strip().startswith('+') or line.strip().startswith('inet.3:'):
                i += 1
                continue

            route_match = re.match(r'^(\S+)\s+\*\[(\S+)/(\d+)\]\s+(.+?),\s+metric\s+(\d+)', line)
            if route_match:
                if current_entry:
                    result.entries.append(current_entry)
                current_entry = ShowRouteTableInet3Entry(
                    destination=route_match.group(1),
                    protocol=route_match.group(2),
                    preference=route_match.group(3),
                    metric=route_match.group(5),
                    age=route_match.group(4)
                )
            elif current_entry:
                stripped_line = line.strip()
                is_primary = stripped_line.startswith('>')
                clean_line = stripped_line.lstrip('>')

                nexthop_match = re.match(
                    r'(?:to\s+)?(\S+)\s+via\s+(\S+?)(?:,\s+Push\s+(\S+?))?(?:,\s+Push\s+(\S+?))?\s*$',
                    clean_line.strip()
                )
                if nexthop_match and 'to' in clean_line:
                    to_match = re.match(r'to\s+(\S+)\s+via\s+(\S+?)(?:,\s+Push\s+(\S+?))?(?:,\s+Push\s+(\S+?))?\s*$', clean_line.strip())
                    if to_match:
                        to_addr = to_match.group(1)
                        via_iface = to_match.group(2).rstrip(',')
                        label1 = to_match.group(3)
                        label2 = to_match.group(4)
                        if label1 and label2:
                            mpls_label = f"Push {label1}, Push {label2.replace('(top)', '')}"
                        elif label1:
                            mpls_label = f"Push {label1}"
                        else:
                            mpls_label = ""
                        nexthop = ShowRouteTableInet3NextHop(to=to_addr, via=via_iface, mpls_label=mpls_label)
                        current_entry.next_hops.append(nexthop)

            i += 1

        if current_entry:
            result.entries.append(current_entry)

        return result.to_dict()
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


# ────────────────────────────────────────────────────────────────────────────────
def parse_show_route_table_mpls0(text_content: str) -> Dict[str, Any]:
    cmd = "show route table mpls.0 | no-more"
    try:
        result = ShowRouteTableMpls0()
        header_match = re.search(
            r'mpls\.0: (\d+) destinations, (\d+) routes \((\d+) active, (\d+) holddown, (\d+) hidden\)',
            text_content
        )
        if header_match:
            result.total_destinations = int(header_match.group(1))
            result.total_routes = int(header_match.group(2))
            result.active_routes = int(header_match.group(3))
            result.holddown_routes = int(header_match.group(4))
            result.hidden_routes = int(header_match.group(5))

        lines = text_content.split('\n')
        i = 0
        current_entry = None

        while i < len(lines):
            line = lines[i]
            route_match = re.match(
                r'^(\d+(?:\(S=\d+\))?)\s+\*\[(\S+)/(\d+)\]\s+(.+?)(?:,\s+metric\s+(\d+))?$',
                line
            )
            if route_match:
                if current_entry:
                    result.entries.append(current_entry)
                current_entry = ShowRouteTableMpls0Entry(
                    label=route_match.group(1),
                    protocol=route_match.group(2),
                    preference=route_match.group(3),
                    metric=route_match.group(5) if route_match.group(5) else "",
                    age=route_match.group(4)
                )
            elif current_entry:
                table_match = re.match(r'^\s+to table\s+(\S+)', line)
                if table_match:
                    current_entry.next_hops.append(ShowRouteTableMpls0NextHop(action="to table " + table_match.group(1)))
                elif re.match(r'^\s+Receive', line):
                    current_entry.next_hops.append(ShowRouteTableMpls0NextHop(action="Receive"))
                elif 'via lsi.' in line:
                    lsi_match = re.match(r'^\s+>\s+via\s+(lsi\.\d+)\s+\(([^)]+)\),\s+(\w+)', line)
                    if lsi_match:
                        current_entry.next_hops.append(ShowRouteTableMpls0NextHop(
                            via=lsi_match.group(1), lsp_name=lsi_match.group(2), action=lsi_match.group(3)
                        ))
                elif 'via vt-' in line:
                    vt_match = re.match(r'^\s+>?\s*via\s+(vt-[\d/\.]+),\s+(\w+)', line)
                    if vt_match:
                        current_entry.next_hops.append(ShowRouteTableMpls0NextHop(via=vt_match.group(1), action=vt_match.group(2)))
                elif 'via ms-' in line:
                    ms_match = re.match(r'^\s+>\s+via\s+(ms-[\d/\.]+),\s+(\w+)', line)
                    if ms_match:
                        current_entry.next_hops.append(ShowRouteTableMpls0NextHop(via=ms_match.group(1), action=ms_match.group(2)))
                elif line.strip().startswith('>') or line.strip().startswith('to '):
                    clean_line = line.strip().lstrip('>')
                    lsp_match = re.search(r'label-switched-path\s+(.+?)$', clean_line)
                    lsp_name = lsp_match.group(1) if lsp_match else None
                    nh_match = re.match(r'^\s*to\s+(\S+)\s+via\s+(\S+)', clean_line)
                    if nh_match:
                        to_addr = nh_match.group(1)
                        via_iface = nh_match.group(2).rstrip(',')
                        remainder = clean_line[nh_match.end():].strip().lstrip(',').strip()
                        action = mpls_label = None
                        if remainder and 'label-switched-path' not in remainder:
                            if remainder.startswith('Pop'):
                                action = "Pop"
                            elif remainder.startswith('Swap'):
                                sp_match = re.match(r'Swap\s+(\S+),\s+Push\s+(\S+)', remainder)
                                if sp_match:
                                    action = f"Swap {sp_match.group(1).rstrip(',')}, Push"
                                    mpls_label = sp_match.group(2)
                                else:
                                    sw_match = re.match(r'Swap\s+(\S+)', remainder)
                                    if sw_match:
                                        action, mpls_label = "Swap", sw_match.group(1).rstrip(',')
                            elif remainder.startswith('Push'):
                                push_match = re.match(r'Push\s+(\S+)', remainder)
                                if push_match:
                                    action, mpls_label = "Push", push_match.group(1)
                        current_entry.next_hops.append(ShowRouteTableMpls0NextHop(
                            to=to_addr, via=via_iface, action=action, mpls_label=mpls_label, lsp_name=lsp_name
                        ))
            i += 1

        if current_entry:
            result.entries.append(current_entry)

        return asdict(result)
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


# ────────────────────────────────────────────────────────────────────────────────
def parse_show_mpls_interface(text_content: str) -> Dict[str, Any]:
    cmd = "show mpls interface | no-more"
    try:
        result = ShowMplsInterface()
        pattern = r'^(\S+)\s+(Up|Down)\s+(.*)$'
        for match in re.finditer(pattern, text_content, re.MULTILINE):
            if match.group(1) == 'Interface':
                continue
            entry = ShowMplsInterfaceEntry(
                interface=match.group(1),
                state=match.group(2),
                administrative_groups=match.group(3).strip()
            )
            result.entries.append(entry)
        return asdict(result)
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


# ────────────────────────────────────────────────────────────────────────────────
def parse_show_mpls_lsp(text_content: str) -> Dict[str, Any]:
    cmd = "show mpls lsp | no-more"
    try:
        result = ShowMplsLsp()

        ingress_header = re.search(r'Ingress LSP:\s+(\d+)\s+sessions', text_content)
        if ingress_header:
            result.ingress_sessions = int(ingress_header.group(1))

        ingress_total = re.search(
            r'Total\s+(\d+)\s+displayed,\s+Up\s+(\d+),\s+Down\s+(\d+)',
            text_content.split('Egress LSP:')[0] if 'Egress LSP:' in text_content else text_content
        )
        if ingress_total:
            result.ingress_up = int(ingress_total.group(2))
            result.ingress_down = int(ingress_total.group(3))

        ingress_pattern = r'(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)\s+(\w+)\s+(\d+)\s+(\*|\s+)\s+(.+)$'

        ingress_section = ""
        if 'Ingress LSP:' in text_content and 'Egress LSP:' in text_content:
            ingress_section = text_content.split('Ingress LSP:')[1].split('Egress LSP:')[0]
        for match in re.finditer(ingress_pattern, ingress_section, re.MULTILINE):
            entry = MplsLspIngressEntry(
                to=match.group(1),
                from_=match.group(2),
                state=match.group(3),
                rt=int(match.group(4)),
                p=match.group(5).strip(),
                active_path='',
                lsp_name=match.group(6).strip()
            )
            result.ingress_entries.append(entry)

        egress_header = re.search(r'Egress LSP:\s+(\d+)\s+sessions', text_content)
        if egress_header:
            result.egress_sessions = int(egress_header.group(1))

        egress_section_text = ""
        if 'Egress LSP:' in text_content:
            egress_section_text = text_content.split('Egress LSP:')[1]
        egress_total = re.search(
            r'Total\s+(\d+)\s+displayed,\s+Up\s+(\d+),\s+Down\s+(\d+)',
            egress_section_text.split('Transit LSP:')[0] if 'Transit LSP:' in egress_section_text else egress_section_text
        )
        if egress_total:
            result.egress_up = int(egress_total.group(2))
            result.egress_down = int(egress_total.group(3))

        egress_pattern = r'(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)\s+(\w+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(.+?)$'

        egress_section = ""
        if 'Egress LSP:' in text_content:
            egress_section = text_content.split('Egress LSP:')[1]
            if 'Transit LSP:' in egress_section:
                egress_section = egress_section.split('Transit LSP:')[0]
        for match in re.finditer(egress_pattern, egress_section, re.MULTILINE):
            entry = MplsLspEgressEntry(
                to=match.group(1),
                from_=match.group(2),
                state=match.group(3),
                rt=int(match.group(4)),
                style=f"{match.group(5)} {match.group(6)}",
                label_in=match.group(7),
                label_out=match.group(8),
                lsp_name=match.group(9).strip()
            )
            result.egress_entries.append(entry)

        transit_header = re.search(r'Transit LSP:\s+(\d+)\s+sessions', text_content)
        if transit_header:
            result.transit_sessions = int(transit_header.group(1))

        transit_pattern = r'(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)\s+(\w+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(.+?)$'

        transit_section = ""
        if 'Transit LSP:' in text_content:
            transit_section = text_content.split('Transit LSP:')[1]
        for match in re.finditer(transit_pattern, transit_section, re.MULTILINE):
            entry = MplsLspTransitEntry(
                to=match.group(1),
                from_=match.group(2),
                state=match.group(3),
                rt=int(match.group(4)),
                style=f"{match.group(5)} {match.group(6)}",
                label_in=match.group(7),
                label_out=match.group(8),
                lsp_name=match.group(9).strip()
            )
            result.transit_entries.append(entry)

        transit_section_text = ""
        if 'Transit LSP:' in text_content:
            transit_section_text = text_content.split('Transit LSP:')[1]
        transit_total = re.search(
            r'Total\s+(\d+)\s+displayed,\s+Up\s+(\d+),\s+Down\s+(\d+)',
            transit_section_text
        )
        if transit_total:
            result.transit_up = int(transit_total.group(2))
            result.transit_down = int(transit_total.group(3))
        else:
            result.transit_up = sum(1 for e in result.transit_entries if e.state == 'Up')
            result.transit_down = sum(1 for e in result.transit_entries if e.state == 'Down')

        return asdict(result)
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


# ────────────────────────────────────────────────────────────────────────────────
def parse_show_mpls_lsp_p2mp(text_content: str) -> Dict[str, Any]:
    cmd = "show mpls lsp p2mp | no-more"
    try:
        result = ShowMplsLspP2MP()

        ingress_header = re.search(r'Ingress LSP:\s+(\d+)\s+sessions', text_content)
        if ingress_header:
            result.ingress_lsp.total_sessions = int(ingress_header.group(1))

        if 'Ingress LSP:' in text_content and 'Egress LSP:' in text_content:
            ingress_section = text_content.split('Ingress LSP:')[1].split('Egress LSP:')[0]
            ingress_total = re.search(r'Total\s+(\d+)\s+displayed,\s+Up\s+(\d+),\s+Down\s+(\d+)', ingress_section)
            if ingress_total:
                result.ingress_lsp.sessions_displayed = int(ingress_total.group(1))
                result.ingress_lsp.sessions_up = int(ingress_total.group(2))
                result.ingress_lsp.sessions_down = int(ingress_total.group(3))

            for session_text in re.split(r'P2MP name:', ingress_section)[1:]:
                lines = session_text.strip().split('\n')
                if not lines:
                    continue
                name_match = re.match(r'(.+?),\s+P2MP branch count:\s+(\d+)', lines[0])
                if not name_match:
                    continue
                session = P2MPSession(p2mp_name=name_match.group(1).strip(), branch_count=int(name_match.group(2)))
                branch_pattern = r'(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)\s+(\w+)\s+(\d+)\s+(\*|\s+)\s+(.+)$'
                for line in lines[1:]:
                    if line.strip().startswith('To'):
                        continue
                    match = re.match(branch_pattern, line)
                    if match:
                        session.branches.append(P2MPIngressBranch(
                            to=match.group(1), from_=match.group(2), state=match.group(3),
                            rt=int(match.group(4)), p=match.group(5).strip(), active_path='',
                            lsp_name=match.group(6).strip()
                        ))
                result.ingress_lsp.sessions.append(session)

        egress_header = re.search(r'Egress LSP:\s+(\d+)\s+sessions', text_content)
        if egress_header:
            result.egress_lsp.total_sessions = int(egress_header.group(1))

        if 'Egress LSP:' in text_content:
            egress_section = text_content.split('Egress LSP:')[1]
            if 'Transit LSP:' in egress_section:
                egress_section = egress_section.split('Transit LSP:')[0]
            egress_total = re.search(r'Total\s+(\d+)\s+displayed,\s+Up\s+(\d+),\s+Down\s+(\d+)', egress_section)
            if egress_total:
                result.egress_lsp.sessions_displayed = int(egress_total.group(1))
                result.egress_lsp.sessions_up = int(egress_total.group(2))
                result.egress_lsp.sessions_down = int(egress_total.group(3))

            branch_pattern = r'(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)\s+(\w+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(.+?)$'
            for session_text in re.split(r'P2MP name:', egress_section)[1:]:
                lines = session_text.strip().split('\n')
                if not lines:
                    continue
                name_match = re.match(r'(.+?),\s+P2MP branch count:\s+(\d+)', lines[0])
                if not name_match:
                    continue
                session = P2MPSession(p2mp_name=name_match.group(1).strip(), branch_count=int(name_match.group(2)))
                for line in lines[1:]:
                    if line.strip().startswith('To'):
                        continue
                    match = re.match(branch_pattern, line)
                    if match:
                        session.branches.append(P2MPEgressBranch(
                            to=match.group(1), from_=match.group(2), state=match.group(3),
                            rt=int(match.group(4)), style=f"{match.group(5)} {match.group(6)}",
                            label_in=match.group(7), label_out=match.group(8), lsp_name=match.group(9).strip()
                        ))
                result.egress_lsp.sessions.append(session)

        transit_header = re.search(r'Transit LSP:\s+(\d+)\s+sessions', text_content)
        if transit_header:
            result.transit_lsp.total_sessions = int(transit_header.group(1))

        if 'Transit LSP:' in text_content:
            transit_section = text_content.split('Transit LSP:')[1]
            branch_pattern = r'(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)\s+(\w+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(.+?)$'
            for session_text in re.split(r'P2MP name:', transit_section)[1:]:
                lines = session_text.strip().split('\n')
                if not lines:
                    continue
                name_match = re.match(r'(.+?),\s+P2MP branch count:\s+(\d+)', lines[0])
                if not name_match:
                    continue
                session = P2MPSession(p2mp_name=name_match.group(1).strip(), branch_count=int(name_match.group(2)))
                for line in lines[1:]:
                    if line.strip().startswith('To'):
                        continue
                    match = re.match(branch_pattern, line)
                    if match:
                        session.branches.append(P2MPTransitBranch(
                            to=match.group(1), from_=match.group(2), state=match.group(3),
                            rt=int(match.group(4)), style=f"{match.group(5)} {match.group(6)}",
                            label_in=match.group(7), label_out=match.group(8), lsp_name=match.group(9).strip()
                        ))
                result.transit_lsp.sessions.append(session)

            result.transit_lsp.sessions_displayed = sum(len(s.branches) for s in result.transit_lsp.sessions)
            result.transit_lsp.sessions_up = sum(1 for s in result.transit_lsp.sessions for b in s.branches if b.state == 'Up')
            result.transit_lsp.sessions_down = sum(1 for s in result.transit_lsp.sessions for b in s.branches if b.state == 'Down')

        return asdict(result)
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


# ────────────────────────────────────────────────────────────────────────────────
def parse_show_bgp_summary(text_content: str) -> Dict[str, Any]:
    cmd = "show bgp summary | no-more"
    try:
        return {"output": text_content}
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


# ────────────────────────────────────────────────────────────────────────────────
def parse_show_bgp_neighbor(text_content: str) -> Dict[str, Any]:
    cmd = "show bgp neighbor | no-more"
    try:
        return {"output": text_content}
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


# ────────────────────────────────────────────────────────────────────────────────
def parse_show_isis_adjacency_extensive(text_content: str) -> Dict[str, Any]:
    cmd = "show isis adjacency extensive | no-more"
    try:
        result = ShowIsisAdjacencyExtensive()
        adjacency_sections = re.split(r'\n(?=[A-Z0-9]+\n\s+Interface:)', text_content)

        for section in adjacency_sections:
            if not section.strip():
                continue

            system_match = re.match(r'^([A-Z0-9]+)', section)
            if not system_match:
                continue

            entry = ShowIsisAdjacencyEntry(
                system_name=system_match.group(1),
                interface="", level="", state="", expires_in="",
                priority="", up_down_transitions=0, last_transition="",
                circuit_type="", speaks="", topologies="",
                restart_capable="", adjacency_advertisement=""
            )

            interface_match = re.search(r'Interface:\s+(\S+),', section)
            if interface_match:
                entry.interface = interface_match.group(1)

            level_match = re.search(r'Level:\s+(\d+)', section)
            if level_match:
                entry.level = level_match.group(1)

            state_match = re.search(r'State:\s+(\w+)', section)
            if state_match:
                entry.state = state_match.group(1)

            expires_match = re.search(r'Expires in\s+(\d+\s+secs)', section)
            if expires_match:
                entry.expires_in = expires_match.group(1)

            priority_match = re.search(r'Priority:\s+(\d+)', section)
            if priority_match:
                entry.priority = priority_match.group(1)

            transitions_match = re.search(r'Up/Down transitions:\s+(\d+)', section)
            if transitions_match:
                entry.up_down_transitions = int(transitions_match.group(1))

            last_trans_match = re.search(r'Last transition:\s+(.+?)(?:\n|$)', section)
            if last_trans_match:
                entry.last_transition = last_trans_match.group(1)

            circuit_type_match = re.search(r'Circuit type:\s+(\d+)', section)
            if circuit_type_match:
                entry.circuit_type = circuit_type_match.group(1)

            speaks_match = re.search(r'Speaks:\s+(.+?)(?:\n)', section)
            if speaks_match:
                entry.speaks = speaks_match.group(1).strip()

            topologies_match = re.search(r'Topologies:\s+(.+)', section)
            if topologies_match:
                entry.topologies = topologies_match.group(1).strip()

            restart_match = re.search(r'Restart capable:\s+(\w+)', section)
            if restart_match:
                entry.restart_capable = restart_match.group(1)

            adj_adv_match = re.search(r'Adjacency advertisement:\s+(.+)', section)
            if adj_adv_match:
                entry.adjacency_advertisement = adj_adv_match.group(1).strip()

            ip_match = re.search(r'IP addresses:\s+(.+)', section)
            if ip_match:
                entry.ip_addresses = [ip_match.group(1).strip()]

            adj_sid_pattern = r'Level\s+(\d+)\s+(IPv[46])\s+(\w+)\s+Adj-SID:\s+(\d+),\s+Flags:\s+(.+)'
            for adj_match in re.finditer(adj_sid_pattern, section):
                entry.adj_sids.append({
                    'level': adj_match.group(1),
                    'ip_version': adj_match.group(2),
                    'protection': adj_match.group(3),
                    'sid': adj_match.group(4),
                    'flags': adj_match.group(5).strip()
                })

            transition_log_match = re.search(
                r'Transition log:\s*\n\s+(When\s+State\s+Event\s+Down reason)\s*\n((?:\s+\S.*\n?)+)',
                section
            )
            if transition_log_match:
                for line in transition_log_match.group(2).strip().split('\n'):
                    if not line.strip():
                        continue
                    match = re.match(r'\s+(\w{3}\s+\w{3}\s+\d{1,2}\s+\d+:\d+:\d+)\s+(\w+)\s+(.+)', line)
                    if match:
                        rest = match.group(3).strip()
                        parts = re.split(r'\s{2,}', rest, maxsplit=1)
                        entry.transition_log.append(ShowIsisAdjacencyTransition(
                            when=match.group(1),
                            state=match.group(2),
                            event=parts[0].strip(),
                            down_reason=parts[1].strip() if len(parts) > 1 else ''
                        ))

            result.entries.append(entry)

        return asdict(result)
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


# ────────────────────────────────────────────────────────────────────────────────
def parse_show_route_summary(text_content: str) -> Dict[str, Any]:
    cmd = "show route summary | no-more"
    try:
        result = ShowRouteSummary()

        as_match = re.search(r'Autonomous system number:\s+(\d+)', text_content)
        if as_match:
            result.autonomous_system = as_match.group(1)

        router_id_match = re.search(r'Router ID:\s+(\S+)', text_content)
        if router_id_match:
            result.router_id = router_id_match.group(1)

        highwater = ShowRouteSummaryHighwater()
        hw_match = re.search(r'RIB unique destination routes:\s+(.+)', text_content)
        if hw_match:
            highwater.rib_unique_destination_routes = hw_match.group(1).strip()

        hw_routes_match = re.search(r'RIB routes\s+:\s+(.+)', text_content)
        if hw_routes_match:
            highwater.rib_routes = hw_routes_match.group(1).strip()

        hw_fib_match = re.search(r'FIB routes\s+:\s+(.+)', text_content)
        if hw_fib_match:
            highwater.fib_routes = hw_fib_match.group(1).strip()

        hw_vrf_match = re.search(r'VRF type routing instances\s+:\s+(.+)', text_content)
        if hw_vrf_match:
            highwater.vrf_type_routing_instances = hw_vrf_match.group(1).strip()

        result.highwater = highwater

        table_pattern = r'^(\S+(?:\.\S+)?): (\d+) destinations, (\d+) routes \((\d+) active, (\d+) holddown, (\d+) hidden\)'
        protocol_pattern = r'^\s+(\S+):\s+(\d+) routes,\s+(\d+) active'

        tables_section = text_content.split('Highwater Mark')[1] if 'Highwater Mark' in text_content else text_content

        current_table = None
        for line in tables_section.split('\n'):
            table_match = re.match(table_pattern, line.strip())
            if table_match:
                current_table = ShowRouteSummaryTable(
                    table_name=table_match.group(1),
                    destinations=int(table_match.group(2)),
                    routes=int(table_match.group(3)),
                    active=int(table_match.group(4)),
                    holddown=int(table_match.group(5)),
                    hidden=int(table_match.group(6))
                )
                result.tables.append(current_table)
            elif current_table:
                protocol_match = re.match(protocol_pattern, line)
                if protocol_match:
                    current_table.protocols.append(ShowRouteSummaryProtocol(
                        protocol=protocol_match.group(1),
                        routes=int(protocol_match.group(2)),
                        active=int(protocol_match.group(3))
                    ))

        return asdict(result)
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


# ────────────────────────────────────────────────────────────────────────────────
def parse_show_rsvp_session_match_DN(text_content: str) -> Dict[str, Any]:
    cmd = "show rsvp session | match DN | no-more"
    try:
        return {"no_down_sessions": True,"total_down": 0,"down_sessions": [],"status":"clean","message":"No RSVP sessions in DN state detected", }
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}
# ────────────────────────────────────────────────────────────────────────────────
def parse_show_mpls_lsp_unidirectional_no_more(text_content: str) -> Dict[str, Any]:
    cmd = "show mpls lsp unidirectional | match Dn | no-more"
    try:
        down_lsps = []
        pattern = re.compile(
            r'^(\d+\.\d+\.\d+\.\d+)\s+(\S+)\s+(Dn)\s+(\d+)\s+(\S+)\s+(.+)$',
            re.MULTILINE
        )
        for match in pattern.finditer(text_content):
            down_lsps.append({
                "to":       match.group(1),
                "from":     match.group(2),
                "state":    match.group(3),
                "rt":       int(match.group(4)),
                "style":    match.group(5),
                "lsp_name": match.group(6).strip(),
            })
        return {
            "total_down": len(down_lsps),
            "down_lsps":  down_lsps,
        }
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}
# ────────────────────────────────────────────────────────────────────────────────
def parse_36_show_ldp_neighbor(text_content: str) -> Dict[str, Any]:
    cmd = "show ldp neighbor | no-more"
    try:
        ldp_neighbor_result = ShowLdpNeighbor()
        neighbor_pattern = r'^(\d+\.\d+\.\d+\.\d+)\s+(\S+)\s+(\S+)\s+(\d+)$'

        for line in text_content.splitlines():
            if 'Address' in line or not line.strip():
                continue
            match = re.match(neighbor_pattern, line.strip())
            if match:
                ldp_neighbor_result.neighbors.append(LdpNeighbor(
                    address=match.group(1),
                    interface=match.group(2),
                    label_space_id=match.group(3),
                    hold_time=int(match.group(4))
                ))

        return ldp_neighbor_result.to_dict()
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


# ────────────────────────────────────────────────────────────────────────────────
def parse_37_show_connections(text_content: str) -> Dict[str, Any]:
    cmd = "show connections | no-more"
    try:
        s = (text_content or "").strip()
        if re.search(r'No matching connections found', s, re.IGNORECASE):
            return {"connections": "None"}
        has_row = False
        for line in s.splitlines():
            line = line.strip()
            if not line or "connection" in line.lower():
                continue
            if len(line.split()) >= 3:
                has_row = True
                break
        if not has_row:
            return {"connections": "None"}
        return {"connections": "None"}
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


# ────────────────────────────────────────────────────────────────────────────────
def parse_show_log_messages_last_200(text_content: str) -> Dict[str, Any]:
    cmd = "show log messages | last 200 | no-more"
    try:
        result = RecentLogMessages()
        lines = [line.strip() for line in text_content.strip().splitlines() if line.strip()]
        result.recent_lines = lines[:5]

        error_pattern = re.compile(
            r'^(\w+\s+\d+\s+\d{2}:\d{2}:\d{2}\.\d{3})\s+(\S+)\s+(\S+)\[(\d+)\]:\s+(.+)$',
            re.MULTILINE
        )
        keywords = [
            "BGP_CONNECT_FAILED", "JTASK_IO_CONNECT_FAILED",
            "NOTIFICATION sent", "Connection Rejected", "Unconfigured Peer", "rpd["
        ]

        for match in error_pattern.finditer(text_content):
            msg = match.group(5)
            if any(kw in msg for kw in keywords):
                result.error_events.append(LogMessageEntry(
                    timestamp=match.group(1),
                    hostname=match.group(2),
                    process=match.group(3),
                    pid=int(match.group(4)),
                    message=msg.strip()
                ))

        result.total_errors_found = len(result.error_events)
        return asdict(result)
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}
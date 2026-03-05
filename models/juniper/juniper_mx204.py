import sys
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Union, Optional


# ────────────────────────────────────────────────────────────────────────────────
# show arp no-resolve | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class ShowArpNoResolveEntry:
    mac_address: str
    ip_address: str
    interface: str
    flags: str

@dataclass
class ShowArpNoResolve:
    entries: List[ShowArpNoResolveEntry] = field(default_factory=list)
    total_entries: int = 0

    def to_dict(self) -> dict:
        return {
            "total_entries": self.total_entries,
            "entries": [
                {
                    "mac_address": e.mac_address,
                    "ip_address": e.ip_address,
                    "interface": e.interface,
                    "flags": e.flags,
                }
                for e in self.entries
            ],
        }


# ────────────────────────────────────────────────────────────────────────────────
# show lldp neighbors | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class ShowLldpNeighborsEntry:
    local_interface: str
    parent_interface: str
    chassis_id: str
    port_info: str
    system_name: str

@dataclass
class ShowLldpNeighbors:
    entries: List[ShowLldpNeighborsEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "entries": [
                {
                    "local_interface": e.local_interface,
                    "parent_interface": e.parent_interface,
                    "chassis_id": e.chassis_id,
                    "port_info": e.port_info,
                    "system_name": e.system_name,
                }
                for e in self.entries
            ]
        }


# ────────────────────────────────────────────────────────────────────────────────
# show chassis routing-engine | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class CpuUtilization:
    user: Optional[int] = None
    background: Optional[int] = None
    kernel: Optional[int] = None
    interrupt: Optional[int] = None
    idle: Optional[int] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class LoadAverages:
    one_minute: Optional[float] = None
    five_minute: Optional[float] = None
    fifteen_minute: Optional[float] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class RoutingEngineStatus:
    temperature: Optional[str] = None
    cpu_temperature: Optional[str] = None
    dram: Optional[str] = None
    memory_utilization: Optional[int] = None
    cpu_util_5_sec: Optional[CpuUtilization] = None
    cpu_util_1_min: Optional[CpuUtilization] = None
    cpu_util_5_min: Optional[CpuUtilization] = None
    cpu_util_15_min: Optional[CpuUtilization] = None
    model: Optional[str] = None
    start_time: Optional[str] = None
    uptime: Optional[str] = None
    last_reboot_reason: Optional[str] = None
    load_averages: Optional[LoadAverages] = None

    def to_dict(self) -> dict:
        return {
            "temperature": self.temperature,
            "cpu_temperature": self.cpu_temperature,
            "dram": self.dram,
            "memory_utilization": self.memory_utilization,
            "cpu_util_5_sec": self.cpu_util_5_sec.to_dict() if self.cpu_util_5_sec else None,
            "cpu_util_1_min": self.cpu_util_1_min.to_dict() if self.cpu_util_1_min else None,
            "cpu_util_5_min": self.cpu_util_5_min.to_dict() if self.cpu_util_5_min else None,
            "cpu_util_15_min": self.cpu_util_15_min.to_dict() if self.cpu_util_15_min else None,
            "model": self.model,
            "start_time": self.start_time,
            "uptime": self.uptime,
            "last_reboot_reason": self.last_reboot_reason,
            "load_averages": self.load_averages.to_dict() if self.load_averages else None,
        }


@dataclass
class ShowChassisRoutingEngine:
    routing_engines: List[RoutingEngineStatus] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"routing_engines": [re.to_dict() for re in self.routing_engines]}


# ────────────────────────────────────────────────────────────────────────────────
# show system uptime | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class ShowSystemUptime:
    current_time: Optional[str] = None
    time_source: Optional[str] = None
    system_booted: Optional[str] = None
    system_booted_ago: Optional[str] = None
    protocols_started: Optional[str] = None
    protocols_started_ago: Optional[str] = None
    last_configured: Optional[str] = None
    last_configured_ago: Optional[str] = None
    last_configured_by: Optional[str] = None
    uptime_time: Optional[str] = None
    uptime_duration: Optional[str] = None
    users: Optional[int] = None
    load_average_1min: Optional[float] = None
    load_average_5min: Optional[float] = None
    load_average_15min: Optional[float] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


# ────────────────────────────────────────────────────────────────────────────────
# show ntp associations no-resolve | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class NtpAssociation:
    remote: Optional[str] = None
    refid: Optional[str] = None
    auth: Optional[str] = None
    st: Optional[int] = None
    t: Optional[str] = None
    when: Optional[str] = None
    poll: Optional[int] = None
    reach: Optional[int] = None
    delay: Optional[float] = None
    offset: Optional[str] = None
    jitter: Optional[float] = None
    rootdelay: Optional[float] = None
    rootdisp: Optional[float] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ShowNtpAssociations:
    associations: List[NtpAssociation] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"associations": [a.to_dict() for a in self.associations]}


# ────────────────────────────────────────────────────────────────────────────────
# show vmhost version | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class VmhostVersionSet:
    version_set: Optional[str] = None
    vmhost_version: Optional[str] = None
    vmhost_root: Optional[str] = None
    vmhost_core: Optional[str] = None
    kernel: Optional[str] = None
    junos_disk: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ShowVmhostVersion:
    current_device: Optional[str] = None
    current_label: Optional[str] = None
    current_partition: Optional[str] = None
    current_boot_disk: Optional[str] = None
    current_root_set: Optional[str] = None
    uefi_version: Optional[str] = None
    disk_type: Optional[str] = None
    upgrade_time: Optional[str] = None
    versions: List[VmhostVersionSet] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "current_device": self.current_device,
            "current_label": self.current_label,
            "current_partition": self.current_partition,
            "current_boot_disk": self.current_boot_disk,
            "current_root_set": self.current_root_set,
            "uefi_version": self.uefi_version,
            "disk_type": self.disk_type,
            "upgrade_time": self.upgrade_time,
            "versions": [v.to_dict() for v in self.versions],
        }


# ────────────────────────────────────────────────────────────────────────────────
# show vmhost snapshot | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class VMHostSnapshotVersion:
    version_set: Optional[str] = None
    vmhost_version: Optional[str] = None
    vmhost_root: Optional[str] = None
    vmhost_core: Optional[str] = None
    kernel: Optional[str] = None
    junos_disk: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class VMHostSnapshot:
    uefi_version: Optional[str] = None
    disk_type: Optional[str] = None
    snapshot_time: Optional[str] = None
    versions: List[VMHostSnapshotVersion] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "uefi_version": self.uefi_version,
            "disk_type": self.disk_type,
            "snapshot_time": self.snapshot_time,
            "versions": [v.to_dict() for v in self.versions],
        }


# ────────────────────────────────────────────────────────────────────────────────
# show chassis hardware | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class ChassisHardwareItem:
    item: Optional[str] = None
    version: Optional[str] = None
    part_number: Optional[str] = None
    serial_number: Optional[str] = None
    description: Optional[str] = None
    indent_level: Optional[int] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ChassisHardware:
    items: List[ChassisHardwareItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"items": [i.to_dict() for i in self.items]}


# ────────────────────────────────────────────────────────────────────────────────
# show chassis fpc detail | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class ChassisFpcDetail:
    slot: Optional[int] = None
    state: Optional[str] = None
    total_cpu_dram: Optional[str] = None
    total_rldram: Optional[str] = None
    total_ddr_dram: Optional[str] = None
    fips_capable: Optional[str] = None
    temperature: Optional[str] = None
    start_time: Optional[str] = None
    uptime: Optional[str] = None
    high_performance_mode_support: Optional[str] = None
    pfes_in_high_performance_mode: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ShowChassisFpcDetail:
    slots: List[ChassisFpcDetail] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"slots": [s.to_dict() for s in self.slots]}


# ────────────────────────────────────────────────────────────────────────────────
# show chassis alarms | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class ChassisAlarm:
    alarm_time: Optional[str] = None
    alarm_class: Optional[str] = None
    alarm_description: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ShowChassisAlarms:
    has_alarms: bool = False
    alarm_count: int = 0
    alarms: List[ChassisAlarm] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "has_alarms": self.has_alarms,
            "alarm_count": self.alarm_count,
            "alarms": [a.to_dict() for a in self.alarms],
        }


# ────────────────────────────────────────────────────────────────────────────────
# show system alarms | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class SystemAlarm:
    alarm_time: Optional[str] = None
    alarm_class: Optional[str] = None
    alarm_description: Optional[str] = None
    alarm_source: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ShowSystemAlarms:
    has_alarms: bool = False
    alarm_count: int = 0
    alarms: List[SystemAlarm] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "has_alarms": self.has_alarms,
            "alarm_count": self.alarm_count,
            "alarms": [a.to_dict() for a in self.alarms],
        }


# ────────────────────────────────────────────────────────────────────────────────
# show chassis environment | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class EnvironmentItem:
    item_class: Optional[str] = None
    item_name: Optional[str] = None
    status: Optional[str] = None
    measurement: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ShowChassisEnvironment:
    items: List[EnvironmentItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"items": [i.to_dict() for i in self.items]}


# ────────────────────────────────────────────────────────────────────────────────
# show system resource-monitor fpc | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class PfeResourceUsage:
    pfe_number: Optional[int] = None
    encap_mem_free_percent: Optional[str] = None
    nh_mem_free_percent: Optional[int] = None
    fw_mem_free_percent: Optional[int] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class FpcResourceUsage:
    slot_number: Optional[int] = None
    heap_free_percent: Optional[int] = None
    pfe_resources: List[PfeResourceUsage] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "slot_number": self.slot_number,
            "heap_free_percent": self.heap_free_percent,
            "pfe_resources": [p.to_dict() for p in self.pfe_resources],
        }


@dataclass
class ShowSystemResourceMonitorFpc:
    free_heap_mem_watermark: Optional[int] = None
    free_nh_mem_watermark: Optional[int] = None
    free_filter_mem_watermark: Optional[int] = None
    fpc_resources: List[FpcResourceUsage] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "free_heap_mem_watermark": self.free_heap_mem_watermark,
            "free_nh_mem_watermark": self.free_nh_mem_watermark,
            "free_filter_mem_watermark": self.free_filter_mem_watermark,
            "fpc_resources": [f.to_dict() for f in self.fpc_resources],
        }


# ────────────────────────────────────────────────────────────────────────────────
# show system processes extensive | match rpd | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class RpdProcessEntry:
    pid: int
    user: str
    pri: int
    nice: int
    size: str
    res: str
    state: str
    cpu: int
    time: str
    pct: str
    thread_name: str

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ShowSystemProcessesRpd:
    entries: List[RpdProcessEntry] = field(default_factory=list)
    total_rpd_threads: int = 0

    def to_dict(self) -> dict:
        return {
            "total_rpd_threads": self.total_rpd_threads,
            "entries": [e.to_dict() for e in self.entries],
        }


# ────────────────────────────────────────────────────────────────────────────────
# show interface terse | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class InterfaceEntry:
    interface: str
    admin: str
    link: str
    proto: str = ""
    local: str = ""
    remote: str = ""

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ShowInterfacesTerse:
    interfaces: List[InterfaceEntry] = field(default_factory=list)
    total_interfaces: int = 0

    def to_dict(self) -> dict:
        return {
            "total_interfaces": self.total_interfaces,
            "interfaces": [i.to_dict() for i in self.interfaces],
        }


# ────────────────────────────────────────────────────────────────────────────────
# show oam ethernet connectivity-fault-management interfaces extensive | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class OamCfmInterface:
    interface_name: Optional[str] = None
    interface_status: Optional[str] = None
    link_status: Optional[str] = None
    maintenance_domain_name: Optional[str] = None
    md_format: Optional[str] = None
    md_level: Optional[int] = None
    md_index: Optional[int] = None
    maintenance_association_name: Optional[str] = None
    ma_format: Optional[str] = None
    ma_index: Optional[int] = None
    continuity_check_status: Optional[str] = None
    cc_interval: Optional[str] = None
    loss_threshold: Optional[str] = None
    mep_identifier: Optional[int] = None
    mep_direction: Optional[str] = None
    mac_address: Optional[str] = None
    mep_status: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ShowOamCfmInterfaces:
    interfaces: List[OamCfmInterface] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"interfaces": [i.to_dict() for i in self.interfaces]}


# ────────────────────────────────────────────────────────────────────────────────
# show vrrp summary | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class ShowVrrpSummaryAddress:
    type: str
    address: str

    def to_dict(self) -> dict:
        return {"type": self.type, "address": self.address}


@dataclass
class ShowVrrpSummaryEntry:
    interface: str
    state: str
    group: int
    vr_state: str
    vr_mode: str
    addresses: List[ShowVrrpSummaryAddress] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "interface": self.interface,
            "state": self.state,
            "group": self.group,
            "vr_state": self.vr_state,
            "vr_mode": self.vr_mode,
            "addresses": [a.to_dict() for a in self.addresses],
        }


@dataclass
class ShowVrrpSummary:
    entries: List[ShowVrrpSummaryEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"entries": [e.to_dict() for e in self.entries]}


# ────────────────────────────────────────────────────────────────────────────────
# show bfd session | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class ShowBfdSessionEntry:
    address: str
    state: str
    interface: str
    detect_time: str
    transmit_interval: str
    multiplier: str

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ShowBfdSession:
    entries: List[ShowBfdSessionEntry] = field(default_factory=list)
    total_sessions: int = 0
    total_clients: int = 0
    cumulative_transmit_rate: str = ""
    cumulative_receive_rate: str = ""

    def to_dict(self) -> dict:
        return {
            "total_sessions": self.total_sessions,
            "total_clients": self.total_clients,
            "cumulative_transmit_rate": self.cumulative_transmit_rate,
            "cumulative_receive_rate": self.cumulative_receive_rate,
            "entries": [e.to_dict() for e in self.entries],
        }


# ────────────────────────────────────────────────────────────────────────────────
# show rsvp neighbor | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class ShowRsvpNeighborEntry:
    address: str
    idle: int
    up_dn: str
    last_change: str
    hello_interval: int
    hello_tx_rx: str
    msg_rcvd: int

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ShowRsvpNeighbor:
    total_neighbors: int = 0
    entries: List[ShowRsvpNeighborEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_neighbors": self.total_neighbors,
            "entries": [e.to_dict() for e in self.entries],
        }


# ────────────────────────────────────────────────────────────────────────────────
# show rsvp session | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class RsvpSessionIngressEntry:
    to: str
    from_: str
    state: str
    rt: int
    style: str
    label_in: str
    label_out: str
    lsp_name: str

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class RsvpSessionEgressEntry:
    to: str
    from_: str
    state: str
    rt: int
    style: str
    label_in: str
    label_out: str
    lsp_name: str

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class RsvpSessionTransitEntry:
    to: str
    from_: str
    state: str
    rt: int
    style: str
    label_in: str
    label_out: str
    lsp_name: str

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ShowRsvpSession:
    ingress_sessions: int = 0
    ingress_up: int = 0
    ingress_down: int = 0
    ingress_entries: List[RsvpSessionIngressEntry] = field(default_factory=list)
    egress_sessions: int = 0
    egress_up: int = 0
    egress_down: int = 0
    egress_entries: List[RsvpSessionEgressEntry] = field(default_factory=list)
    transit_sessions: int = 0
    transit_up: int = 0
    transit_down: int = 0
    transit_entries: List[RsvpSessionTransitEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ingress_sessions": self.ingress_sessions,
            "ingress_up": self.ingress_up,
            "ingress_down": self.ingress_down,
            "ingress_entries": [e.to_dict() for e in self.ingress_entries],
            "egress_sessions": self.egress_sessions,
            "egress_up": self.egress_up,
            "egress_down": self.egress_down,
            "egress_entries": [e.to_dict() for e in self.egress_entries],
            "transit_sessions": self.transit_sessions,
            "transit_up": self.transit_up,
            "transit_down": self.transit_down,
            "transit_entries": [e.to_dict() for e in self.transit_entries],
        }


# ────────────────────────────────────────────────────────────────────────────────
# show route table inet.0 | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class RouteEntry:
    destination: str
    protocol: str
    preference: int
    metric: int
    age: str
    next_hop: str
    interface: str
    flags: str = ""

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class RouteTableData:
    table_name: str
    total_destinations: int
    total_routes: int
    active_routes: int
    holddown_routes: int
    hidden_routes: int
    entries: List[RouteEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "table_name": self.table_name,
            "total_destinations": self.total_destinations,
            "total_routes": self.total_routes,
            "active_routes": self.active_routes,
            "holddown_routes": self.holddown_routes,
            "hidden_routes": self.hidden_routes,
            "entries": [e.to_dict() for e in self.entries],
        }


# ────────────────────────────────────────────────────────────────────────────────
# show route table inet.3 | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class ShowRouteTableInet3NextHop:
    to: str
    via: str
    mpls_label: str = ""

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ShowRouteTableInet3Entry:
    destination: str
    protocol: str
    preference: str
    metric: str
    age: str
    next_hops: List[ShowRouteTableInet3NextHop] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "destination": self.destination,
            "protocol": self.protocol,
            "preference": self.preference,
            "metric": self.metric,
            "age": self.age,
            "next_hops": [nh.to_dict() for nh in self.next_hops],
        }


@dataclass
class ShowRouteTableInet3:
    total_destinations: int = 0
    total_routes: int = 0
    active_routes: int = 0
    holddown_routes: int = 0
    hidden_routes: int = 0
    entries: List[ShowRouteTableInet3Entry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_destinations": self.total_destinations,
            "total_routes": self.total_routes,
            "active_routes": self.active_routes,
            "holddown_routes": self.holddown_routes,
            "hidden_routes": self.hidden_routes,
            "entries": [e.to_dict() for e in self.entries],
        }


# ────────────────────────────────────────────────────────────────────────────────
# show route table mpls.0 | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class ShowRouteTableMpls0NextHop:
    to: Optional[str] = None
    via: Optional[str] = None
    action: Optional[str] = None
    mpls_label: Optional[str] = None
    lsp_name: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ShowRouteTableMpls0Entry:
    label: str = ""
    protocol: str = ""
    preference: str = ""
    metric: str = ""
    age: str = ""
    next_hops: List[ShowRouteTableMpls0NextHop] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "protocol": self.protocol,
            "preference": self.preference,
            "metric": self.metric,
            "age": self.age,
            "next_hops": [nh.to_dict() for nh in self.next_hops],
        }


@dataclass
class ShowRouteTableMpls0:
    total_destinations: int = 0
    total_routes: int = 0
    active_routes: int = 0
    holddown_routes: int = 0
    hidden_routes: int = 0
    entries: List[ShowRouteTableMpls0Entry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_destinations": self.total_destinations,
            "total_routes": self.total_routes,
            "active_routes": self.active_routes,
            "holddown_routes": self.holddown_routes,
            "hidden_routes": self.hidden_routes,
            "entries": [e.to_dict() for e in self.entries],
        }


# ────────────────────────────────────────────────────────────────────────────────
# show mpls interface | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class ShowMplsInterfaceEntry:
    interface: str
    state: str
    administrative_groups: str

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ShowMplsInterface:
    entries: List[ShowMplsInterfaceEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"entries": [e.to_dict() for e in self.entries]}


# ────────────────────────────────────────────────────────────────────────────────
# show mpls lsp | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class MplsLspIngressEntry:
    to: str
    from_: str
    state: str
    rt: int
    p: str
    active_path: str
    lsp_name: str

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class MplsLspEgressEntry:
    to: str
    from_: str
    state: str
    rt: int
    style: str
    label_in: str
    label_out: str
    lsp_name: str

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class MplsLspTransitEntry:
    to: str
    from_: str
    state: str
    rt: int
    style: str
    label_in: str
    label_out: str
    lsp_name: str

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ShowMplsLsp:
    ingress_sessions: int = 0
    ingress_up: int = 0
    ingress_down: int = 0
    ingress_entries: List[MplsLspIngressEntry] = field(default_factory=list)
    egress_sessions: int = 0
    egress_up: int = 0
    egress_down: int = 0
    egress_entries: List[MplsLspEgressEntry] = field(default_factory=list)
    transit_sessions: int = 0
    transit_up: int = 0
    transit_down: int = 0
    transit_entries: List[MplsLspTransitEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ingress_sessions": self.ingress_sessions,
            "ingress_up": self.ingress_up,
            "ingress_down": self.ingress_down,
            "ingress_entries": [e.to_dict() for e in self.ingress_entries],
            "egress_sessions": self.egress_sessions,
            "egress_up": self.egress_up,
            "egress_down": self.egress_down,
            "egress_entries": [e.to_dict() for e in self.egress_entries],
            "transit_sessions": self.transit_sessions,
            "transit_up": self.transit_up,
            "transit_down": self.transit_down,
            "transit_entries": [e.to_dict() for e in self.transit_entries],
        }


# ────────────────────────────────────────────────────────────────────────────────
# show mpls lsp p2mp | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class P2MPIngressBranch:
    to: str
    from_: str
    state: str
    rt: int
    p: str
    active_path: str
    lsp_name: str

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class P2MPEgressBranch:
    to: str
    from_: str
    state: str
    rt: int
    style: str
    label_in: str
    label_out: str
    lsp_name: str

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class P2MPTransitBranch:
    to: str
    from_: str
    state: str
    rt: int
    style: str
    label_in: str
    label_out: str
    lsp_name: str

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class P2MPSession:
    p2mp_name: str
    branch_count: int
    branches: List[Union[P2MPIngressBranch, P2MPEgressBranch, P2MPTransitBranch]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "p2mp_name": self.p2mp_name,
            "branch_count": self.branch_count,
            "branches": [b.to_dict() for b in self.branches],
        }


@dataclass
class P2MPLSPSection:
    total_sessions: int = 0
    sessions_displayed: int = 0
    sessions_up: int = 0
    sessions_down: int = 0
    sessions: List[P2MPSession] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_sessions": self.total_sessions,
            "sessions_displayed": self.sessions_displayed,
            "sessions_up": self.sessions_up,
            "sessions_down": self.sessions_down,
            "sessions": [s.to_dict() for s in self.sessions],
        }


@dataclass
class ShowMplsLspP2MP:
    ingress_lsp: P2MPLSPSection = field(default_factory=P2MPLSPSection)
    egress_lsp: P2MPLSPSection = field(default_factory=P2MPLSPSection)
    transit_lsp: P2MPLSPSection = field(default_factory=P2MPLSPSection)

    def to_dict(self) -> dict:
        return {
            "ingress_lsp": self.ingress_lsp.to_dict(),
            "egress_lsp": self.egress_lsp.to_dict(),
            "transit_lsp": self.transit_lsp.to_dict(),
        }


# ────────────────────────────────────────────────────────────────────────────────
# show bgp summary | no-more  /  show bgp neighbor | no-more
# (raw passthrough — no structured model needed)
# ────────────────────────────────────────────────────────────────────────────────


# ────────────────────────────────────────────────────────────────────────────────
# show isis adjacency extensive | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class ShowIsisAdjacencyTransition:
    when: str
    state: str
    event: str
    down_reason: str = ""

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ShowIsisAdjacencyEntry:
    system_name: str
    interface: str
    level: str
    state: str
    expires_in: str
    priority: str
    up_down_transitions: int
    last_transition: str
    circuit_type: str
    speaks: str
    topologies: str
    restart_capable: str
    adjacency_advertisement: str
    ip_addresses: List[str] = field(default_factory=list)
    adj_sids: List[Dict[str, str]] = field(default_factory=list)
    transition_log: List[ShowIsisAdjacencyTransition] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "system_name": self.system_name,
            "interface": self.interface,
            "level": self.level,
            "state": self.state,
            "expires_in": self.expires_in,
            "priority": self.priority,
            "up_down_transitions": self.up_down_transitions,
            "last_transition": self.last_transition,
            "circuit_type": self.circuit_type,
            "speaks": self.speaks,
            "topologies": self.topologies,
            "restart_capable": self.restart_capable,
            "adjacency_advertisement": self.adjacency_advertisement,
            "ip_addresses": self.ip_addresses,
            "adj_sids": self.adj_sids,
            "transition_log": [t.to_dict() for t in self.transition_log],
        }


@dataclass
class ShowIsisAdjacencyExtensive:
    entries: List[ShowIsisAdjacencyEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"entries": [e.to_dict() for e in self.entries]}


# ────────────────────────────────────────────────────────────────────────────────
# show route summary | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class ShowRouteSummaryHighwater:
    rib_unique_destination_routes: str = ""
    rib_routes: str = ""
    fib_routes: str = ""
    vrf_type_routing_instances: str = ""

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ShowRouteSummaryProtocol:
    protocol: str
    routes: int
    active: int

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ShowRouteSummaryTable:
    table_name: str
    destinations: int
    routes: int
    active: int
    holddown: int
    hidden: int
    protocols: List[ShowRouteSummaryProtocol] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "table_name": self.table_name,
            "destinations": self.destinations,
            "routes": self.routes,
            "active": self.active,
            "holddown": self.holddown,
            "hidden": self.hidden,
            "protocols": [p.to_dict() for p in self.protocols],
        }


@dataclass
class ShowRouteSummary:
    autonomous_system: str = ""
    router_id: str = ""
    highwater: Optional[ShowRouteSummaryHighwater] = None
    tables: List[ShowRouteSummaryTable] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "autonomous_system": self.autonomous_system,
            "router_id": self.router_id,
            "highwater": self.highwater.to_dict() if self.highwater else None,
            "tables": [t.to_dict() for t in self.tables],
        }


# ────────────────────────────────────────────────────────────────────────────────
# show rsvp session | match DN | no-more
# show mpls lsp unidirectional | match Dn | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class RsvpSessionEntry:
    to_address: str
    from_address: str
    state: str
    rt: int
    style: str
    label_in: str
    label_out: str
    lsp_name: str

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class RsvpSection:
    section_type: str
    total_sessions: int
    sessions_up: int
    sessions_down: int
    entries: List[RsvpSessionEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "section_type": self.section_type,
            "total_sessions": self.total_sessions,
            "sessions_up": self.sessions_up,
            "sessions_down": self.sessions_down,
            "entries": [e.to_dict() for e in self.entries],
        }


@dataclass
class ShowRsvpData:
    ingress: Optional[RsvpSection] = None
    egress: Optional[RsvpSection] = None
    transit: Optional[RsvpSection] = None

    def to_dict(self) -> dict:
        return {
            "ingress": self.ingress.to_dict() if self.ingress else None,
            "egress": self.egress.to_dict() if self.egress else None,
            "transit": self.transit.to_dict() if self.transit else None,
        }


@dataclass
class MplsLspEntry:
    to_address: str
    from_address: str
    state: str
    rt: int
    style: str
    label_in: str
    label_out: str
    lsp_name: str

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class MplsLspSection:
    section_type: str
    total_sessions: int
    sessions_displayed: int
    sessions_up: int
    sessions_down: int
    entries: List[MplsLspEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "section_type": self.section_type,
            "total_sessions": self.total_sessions,
            "sessions_displayed": self.sessions_displayed,
            "sessions_up": self.sessions_up,
            "sessions_down": self.sessions_down,
            "entries": [e.to_dict() for e in self.entries],
        }


@dataclass
class ShowMplsLspData:
    ingress: Optional[MplsLspSection] = None
    egress: Optional[MplsLspSection] = None
    transit: Optional[MplsLspSection] = None

    def to_dict(self) -> dict:
        return {
            "ingress": self.ingress.to_dict() if self.ingress else None,
            "egress": self.egress.to_dict() if self.egress else None,
            "transit": self.transit.to_dict() if self.transit else None,
        }


@dataclass
class DownLspEntry:
    to: str
    from_: str
    state: str
    rt: int
    style: str
    lsp_name: str

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class DownLspSummary:
    down_lsps: List[DownLspEntry] = field(default_factory=list)
    total_down: int = 0

    def to_dict(self) -> dict:
        return {
            "total_down": self.total_down,
            "down_lsps": [e.to_dict() for e in self.down_lsps],
        }


# ────────────────────────────────────────────────────────────────────────────────
# show ldp neighbor | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class LdpNeighbor:
    address: Optional[str] = None
    interface: Optional[str] = None
    label_space_id: Optional[str] = None
    hold_time: Optional[int] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ShowLdpNeighbor:
    neighbors: List[LdpNeighbor] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"neighbors": [n.to_dict() for n in self.neighbors]}


# ────────────────────────────────────────────────────────────────────────────────
# show connections | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class Connection:
    connection_id: Optional[str] = None
    source: Optional[str] = None
    destination: Optional[str] = None
    state: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ShowConnections:
    has_connections: bool = False
    connections: List[Connection] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "has_connections": self.has_connections,
            "connections": [c.to_dict() for c in self.connections],
        }


# ────────────────────────────────────────────────────────────────────────────────
# show log messages | last 200 | no-more
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class LogMessageEntry:
    timestamp: str
    hostname: str
    process: str
    pid: int
    message: str

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class RecentLogMessages:
    recent_lines: List[str] = field(default_factory=list)
    error_events: List[LogMessageEntry] = field(default_factory=list)
    total_errors_found: int = 0

    def to_dict(self) -> dict:
        return {
            "total_errors_found": self.total_errors_found,
            "recent_lines": self.recent_lines,
            "error_events": [e.to_dict() for e in self.error_events],
        }
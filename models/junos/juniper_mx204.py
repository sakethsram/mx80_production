import sys
from dataclasses import dataclass, field, asdict
import re
from typing import List, Dict, Any, Union, Optional

@dataclass
class ShowArpNoResolveEntry:
    """Represents a single ARP table entry"""
    mac_address: str
    ip_address: str
    interface: str
    flags: str

@dataclass
class ShowArpNoResolve:
    """Represents the complete ARP table output"""
    entries: List[ShowArpNoResolveEntry] = field(default_factory=list)
    total_entries: int = 0
    
    def to_dict(self):
        """Convert to dictionary format"""
        return {
            "total_entries": self.total_entries,
            "entries": [
                {
                    "mac_address": entry.mac_address,
                    "ip_address": entry.ip_address,
                    "interface": entry.interface,
                    "flags": entry.flags
                }
                for entry in self.entries
            ]
        }

@dataclass
class ShowVrrpSummaryAddress:
    """Represents a VRRP address (lcl or vip)"""
    type: str  # 'lcl' or 'vip'
    address: str

@dataclass
class ShowVrrpSummaryEntry:
    """Represents a single VRRP group entry"""
    interface: str
    state: str
    group: int
    vr_state: str
    vr_mode: str
    addresses: List[ShowVrrpSummaryAddress] = field(default_factory=list)

@dataclass
class ShowVrrpSummary:
    """Represents the complete VRRP summary output"""
    entries: List[ShowVrrpSummaryEntry] = field(default_factory=list)
    
    def to_dict(self):
        """Convert to dictionary format"""
        return {
            "entries": [
                {
                    "interface": entry.interface,
                    "state": entry.state,
                    "group": entry.group,
                    "vr_state": entry.vr_state,
                    "vr_mode": entry.vr_mode,
                    "addresses": [
                        {
                            "type": addr.type,
                            "address": addr.address
                        }
                        for addr in entry.addresses
                    ]
                }
                for entry in self.entries
            ]
        }

@dataclass
class ShowLldpNeighborsEntry:
    """Represents a single LLDP neighbor entry"""
    local_interface: str
    parent_interface: str
    chassis_id: str
    port_info: str
    system_name: str

@dataclass
class ShowLldpNeighbors:
    """Represents the complete LLDP neighbors output"""
    entries: List[ShowLldpNeighborsEntry] = field(default_factory=list)
    
    def to_dict(self):
        """Convert to dictionary format"""
        return {
            "entries": [
                {
                    "local_interface": entry.local_interface,
                    "parent_interface": entry.parent_interface,
                    "chassis_id": entry.chassis_id,
                    "port_info": entry.port_info,
                    "system_name": entry.system_name
                }
                for entry in self.entries
            ]
        }

@dataclass
class ShowBfdSessionEntry:
    """Represents a single BFD session entry"""
    address: str
    state: str
    interface: str
    detect_time: str
    transmit_interval: str
    multiplier: str

@dataclass
class ShowBfdSession:
    """Represents the complete BFD session output"""
    entries: List[ShowBfdSessionEntry] = field(default_factory=list)
    total_sessions: int = 0
    total_clients: int = 0
    cumulative_transmit_rate: str = ""
    cumulative_receive_rate: str = ""
    
    def to_dict(self):
        """Convert to dictionary format"""
        return {
            "total_sessions": self.total_sessions,
            "total_clients": self.total_clients,
            "cumulative_transmit_rate": self.cumulative_transmit_rate,
            "cumulative_receive_rate": self.cumulative_receive_rate,
            "entries": [
                {
                    "address": entry.address,
                    "state": entry.state,
                    "interface": entry.interface,
                    "detect_time": entry.detect_time,
                    "transmit_interval": entry.transmit_interval,
                    "multiplier": entry.multiplier
                }
                for entry in self.entries
            ]
        }

@dataclass
class ShowRouteTableInet3NextHop:
    """Represents a single next-hop for a route"""
    to: str
    via: str
    mpls_label: str = ""

@dataclass
class ShowRouteTableInet3Entry:
    """Represents a single route entry with multiple next-hops"""
    destination: str
    protocol: str
    preference: str
    metric: str
    age: str
    next_hops: List[ShowRouteTableInet3NextHop] = field(default_factory=list)

@dataclass
class ShowRouteTableInet3:
    """Represents the complete inet.3 routing table output"""
    total_destinations: int = 0
    total_routes: int = 0
    active_routes: int = 0
    holddown_routes: int = 0
    hidden_routes: int = 0
    entries: List[ShowRouteTableInet3Entry] = field(default_factory=list)
    
    def to_dict(self):
        """Convert to dictionary format"""
        return {
            "total_destinations": self.total_destinations,
            "total_routes": self.total_routes,
            "active_routes": self.active_routes,
            "holddown_routes": self.holddown_routes,
            "hidden_routes": self.hidden_routes,
            "entries": [
                {
                    "destination": entry.destination,
                    "protocol": entry.protocol,
                    "preference": entry.preference,
                    "metric": entry.metric,
                    "age": entry.age,
                    "next_hops": [
                        {
                            "to": nh.to,
                            "via": nh.via,
                            "mpls_label": nh.mpls_label
                        }
                        for nh in entry.next_hops
                    ]
                }
                for entry in self.entries
            ]
        }

@dataclass
class ShowRouteTableMpls0NextHop:
    """Represents a single next-hop entry in mpls.0 routing table"""
    to: Optional[str] = None
    via: Optional[str] = None
    action: Optional[str] = None  # Pop, Swap, Push, Receive, etc.
    mpls_label: Optional[str] = None
    lsp_name: Optional[str] = None

@dataclass
class ShowRouteTableMpls0Entry:
    """Represents a single route entry in mpls.0 routing table"""
    label: str = ""
    protocol: str = ""
    preference: str = ""
    metric: str = ""
    age: str = ""
    next_hops: List[ShowRouteTableMpls0NextHop] = field(default_factory=list)

@dataclass
class ShowRouteTableMpls0:
    """Represents the complete mpls.0 routing table output"""
    total_destinations: int = 0
    total_routes: int = 0
    active_routes: int = 0
    holddown_routes: int = 0
    hidden_routes: int = 0
    entries: List[ShowRouteTableMpls0Entry] = field(default_factory=list)
    
    def to_dict(self):
        """Convert to dictionary format"""
        return {
            "total_destinations": self.total_destinations,
            "total_routes": self.total_routes,
            "active_routes": self.active_routes,
            "holddown_routes": self.holddown_routes,
            "hidden_routes": self.hidden_routes,
            "entries": [
                {
                    "label": entry.label,
                    "protocol": entry.protocol,
                    "preference": entry.preference,
                    "metric": entry.metric,
                    "age": entry.age,
                    "next_hops": [
                        {
                            "to": nh.to,
                            "via": nh.via,
                            "action": nh.action,
                            "mpls_label": nh.mpls_label,
                            "lsp_name": nh.lsp_name
                        }
                        for nh in entry.next_hops
                    ]
                }
                for entry in self.entries
            ]
        }

@dataclass
class ShowRsvpNeighborEntry:
    address: str
    idle: int
    up_dn: str
    last_change: str
    hello_interval: int
    hello_tx_rx: str
    msg_rcvd: int

@dataclass
class ShowRsvpNeighbor:
    total_neighbors: int = 0
    entries: List[ShowRsvpNeighborEntry] = field(default_factory=list)

@dataclass
class ShowMplsInterfaceEntry:
    """Represents a single MPLS interface entry"""
    interface: str
    state: str
    administrative_groups: str

@dataclass
class ShowMplsInterface:
    """Represents the complete MPLS interface output"""
    entries: List[ShowMplsInterfaceEntry] = field(default_factory=list)
    
    def to_dict(self):
        """Convert to dictionary format"""
        return {
            "entries": [
                {
                    "interface": entry.interface,
                    "state": entry.state,
                    "administrative_groups": entry.administrative_groups
                }
                for entry in self.entries
            ]
        }

@dataclass
class ShowIsisAdjacencyTransition:
    """Represents a single transition log entry"""
    when: str
    state: str
    event: str
    down_reason: str = ""

@dataclass
class ShowIsisAdjacencyEntry:
    """Represents a single ISIS adjacency"""
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

@dataclass
class ShowIsisAdjacencyExtensive:
    """Represents the complete ISIS adjacency extensive output"""
    entries: List[ShowIsisAdjacencyEntry] = field(default_factory=list)
    
    def to_dict(self):
        """Convert to dictionary format"""
        return {
            "entries": [
                {
                    "system_name": entry.system_name,
                    "interface": entry.interface,
                    "level": entry.level,
                    "state": entry.state,
                    "expires_in": entry.expires_in,
                    "up_down_transitions": entry.up_down_transitions,
                    "last_transition": entry.last_transition,
                    "ip_addresses": entry.ip_addresses,
                    "adj_sids": entry.adj_sids,
                    "transition_log": [
                        {
                            "when": t.when,
                            "state": t.state,
                            "event": t.event,
                            "down_reason": t.down_reason
                        }
                        for t in entry.transition_log
                    ]
                }
                for entry in self.entries
            ]
        }

@dataclass
class ShowRouteSummaryHighwater:
    """Represents highwater mark statistics"""
    rib_unique_destination_routes: str = ""
    rib_routes: str = ""
    fib_routes: str = ""
    vrf_type_routing_instances: str = ""

@dataclass
class ShowRouteSummaryProtocol:
    """Represents protocol statistics for a routing table"""
    protocol: str
    routes: int
    active: int

@dataclass
class ShowRouteSummaryTable:
    """Represents a routing table summary"""
    table_name: str
    destinations: int
    routes: int
    active: int
    holddown: int
    hidden: int
    protocols: List[ShowRouteSummaryProtocol] = field(default_factory=list)

@dataclass
class ShowRouteSummary:
    """Represents the complete route summary output"""
    autonomous_system: str = ""
    router_id: str = ""
    highwater: Optional[ShowRouteSummaryHighwater] = None
    tables: List[ShowRouteSummaryTable] = field(default_factory=list)
    
    def to_dict(self):
        """Convert to dictionary format"""
        result = {
            "autonomous_system": self.autonomous_system,
            "router_id": self.router_id,
            "tables": [
                {
                    "table_name": table.table_name,
                    "destinations": table.destinations,
                    "routes": table.routes,
                    "active": table.active,
                    "holddown": table.holddown,
                    "hidden": table.hidden,
                    "protocols": [
                        {
                            "protocol": proto.protocol,
                            "routes": proto.routes,
                            "active": proto.active
                        }
                        for proto in table.protocols
                    ]
                }
                for table in self.tables
            ]
        }
        
        if self.highwater:
            result["highwater"] = {
                "rib_unique_destination_routes": self.highwater.rib_unique_destination_routes,
                "rib_routes": self.highwater.rib_routes,
                "fib_routes": self.highwater.fib_routes,
                "vrf_type_routing_instances": self.highwater.vrf_type_routing_instances
            }
        
        return result


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

@dataclass
class MplsLspIngressEntry:
    to: str
    from_: str
    state: str
    rt: int
    p: str
    active_path: str
    lsp_name: str

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

@dataclass
class RsvpSection:
    section_type: str
    total_sessions: int
    sessions_up: int
    sessions_down: int
    entries: List[RsvpSessionEntry] = field(default_factory=list)

@dataclass
class ShowRsvpData:
    ingress: RsvpSection = None
    egress: RsvpSection = None
    transit: RsvpSection = None

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

@dataclass
class MplsLspSection:
    section_type: str
    total_sessions: int
    sessions_displayed: int
    sessions_up: int
    sessions_down: int
    entries: List[MplsLspEntry] = field(default_factory=list)

@dataclass
class ShowMplsLspData:
    ingress: MplsLspSection = None
    egress: MplsLspSection = None
    transit: MplsLspSection = None

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

@dataclass
class RouteTableData:
    table_name: str
    total_destinations: int
    total_routes: int
    active_routes: int
    holddown_routes: int
    hidden_routes: int
    entries: List[RouteEntry] = field(default_factory=list)

@dataclass
class RsvpNeighborEntry:
    address: str
    idle: int
    up_down: str
    last_change: str
    hello_int: int
    hello_tx_rx: str
    msg_rcvd: int

@dataclass
class ShowRsvpNeighborData:
    total_neighbors: int = 0  
    neighbors: List[RsvpNeighborEntry] = field(default_factory=list)

# Data Models for P2MP LSP
@dataclass
class P2MPIngressBranch:
    to: str
    from_: str
    state: str
    rt: int
    p: str
    active_path: str
    lsp_name: str

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

@dataclass
class P2MPSession:
    p2mp_name: str
    branch_count: int
    branches: List[Union[P2MPIngressBranch, P2MPEgressBranch, P2MPTransitBranch]] = field(default_factory=list)

@dataclass
class P2MPLSPSection:
    total_sessions: int = 0
    sessions_displayed: int = 0
    sessions_up: int = 0
    sessions_down: int = 0
    sessions: List[P2MPSession] = field(default_factory=list)

@dataclass
class ShowMplsLspP2MP:
    ingress_lsp: P2MPLSPSection = field(default_factory=P2MPLSPSection)
    egress_lsp: P2MPLSPSection = field(default_factory=P2MPLSPSection)
    transit_lsp: P2MPLSPSection = field(default_factory=P2MPLSPSection)


from dataclasses import dataclass, field
from typing import Optional


# ── parse_21_show_system_uptime ──────────────────────────────────────────────

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


# ── parse_22_show_ntp_associations ───────────────────────────────────────────

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
    associations: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"associations": [a.to_dict() for a in self.associations]}


# ── parse_23_show_vmhost_version ─────────────────────────────────────────────

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
    versions: list = field(default_factory=list)

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


# ── parse_24_show_vmhost_snapshot ────────────────────────────────────────────

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
    versions: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "uefi_version": self.uefi_version,
            "disk_type": self.disk_type,
            "snapshot_time": self.snapshot_time,
            "versions": [v.to_dict() for v in self.versions],
        }


# ── parse_25_show_chassis_hardware ───────────────────────────────────────────

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
    items: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"items": [i.to_dict() for i in self.items]}


# ── parse_26_show_chassis_fpc_detail ─────────────────────────────────────────

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
    slots: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"slots": [s.to_dict() for s in self.slots]}


# ── parse_27_show_chassis_alarms ─────────────────────────────────────────────

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
    alarms: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "has_alarms": self.has_alarms,
            "alarm_count": self.alarm_count,
            "alarms": [a.to_dict() for a in self.alarms],
        }


# ── parse_28_show_system_alarms ──────────────────────────────────────────────

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
    alarms: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "has_alarms": self.has_alarms,
            "alarm_count": self.alarm_count,
            "alarms": [a.to_dict() for a in self.alarms],
        }


# ── parse_29_show_chassis_routing_engine ─────────────────────────────────────

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
    routing_engines: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"routing_engines": [re.to_dict() for re in self.routing_engines]}


# ── parse_30_show_chassis_environment ────────────────────────────────────────

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
    items: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"items": [i.to_dict() for i in self.items]}


# ── parse_31_show_system_resource_monitor_fpc ────────────────────────────────

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
    pfe_resources: list = field(default_factory=list)

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
    fpc_resources: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "free_heap_mem_watermark": self.free_heap_mem_watermark,
            "free_nh_mem_watermark": self.free_nh_mem_watermark,
            "free_filter_mem_watermark": self.free_filter_mem_watermark,
            "fpc_resources": [f.to_dict() for f in self.fpc_resources],
        }


# ── parse_32_show_krt_table ──────────────────────────────────────────────────

@dataclass
class KrtTableEntry:
    kernel_id: Optional[str] = None
    route_prefix: Optional[str] = None
    interface: Optional[str] = None
    next_hop: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ShowKrtTable:
    entries: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"entries": [e.to_dict() for e in self.entries]}


# ── parse_33_show_system_processes ───────────────────────────────────────────

@dataclass
class SystemProcess:
    pid: Optional[int] = None
    user: Optional[str] = None
    priority: Optional[int] = None
    nice: Optional[int] = None
    size: Optional[str] = None
    res: Optional[str] = None
    state: Optional[str] = None
    cpu_id: Optional[int] = None
    time: Optional[str] = None
    cpu_percent: Optional[str] = None
    command: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ShowSystemProcesses:
    processes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"processes": [p.to_dict() for p in self.processes]}


# ── parse_34_show_interface_descriptions ─────────────────────────────────────

@dataclass
class InterfaceDescription:
    interface: Optional[str] = None
    admin_status: Optional[str] = None
    link_status: Optional[str] = None
    description: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ShowInterfaceDescriptions:
    interfaces: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"interfaces": [i.to_dict() for i in self.interfaces]}


# ── parse_35_show_oam_cfm_interfaces ─────────────────────────────────────────

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
    interfaces: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"interfaces": [i.to_dict() for i in self.interfaces]}


# ── parse_36_show_ldp_neighbor ───────────────────────────────────────────────

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
    neighbors: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"neighbors": [n.to_dict() for n in self.neighbors]}


# ── parse_37_show_connections ────────────────────────────────────────────────

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
    connections: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "has_connections": self.has_connections,
            "connections": [c.to_dict() for c in self.connections],
        }
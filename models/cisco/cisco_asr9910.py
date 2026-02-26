from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any



from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class BFDSession:
    interface: str
    dest_addr: str
    echo_time: str
    echo_interval: str
    echo_multiplier: str
    async_time: str
    async_interval: str
    async_multiplier: str
    state: str
    hardware: str
    npu: str
 

@dataclass
class ShowInstallActiveSummary:
    Label: str                
    AcivePackages: int       
    Packages: List[str]


@dataclass
class ShowRouteSummary:
    routeSource: str
    routes: int
    backup: int
    deleted: int
    memory: int


@dataclass
class PimNeighbor:
    vrf: str                 
    neighborAddress: str     
    isSelf: bool             
    interface: str           
    uptime: str              
    expires: str            
    drPriority: int          
    isDR: bool              
    flags: List[str]         
    flagsRaw: str    


@dataclass
class ShowFileSystemEntry:
    sizeBytes: int         
    freeBytes: int          
    fsType: str            
    flags: str              
    prefixesRaw: str       
    prefixes: List[str]            

@dataclass 
class FPDEntry: 
	Location: str 
	CardType: str 
	HWver: str 
	FPDdevice: str 
	ATRstatus: str 
	FPDVersions: dict


@dataclass
class L2vpnXconnectBriefRow:
    domain: str             
    category: str            
    typeName: str           
    up: int
    down: int
    unresolved: int

@dataclass
class L2vpnXconnectBriefSummary:
    totalUp: int
    totalDown: int
    totalUnresolved: int

@dataclass
class IsisAdjacencyEntry:
    SystemId: str
    Interface: str
    SNPA: str
    State: str
    Hold: int
    Changed: str
    NSF: str
    IPv4BFD: str
    IPv6BFD: str


@dataclass
class IsisAdjacencyLevelBlock:
    Level: str 
    TotalAdjacencyCount: int = 0
    Adjacencies: List[IsisAdjacencyEntry] = field(default_factory=list)

    # Optional: useful derived stats
    UpCount: int = 0
    NonUpCount: int = 0
    IPv4BFDUpCount: int = 0
    IPv4BFDNonUpCount: int = 0


@dataclass
class IsisAdjacencyReport:

    Blocks: List[IsisAdjacencyLevelBlock] = field(default_factory=list)

    # Optional: metadata
    SourceFile: Optional[str] = None
    ParsedAt: Optional[str] = None  # ISO timestamp if you want


@dataclass
class ShowMemorySummary:
    node: str
    physical_total: str
    physical_available: str
    app_total: str
    app_available: str
    image: str
    bootram: str
    reserved: str
    iomem: str
    flashfsys: str
    shared_window: str
from dataclasses import dataclass, asdict, field
from typing import List
#  OOPS CONCEPT
@dataclass
class ShowInventory: 
	NAME: str 
	DESCR: str 
	PID: str
	VID: str 
	SN: str

@dataclass 
class ShowInstallActiveSummary: 
	AcivePackages: int 
	Packages: List[str]

@dataclass 
class ShowPlatform: 
	Node: str 
	Type: str
	State: str 
	ConfigState: str

@dataclass
class ShowInstallCommittedSummary: 
	CommittedPackages: int 
	Packages: List[str]


@dataclass 
class FPDEntry: 
	Location: str 
	CardType: str 
	HWver: str 
	FPDdevice: str 
	ATRstatus: str 
	FPDVersions: dict

@dataclass
class ShowhwModuleFPD: 
	AutoUpgrade: str 
	FPDs: List[FPDEntry]
	
@dataclass
class MediaInfo: 
	Partition: str 
	Size: str 
	Used: str 
	Percent: str 
	Avail: str

@dataclass
class ShowMedia:
	MediaLoc: str
	MediaInfo: List[MediaInfo]

@dataclass
class ShowRouteSummary: 
	routeSource: str 
	routes: int 
	backup: int 
	deleted: int 
	memory: int

@dataclass
class memoryInfo:
	physicalMem: str
	freeMem: str
	memoryState: str

@dataclass
class ShowWatchdogMemoryState:
	nodeName: str
	memoryInfo: List[memoryInfo]

@dataclass
class ShowIpv4VrfAllInterfaceBrief:
    interface: str
    IPAddress: str
    status: str
    protocol: str
    VRFName: str

@dataclass
class lldpNeighbors:
    deviceId: str
    localIntf: str
    holdTime: int
    capability: str
    portId: str

@dataclass
class ShowLLDPNeighbors:
    totalEntriesDisplayed: int
    neighbors: List[lldpNeighbors]

@dataclass
class ISISAdjacencies: 
	systemID: str 
	interface: str 
	SNPA: str 
	state: str 
	hold: int 
	changed: str 

@dataclass
class ShowInterfaceDescription:
    interface: str
    status: str
    protocol: str
    description: str

@dataclass
class cpuSummary:
    oneMin: str
    fiveMin: str
    fifteenMin: str

@dataclass
class cpuProcess:
    pid: int
    oneMin: str
    fiveMin: str
    fifteenMin: str
    process: str

@dataclass
class ShowProcCPU:
    name: str
    summary: cpuSummary
    processes: List[cpuProcess]
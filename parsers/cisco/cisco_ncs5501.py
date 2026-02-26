from typing import List, Dict, Any
import re, os
import sys
from models.cisco.cisco_ncs5501 import *
from models.junos import *
import json
from datetime import datetime
from dataclasses import dataclass, asdict, field
import logging
from lib.utilities import *


logger = logging.getLogger(__name__)


def show_inventory() -> List[dict]: 
    """
    Function: show_inventory
    Purpose: Display the product inventory of all Cisco products
            installed in the networking device. 
    command: show inventory
    """
    try:
        print("Running Show inventory ....") 
        cmd = "show inventory"
        
        content = COMMAND_OUTPUT_STORE.get(cmd).get("output")

        if not content: 
            raise ValueError(f"No output found for command: {cmd}")

        pattern = re.compile(
            r'NAME:\s*"(?P<NAME>[^"]+)",\s*DESCR:\s*"(?P<DESCR>[^"]+)"\s*'
            r'[\s\n]'
            r'PID:\s*(?P<PID>[^,]+?)\s*,\s*'
            r'VID:\s*(?P<VID>[^,]+?)\s*,\s*'
            r'SN:\s*(?P<SN>\S+)'
        )  

        print("pattern: ", pattern)
        inventory = [] 

        matches = list(pattern.finditer(content))

        for match in matches: 
            print("match: ", match)
            inventory.append(
                asdict(
                    cisco_ncs5501.ShowInventory(
                        NAME=match.group("NAME").strip(), 
                        DESCR=match.group("DESCR").strip(), 
                        PID=match.group("PID").strip(), 
                        VID=match.group("VID").strip(), 
                        SN=match.group("SN").strip(),
                    )
                )
            )
            
        print("inventory: ", inventory)

        # Creating json file 
        output_file = write_json(
            command_name="show_inventory",
            vendor="cisco",
            model="ncs5501",
            json_data=inventory,
            json_file_path="precheck_jsons/"
        )
        return output_file

    except Exception as e: 
        return {"error": f"Error reading file: {str(e)}"}

def show_install_active_summary() -> Dict[str, Any]:
    """
    Docstring for show_install_active_summary
    
    :param folder_path: Includes that output of show_install_active_summary
    :type folder_path: str
    :return: Json string of show_install_active_summary.txt file
    :rtype: Dict[str, Any]
    """
    try: 
        print(" Show install active summary ....")
        cmd = "show install active summary"
        content = COMMAND_OUTPUT_STORE.get(cmd)
        print(f" Content: {content}")
        if not content: 
            raise ValueError(f"No output found for command: {cmd}")

        match = re.search(
            r'Active Packages:\s*(?P<count>\d+)', 
            content
        )
        activePackages = int(match.group("count")) if match else 0
        
        print(f" Active Packages: {activePackages}")

        package = re.findall(
            r'^\s+(?!Active)(?!Mon)(\S+)',
            content,
            re.MULTILINE
        )

        packages = [line.strip() for line in package  if line.strip() ]

        result = [asdict(
            ShowInstallActiveSummary(
                AcivePackages = activePackages, 
                Packages=packages
            )
        )]

        # Creating json file 
        output_file = write_json(
            command_name="show_install_active_summary",
            vendor="cisco",
            model="ncs5501",
            json_data=result,
            json_file_path="precheck_jsons/"
        )
        
        return output_file
    
    except Exception as e: 
        return {"error": f"Error reading file: {str(e)}"}
            
def show_platform() -> Dict[str, Any]: 
    """
    Docstring for show_platform
    
    :param folder_path:  Includes that output of show platform
    :type folder_path: str
    :return: Return the JSON file of the show_platform.txt
    :rtype: Dict[str, Any]
    """
    try: 
        print("Show platform ...")
        cmd = "show platform" 
        content = COMMAND_OUTPUT_STORE.get(cmd)
        print(f" Content: {content}")
        if not content: 
            raise ValueError(f"No output found for command: {cmd}")

        result = []

        for line in content.splitlines(): 
            line = line.strip()
            print(f" Line: {line}") 

            # Skip headers and separators 
            if not line or line.startswith("Node") or line.startswith("-"): 
                continue

            cols = re.split(r'\s{2,}', line)
            print(f" cols: {cols}")

            entry = ShowPlatform(
                Node=cols[0], 
                Type=cols[1], 
                State=cols[2], 
                ConfigState=cols[3] if len(cols) > 3 else None
            )
            print(f" entry: {entry}")
            result.append(asdict(entry))
            print(f" result: {result}")
        print(f" Result: {result}")

        # Creating json file 
        output_file = write_json(
            command_name="show_platform", 
            vendor="cisco",
            model="ncs5501",
            json_data=result,
            json_file_path="precheck_jsons/"
        )

        return output_file
    except Exception as e: 
        return {"error": f"Error reading file: {str(e)}"}
    
def show_install_committed_summary() -> Dict[str, Any]: 
    """
    Docstring for show_install_committed_summary
    
    :param folder_path: Description
    :type folder_path: str
    :return: Description
    :rtype: Dict[str, Any]
    """
    try: 
        print("show install committed summary ...")
        cmd = "show install committed summary"
        content = COMMAND_OUTPUT_STORE.get(cmd)
        print(f" Content: {content}")
        if not content: 
            raise ValueError(f"No output found for command: {cmd}")
        
        match = re.search(
            r'Committed Packages:\s*(?P<count>\d+)',
            content
        )

        committedPackages = int(match.group("count")) if match else 0 

        print(f"Committed Package: {committedPackages}")

        package = re.findall(
            r'^\s+(\S+)', 
            content, 
            re.MULTILINE
        )

        packages = [line.strip() for line in package  if line.strip() ]

        result = [asdict(
            ShowInstallCommittedSummary(
                CommittedPackages= committedPackages, 
                Packages=packages
            )
        )]

        # Creating json file 
        output_file = write_json(
            command_name="show_install_committed_summary",
            vendor="cisco",
            model="ncs5501",
            json_data=result,
            json_file_path="precheck_jsons/"
        )

        return output_file
    except Exception as e: 
        return {"error": f"Error reading file: {str(e)}"}
    
def show_hw_module_fpd(): 
    """
    Docstring for show_hw_module_fpd
    
    :param folder_path: Description
    :type folder_path: str
    """
    try: 
        print("show hw_module fpd ...")
        
        cmd = "show hw-module fpd"
        content = COMMAND_OUTPUT_STORE.get(cmd)
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
            model="ncs5501",
            json_data=result,
            json_file_path="precheck_jsons/"
        )

        return output_file
    except Exception as e: 
        return {"error": f"Error reading file: {str(e)}"}

def show_media(): 
    """
    Docstring for show_media
    
    :param folder_path: Description
    :type folder_path: str
    """
    try: 
        print("show media ...")
        
        cmd = "show media"
        content = COMMAND_OUTPUT_STORE.get(cmd)
        print(f" Content: {content}")
        if not content: 
            raise ValueError(f"No output found for command: {cmd}")

        print(f" Content: {content}")
        mediaInfo, result = [] , []

        mediaLocation = re.search(
            r'^Media Info for Location:\s*([A-Za-z0-9_-]+)$',
            content, 
            re.MULTILINE
        )
        location = mediaLocation.group(1) if mediaLocation else ""

        for line in content.splitlines(): 
            line = line.strip() 
            print(f" Line: {line}")

            # Skip headers and separators 
            if (
                not line 
                or line.startswith("-") 
                or line.startswith("Partition")
                or line.startswith("Media")
                ): 
                continue 
            
            cols = re.split(r'\s{2,}', line)
            print(f"cols: {cols}")

            entry = MediaInfo( 
                Partition=cols[0], 
                Size=cols[1],
                Used=cols[2],
                Percent=cols[3],
                Avail=cols[4]
            )
            mediaInfo.append(asdict(entry))
            print(f"Media Info: {mediaInfo}")
        
        result.append(
            {
                "MediaLoc": location, 
                "MediaInfo": mediaInfo
            }
        )
        print(f" Result: {result}")

        output_file = write_json(
            command_name="show_media", 
            vendor="cisco",
            model="ncs5501",
            json_data=result,
            json_file_path="precheck_jsons/"
        )

        return output_file
    except Exception as e: 
        return {"error": f"Error reading file: {str(e)}"}

def show_route_summary(): 
    """
    Docstring for show_route_summary
    
    :param folder_path: Description
    :type folder_path: str
    """
    try: 
        print(" show route summary ...")
        
        cmd = "show route summary"
        content = COMMAND_OUTPUT_STORE.get(cmd)
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
                model="ncs5501",
                json_data=result,
                json_file_path="precheck_jsons/"
            )

            return output_file
    except Exception as e: 
        return {"error": f"Error reading file: {str(e)}"}

def show_watchdog_memory_state(): 
    """
    Docstring for show_watchdog_memory_state
    
    :param folder_path: Description
    """
    try: 
        logger.info("show watchdog memory-state location all")
        
        cmd = "show watchdog memory-state location all"
        content = COMMAND_OUTPUT_STORE.get(cmd)
        print(f" Content: {content}")
        if not content: 
            raise ValueError(f"No output found for command: {cmd}")
        
        result = [] 

        pattern = re.compile(
            r"----\s*(?P<section>[^-]+?)\s*----\s*"
            r"Memory information:\s"
            r"\s*Physical Memory\s*:\s*(?P<physical>[\d.]+)\s*MB\s*"
            r"\s*Free Memory\s*:\s*(?P<free>[\d.]+)\s*MB\s*"
            r"\s*Memory State\s*:\s*(?P<state>\w+)", 
            content, 
            re.MULTILINE
        )

        matches = pattern.finditer(content)

        for match in matches: 
            mem_info = cisco_ncs5501.memoryInfo(
                physicalMem=match.group("physical"), 
                freeMem=match.group("free"), 
                memoryState=match.group("state")
            )

            node_state = cisco_ncs5501.ShowWatchdogMemoryState(
                nodeName=match.group("section").strip(),
                memoryInfo=[mem_info]
            )

            result.append(asdict(node_state))

        output_file = write_json(
            command_name="show_watchdog_memory_state", 
            vendor="cisco",
            model="ncs5501",
            json_data=result,
            json_file_path="precheck_jsons/"
        )
        
        return output_file
    except Exception as e: 
        return {"error": f"Error reading file: {str(e)}"}

def show_ipv4_vrf_all_interface_brief():
    try:
        logger.info("show ipv4 vrf all interface brief")

        cmd = "show ipv4 vrf all interface brief"
        content = COMMAND_OUTPUT_STORE.get(cmd).get("output")
        print(f" Content: {content}")
        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        result = []

        for line in content.splitlines():
            line = line.strip()
            print(f" line: {line}")

            if(
                not line
                or line.startswith("Interface")
            ):
                continue

            cols = re.split(r'\s{2,}', line)
            print(f"cols: {cols}")

            entry = ShowIpv4VrfAllInterfaceBrief(
                interface = cols[0],
                IPAddress = cols[1],
                status = cols[2],
                protocol = cols[3],
                VRFName = cols[4]
            )
            result.append(asdict(entry))
        print(f"result: {result}")

        output_file = write_json(
            command_name="show_ipv4_vrf_all_interface_brief",
            vendor="cisco",
            model="ncs5501",
            json_data=result
            json_file_path="precheck_jsons/"
        )
        return output_file
    except Exception as e:
        return {"error": f"Error reading file: {str(e)}"}

def show_lldp_neighbors():
    try:
        logger.info("show lldp neighbors")

        cmd = "show lldp neighbors"
        content = COMMAND_OUTPUT_STORE.get(cmd).get("output")
        print(f" Content: {content}")
        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        result, neighbors = [], []

        match = re.search(
            r'^Total\sentries\sdisplayed:\s*(?P<count>\d+)',
            content
        )
        total_neighbors = int(match.group("count")) if match else 0


        for line in content.splitlines():
            line = line.strip()
            print(f" line: {line}")

            if(
                not line
                or line.startswith("Capability")
                or line.startswith("(")
                or line.startswith("Device ID")
                or line.startswith("Total")
            ):
                continue

            cols = re.split(r'\s{1,}', line)

            entry = lldpNeighbors(
                deviceId = cols[0],
                localIntf = cols[1],
                holdTime = cols[2],
                capability = cols[3],
                portId = cols[4]
            )
            neighbors.append(asdict(entry))

        result.append(
            {
                "Total entries displayed": total_neighbors,
                "neighbors": neighbors
            }
        )

        output_file = write_json(
            command_name="show_lldp_neighbors",
            vendor="cisco"
            model="ncs5501",
            json_data=result,
            json_file_path="precheck_jsons/"
        )
        return output_file
    except Exception as e:
        return {"error": f"Error reading file: {str(e)}"}

def show_isis_adjacency():
    try:
        logger.info("show isis adjacency")

        cmd = "show isis adjacency"
        content = pre_output.get(cmd).get("output")
        print(f" Content: {content}")
        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        result, adjacencies = [], []

        match = re.search(
            r'^IS-IS\sCOLT\sLevel-(?P<adjacencyLevel>\d+)',
            content
        )
        adjacencyLevel = int(match.group("adjacencyLevel")) if match else 0
        print(f"Adjacency Level: {adjacencyLevel}")

        for line in content.splitlines():
            line = line.strip()
            print(f" line: {line}")

            if(
                not line
                or line.startswith("System")
                or line.startswith("IS-IS")
                or line.startswith("Total")
                or line.startswith("BFD")
            ):
                continue
            
            cols = re.split(r'\s{1,}', line)
            print(f"cols: {cols}")

            entry = ISISAdjacencies(
                systemID = cols[0],
                interface = cols[1],
                SNPA = cols[2],
                state = cols[3],
                hold = cols[4],
                changed = cols[5],
                NSF = cols[6],
                ipv4BFD = cols[7],
                ipv6BFD = cols[8]
            )
            adjacencies.append(asdict(entry))
        print(f"adjacency: {adjacencies}")

        match = re.search(
            r'^Total\s+adjacency\s+count:\s*(?P<adjacencyCount>\d+)',
            content,
            re.MULTILINE
        )

        adjacencyCount = int(match.group("adjacencyCount")) if match else 0 
        print(f"Adjacency count: {adjacencyCount}")

        result.append(
            {
                "ISISColtAdjacencyLevel": adjacencyLevel,
                "adjacencies": adjacencies,
                "totalAdjacency": adjacencyCount
            }
        )
        print(f" result: {result}")

        output_file = write_json(
            command_name="show_isis_adjacencies",
            vendor="cisco",
            model="ncs5501",
            json_data=result,
            json_file_path="precheck_jsons/"
        )
        return output_file
    except Exception as e:
        return {"error": f"Error reading file: {str(e)}"}
                                             
def show_interface_description():
        logger.info("show interface description")
        print("coming")
        cmd = "show interface description"
        content = COMMAND_OUTPUT_STORE.get(cmd).get("output")
        print(f" Content: {content}\n")
        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        result = []

        for line in content.splitlines():
            line = line.strip()
            print(f"Line: {line}")

            if (
                not line
                or line.startswith("Interface")
                or line.startswith("-")
            ):
                continue

            cols = re.split(r'\s{2,}', line)
            print(f"cols: {cols}")

            entry = ShowInterfaceDescription(
                    interface = cols[0],
                    status = cols[1],
                    protocol = cols[2],
                    description = cols[3] if len(cols) > 3 else None
            )

            result.append(asdict(entry))
        print(f"result: {result}")
        output_file = write_json(
            command_name="show_interface_description",
            vendor="cisco",
            model="ncs5501",
            json_data=result,
            json_file_path="precheck_jsons/"
        )
        return output_file


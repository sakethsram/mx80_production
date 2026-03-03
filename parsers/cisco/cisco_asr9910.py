from typing import List, Dict, Any
import re
import sys
from models.cisco.cisco_ncs5501 import *
from models.junos import *
import json
from datetime import datetime
from dataclasses import dataclass, asdict, field
import logging
from lib.utilities import *
import os

logger = logging.getLogger(__name__)


def show_install_active_summary(content) -> Dict[str, Any]:
    """
    Docstring for show_install_active_summary

    :param folder_path: (unused) Kept for signature compatibility. Input comes from global_config.pre_output.
    :type folder_path: str
    :return: JSON-like dict (whatever write_json returns) for 'show install active summary'
    :rtype: Dict[str, Any]
    """
    try:

        cmd = "show install active summary"
        

        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        # Label (optional on some platforms)
        label_match = re.search(r'^\s*Label\s*:\s*(.+?)\s*$', content, flags=re.MULTILINE)
        label = label_match.group(1).strip() if label_match else "Unknown"

        # Active packages count (optional fallback to 0)
        m_count = re.search(r'Active Packages:\s*(?P<count>\d+)', content)
        activePackages = int(m_count.group("count")) if m_count else 0

        # Package lines: lines starting with indentation but not headers
        # Excludes lines beginning with 'Active' or 'Mon' to avoid header bleed
        package_lines = re.findall(
            r'^(?:[ \t]+)(?!Active)(?!Label)(.+\S)',
            content,
            re.MULTILINE
        )
        packages = [line.strip() for line in package_lines if line.strip()]

        # Build result with your field names
        result = [asdict(ShowInstallActiveSummary(
            AcivePackages=activePackages,
            Packages=packages
        ))]

        # Write JSON via your helper


        return result



def show_isis_adjacency(content):
    try:

        cmd = "show isis adjacency"
        if not content:
            raise ValueError(f"No output found for command: {cmd}")

        result, adjacencies = [], []

        match = re.search(
            r'^IS-IS\sCOLT\sLevel-(?P<adjacencyLevel>\d+)',
            content
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

        match = re.search(
            r'^Total\s+adjacency\s+count:\s*(?P<adjacencyCount>\d+)',
            content,
            re.MULTILINE
        )

        adjacencyCount = int(match.group("adjacencyCount")) if match else 0

        result.append(
            {
                "ISISColtAdjacencyLevel": adjacencyLevel,
                "adjacencies": adjacencies,
                "totalAdjacency": adjacencyCount
            }
        )


        return result


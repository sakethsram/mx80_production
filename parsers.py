
# ────────────────────────────────────────────────────────────────────────────────
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

        summary_match = re.search(r'(\d+)\s+sessions?,\s+(\d+)\s+clients?', text_content)
        if summary_match:
            result.total_sessions = int(summary_match.group(1))
            result.total_clients = int(summary_match.group(2))

        return asdict(result)
    except Exception as e:
        return {"error": f"Error parsing {cmd}: {str(e)}"}


# ────────────────────────────────────────────────────────────────────────────────
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


# ────────────────────────────────────────────────────────────────────────────────
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
            result.ingress_up = int(ingress_total.group(2))
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
                result.egress_up = int(egress_total.group(2))
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

        transit_pattern = r'(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)\s+(\w+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(.+)$'

        if 'Transit RSVP:' in text_content:
            transit_section = text_content.split('Transit RSVP:')[1]
            for match in re.finditer(transit_pattern, transit_section, re.MULTILINE):
                entry = RsvpSessionTransitEntry(
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

        if 'Transit RSVP:' in text_content:
            transit_section_text = text_content.split('Transit RSVP:')[1]
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


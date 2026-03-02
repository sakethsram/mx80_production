import re
import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Any

# ─────────────────────────────────────────────────────────────
# 1. Parser: show system processes extensive | match rpd | no-more
# ─────────────────────────────────────────────────────────────

# Mock input data (exactly as you provided)
# ─────────────────────────────────────────────────────────────
MOCK_RPD = """18648 root 20 0 1176M 272M kqread 3 0:10 0.00% rpd{rpd}
18701 root 20 0 958M 153M kqread 3 0:05 0.00% rpd{TraceThread}
18700 root 20 0 954M 152M kqread 0 0:05 0.00% rpd{TraceThread}
18702 root 20 0 946M 149M kqread 0 0:05 0.00% rpd{TraceThread}
18648 root 20 0 1176M 272M kqread 4 0:04 0.00% rpd{TraceThread}
18700 root 20 0 954M 152M kqread 3 0:03 0.00% rpd{rpd}
18701 root 20 0 958M 153M kqread 3 0:03 0.00% rpd{rpd}
18702 root 20 0 946M 149M kqread 4 0:03 0.00% rpd{rpd}
18648 root 20 0 1176M 272M kqread 3 0:01 0.00% rpd{rsvp-io}
18648 root 20 0 1176M 272M kqread 1 0:00 0.00% rpd{bgpio-0-th}
18697 root 20 0 799M 14M kqread 3 0:00 0.00% rpdtmd
18648 root 20 0 1176M 272M kqread 2 0:00 0.00% rpd{krtio-th}"""

MOCK_DOWN_RSVP = """109.74.16.10 0.0.0.0 Dn 0 - EFF01-BME01
109.74.16.2 0.0.0.0 Dn 0 - EFF01-IXL01"""

MOCK_LOG_MESSAGES = """Mar 2 13:41:22.927 EFFPER01 rpd[18648]: JTASK_IO_CONNECT_FAILED: BGP_8220.10.10.101.2: Connecting to 10.10.101.2+179 failed: Can't assign requested address
Mar 2 13:41:22.928 EFFPER01 rpd[18648]: BGP_CONNECT_FAILED: bgp_connect_start: connect 10.10.101.2 (Internal AS 8220) (instance CUST-C10A1-UCAST-inside-EFF01): Can't assign requested address
Mar 2 13:41:29.781 EFFPER01 rpd[18648]: bgp_pp_recv:5726: NOTIFICATION sent to 10.10.104.2+60671 (proto): code 6 (Cease) subcode 5 (Connection Rejected), Reason: no group for 10.10.104.2+60671 (proto) from AS 8220 found (Unconfigured Peer) in master(ae0.104), dropping him
Mar 2 13:41:30.923 EFFPER01 rpd[18648]: JTASK_IO_CONNECT_FAILED: BGP_8220.172.16.172.2: Connecting to 172.16.172.2+179 failed: Can't assign requested address
Mar 2 13:41:30.923 EFFPER01 rpd[18648]: BGP_CONNECT_FAILED: bgp_connect_start: connect 172.16.172.2 (Internal AS 8220) (instance PROV-P3A1-UCAST-inside-EFF01): Can't assign requested address
Mar 2 13:41:34.929 EFFPER01 rpd[18648]: JTASK_IO_CONNECT_FAILED: BGP_8220.10.10.11.2: Connecting to 10.10.11.2+179 failed: Can't assign requested address"""

MOCK_INTERFACES_TERSE = """Interface       Admin Link Proto    Local                 Remote
gr-0/0/0        up    up
ip-0/0/0        up    up
lc-0/0/0        up    up
lc-0/0/0.32769  up    up   vpls
lt-0/0/0        up    up
lt-0/0/0.11     up    up   inet     10.0.0.176/31
lt-0/0/0.12     up    up   inet     10.0.0.177/31
xe-0/0/0:1.2000 up    up   inet     172.17.20.9/30
et-0/0/2.20     up    up   inet     100.96.112.46/31
lo0.0           up    up   inet     194.180.107.5         --> 0/0
ae0.1           up    up   inet     100.70.48.2/30"""


# ─────────────────────────────────────────────────────────────
# Main function - runs all four parsers on the mock data
# ─────────────────────────────────────────────────────────────
def main():
    results = {}

    # 1. rpd processes
    results["show system processes extensive | match rpd | no-more"] = \
        parse_show_system_processes_rpd_match(MOCK_RPD)

    # 2. down rsvp / lsp
    results["show rsvp session | match DN | no-more"] = \
        parse_show_down_lsp_or_session(MOCK_DOWN_RSVP)

    # 3. log messages
    results["show log messages | last 200 | no-more"] = \
        parse_show_log_messages_last_200(MOCK_LOG_MESSAGES)

    # 4. interfaces terse
    results["show interfaces terse | no-more"] = \
        parse_show_interfaces_terse(MOCK_INTERFACES_TERSE)

    # Print all results in JSON
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
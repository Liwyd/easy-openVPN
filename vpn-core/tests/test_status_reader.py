"""Unit tests for vpn_core.status_reader — parsing `status 2` output.

Pure-string parsing tests; no real OpenVPN server or management socket
required.  The sample payloads mirror real `status 2` output across
OpenVPN versions (2.3 vs 2.4+ column layouts).
"""

from __future__ import annotations

from vpn_core.status_reader import _parse_status

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _modern_status() -> str:
    """`status 2` payload from OpenVPN 2.4+ (includes Virtual IPv6 column)."""
    return """TITLE,OpenVPN 2.6.8
TIME,2024-03-21 14:30:00,1711031400
HEADER,CLIENT_LIST,Common Name,Real Address,Virtual Address,Virtual IPv6 Address,Bytes Received,Bytes Sent,Connected Since,Connected Since (time_t),Username,Client ID,Peer ID,Data Channel Cipher
CLIENT_LIST,peer1,203.0.113.10:52841,10.8.0.6,,1548576,984320,2024-03-21 09:15:00,1711012500,UNDEF,0,0,AES-256-GCM
CLIENT_LIST,peer2,203.0.113.20:9999,10.8.0.7,2001:db8::1,500,700,2024-03-21 10:00:00,1711015200,UNDEF,1,1,AES-256-GCM
HEADER,ROUTING_TABLE,Virtual Address,Common Name,Real Address,Last Ref,Last Ref (time_t)
ROUTING_TABLE,10.8.0.6,peer1,203.0.113.10:52841,2024-03-21 14:29:50,1711031390
ROUTING_TABLE,10.8.0.7,peer2,203.0.113.20:9999,2024-03-21 14:29:55,1711031395
GLOBAL_STATS,Max bcast/mcast queue length,3
END
"""


def _legacy_status() -> str:
    """`status 2` payload from OpenVPN 2.3 (no Virtual IPv6 column)."""
    return """TITLE,OpenVPN 2.3.18
TIME,2016-12-31 15:06:04,1483193164
HEADER,CLIENT_LIST,Common Name,Real Address,Virtual Address,Bytes Received,Bytes Sent,Connected Since,Connected Since (time_t),Username,Client ID,Peer ID
CLIENT_LIST,ntafs,133.2.11.3,10.1.1.8,521679042,155407560,Fri Dec 30 13:41:11 2016,1483101671,UNDEF,0,0
HEADER,ROUTING_TABLE,Virtual Address,Common Name,Real Address,Last Ref,Last Ref (time_t)
ROUTING_TABLE,10.1.1.8,ntafs,133.2.11.3,Sat Dec 31 15:06:04 2016,1483193164
GLOBAL_STATS,Max bcast/mcast queue length,2
END
"""


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

class TestParseModernStatus:
    """Modern (2.4+) `status 2` payloads."""

    def test_parses_all_clients(self):
        clients = _parse_status(_modern_status())
        assert len(clients) == 2

    def test_client_fields_populated(self):
        clients = _parse_status(_modern_status())
        peer1, peer2 = clients

        assert peer1.common_name == "peer1"
        assert peer1.real_address == "203.0.113.10:52841"
        assert peer1.bytes_received == 1548576
        assert peer1.bytes_sent == 984320
        assert peer1.connected_since == "2024-03-21 09:15:00"

        assert peer2.common_name == "peer2"
        assert peer2.bytes_received == 500
        assert peer2.bytes_sent == 700


class TestParseLegacyStatus:
    """Older (2.3) `status 2` payloads without the IPv6 column."""

    def test_parses_client_without_ipv6_column(self):
        clients = _parse_status(_legacy_status())
        assert len(clients) == 1
        client = clients[0]

        assert client.common_name == "ntafs"
        assert client.real_address == "133.2.11.3"
        assert client.bytes_received == 521679042
        assert client.bytes_sent == 155407560
        assert client.connected_since == "Fri Dec 30 13:41:11 2016"


class TestParseEdgeCases:
    """Empty, malformed, or minimal `status 2` payloads."""

    def test_empty_payload(self):
        assert _parse_status("") == []

    def test_no_clients_connected(self):
        payload = """TITLE,OpenVPN 2.6.8
TIME,2024-03-21 14:30:00,1711031400
HEADER,CLIENT_LIST,Common Name,Real Address,Virtual Address,Virtual IPv6 Address,Bytes Received,Bytes Sent,Connected Since,Connected Since (time_t),Username,Client ID,Peer ID,Data Channel Cipher
HEADER,ROUTING_TABLE,Virtual Address,Common Name,Real Address,Last Ref,Last Ref (time_t)
GLOBAL_STATS,Max bcast/mcast queue length,0
END
"""
        assert _parse_status(payload) == []

    def test_truncated_data_row_skipped(self):
        # Data row missing byte-counter columns — parser must not crash
        payload = """TITLE,OpenVPN 2.6.8
HEADER,CLIENT_LIST,Common Name,Real Address,Virtual Address,Virtual IPv6 Address,Bytes Received,Bytes Sent,Connected Since,Connected Since (time_t),Username,Client ID,Peer ID,Data Channel Cipher
CLIENT_LIST,partial
END
"""
        assert _parse_status(payload) == []

    def test_malformed_bytes_values_default_to_zero(self):
        payload = """TITLE,OpenVPN 2.6.8
HEADER,CLIENT_LIST,Common Name,Real Address,Virtual Address,Virtual IPv6 Address,Bytes Received,Bytes Sent,Connected Since,Connected Since (time_t),Username,Client ID,Peer ID,Data Channel Cipher
CLIENT_LIST,weird,1.2.3.4:5,10.8.0.9,,not-a-number,also-bad,2024-03-21 09:15:00,1711012500,UNDEF,0,0,AES-256-GCM
END
"""
        clients = _parse_status(payload)
        assert len(clients) == 1
        assert clients[0].bytes_received == 0
        assert clients[0].bytes_sent == 0

    def test_ignores_routing_table_rows(self):
        # ROUTING_TABLE rows are not clients and must not be parsed
        clients = _parse_status(_modern_status())
        assert all(c.common_name != "10.8.0.6" for c in clients)

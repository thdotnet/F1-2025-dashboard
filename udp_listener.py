"""
F1 UDP Protocol - receives and parses F1 2025 telemetry packets.
"""

import asyncio
import logging
import time
from typing import Any, Dict

from packets import PacketParser

logger = logging.getLogger("f1dashboard.udp")


class F1UDPProtocol(asyncio.DatagramProtocol):
    """Async UDP protocol handler for F1 telemetry packets."""

    def __init__(self, parser: PacketParser, telemetry_state: Dict[str, Any], recorder):
        self.parser = parser
        self.telemetry_state = telemetry_state
        self.recorder = recorder
        self.packet_count = 0
        self.error_count = 0

    def connection_made(self, transport):
        logger.info("UDP listener ready")

    def datagram_received(self, data: bytes, addr):
        self.packet_count += 1
        result = self.parser.parse(data)
        if result:
            packet_type, parsed = result
            self.telemetry_state[packet_type] = parsed
            self.telemetry_state["connected"] = True
            self.telemetry_state["last_packet_time"] = time.time()

            # Record to session file
            header = parsed.get("session_time")
            if header is not None:
                session_uid = self.parser.parse_header(data)
                if session_uid:
                    self.recorder.record(str(session_uid["session_uid"]), self.telemetry_state)

    def error_received(self, exc):
        self.error_count += 1
        logger.error("UDP error: %s", exc)


async def start_udp_listener(config: Dict[str, Any], telemetry_state: Dict[str, Any], recorder):
    """Start the async UDP listener."""
    parser = PacketParser(num_cars=config["telemetry"]["num_cars"])
    loop = asyncio.get_running_loop()

    udp_host = config["udp"]["host"]
    udp_port = config["udp"]["port"]

    transport, protocol = await loop.create_datagram_endpoint(
        lambda: F1UDPProtocol(parser, telemetry_state, recorder),
        local_addr=(udp_host, udp_port),
    )
    logger.info("UDP listener started on %s:%d", udp_host, udp_port)
    return transport, protocol

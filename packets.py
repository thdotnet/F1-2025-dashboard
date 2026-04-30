"""
F1 2025 UDP Telemetry Packet Parser.

Parses binary UDP packets from the EA Sports F1 2025 game into dictionaries.
"""

import struct
import logging
from typing import Dict, Any, Optional, Tuple

from packet_definitions import (
    PACKET_MOTION, PACKET_SESSION, PACKET_LAP_DATA,
    PACKET_CAR_TELEMETRY, PACKET_CAR_STATUS, PACKET_NAMES,
    HEADER_FORMAT, HEADER_SIZE, HEADER_FIELDS,
    CAR_TELEMETRY_FORMAT, CAR_TELEMETRY_SIZE, CAR_TELEMETRY_FIELDS,
    TELEMETRY_EXTRA_FORMAT, TELEMETRY_EXTRA_FIELDS,
    CAR_MOTION_FORMAT, CAR_MOTION_SIZE, CAR_MOTION_FIELDS,
    LAP_DATA_FORMAT, LAP_DATA_SIZE, LAP_DATA_FIELDS,
    CAR_STATUS_FORMAT, CAR_STATUS_SIZE, CAR_STATUS_FIELDS,
    TYRE_COMPOUNDS, VISUAL_TYRE_COMPOUNDS,
    WEATHER_TYPES, SESSION_TYPES, TRACK_IDS,
)

logger = logging.getLogger(__name__)


class PacketParser:
    """Parses F1 UDP telemetry packets from raw binary data."""

    def __init__(self, num_cars: int = 22):
        self.num_cars = num_cars
        # Pre-compile struct objects for performance
        self._header_struct = struct.Struct(HEADER_FORMAT)
        self._car_telemetry_struct = struct.Struct(CAR_TELEMETRY_FORMAT)
        self._car_motion_struct = struct.Struct(CAR_MOTION_FORMAT)
        self._lap_data_struct = struct.Struct(LAP_DATA_FORMAT)
        self._car_status_struct = struct.Struct(CAR_STATUS_FORMAT)
        self._telemetry_extra_struct = struct.Struct(TELEMETRY_EXTRA_FORMAT)

    def parse_header(self, data: bytes) -> Optional[Dict[str, Any]]:
        """Parse packet header. Returns None if data is too short."""
        if len(data) < HEADER_SIZE:
            return None
        values = self._header_struct.unpack_from(data, 0)
        return dict(zip(HEADER_FIELDS, values))

    def parse(self, data: bytes) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Parse a complete packet. Returns (packet_type_name, parsed_data) or None.
        Only parses packet types we use for the dashboard.
        """
        header = self.parse_header(data)
        if header is None:
            return None

        packet_id = header["packet_id"]
        player_idx = header["player_car_index"]

        try:
            if packet_id == PACKET_CAR_TELEMETRY:
                return ("telemetry", self._parse_car_telemetry(data, header, player_idx))
            elif packet_id == PACKET_MOTION:
                return ("motion", self._parse_motion(data, header, player_idx))
            elif packet_id == PACKET_LAP_DATA:
                return ("lap_data", self._parse_lap_data(data, header, player_idx))
            elif packet_id == PACKET_CAR_STATUS:
                return ("car_status", self._parse_car_status(data, header, player_idx))
            elif packet_id == PACKET_SESSION:
                return ("session", self._parse_session(data, header))
            else:
                return None
        except struct.error as e:
            logger.warning(
                "Failed to parse %s packet: %s (data length: %d)",
                PACKET_NAMES.get(packet_id, f"Unknown({packet_id})"),
                e,
                len(data),
            )
            return None

    def _parse_car_data(
        self, data: bytes, offset: int, car_struct: struct.Struct,
        fields: list, car_index: int
    ) -> Dict[str, Any]:
        """Parse a single car's data from an array of car structs."""
        car_offset = offset + (car_index * car_struct.size)
        values = car_struct.unpack_from(data, car_offset)
        return dict(zip(fields, values))

    def _parse_car_telemetry(
        self, data: bytes, header: Dict, player_idx: int
    ) -> Dict[str, Any]:
        offset = HEADER_SIZE
        player = self._parse_car_data(
            data, offset, self._car_telemetry_struct,
            CAR_TELEMETRY_FIELDS, player_idx
        )

        # Parse extra packet-level fields if data is long enough
        extra_offset = offset + (self.num_cars * CAR_TELEMETRY_SIZE)
        if len(data) >= extra_offset + self._telemetry_extra_struct.size:
            extra_values = self._telemetry_extra_struct.unpack_from(data, extra_offset)
            extra = dict(zip(TELEMETRY_EXTRA_FIELDS, extra_values))
            player.update(extra)

        player["session_time"] = header["session_time"]
        return player

    def _parse_motion(
        self, data: bytes, header: Dict, player_idx: int
    ) -> Dict[str, Any]:
        offset = HEADER_SIZE
        max_cars = min(self.num_cars, (len(data) - offset) // CAR_MOTION_SIZE)

        if player_idx < max_cars:
            player = self._parse_car_data(
                data, offset, self._car_motion_struct,
                CAR_MOTION_FIELDS, player_idx
            )
        else:
            player = dict.fromkeys(CAR_MOTION_FIELDS, 0.0)

        # All cars positions for the track map
        all_positions = []
        for i in range(max_cars):
            try:
                car_offset = offset + (i * CAR_MOTION_SIZE)
                values = self._car_motion_struct.unpack_from(data, car_offset)
                car = dict(zip(CAR_MOTION_FIELDS, values))
                if car["world_position_x"] != 0 or car["world_position_z"] != 0:
                    all_positions.append({
                        "index": i,
                        "x": round(car["world_position_x"], 1),
                        "z": round(car["world_position_z"], 1),
                        "is_player": i == player_idx,
                    })
            except struct.error:
                break

        player["all_car_positions"] = all_positions
        player["session_time"] = header["session_time"]
        return player

    def _parse_lap_data(
        self, data: bytes, header: Dict, player_idx: int
    ) -> Dict[str, Any]:
        offset = HEADER_SIZE
        player = self._parse_car_data(
            data, offset, self._lap_data_struct,
            LAP_DATA_FIELDS, player_idx
        )
        player["session_time"] = header["session_time"]

        # Combine ms + minutes parts into total milliseconds for deltas
        player["delta_to_car_in_front_ms"] = (
            player["delta_to_car_in_front_minutes"] * 60000
            + player["delta_to_car_in_front_ms"]
        )
        player["delta_to_race_leader_ms"] = (
            player["delta_to_race_leader_minutes"] * 60000
            + player["delta_to_race_leader_ms"]
        )

        # Format time values for display
        if player["last_lap_time_ms"] > 0:
            player["last_lap_time_str"] = self._format_time(player["last_lap_time_ms"])
        else:
            player["last_lap_time_str"] = "--:--:---"

        if player["current_lap_time_ms"] > 0:
            player["current_lap_time_str"] = self._format_time(player["current_lap_time_ms"])
        else:
            player["current_lap_time_str"] = "0:00.000"

        return player

    def _parse_car_status(
        self, data: bytes, header: Dict, player_idx: int
    ) -> Dict[str, Any]:
        offset = HEADER_SIZE
        player = self._parse_car_data(
            data, offset, self._car_status_struct,
            CAR_STATUS_FIELDS, player_idx
        )
        player["session_time"] = header["session_time"]

        # Resolve tyre compound names
        actual = player.get("actual_tyre_compound", 0)
        visual = player.get("visual_tyre_compound", 0)
        player["tyre_compound_name"] = TYRE_COMPOUNDS.get(actual, f"Unknown({actual})")
        player["visual_tyre_name"] = VISUAL_TYRE_COMPOUNDS.get(visual, f"Unknown({visual})")

        # ERS energy as percentage (max ~4MJ = 4,000,000 J)
        ers_energy = player.get("ers_store_energy", 0)
        player["ers_percent"] = min(100, round((ers_energy / 4_000_000) * 100, 1))

        return player

    def _parse_session(self, data: bytes, header: Dict) -> Dict[str, Any]:
        """Parse session data (weather, track, etc.). Partial parse of key fields."""
        offset = HEADER_SIZE
        try:
            weather = struct.unpack_from("<B", data, offset)[0]
            track_temp = struct.unpack_from("<b", data, offset + 1)[0]
            air_temp = struct.unpack_from("<b", data, offset + 2)[0]
            total_laps = struct.unpack_from("<B", data, offset + 3)[0]
            track_length = struct.unpack_from("<H", data, offset + 4)[0]
            session_type = struct.unpack_from("<B", data, offset + 6)[0]
            track_id = struct.unpack_from("<b", data, offset + 7)[0]

            return {
                "weather": weather,
                "weather_name": WEATHER_TYPES.get(weather, f"Unknown({weather})"),
                "track_temperature": track_temp,
                "air_temperature": air_temp,
                "total_laps": total_laps,
                "track_length": track_length,
                "session_type": session_type,
                "session_type_name": SESSION_TYPES.get(session_type, f"Unknown({session_type})"),
                "track_id": track_id,
                "track_name": TRACK_IDS.get(track_id, f"Unknown({track_id})"),
                "session_time": header["session_time"],
            }
        except struct.error as e:
            logger.warning("Failed to parse session data: %s", e)
            return {"session_time": header["session_time"]}

    @staticmethod
    def _format_time(ms: int) -> str:
        """Format milliseconds to M:SS.mmm"""
        minutes = ms // 60000
        seconds = (ms % 60000) / 1000
        return f"{minutes}:{seconds:06.3f}"

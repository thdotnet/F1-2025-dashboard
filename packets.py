"""
F1 2025 UDP Telemetry Packet Definitions and Parser.

Based on the EA Sports F1 24/25 UDP specification.
Packet structures are defined as struct format strings for efficient binary parsing.
"""

import struct
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Packet IDs
# ---------------------------------------------------------------------------
PACKET_MOTION = 0
PACKET_SESSION = 1
PACKET_LAP_DATA = 2
PACKET_EVENT = 3
PACKET_PARTICIPANTS = 4
PACKET_CAR_SETUPS = 5
PACKET_CAR_TELEMETRY = 6
PACKET_CAR_STATUS = 7
PACKET_FINAL_CLASSIFICATION = 8
PACKET_LOBBY_INFO = 9
PACKET_CAR_DAMAGE = 10
PACKET_SESSION_HISTORY = 11
PACKET_TYRE_SETS = 12
PACKET_MOTION_EX = 13

PACKET_NAMES = {
    PACKET_MOTION: "Motion",
    PACKET_SESSION: "Session",
    PACKET_LAP_DATA: "LapData",
    PACKET_EVENT: "Event",
    PACKET_PARTICIPANTS: "Participants",
    PACKET_CAR_SETUPS: "CarSetups",
    PACKET_CAR_TELEMETRY: "CarTelemetry",
    PACKET_CAR_STATUS: "CarStatus",
    PACKET_FINAL_CLASSIFICATION: "FinalClassification",
    PACKET_LOBBY_INFO: "LobbyInfo",
    PACKET_CAR_DAMAGE: "CarDamage",
    PACKET_SESSION_HISTORY: "SessionHistory",
    PACKET_TYRE_SETS: "TyreSets",
    PACKET_MOTION_EX: "MotionEx",
}

# ---------------------------------------------------------------------------
# Header (common to all packets) - 29 bytes
# ---------------------------------------------------------------------------
HEADER_FORMAT = "<HBBBBBQfIIBB"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 29 bytes

HEADER_FIELDS = [
    "packet_format",            # uint16 - e.g. 2025
    "game_year",                # uint8  - e.g. 25
    "game_major_version",       # uint8
    "game_minor_version",       # uint8
    "packet_version",           # uint8
    "packet_id",                # uint8
    "session_uid",              # uint64
    "session_time",             # float
    "frame_identifier",         # uint32
    "overall_frame_identifier", # uint32
    "player_car_index",         # uint8
    "secondary_player_car_index",  # uint8
]

# ---------------------------------------------------------------------------
# CarTelemetryData (per car) - 60 bytes
# ---------------------------------------------------------------------------
CAR_TELEMETRY_FORMAT = "<HfffBbHBBH4H4B4BH4f4B"
CAR_TELEMETRY_SIZE = struct.calcsize(CAR_TELEMETRY_FORMAT)

CAR_TELEMETRY_FIELDS = [
    "speed",                    # uint16 - km/h
    "throttle",                 # float  - 0.0 to 1.0
    "steer",                    # float  - -1.0 (left) to 1.0 (right)
    "brake",                    # float  - 0.0 to 1.0
    "clutch",                   # uint8  - 0 to 100
    "gear",                     # int8   - 1-8, N=0, R=-1
    "engine_rpm",               # uint16
    "drs",                      # uint8  - 0=off, 1=on
    "rev_lights_percent",       # uint8  - 0-100
    "rev_lights_bit_value",     # uint16
    "brakes_temp_rl",           # uint16 - Rear Left
    "brakes_temp_rr",           # uint16 - Rear Right
    "brakes_temp_fl",           # uint16 - Front Left
    "brakes_temp_fr",           # uint16 - Front Right
    "tyres_surface_temp_rl",    # uint8
    "tyres_surface_temp_rr",    # uint8
    "tyres_surface_temp_fl",    # uint8
    "tyres_surface_temp_fr",    # uint8
    "tyres_inner_temp_rl",      # uint8
    "tyres_inner_temp_rr",      # uint8
    "tyres_inner_temp_fl",      # uint8
    "tyres_inner_temp_fr",      # uint8
    "engine_temperature",       # uint16
    "tyres_pressure_rl",        # float - PSI
    "tyres_pressure_rr",        # float
    "tyres_pressure_fl",        # float
    "tyres_pressure_fr",        # float
    "surface_type_rl",          # uint8
    "surface_type_rr",          # uint8
    "surface_type_fl",          # uint8
    "surface_type_fr",          # uint8
]

# Packet-level extra fields after the 22 car entries
TELEMETRY_EXTRA_FORMAT = "<BBb"
TELEMETRY_EXTRA_FIELDS = [
    "mfd_panel_index",
    "mfd_panel_index_secondary",
    "suggested_gear",
]

# ---------------------------------------------------------------------------
# CarMotionData (per car) - 72 bytes (18 floats)
# ---------------------------------------------------------------------------
CAR_MOTION_FORMAT = "<18f"
CAR_MOTION_SIZE = struct.calcsize(CAR_MOTION_FORMAT)

CAR_MOTION_FIELDS = [
    "world_position_x",
    "world_position_y",
    "world_position_z",
    "world_velocity_x",
    "world_velocity_y",
    "world_velocity_z",
    "world_forward_dir_x",
    "world_forward_dir_y",
    "world_forward_dir_z",
    "world_right_dir_x",
    "world_right_dir_y",
    "world_right_dir_z",
    "g_force_lateral",
    "g_force_longitudinal",
    "g_force_vertical",
    "yaw",
    "pitch",
    "roll",
]

# ---------------------------------------------------------------------------
# LapData (per car) - ~50 bytes
# ---------------------------------------------------------------------------
LAP_DATA_FORMAT = "<IIHHHHHHfBBBBBBBBBBBBBBBHHBfB"
LAP_DATA_SIZE = struct.calcsize(LAP_DATA_FORMAT)

LAP_DATA_FIELDS = [
    "last_lap_time_ms",
    "current_lap_time_ms",
    "sector1_time_ms",
    "sector1_time_minutes",
    "sector2_time_ms",
    "sector2_time_minutes",
    "delta_to_car_in_front_ms",
    "delta_to_race_leader_ms",
    "safety_car_delta",
    "car_position",
    "current_lap_num",
    "pit_status",
    "num_pit_stops",
    "sector",
    "current_lap_invalid",
    "penalties",
    "total_warnings",
    "corner_cutting_warnings",
    "num_unserved_drive_through_pens",
    "num_unserved_stop_go_pens",
    "grid_position",
    "driver_status",
    "result_status",
    "pit_lane_timer_active",
    "pit_lane_time_in_lane_ms",
    "pit_stop_timer_ms",
    "pit_stop_should_serve_pen",
    "speed_trap_fastest_speed",
    "speed_trap_fastest_lap",
]

# ---------------------------------------------------------------------------
# CarStatusData (per car)
# ---------------------------------------------------------------------------
CAR_STATUS_FORMAT = "<BBBBBfffHHBBHBBBbfffBfffB"
CAR_STATUS_SIZE = struct.calcsize(CAR_STATUS_FORMAT)

CAR_STATUS_FIELDS = [
    "traction_control",
    "anti_lock_brakes",
    "fuel_mix",
    "front_brake_bias",
    "pit_limiter_status",
    "fuel_in_tank",
    "fuel_capacity",
    "fuel_remaining_laps",
    "max_rpm",
    "idle_rpm",
    "max_gears",
    "drs_allowed",
    "drs_activation_distance",
    "actual_tyre_compound",
    "visual_tyre_compound",
    "tyres_age_laps",
    "vehicle_fia_flags",
    "engine_power_ice",
    "engine_power_mguk",
    "ers_store_energy",
    "ers_deploy_mode",
    "ers_harvested_this_lap_mguk",
    "ers_harvested_this_lap_mguh",
    "ers_deployed_this_lap",
    "network_paused",
]

# ---------------------------------------------------------------------------
# SessionData (partial - key fields)
# ---------------------------------------------------------------------------
SESSION_PARTIAL_FORMAT = "<BbbBBBHHBBiBBBBBBB"
SESSION_PARTIAL_SIZE = struct.calcsize(SESSION_PARTIAL_FORMAT)

SESSION_PARTIAL_FIELDS = [
    "weather",
    "track_temperature",
    "air_temperature",
    "total_laps",
    "track_length_unknown",  # placeholder
    "session_type",
    "track_id",
    "formula",
    "session_time_left",
    "session_duration",
    "pit_speed_limit",
    "game_paused",
    "is_spectating",
    "spectator_car_index",
    "sli_pro_native_support",
    "num_marshal_zones",
    "safety_car_status",
    "network_game",
]

# ---------------------------------------------------------------------------
# Tyre compound mapping
# ---------------------------------------------------------------------------
TYRE_COMPOUNDS = {
    16: "C5 (Softest)",
    17: "C4",
    18: "C3",
    19: "C2",
    20: "C1 (Hardest)",
    7: "Inter",
    8: "Wet",
}

VISUAL_TYRE_COMPOUNDS = {
    16: "Soft",
    17: "Medium",
    18: "Hard",
    7: "Inter",
    8: "Wet",
}

WEATHER_TYPES = {
    0: "Clear",
    1: "Light Cloud",
    2: "Overcast",
    3: "Light Rain",
    4: "Heavy Rain",
    5: "Storm",
}

SESSION_TYPES = {
    0: "Unknown",
    1: "P1",
    2: "P2",
    3: "P3",
    4: "Short Practice",
    5: "Q1",
    6: "Q2",
    7: "Q3",
    8: "Short Qualifying",
    9: "OSQ",
    10: "R",
    11: "R2",
    12: "R3",
    13: "Time Trial",
}

TRACK_IDS = {
    0: "Melbourne",
    1: "Paul Ricard",
    2: "Shanghai",
    3: "Sakhir",
    4: "Catalunya",
    5: "Monaco",
    6: "Montreal",
    7: "Silverstone",
    8: "Hockenheim",
    9: "Hungaroring",
    10: "Spa",
    11: "Monza",
    12: "Singapore",
    13: "Suzuka",
    14: "Abu Dhabi",
    15: "Texas",
    16: "Brazil",
    17: "Austria",
    18: "Sochi",
    19: "Mexico",
    20: "Baku",
    21: "Sakhir Short",
    22: "Silverstone Short",
    23: "Texas Short",
    24: "Suzuka Short",
    25: "Hanoi",
    26: "Zandvoort",
    27: "Imola",
    28: "Portimao",
    29: "Jeddah",
    30: "Miami",
    31: "Las Vegas",
    32: "Losail",
}


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
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

        # Player car data
        player = self._parse_car_data(
            data, offset, self._car_motion_struct,
            CAR_MOTION_FIELDS, player_idx
        )

        # All cars positions for the track map
        all_positions = []
        for i in range(self.num_cars):
            try:
                car_offset = offset + (i * CAR_MOTION_SIZE)
                values = self._car_motion_struct.unpack_from(data, car_offset)
                car = dict(zip(CAR_MOTION_FIELDS, values))
                # Only include cars with non-zero positions (active cars)
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
            # The session packet has a complex structure; parse the first block
            weather = struct.unpack_from("<B", data, offset)[0]
            track_temp = struct.unpack_from("<b", data, offset + 1)[0]
            air_temp = struct.unpack_from("<b", data, offset + 2)[0]
            total_laps = struct.unpack_from("<B", data, offset + 3)[0]
            # track_length is at offset+4 as uint16
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

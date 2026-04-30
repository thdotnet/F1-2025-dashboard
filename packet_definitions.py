"""
F1 2025 UDP Telemetry Packet Definitions.

Struct format strings, field names, and lookup tables for EA Sports F1 2025 packets.
"""

import struct

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
# CarMotionData (per car) - 60 bytes
# 6 floats (position + velocity) + 6 int16 (forward + right dirs) + 6 floats (g-force + rotation)
# ---------------------------------------------------------------------------
CAR_MOTION_FORMAT = "<6f6h6f"
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
# LapData (per car) - 57 bytes
# ---------------------------------------------------------------------------
LAP_DATA_FORMAT = "<IIHBHBHBHBfffBBBBBBBBBBBBBBBHHBfB"
LAP_DATA_SIZE = struct.calcsize(LAP_DATA_FORMAT)

LAP_DATA_FIELDS = [
    "last_lap_time_ms",
    "current_lap_time_ms",
    "sector1_time_ms",
    "sector1_time_minutes",
    "sector2_time_ms",
    "sector2_time_minutes",
    "delta_to_car_in_front_ms",
    "delta_to_car_in_front_minutes",
    "delta_to_race_leader_ms",
    "delta_to_race_leader_minutes",
    "lap_distance",
    "total_distance",
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
# Lookup Tables
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

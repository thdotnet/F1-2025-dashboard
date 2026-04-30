"""
Session Recorder - persists telemetry data to JSON/JSONL files.

One file per game session, with efficient append-only writes.
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("f1dashboard.recorder")


class SessionRecorder:
    """Records telemetry data to JSON files, one file per game session."""

    def __init__(self, cfg: Dict[str, Any]):
        storage_cfg = cfg.get("storage", {})
        self.enabled = storage_cfg.get("enabled", True)
        self.data_dir = Path(storage_cfg.get("data_dir", "data"))
        self.flush_interval = storage_cfg.get("flush_interval_seconds", 5)
        self.sample_rate = storage_cfg.get("sample_rate_hz", 4)
        self.sample_interval = 1.0 / self.sample_rate

        self._current_session_uid: Optional[str] = None
        self._session_file: Optional[Path] = None
        self._samples: List[Dict[str, Any]] = []
        self._session_meta: Dict[str, Any] = {}
        self._last_sample_time: float = 0
        self._total_samples: int = 0

        if self.enabled:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Session recorder enabled → %s", self.data_dir.resolve())

    def record(self, session_uid: str, state: Dict[str, Any]):
        """Record a telemetry snapshot if enough time has elapsed."""
        if not self.enabled:
            return

        now = time.time()

        # Detect new session
        if session_uid and session_uid != self._current_session_uid:
            self._start_new_session(session_uid, state)

        # Sample at configured rate
        if now - self._last_sample_time < self.sample_interval:
            return

        self._last_sample_time = now

        # Build a compact snapshot
        snapshot = {"t": round(state.get("telemetry", {}).get("session_time", 0), 3)}

        tel = state.get("telemetry", {})
        if tel:
            snapshot["tel"] = {
                "speed": tel.get("speed", 0),
                "throttle": round(tel.get("throttle", 0), 3),
                "brake": round(tel.get("brake", 0), 3),
                "steer": round(tel.get("steer", 0), 3),
                "gear": tel.get("gear", 0),
                "rpm": tel.get("engine_rpm", 0),
                "drs": tel.get("drs", 0),
                "engine_temp": tel.get("engine_temperature", 0),
                "brakes_temp": [
                    tel.get("brakes_temp_rl", 0), tel.get("brakes_temp_rr", 0),
                    tel.get("brakes_temp_fl", 0), tel.get("brakes_temp_fr", 0),
                ],
                "tyres_inner": [
                    tel.get("tyres_inner_temp_rl", 0), tel.get("tyres_inner_temp_rr", 0),
                    tel.get("tyres_inner_temp_fl", 0), tel.get("tyres_inner_temp_fr", 0),
                ],
                "tyres_surface": [
                    tel.get("tyres_surface_temp_rl", 0), tel.get("tyres_surface_temp_rr", 0),
                    tel.get("tyres_surface_temp_fl", 0), tel.get("tyres_surface_temp_fr", 0),
                ],
                "tyres_pressure": [
                    round(tel.get("tyres_pressure_rl", 0), 1),
                    round(tel.get("tyres_pressure_rr", 0), 1),
                    round(tel.get("tyres_pressure_fl", 0), 1),
                    round(tel.get("tyres_pressure_fr", 0), 1),
                ],
            }

        mot = state.get("motion", {})
        if mot:
            snapshot["mot"] = {
                "x": round(mot.get("world_position_x", 0), 1),
                "z": round(mot.get("world_position_z", 0), 1),
                "g_lat": round(mot.get("g_force_lateral", 0), 2),
                "g_lon": round(mot.get("g_force_longitudinal", 0), 2),
            }

        lap = state.get("lap_data", {})
        if lap:
            snapshot["lap"] = {
                "pos": lap.get("car_position", 0),
                "lap_num": lap.get("current_lap_num", 0),
                "lap_time_ms": lap.get("current_lap_time_ms", 0),
                "last_lap_ms": lap.get("last_lap_time_ms", 0),
                "sector": lap.get("sector", 0),
                "lap_dist": round(lap.get("lap_distance", 0), 1) if lap.get("lap_distance") else 0,
            }

        status = state.get("car_status", {})
        if status:
            snapshot["status"] = {
                "fuel": round(status.get("fuel_in_tank", 0), 2),
                "fuel_laps": round(status.get("fuel_remaining_laps", 0), 1),
                "ers_pct": status.get("ers_percent", 0),
                "ers_mode": status.get("ers_deploy_mode", 0),
                "tyre": status.get("visual_tyre_name", ""),
                "tyre_age": status.get("tyres_age_laps", 0),
            }

        self._samples.append(snapshot)
        self._total_samples += 1

        # Update session metadata with latest session info
        sess = state.get("session", {})
        if sess and sess.get("track_name"):
            self._session_meta["track"] = sess.get("track_name", "")
            self._session_meta["session_type"] = sess.get("session_type_name", "")
            self._session_meta["weather"] = sess.get("weather_name", "")

    def _start_new_session(self, session_uid: str, state: Dict[str, Any]):
        """Flush current session and start a new one."""
        if self._current_session_uid:
            self.flush()
            logger.info(
                "Session ended: %s (%d samples saved)",
                self._session_file.name if self._session_file else "?",
                self._total_samples,
            )

        self._current_session_uid = session_uid
        self._samples = []
        self._total_samples = 0

        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        uid_short = str(session_uid)[-8:] if session_uid else "unknown"
        filename = f"session_{ts}_{uid_short}.json"
        self._session_file = self.data_dir / filename

        self._session_meta = {
            "session_uid": str(session_uid),
            "start_time": datetime.now(timezone.utc).isoformat(),
            "track": "",
            "session_type": "",
            "weather": "",
        }
        logger.info("New session started → %s", filename)

    def flush(self):
        """Write buffered samples to disk (append-only for performance)."""
        if not self.enabled or not self._session_file or not self._samples:
            return

        try:
            samples_to_write = self._samples
            self._samples = []

            if not self._session_file.exists():
                # Create new file with metadata
                data = {
                    **self._session_meta,
                    "total_samples": len(samples_to_write),
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                    "samples": samples_to_write,
                }
                with open(self._session_file, "w") as f:
                    json.dump(data, f, separators=(",", ":"))
            else:
                # Append samples to JSONL file for performance
                append_file = self._session_file.with_suffix(".jsonl")
                with open(append_file, "a") as f:
                    for sample in samples_to_write:
                        f.write(json.dumps(sample, separators=(",", ":")) + "\n")

            flushed_count = len(samples_to_write)
            logger.debug("Flushed %d samples to %s", flushed_count, self._session_file.name)
        except Exception as e:
            logger.error("Failed to flush session data: %s", e)

    def close(self):
        """Final flush on shutdown."""
        if self.enabled:
            self.flush()
            if self._session_file and self._total_samples > 0:
                logger.info(
                    "Session saved: %s (%d total samples)",
                    self._session_file.name,
                    self._total_samples,
                )

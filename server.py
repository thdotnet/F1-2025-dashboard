"""
F1 2025 Telemetry Dashboard Server.

Uses only Python stdlib (asyncio, http.server) plus the 'websockets' library
for WebSocket support. No FastAPI, no aiohttp, no pydantic.
"""

import asyncio
import json
import logging
import os
import time
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Set, List, Optional
from http import HTTPStatus

import yaml

try:
    import websockets
    from websockets.asyncio.server import serve as ws_serve
except ImportError:
    print("ERROR: 'websockets' package not installed. Run: pip install websockets")
    raise

from packets import PacketParser

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CONFIG_PATH = os.environ.get("F1_CONFIG_PATH", "config.yaml")


def load_config() -> Dict[str, Any]:
    """Load configuration from YAML file with environment variable overrides."""
    config_file = Path(CONFIG_PATH)
    if config_file.exists():
        with open(config_file, "r") as f:
            config = yaml.safe_load(f)
    else:
        config = {}

    # Defaults
    defaults = {
        "udp": {"host": "0.0.0.0", "port": 20777},
        "web": {"host": "0.0.0.0", "port": 8000, "allowed_origins": ["*"]},
        "telemetry": {
            "broadcast_rate_hz": 60,
            "history_seconds": 60,
            "num_cars": 22,
        },
        "game": {"packet_format": 2025},
        "logging": {"level": "info"},
        "storage": {
            "enabled": True,
            "data_dir": "data",
            "flush_interval_seconds": 5,
            "sample_rate_hz": 4,
        },
    }

    def merge(base, override):
        for k, v in override.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                merge(base[k], v)
            else:
                base[k] = v

    merge(defaults, config)

    # Environment variable overrides (F1_UDP_PORT, F1_WEB_PORT, etc.)
    env_map = {
        "F1_UDP_HOST": ("udp", "host"),
        "F1_UDP_PORT": ("udp", "port", int),
        "F1_WEB_HOST": ("web", "host"),
        "F1_WEB_PORT": ("web", "port", int),
        "F1_BROADCAST_RATE": ("telemetry", "broadcast_rate_hz", int),
        "F1_LOG_LEVEL": ("logging", "level"),
    }
    for env_key, path in env_map.items():
        val = os.environ.get(env_key)
        if val is not None:
            section = defaults[path[0]]
            key = path[1]
            converter = path[2] if len(path) > 2 else str
            section[key] = converter(val)

    return defaults


config = load_config()

# Logging
log_level = getattr(logging, config["logging"]["level"].upper(), logging.INFO)
logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("f1dashboard")

# ---------------------------------------------------------------------------
# Static file directory
# ---------------------------------------------------------------------------
STATIC_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# Session Recorder - persists telemetry to JSON files
# ---------------------------------------------------------------------------
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

        # Build a compact snapshot (skip empty dicts and non-data keys)
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
        # Use short uid suffix for uniqueness
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
        """Write buffered samples to disk."""
        if not self.enabled or not self._session_file or not self._samples:
            return

        try:
            # Read existing data if file exists (append mode)
            existing_samples = []
            if self._session_file.exists():
                with open(self._session_file, "r") as f:
                    existing = json.load(f)
                    existing_samples = existing.get("samples", [])

            all_samples = existing_samples + self._samples

            data = {
                **self._session_meta,
                "total_samples": len(all_samples),
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "samples": all_samples,
            }

            with open(self._session_file, "w") as f:
                json.dump(data, f, separators=(",", ":"))

            flushed_count = len(self._samples)
            self._samples = []
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


recorder = SessionRecorder(config)

# ---------------------------------------------------------------------------
# WebSocket Manager
# ---------------------------------------------------------------------------
class ConnectionManager:
    """Manages WebSocket connections and broadcasts."""

    def __init__(self):
        self.active_connections: Set = set()

    def connect(self, ws):
        self.active_connections.add(ws)
        logger.info("Client connected. Total: %d", len(self.active_connections))

    def disconnect(self, ws):
        self.active_connections.discard(ws)
        logger.info("Client disconnected. Total: %d", len(self.active_connections))

    async def broadcast(self, message: str):
        if not self.active_connections:
            return
        disconnected = set()
        # Send to all clients concurrently with a timeout
        async def _send(ws):
            try:
                await asyncio.wait_for(ws.send(message), timeout=0.1)
            except Exception:
                disconnected.add(ws)

        await asyncio.gather(*[_send(ws) for ws in list(self.active_connections)])
        for ws in disconnected:
            self.active_connections.discard(ws)


manager = ConnectionManager()

# ---------------------------------------------------------------------------
# Telemetry State (latest data per type)
# ---------------------------------------------------------------------------
telemetry_state: Dict[str, Any] = {
    "telemetry": {},
    "motion": {},
    "lap_data": {},
    "car_status": {},
    "session": {},
    "connected": False,
    "last_packet_time": 0,
}

# ---------------------------------------------------------------------------
# UDP Listener
# ---------------------------------------------------------------------------


class F1UDPProtocol(asyncio.DatagramProtocol):
    """Async UDP protocol handler for F1 telemetry packets."""

    def __init__(self, parser: PacketParser):
        self.parser = parser
        self.packet_count = 0
        self.error_count = 0

    def connection_made(self, transport):
        logger.info("UDP listener ready")

    def datagram_received(self, data: bytes, addr):
        self.packet_count += 1
        result = self.parser.parse(data)
        if result:
            packet_type, parsed = result
            telemetry_state[packet_type] = parsed
            telemetry_state["connected"] = True
            telemetry_state["last_packet_time"] = time.time()

            # Record to session file
            header = self.parser.parse_header(data)
            if header:
                recorder.record(str(header["session_uid"]), telemetry_state)

    def error_received(self, exc):
        self.error_count += 1
        logger.error("UDP error: %s", exc)


async def start_udp_listener():
    """Start the async UDP listener."""
    parser = PacketParser(num_cars=config["telemetry"]["num_cars"])
    loop = asyncio.get_running_loop()

    udp_host = config["udp"]["host"]
    udp_port = config["udp"]["port"]

    transport, protocol = await loop.create_datagram_endpoint(
        lambda: F1UDPProtocol(parser),
        local_addr=(udp_host, udp_port),
    )
    logger.info("UDP listener started on %s:%d", udp_host, udp_port)
    return transport, protocol


# ---------------------------------------------------------------------------
# Broadcast Loop
# ---------------------------------------------------------------------------
async def broadcast_loop():
    """Broadcast telemetry state to WebSocket clients at a fixed rate."""
    rate = config["telemetry"]["broadcast_rate_hz"]
    interval = 1.0 / rate

    while True:
        await asyncio.sleep(interval)

        if not manager.active_connections:
            continue

        if telemetry_state["connected"] and time.time() - telemetry_state["last_packet_time"] > 5:
            telemetry_state["connected"] = False

        if not telemetry_state["connected"]:
            continue

        try:
            # Always serialize fresh state right before sending
            message = json.dumps(telemetry_state, default=str)
            await manager.broadcast(message)
        except Exception as e:
            logger.error("Broadcast error: %s", e)


async def flush_loop():
    """Periodically flush recorded session data to disk."""
    interval = config.get("storage", {}).get("flush_interval_seconds", 5)
    while True:
        await asyncio.sleep(interval)
        recorder.flush()


# ---------------------------------------------------------------------------
# HTTP Request Handler (stdlib asyncio)
# ---------------------------------------------------------------------------
STATIC_FILES = {
    "/": ("index.html", "text/html"),
    "/index.html": ("index.html", "text/html"),
    "/dashboard.css": ("dashboard.css", "text/css"),
    "/app.js": ("app.js", "application/javascript"),
    "/charts.js": ("charts.js", "application/javascript"),
}


async def handle_http(reader, writer):
    """Minimal async HTTP handler for static files and API endpoints."""
    try:
        request_line = await asyncio.wait_for(reader.readline(), timeout=5.0)
        if not request_line:
            writer.close()
            return

        request_text = request_line.decode("utf-8", errors="replace").strip()
        parts = request_text.split(" ")
        if len(parts) < 2:
            writer.close()
            return

        method, path = parts[0], parts[1]

        # Read and discard remaining headers
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=5.0)
            if line in (b"\r\n", b"\n", b""):
                break

        # API endpoints
        if path == "/api/config":
            body = json.dumps({
                "broadcast_rate_hz": config["telemetry"]["broadcast_rate_hz"],
                "history_seconds": config["telemetry"]["history_seconds"],
                "udp_port": config["udp"]["port"],
            }).encode()
            _send_response(writer, 200, "application/json", body)

        elif path == "/api/status":
            body = json.dumps({
                "connected": telemetry_state["connected"],
                "last_packet_time": telemetry_state["last_packet_time"],
            }).encode()
            _send_response(writer, 200, "application/json", body)

        elif path == "/api/sessions":
            sessions = []
            if recorder.enabled and recorder.data_dir.exists():
                for f in sorted(recorder.data_dir.glob("session_*.json"), reverse=True):
                    try:
                        with open(f, "r") as fh:
                            meta = json.load(fh)
                        sessions.append({
                            "filename": f.name,
                            "track": meta.get("track", ""),
                            "session_type": meta.get("session_type", ""),
                            "start_time": meta.get("start_time", ""),
                            "total_samples": meta.get("total_samples", 0),
                        })
                    except Exception:
                        pass
            body = json.dumps(sessions).encode()
            _send_response(writer, 200, "application/json", body)

        # Static files
        elif path in STATIC_FILES:
            filename, content_type = STATIC_FILES[path]
            file_path = STATIC_DIR / filename
            if file_path.exists():
                body = file_path.read_bytes()
                _send_response(writer, 200, content_type, body)
            else:
                _send_response(writer, 404, "text/plain", b"File not found")

        else:
            _send_response(writer, 404, "text/plain", b"Not found")

    except Exception as e:
        logger.debug("HTTP handler error: %s", e)
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


def _send_response(writer, status_code, content_type, body):
    status_text = HTTPStatus(status_code).phrase
    header = (
        f"HTTP/1.1 {status_code} {status_text}\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Access-Control-Allow-Origin: *\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    )
    writer.write(header.encode() + body)


# ---------------------------------------------------------------------------
# WebSocket Handler
# ---------------------------------------------------------------------------
async def handle_websocket(ws):
    """Handle a single WebSocket client connection."""
    manager.connect(ws)
    try:
        async for message in ws:
            logger.debug("Client message: %s", message)
    except websockets.ConnectionClosed:
        pass
    except Exception as e:
        logger.debug("WebSocket error: %s", e)
    finally:
        manager.disconnect(ws)


# ---------------------------------------------------------------------------
# App Lifecycle
# ---------------------------------------------------------------------------
async def main():
    print(f"F1 Telemetry Dashboard starting...")
    print(f"  UDP listener: {config['udp']['host']}:{config['udp']['port']}")
    print(f"  Web server:   http://localhost:{config['web']['port']}")
    print(f"  Open http://localhost:{config['web']['port']} in your browser")
    print()

    # Start UDP listener
    udp_transport, udp_protocol = await start_udp_listener()

    # Start broadcast loop
    broadcast_task = asyncio.create_task(broadcast_loop())

    # Start session data flush loop
    flush_task = asyncio.create_task(flush_loop())

    # Start HTTP server for static files and API
    http_server = await asyncio.start_server(
        handle_http,
        config["web"]["host"],
        config["web"]["port"],
    )
    logger.info("HTTP server started on %s:%d", config["web"]["host"], config["web"]["port"])

    # Start WebSocket server on port+1
    ws_port = config["web"]["port"] + 1
    ws_server = await ws_serve(handle_websocket, config["web"]["host"], ws_port)
    logger.info("WebSocket server started on %s:%d", config["web"]["host"], ws_port)
    print(f"  WebSocket:    ws://localhost:{ws_port}")

    try:
        await asyncio.Future()  # run forever
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        print("\nShutting down...")
        recorder.close()
        broadcast_task.cancel()
        flush_task.cancel()
        udp_transport.close()
        http_server.close()
        ws_server.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

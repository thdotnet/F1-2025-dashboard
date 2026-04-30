"""
F1 2025 Telemetry Dashboard Server.

Orchestrates UDP telemetry ingestion, WebSocket broadcasting, HTTP API,
session recording, and AI feedback via Azure Foundry.
"""

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, Any
from http import HTTPStatus

import yaml

try:
    import websockets
    from websockets.asyncio.server import serve as ws_serve
except ImportError:
    print("ERROR: 'websockets' package not installed. Run: pip install websockets")
    raise

from recorder import SessionRecorder
from websocket_manager import ConnectionManager
from udp_listener import start_udp_listener
from foundry_agent import call_foundry_agent, collect_session_data

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
        "foundry": {
            "endpoint": "",
            "agent_name": "",
            "agent_version": "1",
        },
    }

    def merge(base, override):
        for k, v in override.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                merge(base[k], v)
            else:
                base[k] = v

    merge(defaults, config)

    # Environment variable overrides
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
# Shared state
# ---------------------------------------------------------------------------
STATIC_DIR = Path(__file__).parent

recorder = SessionRecorder(config)
manager = ConnectionManager()

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
# Broadcast & Flush Loops
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
            message = json.dumps(telemetry_state, default=str)
            await manager.broadcast(message)
        except Exception as e:
            logger.error("Broadcast error: %s", e)


async def flush_loop():
    """Periodically flush recorded session data to disk in a thread."""
    interval = config.get("storage", {}).get("flush_interval_seconds", 5)
    loop = asyncio.get_running_loop()
    while True:
        await asyncio.sleep(interval)
        if recorder.enabled and recorder._samples:
            await loop.run_in_executor(None, recorder.flush)


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------
STATIC_FILES = {
    "/": ("index.html", "text/html"),
    "/index.html": ("index.html", "text/html"),
    "/dashboard.css": ("dashboard.css", "text/css"),
    "/app.js": ("app.js", "application/javascript"),
    "/charts.js": ("charts.js", "application/javascript"),
}


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


async def _handle_ai_feedback(writer):
    """Call the Foundry agent with telemetry data and return JSON response."""
    try:
        telemetry_content = collect_session_data(recorder, telemetry_state)

        if not telemetry_content or not telemetry_content.strip():
            body = json.dumps({"ok": False, "error": "No session data available. Start a session first."}).encode()
            _send_response(writer, 200, "application/json", body)
            return

        logger.info("AI Feedback: collected %d bytes of telemetry", len(telemetry_content))

        loop = asyncio.get_running_loop()
        response_text = await loop.run_in_executor(
            None, lambda: call_foundry_agent(telemetry_content, config)
        )

        logger.info("AI Feedback: got response (%d chars)", len(response_text))
        body = json.dumps({"ok": True, "feedback": response_text}).encode()
        _send_response(writer, 200, "application/json", body)

    except Exception as e:
        logger.error("AI Feedback error: %s", e, exc_info=True)
        error_msg = str(e).replace("\n", " ")[:200]
        body = json.dumps({"ok": False, "error": error_msg}).encode()
        _send_response(writer, 200, "application/json", body)


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

        # Read headers, capture content-length
        content_length = 0
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=5.0)
            if line in (b"\r\n", b"\n", b""):
                break
            header_lower = line.decode("utf-8", errors="replace").lower()
            if header_lower.startswith("content-length:"):
                try:
                    content_length = int(header_lower.split(":", 1)[1].strip())
                except ValueError:
                    pass

        # Consume request body
        if content_length > 0:
            await reader.read(min(content_length, 1024 * 1024))

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

        elif path == "/api/session/start" and method == "POST":
            if recorder.data_dir.exists():
                for f in recorder.data_dir.glob("session_*"):
                    try:
                        f.unlink()
                    except Exception:
                        pass
            recorder._current_session_uid = None
            recorder._samples = []
            recorder._total_samples = 0
            body = json.dumps({"ok": True}).encode()
            _send_response(writer, 200, "application/json", body)

        elif path == "/api/session/stop" and method == "POST":
            recorder.flush()
            samples = recorder._total_samples
            body = json.dumps({"ok": True, "samples": samples}).encode()
            _send_response(writer, 200, "application/json", body)

        elif path == "/api/ai-feedback" and method == "POST":
            await _handle_ai_feedback(writer)

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
    print("F1 Telemetry Dashboard starting...")
    print(f"  UDP listener: {config['udp']['host']}:{config['udp']['port']}")
    print(f"  Web server:   http://localhost:{config['web']['port']}")
    print(f"  Open http://localhost:{config['web']['port']} in your browser")
    print()

    udp_transport, _ = await start_udp_listener(config, telemetry_state, recorder)
    broadcast_task = asyncio.create_task(broadcast_loop())
    flush_task = asyncio.create_task(flush_loop())

    http_server = await asyncio.start_server(
        handle_http, config["web"]["host"], config["web"]["port"]
    )
    logger.info("HTTP server started on %s:%d", config["web"]["host"], config["web"]["port"])

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

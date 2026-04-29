# F1 2025 Real-Time Telemetry Dashboard

A real-time telemetry dashboard for EA Sports F1 2025 (Xbox/PC). Captures UDP
telemetry data from the game and displays live charts and visualizations.

## Features

- **15 dashboard panels** with live data:
  - Speed, Gear, RPM with rev lights bar
  - Throttle & Brake trace (time series)
  - Speed trace (time series)
  - RPM trace (time series)
  - Track Map (live 2D position of all cars)
  - G-Force plot (lateral vs longitudinal)
  - Steering wheel indicator
  - Tyre temperatures (inner + surface, all 4 wheels)
  - Brake temperatures (all 4 wheels)
  - Tyre pressures (all 4 wheels)
  - DRS status indicator
  - ERS energy bar and deployment mode
  - Fuel remaining (kg + laps)
  - Tyre compound and age
  - Lap info (position, lap number, sector, times, delta)

- **Configurable** via `config.yaml` and environment variables
- **WebSocket** real-time data push (default 20Hz)
- **Responsive** dark theme racing UI
- **Azure-ready** architecture (FastAPI + Uvicorn)

## Prerequisites

- Python 3.9+
- EA Sports F1 2025 with UDP Telemetry enabled

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure your F1 game (Xbox/PC):**
   - Go to Settings > Telemetry
   - UDP Telemetry: **On**
   - UDP Broadcast Mode: **Off**
   - UDP IP Address: **Your PC's local IP** (e.g., `192.168.1.100`)
   - UDP Port: **20777** (must match `config.yaml`)
   - UDP Send Rate: **20Hz** or higher
   - UDP Format: **2025**

3. **Run the server:**
   ```bash
   python server.py
   ```

4. **Open the dashboard:**
   Navigate to `http://localhost:8000` in your browser.

5. **Start a session** in F1 2025 - data will appear automatically.

## Configuration

Edit `config.yaml` to change settings:

```yaml
udp:
  host: "0.0.0.0"     # Listen on all interfaces
  port: 20777          # Must match F1 game setting

web:
  host: "0.0.0.0"
  port: 8000

telemetry:
  broadcast_rate_hz: 20   # WebSocket push rate
  history_seconds: 60     # Chart history length
```

### Environment Variable Overrides

All settings can be overridden with environment variables:

| Variable            | Description                |
|---------------------|----------------------------|
| `F1_UDP_HOST`       | UDP listener bind address  |
| `F1_UDP_PORT`       | UDP listener port          |
| `F1_WEB_HOST`       | Web server bind address    |
| `F1_WEB_PORT`       | Web server port            |
| `F1_BROADCAST_RATE` | WebSocket broadcast rate   |
| `F1_LOG_LEVEL`      | Logging level              |
| `F1_CONFIG_PATH`    | Path to config.yaml        |

## Architecture

```
Xbox (F1 2025) --UDP--> Python Backend --WebSocket--> Browser Dashboard
                         (server.py)                   (index.html)
                         (packets.py)                  (charts.js)
```

- **packets.py** - Binary packet parsing (struct-based, zero dependencies)
- **server.py** - FastAPI web server + async UDP listener + WebSocket broadcast
- **charts.js** - Chart.js time series + custom Canvas visualizations
- **app.js** - WebSocket client with auto-reconnect

## Azure Deployment Notes

The app is designed for easy Azure deployment:

- **Azure App Service**: Deploy as a Python web app
- **Azure Container Apps**: Dockerize with the included architecture
- Set environment variables in Azure App Settings
- Note: For remote hosting, you'll need a UDP relay/proxy since the
  Xbox sends UDP to your local network only

## Packet Format

Based on the F1 24/25 UDP specification. If the game updates the packet
format, edit `packets.py` struct definitions. The parser gracefully handles
format mismatches with warning logs.

## License

MIT

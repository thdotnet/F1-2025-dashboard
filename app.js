/**
 * F1 2025 Telemetry Dashboard - WebSocket Client & Data Router
 *
 * Connects to the backend WebSocket, receives telemetry data, and
 * routes it to the appropriate chart/display update functions.
 */

(() => {
    'use strict';

    // -----------------------------------------------------------------------
    // Configuration
    // -----------------------------------------------------------------------
    const WS_RECONNECT_DELAY_MS = 2000;
    const WS_MAX_RECONNECT_DELAY_MS = 30000;

    let ws = null;
    let reconnectDelay = WS_RECONNECT_DELAY_MS;
    let reconnectTimer = null;
    let configData = null;

    // -----------------------------------------------------------------------
    // Initialization
    // -----------------------------------------------------------------------
    async function init() {
        // Fetch config from server
        try {
            const resp = await fetch('/api/config');
            configData = await resp.json();
        } catch (e) {
            console.warn('Failed to fetch config, using defaults:', e);
            configData = { broadcast_rate_hz: 20, history_seconds: 60 };
        }

        // Initialize charts
        DashboardCharts.init(configData);

        // Connect WebSocket
        connectWebSocket();
    }

    // -----------------------------------------------------------------------
    // WebSocket Connection
    // -----------------------------------------------------------------------
    function getWsUrl() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsPort = parseInt(window.location.port) + 1;
        return `${protocol}//${window.location.hostname}:${wsPort}`;
    }

    function connectWebSocket() {
        if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) {
            return;
        }

        const url = getWsUrl();
        console.log(`Connecting to ${url}...`);
        ws = new WebSocket(url);

        ws.onopen = () => {
            console.log('WebSocket connected');
            reconnectDelay = WS_RECONNECT_DELAY_MS;
            updateConnectionStatus(true);
        };

        ws.onmessage = (event) => {
            try {
                const state = JSON.parse(event.data);
                handleTelemetryState(state);
            } catch (e) {
                console.error('Failed to parse message:', e);
            }
        };

        ws.onclose = (event) => {
            console.log(`WebSocket closed: ${event.code} ${event.reason}`);
            updateConnectionStatus(false);
            scheduleReconnect();
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    function scheduleReconnect() {
        if (reconnectTimer) return;
        console.log(`Reconnecting in ${reconnectDelay}ms...`);
        reconnectTimer = setTimeout(() => {
            reconnectTimer = null;
            connectWebSocket();
            // Exponential backoff
            reconnectDelay = Math.min(reconnectDelay * 1.5, WS_MAX_RECONNECT_DELAY_MS);
        }, reconnectDelay);
    }

    // -----------------------------------------------------------------------
    // State Handling
    // -----------------------------------------------------------------------
    let lastSessionUid = null;

    function handleTelemetryState(state) {
        if (!state) return;

        // Update connection status
        const gameConnected = state.connected === true;
        updateGameStatus(gameConnected);

        if (!gameConnected) return;

        // Route data to chart modules
        if (state.telemetry && Object.keys(state.telemetry).length > 0) {
            DashboardCharts.updateTelemetry(state.telemetry);
        }

        if (state.motion && Object.keys(state.motion).length > 0) {
            DashboardCharts.updateMotion(state.motion);
        }

        if (state.lap_data && Object.keys(state.lap_data).length > 0) {
            DashboardCharts.updateLapData(state.lap_data);
        }

        if (state.car_status && Object.keys(state.car_status).length > 0) {
            DashboardCharts.updateCarStatus(state.car_status);
        }

        if (state.session && Object.keys(state.session).length > 0) {
            DashboardCharts.updateSession(state.session);
        }
    }

    // -----------------------------------------------------------------------
    // UI Status Updates
    // -----------------------------------------------------------------------
    function updateConnectionStatus(connected) {
        const badge = document.getElementById('connection-status');
        if (!badge) return;

        if (connected) {
            badge.textContent = 'SERVER OK';
            badge.className = 'status-badge connected';
        } else {
            badge.textContent = 'DISCONNECTED';
            badge.className = 'status-badge disconnected';
        }
    }

    function updateGameStatus(gameConnected) {
        const badge = document.getElementById('connection-status');
        if (!badge) return;

        if (gameConnected) {
            badge.textContent = 'LIVE';
            badge.className = 'status-badge connected';
        } else {
            badge.textContent = 'WAITING FOR GAME';
            badge.className = 'status-badge disconnected';
        }
    }

    // -----------------------------------------------------------------------
    // Start
    // -----------------------------------------------------------------------
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();

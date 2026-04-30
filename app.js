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

// ---------------------------------------------------------------------------
// Session Controls (global scope for onclick handlers)
// ---------------------------------------------------------------------------
async function startSession() {
    const btn = document.getElementById('btn-start-session');
    btn.disabled = true;
    try {
        const resp = await fetch('/api/session/start', { method: 'POST' });
        const data = await resp.json();
        if (data.ok) {
            document.getElementById('session-info').textContent = 'Session recording...';
        }
    } catch (e) {
        console.error('Start session failed:', e);
    } finally {
        btn.disabled = false;
    }
}

async function stopSession() {
    const btn = document.getElementById('btn-stop-session');
    btn.disabled = true;
    try {
        const resp = await fetch('/api/session/stop', { method: 'POST' });
        const data = await resp.json();
        if (data.ok) {
            document.getElementById('session-info').textContent = `Session saved (${data.samples} samples)`;
        }
    } catch (e) {
        console.error('Stop session failed:', e);
    } finally {
        btn.disabled = false;
    }
}

async function requestAIFeedback() {
    const btn = document.getElementById('btn-ai-feedback');
    btn.disabled = true;
    btn.classList.add('loading');
    btn.textContent = '🤖 Analyzing...';

    try {
        const resp = await fetch('/api/ai-feedback', { method: 'POST' });
        const data = await resp.json();
        console.log('AI Feedback response:', data);

        if (data.ok) {
            console.log('AI Agent says:', data.feedback);
            speakText(data.feedback);
        } else {
            console.warn('AI Feedback error:', data.error);
            speakText('Sorry, I could not get AI feedback at this time.');
        }
    } catch (e) {
        console.error('AI Feedback failed:', e);
        speakText('Sorry, I could not get AI feedback at this time.');
    } finally {
        btn.disabled = false;
        btn.classList.remove('loading');
        btn.textContent = '🤖 AI Feedback';
    }
}

function speakText(text) {
    if (!('speechSynthesis' in window)) {
        console.warn('Speech synthesis not supported');
        return;
    }
    window.speechSynthesis.cancel();
    // Strip markdown formatting for cleaner speech
    const cleanText = text
        .replace(/###?\s*/g, '')
        .replace(/[-*]\s+/g, '')
        .replace(/\n+/g, '. ');
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1.1;
    utterance.pitch = 1.0;

    function setVoiceAndSpeak() {
        const voices = window.speechSynthesis.getVoices();
        console.log('Available voices:', voices.map(v => v.name));
        const avaVoice = voices.find(v => v.name.includes('Ava') && v.name.includes('Natural'))
            || voices.find(v => v.name.includes('Ava') && v.lang.startsWith('en'))
            || voices.find(v => v.lang.startsWith('en') && v.name.includes('Natural'))
            || voices.find(v => v.lang.startsWith('en'));
        if (avaVoice) {
            console.log('Using voice:', avaVoice.name);
            utterance.voice = avaVoice;
        }
        window.speechSynthesis.speak(utterance);
    }

    // Voices may not be loaded yet — wait for them
    const voices = window.speechSynthesis.getVoices();
    if (voices.length > 0) {
        setVoiceAndSpeak();
    } else {
        window.speechSynthesis.onvoiceschanged = setVoiceAndSpeak;
    }
}

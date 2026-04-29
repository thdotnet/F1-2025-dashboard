/**
 * F1 2025 Telemetry Dashboard - Chart Definitions
 *
 * Creates and manages all Chart.js charts and custom canvas visualizations.
 * Exported as a global `DashboardCharts` object used by app.js.
 */

const DashboardCharts = (() => {
    // -----------------------------------------------------------------------
    // Configuration (loaded from server on init)
    // -----------------------------------------------------------------------
    let HISTORY_SECONDS = 60;
    let BROADCAST_RATE = 20;
    let MAX_POINTS = HISTORY_SECONDS * BROADCAST_RATE;

    // Shared Chart.js defaults
    Chart.defaults.color = '#8888a0';
    Chart.defaults.borderColor = '#2a2a3a';
    Chart.defaults.font.family = "'Segoe UI', Roboto, sans-serif";
    Chart.defaults.font.size = 10;
    Chart.defaults.animation = false;
    Chart.defaults.responsive = true;
    Chart.defaults.maintainAspectRatio = false;

    // -----------------------------------------------------------------------
    // Data buffers (ring buffers for time series)
    // -----------------------------------------------------------------------
    const buffers = {
        time: [],
        throttle: [],
        brake: [],
        speed: [],
        steer: [],
        rpm: [],
        gForceHistory: [],
    };

    function pushToBuffer(arr, value) {
        arr.push(value);
        if (arr.length > MAX_POINTS) arr.shift();
    }

    // -----------------------------------------------------------------------
    // Chart instances
    // -----------------------------------------------------------------------
    let throttleBrakeChart = null;
    let speedChart = null;
    let rpmChart = null;

    function createThrottleBrakeChart() {
        const ctx = document.getElementById('chart-throttle-brake');
        if (!ctx) return;
        throttleBrakeChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Throttle',
                        data: [],
                        borderColor: '#00e676',
                        backgroundColor: 'rgba(0, 230, 118, 0.1)',
                        fill: true,
                        borderWidth: 1.5,
                        pointRadius: 0,
                        tension: 0.2,
                    },
                    {
                        label: 'Brake',
                        data: [],
                        borderColor: '#ff1744',
                        backgroundColor: 'rgba(255, 23, 68, 0.1)',
                        fill: true,
                        borderWidth: 1.5,
                        pointRadius: 0,
                        tension: 0.2,
                    },
                ],
            },
            options: {
                scales: {
                    x: { display: false },
                    y: { min: 0, max: 1.05, ticks: { stepSize: 0.25 } },
                },
                plugins: {
                    legend: { position: 'top', labels: { boxWidth: 12, padding: 8 } },
                },
            },
        });
    }

    function createSpeedChart() {
        const ctx = document.getElementById('chart-speed');
        if (!ctx) return;
        speedChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Speed (km/h)',
                    data: [],
                    borderColor: '#00d4ff',
                    backgroundColor: 'rgba(0, 212, 255, 0.08)',
                    fill: true,
                    borderWidth: 1.5,
                    pointRadius: 0,
                    tension: 0.2,
                }],
            },
            options: {
                scales: {
                    x: { display: false },
                    y: { min: 0, suggestedMax: 350 },
                },
                plugins: { legend: { display: false } },
            },
        });
    }

    function createRpmChart() {
        const ctx = document.getElementById('chart-rpm');
        if (!ctx) return;
        rpmChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'RPM',
                    data: [],
                    borderColor: '#f1c40f',
                    backgroundColor: 'rgba(241, 196, 15, 0.08)',
                    fill: true,
                    borderWidth: 1.5,
                    pointRadius: 0,
                    tension: 0.2,
                }],
            },
            options: {
                scales: {
                    x: { display: false },
                    y: { min: 0, suggestedMax: 15000 },
                },
                plugins: { legend: { display: false } },
            },
        });
    }

    // -----------------------------------------------------------------------
    // Custom Canvas: Track Map
    // -----------------------------------------------------------------------
    let trackMapCtx = null;
    let trackHistory = [];
    const TRACK_HISTORY_MAX = 2000;

    function initTrackMap() {
        const canvas = document.getElementById('canvas-track-map');
        if (!canvas) return;
        trackMapCtx = canvas.getContext('2d');
        resizeCanvas(canvas);
    }

    function drawTrackMap(motionData) {
        if (!trackMapCtx || !motionData) return;
        const canvas = trackMapCtx.canvas;
        resizeCanvas(canvas);

        const w = canvas.width;
        const h = canvas.height;

        trackMapCtx.fillStyle = '#0a0a0f';
        trackMapCtx.fillRect(0, 0, w, h);

        const positions = motionData.all_car_positions || [];
        if (positions.length === 0) return;

        // Add player position to history for track outline
        const player = positions.find(p => p.is_player);
        if (player) {
            trackHistory.push({ x: player.x, z: player.z });
            if (trackHistory.length > TRACK_HISTORY_MAX) trackHistory.shift();
        }

        // Calculate bounds from history + current positions
        const allPoints = [...trackHistory, ...positions.map(p => ({ x: p.x, z: p.z }))];
        if (allPoints.length < 2) return;

        let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
        for (const p of allPoints) {
            minX = Math.min(minX, p.x);
            maxX = Math.max(maxX, p.x);
            minZ = Math.min(minZ, p.z);
            maxZ = Math.max(maxZ, p.z);
        }

        const rangeX = maxX - minX || 1;
        const rangeZ = maxZ - minZ || 1;
        const padding = 20;
        const scaleX = (w - padding * 2) / rangeX;
        const scaleZ = (h - padding * 2) / rangeZ;
        const scale = Math.min(scaleX, scaleZ);
        const offsetX = (w - rangeX * scale) / 2;
        const offsetZ = (h - rangeZ * scale) / 2;

        function toScreen(x, z) {
            return [
                offsetX + (x - minX) * scale,
                offsetZ + (z - minZ) * scale,
            ];
        }

        // Draw track outline from history
        if (trackHistory.length > 2) {
            trackMapCtx.beginPath();
            trackMapCtx.strokeStyle = '#2a2a3a';
            trackMapCtx.lineWidth = 4;
            const [sx, sz] = toScreen(trackHistory[0].x, trackHistory[0].z);
            trackMapCtx.moveTo(sx, sz);
            for (let i = 1; i < trackHistory.length; i++) {
                const [px, pz] = toScreen(trackHistory[i].x, trackHistory[i].z);
                trackMapCtx.lineTo(px, pz);
            }
            trackMapCtx.stroke();
        }

        // Draw all cars
        for (const car of positions) {
            const [cx, cz] = toScreen(car.x, car.z);
            trackMapCtx.beginPath();
            if (car.is_player) {
                trackMapCtx.fillStyle = '#00d4ff';
                trackMapCtx.arc(cx, cz, 5, 0, Math.PI * 2);
                trackMapCtx.fill();
                // Glow effect
                trackMapCtx.beginPath();
                trackMapCtx.fillStyle = 'rgba(0, 212, 255, 0.3)';
                trackMapCtx.arc(cx, cz, 10, 0, Math.PI * 2);
                trackMapCtx.fill();
            } else {
                trackMapCtx.fillStyle = '#555568';
                trackMapCtx.arc(cx, cz, 3, 0, Math.PI * 2);
                trackMapCtx.fill();
            }
        }
    }

    // -----------------------------------------------------------------------
    // Custom Canvas: G-Force Plot
    // -----------------------------------------------------------------------
    let gforceCtx = null;

    function initGForce() {
        const canvas = document.getElementById('canvas-gforce');
        if (!canvas) return;
        gforceCtx = canvas.getContext('2d');
        resizeCanvas(canvas);
    }

    function drawGForce(lateral, longitudinal) {
        if (!gforceCtx) return;
        const canvas = gforceCtx.canvas;
        resizeCanvas(canvas);

        const w = canvas.width;
        const h = canvas.height;
        const cx = w / 2;
        const cy = h / 2;
        const maxG = 5;
        const radius = Math.min(cx, cy) - 10;

        gforceCtx.fillStyle = '#0a0a0f';
        gforceCtx.fillRect(0, 0, w, h);

        // Grid circles
        for (let g = 1; g <= maxG; g++) {
            const r = (g / maxG) * radius;
            gforceCtx.beginPath();
            gforceCtx.strokeStyle = '#1a1a2e';
            gforceCtx.lineWidth = 1;
            gforceCtx.arc(cx, cy, r, 0, Math.PI * 2);
            gforceCtx.stroke();
        }

        // Crosshairs
        gforceCtx.beginPath();
        gforceCtx.strokeStyle = '#1a1a2e';
        gforceCtx.moveTo(0, cy);
        gforceCtx.lineTo(w, cy);
        gforceCtx.moveTo(cx, 0);
        gforceCtx.lineTo(cx, h);
        gforceCtx.stroke();

        // G-force history trail
        const history = buffers.gForceHistory;
        pushToBuffer(history, { lat: lateral || 0, lon: longitudinal || 0 });

        if (history.length > 1) {
            gforceCtx.beginPath();
            gforceCtx.strokeStyle = 'rgba(0, 212, 255, 0.15)';
            gforceCtx.lineWidth = 1;
            const startIdx = Math.max(0, history.length - 100);
            for (let i = startIdx; i < history.length; i++) {
                const gx = cx + (history[i].lat / maxG) * radius;
                const gy = cy - (history[i].lon / maxG) * radius;
                if (i === startIdx) gforceCtx.moveTo(gx, gy);
                else gforceCtx.lineTo(gx, gy);
            }
            gforceCtx.stroke();
        }

        // Current position dot
        const dotX = cx + ((lateral || 0) / maxG) * radius;
        const dotY = cy - ((longitudinal || 0) / maxG) * radius;

        gforceCtx.beginPath();
        gforceCtx.fillStyle = 'rgba(0, 212, 255, 0.3)';
        gforceCtx.arc(dotX, dotY, 8, 0, Math.PI * 2);
        gforceCtx.fill();

        gforceCtx.beginPath();
        gforceCtx.fillStyle = '#00d4ff';
        gforceCtx.arc(dotX, dotY, 4, 0, Math.PI * 2);
        gforceCtx.fill();

        // Labels
        gforceCtx.fillStyle = '#555568';
        gforceCtx.font = '9px sans-serif';
        gforceCtx.textAlign = 'center';
        gforceCtx.fillText('BRAKE', cx, 12);
        gforceCtx.fillText('ACCEL', cx, h - 4);
        gforceCtx.textAlign = 'left';
        gforceCtx.fillText('L', 4, cy + 4);
        gforceCtx.textAlign = 'right';
        gforceCtx.fillText('R', w - 4, cy + 4);
    }

    // -----------------------------------------------------------------------
    // Custom Canvas: Steering
    // -----------------------------------------------------------------------
    let steerCtx = null;

    function initSteering() {
        const canvas = document.getElementById('canvas-steering');
        if (!canvas) return;
        steerCtx = canvas.getContext('2d');
        resizeCanvas(canvas);
    }

    function drawSteering(steerValue) {
        if (!steerCtx) return;
        const canvas = steerCtx.canvas;
        resizeCanvas(canvas);

        const w = canvas.width;
        const h = canvas.height;
        const cx = w / 2;
        const cy = h * 0.55;
        const radius = Math.min(cx, cy) - 20;
        const steer = steerValue || 0;

        steerCtx.fillStyle = '#0a0a0f';
        steerCtx.fillRect(0, 0, w, h);

        // Steering wheel arc
        steerCtx.beginPath();
        steerCtx.strokeStyle = '#2a2a3a';
        steerCtx.lineWidth = 8;
        steerCtx.arc(cx, cy, radius, Math.PI * 0.8, Math.PI * 2.2);
        steerCtx.stroke();

        // Active position
        const angle = Math.PI * 1.5 + steer * Math.PI * 0.7;
        const indicatorX = cx + Math.cos(angle) * radius;
        const indicatorY = cy + Math.sin(angle) * radius;

        steerCtx.beginPath();
        steerCtx.fillStyle = '#00d4ff';
        steerCtx.arc(indicatorX, indicatorY, 6, 0, Math.PI * 2);
        steerCtx.fill();

        // Value text
        steerCtx.fillStyle = '#e0e0e8';
        steerCtx.font = 'bold 16px monospace';
        steerCtx.textAlign = 'center';
        steerCtx.fillText(steer.toFixed(2), cx, h - 8);
    }

    // -----------------------------------------------------------------------
    // Utility
    // -----------------------------------------------------------------------
    function resizeCanvas(canvas) {
        const rect = canvas.getBoundingClientRect();
        if (canvas.width !== rect.width || canvas.height !== rect.height) {
            canvas.width = rect.width;
            canvas.height = rect.height;
        }
    }

    function getTempClass(temp, type) {
        if (type === 'tyre') {
            if (temp < 60) return 'temp-cold';
            if (temp < 100) return 'temp-optimal';
            if (temp < 120) return 'temp-hot';
            return 'temp-critical';
        }
        if (type === 'brake') {
            if (temp < 200) return 'temp-cold';
            if (temp < 600) return 'temp-optimal';
            if (temp < 900) return 'temp-hot';
            return 'temp-critical';
        }
        return '';
    }

    function getTempColor(temp, type) {
        const cls = getTempClass(temp, type);
        const colors = {
            'temp-cold': '#2979ff',
            'temp-optimal': '#00e676',
            'temp-hot': '#ff9100',
            'temp-critical': '#ff1744',
        };
        return colors[cls] || '#8888a0';
    }

    // -----------------------------------------------------------------------
    // Public API
    // -----------------------------------------------------------------------
    return {
        init(configData) {
            if (configData) {
                HISTORY_SECONDS = configData.history_seconds || 60;
                BROADCAST_RATE = configData.broadcast_rate_hz || 20;
                MAX_POINTS = HISTORY_SECONDS * BROADCAST_RATE;
            }
            createThrottleBrakeChart();
            createSpeedChart();
            createRpmChart();
            initTrackMap();
            initGForce();
            initSteering();
        },

        updateTelemetry(data) {
            if (!data || Object.keys(data).length === 0) return;

            const t = buffers.time.length;
            pushToBuffer(buffers.time, t);
            pushToBuffer(buffers.throttle, data.throttle || 0);
            pushToBuffer(buffers.brake, data.brake || 0);
            pushToBuffer(buffers.speed, data.speed || 0);
            pushToBuffer(buffers.rpm, data.engine_rpm || 0);

            // Speed display
            const speedEl = document.getElementById('speed-value');
            if (speedEl) speedEl.textContent = data.speed || 0;

            // Gear display
            const gearEl = document.getElementById('gear-value');
            if (gearEl) {
                const gear = data.gear;
                gearEl.textContent = gear === 0 ? 'N' : gear === -1 ? 'R' : gear;
                gearEl.style.color = gear === 0 ? '#f1c40f' : gear === -1 ? '#ff1744' : '#00d4ff';
            }

            // RPM & rev bar
            const rpmEl = document.getElementById('rpm-value');
            if (rpmEl) rpmEl.textContent = `${data.engine_rpm || 0} RPM`;
            const revBar = document.getElementById('rev-bar');
            if (revBar) revBar.style.width = `${data.rev_lights_percent || 0}%`;

            // DRS
            const drsEl = document.getElementById('drs-indicator');
            if (drsEl) {
                const active = data.drs === 1;
                drsEl.textContent = active ? 'DRS' : 'OFF';
                drsEl.classList.toggle('active', active);
            }
            const suggestedGear = document.getElementById('suggested-gear');
            if (suggestedGear && data.suggested_gear != null) {
                suggestedGear.textContent = data.suggested_gear > 0
                    ? `Suggested: ${data.suggested_gear}`
                    : '';
            }

            // Tyre temps
            this._updateTyreTemp('fl', data.tyres_inner_temp_fl, data.tyres_surface_temp_fl);
            this._updateTyreTemp('fr', data.tyres_inner_temp_fr, data.tyres_surface_temp_fr);
            this._updateTyreTemp('rl', data.tyres_inner_temp_rl, data.tyres_surface_temp_rl);
            this._updateTyreTemp('rr', data.tyres_inner_temp_rr, data.tyres_surface_temp_rr);

            // Brake temps
            this._updateBrakeTemp('fl', data.brakes_temp_fl);
            this._updateBrakeTemp('fr', data.brakes_temp_fr);
            this._updateBrakeTemp('rl', data.brakes_temp_rl);
            this._updateBrakeTemp('rr', data.brakes_temp_rr);

            // Tyre pressures
            this._updatePressure('fl', data.tyres_pressure_fl);
            this._updatePressure('fr', data.tyres_pressure_fr);
            this._updatePressure('rl', data.tyres_pressure_rl);
            this._updatePressure('rr', data.tyres_pressure_rr);

            // Engine temp
            // (displayed in RPM chart title if needed)

            // Update charts (throttle every frame for smoother rendering)
            if (throttleBrakeChart) {
                throttleBrakeChart.data.labels = buffers.time;
                throttleBrakeChart.data.datasets[0].data = buffers.throttle;
                throttleBrakeChart.data.datasets[1].data = buffers.brake;
                throttleBrakeChart.update('none');
            }
            if (speedChart) {
                speedChart.data.labels = buffers.time;
                speedChart.data.datasets[0].data = buffers.speed;
                speedChart.update('none');
            }
            if (rpmChart) {
                rpmChart.data.labels = buffers.time;
                rpmChart.data.datasets[0].data = buffers.rpm;
                rpmChart.update('none');
            }

            // Steering
            drawSteering(data.steer);
        },

        updateMotion(data) {
            if (!data || Object.keys(data).length === 0) return;

            drawTrackMap(data);
            drawGForce(data.g_force_lateral, data.g_force_longitudinal);

            const glatEl = document.getElementById('gforce-lat');
            const glonEl = document.getElementById('gforce-long');
            if (glatEl) glatEl.textContent = `Lat: ${(data.g_force_lateral || 0).toFixed(1)}g`;
            if (glonEl) glonEl.textContent = `Long: ${(data.g_force_longitudinal || 0).toFixed(1)}g`;
        },

        updateLapData(data) {
            if (!data || Object.keys(data).length === 0) return;

            const set = (id, val) => {
                const el = document.getElementById(id);
                if (el) el.textContent = val;
            };

            set('position-value', `P${data.car_position || '--'}`);
            set('lap-number', data.current_lap_num || '--');
            set('current-lap-time', data.current_lap_time_str || '--:--:---');
            set('last-lap-time', data.last_lap_time_str || '--:--:---');
            set('sector-value', `S${(data.sector || 0) + 1}`);
            set('delta-front',
                data.delta_to_car_in_front_ms
                    ? `${(data.delta_to_car_in_front_ms / 1000).toFixed(3)}s`
                    : '--'
            );
        },

        updateCarStatus(data) {
            if (!data || Object.keys(data).length === 0) return;

            // ERS
            const ersBar = document.getElementById('ers-bar');
            const ersLabel = document.getElementById('ers-label');
            const ersMode = document.getElementById('ers-mode');
            const ersDeployed = document.getElementById('ers-deployed');
            if (ersBar) ersBar.style.width = `${data.ers_percent || 0}%`;
            if (ersLabel) ersLabel.textContent = `${data.ers_percent || 0}%`;

            const ersModes = { 0: 'None', 1: 'Medium', 2: 'Hotlap', 3: 'Overtake' };
            if (ersMode) ersMode.textContent = `Mode: ${ersModes[data.ers_deploy_mode] || '--'}`;
            if (ersDeployed) {
                const deployed = data.ers_deployed_this_lap || 0;
                ersDeployed.textContent = `Deployed: ${(deployed / 1_000_000).toFixed(2)} MJ`;
            }

            // Fuel
            const fuelBar = document.getElementById('fuel-bar');
            const fuelRemaining = document.getElementById('fuel-remaining');
            const fuelLaps = document.getElementById('fuel-laps');
            if (data.fuel_capacity && data.fuel_in_tank && fuelBar) {
                const pct = Math.min(100, (data.fuel_in_tank / data.fuel_capacity) * 100);
                fuelBar.style.width = `${pct}%`;
            }
            if (fuelRemaining) fuelRemaining.textContent = `Remaining: ${(data.fuel_in_tank || 0).toFixed(1)} kg`;
            if (fuelLaps) fuelLaps.textContent = `Laps left: ${(data.fuel_remaining_laps || 0).toFixed(1)}`;

            // Tyre compound
            const compEl = document.getElementById('tyre-compound');
            if (compEl) {
                const name = data.visual_tyre_name || '--';
                compEl.textContent = name;
                compEl.className = 'tyre-compound ' + name.toLowerCase();
            }
            const ageEl = document.getElementById('tyre-age');
            if (ageEl) ageEl.textContent = `Age: ${data.tyres_age_laps || 0} laps`;

            // Fuel mix
            const fuelMixEl = document.getElementById('fuel-mix');
            const mixNames = { 0: 'Lean', 1: 'Standard', 2: 'Rich', 3: 'Max' };
            if (fuelMixEl) fuelMixEl.textContent = `Fuel Mix: ${mixNames[data.fuel_mix] || '--'}`;

            // Brake bias
            const biasEl = document.getElementById('brake-bias');
            if (biasEl) biasEl.textContent = `Brake Bias: ${data.front_brake_bias || '--'}%`;
        },

        updateSession(data) {
            if (!data || Object.keys(data).length === 0) return;

            const sessionInfo = document.getElementById('session-info');
            if (sessionInfo) {
                sessionInfo.textContent = `${data.track_name || 'Unknown'} - ${data.session_type_name || '--'}`;
            }
            const weatherInfo = document.getElementById('weather-info');
            if (weatherInfo) weatherInfo.textContent = `🌤️ ${data.weather_name || '--'}`;

            const trackTemp = document.getElementById('track-temp');
            if (trackTemp) trackTemp.textContent = `Track: ${data.track_temperature || '--'}°C`;

            const airTemp = document.getElementById('air-temp');
            if (airTemp) airTemp.textContent = `Air: ${data.air_temperature || '--'}°C`;
        },

        resetTrackHistory() {
            trackHistory = [];
        },

        // Private helpers
        _updateTyreTemp(pos, inner, surface) {
            const innerEl = document.getElementById(`tyre-${pos}-inner`);
            const surfaceEl = document.getElementById(`tyre-${pos}-surface`);
            const boxEl = document.getElementById(`tyre-${pos}`);
            if (innerEl && inner != null) {
                innerEl.textContent = `${inner}°`;
                innerEl.style.color = getTempColor(inner, 'tyre');
            }
            if (surfaceEl && surface != null) {
                surfaceEl.textContent = `${surface}°`;
            }
            if (boxEl && inner != null) {
                boxEl.style.borderColor = getTempColor(inner, 'tyre');
            }
        },

        _updateBrakeTemp(pos, temp) {
            const el = document.getElementById(`brake-${pos}-temp`);
            const box = document.getElementById(`brake-${pos}`);
            if (el && temp != null) {
                el.textContent = `${temp}°`;
                el.style.color = getTempColor(temp, 'brake');
            }
            if (box && temp != null) {
                box.style.borderColor = getTempColor(temp, 'brake');
            }
        },

        _updatePressure(pos, pressure) {
            const el = document.getElementById(`pressure-${pos}-val`);
            if (el && pressure != null) {
                el.textContent = pressure.toFixed(1);
            }
        },
    };
})();

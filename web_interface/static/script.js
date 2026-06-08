console.log("🚀 script.js module execution START");
/**
 * LUNA Robotic Arm - Frontend JavaScript (MPA Overhaul)
 * Socket.IO Client & Modular Control Logic
 */

console.log("📦 Importing Three.js...");
// Import Three.js and Loaders via Importmap
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
console.log("✅ Three.js and GLTFLoader imported");

// Initialize Socket.IO (Global as it's from CDN)
const socket = io({
    transports: ['polling', 'websocket']
});

// Global State
let robotState = {
    motors: { 2: 90, 3: 90, 4: 90, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0 },
    sensors: { distance: 9999, accel_x: 0.0, accel_y: 0.0, accel_z: 0.0 },
    emergency_stop: false,
    connected: false
};

// Chart Instance
let telemetryChart = null;

// Gamepad state
let gamepadConnected = false;
let lastGamepadState = {};
let lastEmitTime = 0;
const EMIT_INTERVAL = 33; // ~30Hz (1000ms / 30)

// Digital Twin (Three.js) variables
let scene, camera, renderer, armModel;
let joints = {}; // Store references to arm parts
let lastTwinUpdateTime = 0;
const TWIN_UPDATE_INTERVAL = 100; // 10Hz update rate
let twinEnabled = true;

// Cleaning and Initialization State (Fix Bug 2.1)
let joystickInstance = null;
let handleTwinResize = null;
let dashboardControlsInitialized = false;
let settingsControlsInitialized = false;
let calibrationControlsInitialized = false;
let voiceCommandsInitialized = false;
let gamepadInitialized = false;
let throttleLastValues = {};

// ==================== UTILITY: MJPEG STREAM THROTTLING ====================
function throttleCameraFeed(active) {
    const videoFeed = document.getElementById('video-feed');
    if (videoFeed) {
        if (active) {
            // Restore active feed
            videoFeed.src = "/video_feed";
            console.log("📹 Camera Feed Restored (Active Dashboard)");
        } else {
            // Shut down network socket feed by setting to empty
            videoFeed.src = "";
            console.log("💤 Camera Feed Throttled (Off-Dashboard)");
        }
    }
}

// ==================== UTILITY: MOBILE SIDEBAR & A11Y SETUP ====================
function setupResponsiveSidebarAndA11y() {
    // Add floating hamburger menu for mobile screens
    if (!document.getElementById('sidebar-toggle')) {
        const toggleBtn = document.createElement('button');
        toggleBtn.id = 'sidebar-toggle';
        toggleBtn.innerHTML = '☰';
        toggleBtn.style.cssText = `
            display: none;
            position: fixed;
            top: 15px;
            left: 15px;
            z-index: 1100;
            background: rgba(10, 10, 10, 0.9);
            border: 2px solid #00f3ff;
            border-radius: 5px;
            color: #00f3ff;
            font-size: 1.5rem;
            padding: 2px 10px;
            cursor: pointer;
            box-shadow: 0 0 10px rgba(0, 243, 255, 0.3);
        `;
        document.body.appendChild(toggleBtn);

        const sidebar = document.querySelector('.sidebar');
        
        toggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (sidebar) {
                sidebar.classList.toggle('active');
            }
        });

        document.addEventListener('click', (e) => {
            if (sidebar && sidebar.classList.contains('active') && !sidebar.contains(e.target) && e.target !== toggleBtn) {
                sidebar.classList.remove('active');
            }
        });

        // Add dynamic CSS rules for mobile responsiveness
        const style = document.createElement('style');
        style.id = 'sidebar-mobile-responsive-styles';
        style.textContent = `
            @media (max-width: 768px) {
                #sidebar-toggle {
                    display: block !important;
                }
                .sidebar {
                    transform: translateX(-100%);
                    transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                }
                .sidebar.active {
                    transform: translateX(0);
                }
                .main-content.with-sidebar {
                    margin-left: 0 !important;
                    width: 100% !important;
                    padding-top: 70px !important;
                }
            }
        `;
        document.head.appendChild(style);
    }

    // Set accessibility live attributes dynamically on speech elements
    ['robot-speech', 'robot-speech-settings', 'robot-speech-diag'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.setAttribute('aria-live', 'polite');
        }
    });
}

// Initialize based on active page
document.addEventListener('DOMContentLoaded', () => {
    initSocketIO();
    initSidebar(); // Still run initially to set up styling
    setupResponsiveSidebarAndA11y();
});

// ==================== PAGE INITIALIZERS ====================

window.initDashboard = function() {
    throttleCameraFeed(true);

    if (document.getElementById('telemetry-chart')) {
        initTelemetryChart();
    }
    initDashboardControls();
    initDigitalTwin();
    initVirtualJoystick();
    initVoiceCommands();
    initGamepad();
};

window.initSettings = function() {
    throttleCameraFeed(false);
    initSettingsControls();
};

window.initDiagnostics = function() {
    throttleCameraFeed(false);
    initCalibrationControls();
};

window.initLogs = async function() {
    throttleCameraFeed(false);
    // Initialize or refresh mission logs asynchronously if needed
    const tableBody = document.getElementById('logs-table-body');
    if (!tableBody) return;

    tableBody.innerHTML = `<tr><td colspan="3" style="padding: 20px; text-align: center; color: #00f3ff;">CONNECTING TO CORE DATAFEED...</td></tr>`;
    try {
        const res = await fetch('/api/logs?page=1&per_page=15');
        const data = await res.json();
        
        if (!data.logs || data.logs.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="3" style="padding: 20px; text-align: center; color: #666;">No recorded mission entries.</td></tr>`;
            return;
        }

        tableBody.innerHTML = '';
        data.logs.forEach(log => {
            const tr = document.createElement('tr');
            tr.style.borderBottom = '1px solid rgba(0, 243, 255, 0.1)';
            const formattedTime = new Date(log.timestamp).toISOString().replace('T', ' ').substring(0, 19);

            tr.innerHTML = `
                <td style="padding: 12px; color: #aaa; font-family: monospace;">${formattedTime}</td>
                <td style="padding: 12px; color: #00f3ff; font-weight: bold; font-family: monospace;">${log.command}</td>
                <td style="padding: 12px; color: #fff; font-family: monospace; font-size: 0.85rem; max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title='${JSON.stringify(log.robot_state)}'>
                    ${JSON.stringify(log.robot_state)}
                </td>
            `;
            tableBody.appendChild(tr);
        });
    } catch (e) {
        console.error("Failed to load logs:", e);
        tableBody.innerHTML = `<tr><td colspan="3" style="padding: 20px; text-align: center; color: #ff0055;">ERROR RETRIEVING MISSION DATA</td></tr>`;
    }
};

window.initProfile = function() {
    throttleCameraFeed(false);
    // Fetch and populate profile if elements exist
    const nameEl = document.getElementById('profile-name');
    if (nameEl && nameEl.textContent === 'Operator Name') {
        fetch('/api/profile')
            .then(res => res.json())
            .then(user => {
                if (user.full_name) nameEl.textContent = user.full_name;
                const roleEl = document.getElementById('profile-role');
                if (roleEl && user.role) roleEl.textContent = user.role.toUpperCase();
                const bioEl = document.getElementById('profile-bio');
                if (bioEl && user.bio) bioEl.textContent = user.bio;
                const usernameEl = document.getElementById('profile-username');
                if (usernameEl && user.username) usernameEl.textContent = user.username;
            })
            .catch(err => console.error("Operator Profile Sync Offline:", err));
    }
};

// ==================== SIDEBAR ====================
function initSidebar() {
    const currentPath = window.location.pathname;
    document.querySelectorAll('.nav-item').forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });
}

// ==================== SOCKET.IO ====================

function initSocketIO() {
    socket.on('connect', () => updateConnectionStatus(true));
    socket.on('disconnect', () => updateConnectionStatus(false));

    socket.on('state_update', (state) => {
        console.log("State update received:", state);
        robotState = state;
        syncUIWithState();
    });

    socket.on('telemetry_update', (sensors) => {
        robotState.sensors = sensors;
        updateTelemetryUI();
        updateTelemetryChart();
    });

    socket.on('emergency_stop', (data) => {
        robotState.emergency_stop = data.active;
        updateEmergencyUI(data.active);
    });

    socket.on('robot_speech', (data) => {
        const speechEl = document.getElementById('robot-speech');
        if (speechEl) {
            speechEl.textContent = `🤖 LUNA: "${data.text}"`;
            speechEl.style.opacity = '1';
        }
    });
}

function updateConnectionStatus(connected) {
    const statusEl = document.getElementById('connection-status');
    if (statusEl) {
        statusEl.textContent = connected ? '🟢 ONLINE' : '🔴 OFFLINE';
        statusEl.classList.toggle('connected', connected);
    }
    robotState.connected = connected;
}

function updateEmergencyUI(active) {
    const statusEl = document.getElementById('emergency-status');
    if (statusEl) {
        statusEl.classList.toggle('hidden', !active);
        statusEl.classList.toggle('emergency', active);
    }
}

// ==================== DASHBOARD LOGIC ====================

function initTelemetryChart() {
    if (telemetryChart) {
        telemetryChart.destroy(); // Make idempotent
    }
    const ctx = document.getElementById('telemetry-chart')?.getContext('2d');
    if (!ctx) return;
    
    telemetryChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Distance (cm)',
                data: [],
                borderColor: '#00f3ff',
                backgroundColor: 'rgba(0, 243, 255, 0.1)',
                borderWidth: 2,
                pointRadius: 0,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { display: false },
                y: { grid: { color: 'rgba(255,255,255,0.05)' }, min: 0, max: 200 }
            },
            plugins: { legend: { display: false } }
        }
    });
}

function updateTelemetryChart() {
    if (!telemetryChart) return;
    const now = new Date().toLocaleTimeString();
    telemetryChart.data.labels.push(now);
    telemetryChart.data.datasets[0].data.push(robotState.sensors.distance);
    if (telemetryChart.data.labels.length > 50) {
        telemetryChart.data.labels.shift();
        telemetryChart.data.datasets[0].data.shift();
    }
    telemetryChart.update('none');
}

function initDashboardControls() {
    if (dashboardControlsInitialized) return;
    document.getElementById('toggle-camera')?.addEventListener('click', () => {
        socket.emit('toggle_camera');
    });

    document.getElementById('home-btn')?.addEventListener('click', () => {
        socket.emit('home_position');
    });

    document.getElementById('emergency-btn')?.addEventListener('click', () => {
        socket.emit('emergency_stop');
    });

    document.getElementById('toggle-3d')?.addEventListener('change', (e) => {
        twinEnabled = e.target.checked;
        const container = document.getElementById('twin-container');
        if (container) container.style.opacity = twinEnabled ? '1' : '0.2';
    });
    dashboardControlsInitialized = true;
}

function updateTelemetryUI() {
    const distEl = document.getElementById('distance-value');
    if (distEl) {
        const newText = `${robotState.sensors.distance} cm`;
        if (distEl.textContent !== newText) {
            distEl.textContent = newText;
        }
    }

    ['x', 'y', 'z'].forEach(axis => {
        const el = document.getElementById(`accel-${axis}-value`);
        if (el) {
            const newVal = robotState.sensors[`accel_${axis}`].toFixed(2);
            if (el.textContent !== newVal) {
                el.textContent = newVal;
            }
        }
    });

    updateDigitalTwin();
}

// ==================== DIGITAL TWIN (THREE.JS) ====================

function initDigitalTwin() {
    console.log("🛠️ Initializing Three.js scene...");
    const container = document.querySelector('.digital-twin-container');
    const canvas = document.getElementById('digital-twin');
    if (!container || !canvas) return;

    // Clean up previous Digital Twin if it exists (Fix Bug 2.1)
    if (renderer) {
        console.log("♻️ Disposing of previous Three.js digital twin renderer...");
        try {
            renderer.dispose();
        } catch (e) {
            console.error("Error disposing renderer:", e);
        }
    }
    if (scene) {
        scene.traverse((object) => {
            if (object.isMesh) {
                if (object.geometry) {
                    try {
                        object.geometry.dispose();
                    } catch (e) {}
                }
                if (object.material) {
                    if (Array.isArray(object.material)) {
                        object.material.forEach(mat => {
                            try { mat.dispose(); } catch (e) {}
                        });
                    } else {
                        try { object.material.dispose(); } catch (e) {}
                    }
                }
            }
        });
    }

    joints = {};
    armModel = null;

    // Scene Setup
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x050505);

    // Camera
    const aspect = container.clientWidth / container.clientHeight;
    camera = new THREE.PerspectiveCamera(45, aspect, 0.1, 1000);
    camera.position.set(5, 5, 5); // Closer for the model
    camera.lookAt(0, 1, 0);

    // Renderer
    renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(window.devicePixelRatio);

    // Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 1.2); // Brighter
    scene.add(ambientLight);

    const pointLight = new THREE.PointLight(0x00f3ff, 2); // Brighter
    pointLight.position.set(5, 10, 5);
    scene.add(pointLight);

    const gridHelper = new THREE.GridHelper(10, 10, 0x00f3ff, 0x111111);
    scene.add(gridHelper);

    // Load GLB Model
    // ----------------------------------------------------
    const loader = new GLTFLoader();
    loader.load('/static/models/luna_arm.glb', (gltf) => {
        armModel = gltf.scene;
        scene.add(armModel);

        // Center and scale model properly
        const box = new THREE.Box3().setFromObject(armModel);
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        console.log(`📏 Model Size: ${size.x.toFixed(2)}x${size.y.toFixed(2)}x${size.z.toFixed(2)}`);

        // Offset so base is at 0,0,0
        armModel.position.set(-center.x, -box.min.y, -center.z);

        // Scale to fit roughly half the grid (5 units)
        const maxDim = Math.max(size.x, size.y, size.z);
        const targetSize = 5;
        const scale = targetSize / maxDim;
        armModel.scale.setScalar(scale);
        console.log(`⚖️ Applied Scale: ${scale.toFixed(4)}`);

        // Discovery and mapping of joints
        console.log("🔍 Traversing model for parts...");

        const logHierarchy = (obj, depth = 0) => {
            console.log("  ".repeat(depth) + `- "${obj.name}" [${obj.type}]`);
            obj.children.forEach(child => logHierarchy(child, depth + 1));
        };
        logHierarchy(armModel);

        armModel.traverse(child => {
            const name = child.name;
            const lowerName = name.toLowerCase();

            // Broaden mapping logic
            if (lowerName.includes('base') || name.includes('Node1')) joints['base'] = child;
            if (lowerName.includes('link1') || lowerName.includes('elbow') || name.includes('Node2') || name.includes('Node3')) joints[2] = child;
            if (lowerName.includes('link2') || lowerName.includes('wrist_pitch') || name.includes('Node4') || name.includes('Node5')) joints[3] = child;
            if (lowerName.includes('link3') || lowerName.includes('wrist_roll') || name.includes('Node6') || name.includes('Node7')) joints[4] = child;

            // Heuristic for fingers
            if (name.includes('Node10')) joints[5] = child;
            if (name.includes('Node11')) joints[6] = child;
            if (name.includes('Node12')) joints[7] = child;
            if (name.includes('Node13')) joints[8] = child;
            if (name.includes('Node14')) joints[9] = child;
        });

        // Expose for browser debugging
        window.lunaArm = armModel;
        window.lunaJoints = joints;

        console.log("🤖 LUNA GLB LOADED. Joints detected:", Object.keys(joints));
        
        // Validation: Check for missing joints
        const requiredJoints = [2, 3, 4, 5, 6, 7, 8, 9];
        const missingJoints = requiredJoints.filter(id => !joints[id]);
        if (missingJoints.length > 0) {
            console.warn(`⚠️ Missing joints in model: ${missingJoints.join(', ')}`);
            console.warn("Digital twin animation may not work correctly for these motors.");
        }
    }, undefined, (error) => {
        console.error("❌ GLB LOAD FAILED:", error);
    });

    animateDigitalTwin();

    if (handleTwinResize) {
        window.removeEventListener('resize', handleTwinResize);
    }
    handleTwinResize = () => {
        if (!container || !camera || !renderer) return;
        const width = container.clientWidth;
        const height = container.clientHeight;
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
        renderer.setSize(width, height);
    };
    window.addEventListener('resize', handleTwinResize);
}

function animateDigitalTwin() {
    if (renderer && scene && camera) {
        renderer.render(scene, camera);
    }
    requestAnimationFrame(animateDigitalTwin);
}

function updateDigitalTwin() {
    if (!armModel || !twinEnabled) return;

    const now = Date.now();
    if (now - lastTwinUpdateTime < TWIN_UPDATE_INTERVAL) return;
    lastTwinUpdateTime = now;

    // Apply motor angles to identified joints
    Object.keys(joints).forEach(id => {
        const joint = joints[id];
        if (id === 'base') return; // Base is usually static or pivot

        const motorId = parseInt(id);
        if (isNaN(motorId)) return;

        const angleVal = robotState.motors[motorId];
        if (angleVal === undefined) return;

        const rads = THREE.MathUtils.degToRad(angleVal - 90); // Normalizing 0-180 to -90 to 90

        // Axis mapping (may need tuning per model orientation)
        if (motorId === 2) joint.rotation.x = rads;      // Elbow
        if (motorId === 3) joint.rotation.x = rads;      // Wrist Pitch
        if (motorId === 4) joint.rotation.y = rads;      // Wrist Roll

        // Grip/Fingers (IDs 5-9)
        if (motorId >= 5) {
            // Fingers usually curl on one axis
            const curlRads = THREE.MathUtils.degToRad(angleVal);
            joint.rotation.z = curlRads;
        }
    });
}

// ==================== VIRTUAL JOYSTICK (NIPPLEJS) ====================

function initVirtualJoystick() {
    const zone = document.getElementById('joystick-zone');
    if (!zone) return;

    // Destroy existing joystick if present (Fix Bug 2.1)
    if (joystickInstance) {
        try {
            joystickInstance.destroy();
            console.log("♻️ Destroyed previous virtual joystick instance");
        } catch (e) {
            console.warn("Error destroying joystick:", e);
        }
        joystickInstance = null;
    }

    // Support responsive scaling on mobile/touch interfaces
    const isTouch = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);
    const joystickSize = isTouch ? 150 : 100;
    const joystickMode = isTouch ? 'dynamic' : 'static';

    joystickInstance = nipplejs.create({
        zone: zone,
        mode: joystickMode,
        position: isTouch ? undefined : { left: '50%', top: '50%' },
        color: '#00f3ff',
        size: joystickSize
    });

    joystickInstance.on('move', (evt, data) => {
        if (data.vector) {
            socket.emit('joystick_move', { x: data.vector.x, y: data.vector.y });
        }
    });

    joystickInstance.on('end', () => socket.emit('joystick_move', { x: 0, y: 0 }));
}

// ==================== SETTINGS LOGIC ====================

function initSettingsControls() {
    if (settingsControlsInitialized) return;
    document.getElementById('toggle-track')?.addEventListener('change', (e) => {
        socket.emit('toggle_track_mode', { enable: e.target.checked });
    });

    document.getElementById('toggle-mimic')?.addEventListener('change', (e) => {
        socket.emit('toggle_mimic_mode', { enable: e.target.checked });
    });

    document.getElementById('update-ai')?.addEventListener('click', () => {
        const prompt = document.getElementById('ai-prompt').value;
        socket.emit('update_ai_personality', { prompt: prompt });
        alert('Directive Uplinked to Brain.');
    });
    settingsControlsInitialized = true;
}

// ==================== DIAGNOSTICS LOGIC ====================

let throttleTimeouts = {};

function initCalibrationControls() {
    if (calibrationControlsInitialized) return;
    for (let i = 2; i <= 9; i++) {
        const slider = document.getElementById(`motor-${i}-diag`);
        const valueEl = document.getElementById(`motor-${i}-value-diag`);
        if (slider) {
            slider.addEventListener('input', (e) => {
                const angle = parseInt(e.target.value);
                if (valueEl) valueEl.textContent = angle;
                
                throttleLastValues[i] = angle;

                // Implement trailing-edge and leading-edge hybrid throttle (Fix Bug 2.5)
                if (!throttleTimeouts[i]) {
                    // Send leading edge
                    socket.emit('motor_command', { motor_id: i, angle: angle });
                    
                    throttleTimeouts[i] = setTimeout(() => {
                        // Check if a new value was received during the timeout
                        if (throttleLastValues[i] !== undefined && throttleLastValues[i] !== angle) {
                            socket.emit('motor_command', { motor_id: i, angle: throttleLastValues[i] });
                        }
                        throttleTimeouts[i] = null;
                    }, 40);
                }
            });
        }
    }
    calibrationControlsInitialized = true;
}

function syncUIWithState() {
    for (let i = 2; i <= 9; i++) {
        const slider = document.getElementById(`motor-${i}-diag`);
        const valueEl = document.getElementById(`motor-${i}-value-diag`);
        if (slider && robotState.motors[i] !== undefined) {
            const targetVal = robotState.motors[i];
            // Only update if value is different to avoid layout thrashing (Fix Bug 2.9)
            if (parseInt(slider.value) !== targetVal) {
                slider.value = targetVal;
            }
            if (valueEl && parseInt(valueEl.textContent) !== targetVal) {
                valueEl.textContent = targetVal;
            }
        }
    }
}

// ==================== VOICE COMMANDS ====================

function initVoiceCommands() {
    if (voiceCommandsInitialized) return;
    const startBtn = document.getElementById('start-voice');
    if (!startBtn) return;

    startBtn.addEventListener('click', () => {
        socket.emit('toggle_voice', { enable: true });
        startBtn.textContent = 'LISTENING...';
        startBtn.classList.add('btn-danger');
    });

    socket.on('voice_status', (data) => {
        const statusEl = document.getElementById('voice-status');
        if (statusEl) statusEl.textContent = `MODE: ${data.status.toUpperCase()}`;
        if (!data.listening) {
            startBtn.textContent = 'START UPLINK';
            startBtn.classList.remove('btn-danger');
        }
    });
    voiceCommandsInitialized = true;
}

// ==================== GAMEPAD CONTROL ====================

function initGamepad() {
    if (gamepadInitialized) return;
    window.addEventListener("gamepadconnected", (e) => {
        updateGamepadStatus(true);
        gamepadConnected = true;
        startGamepadLoop();
    });

    window.addEventListener("gamepaddisconnected", () => {
        updateGamepadStatus(false);
        gamepadConnected = false;
    });

    if (navigator.getGamepads()[0]) {
        updateGamepadStatus(true);
        gamepadConnected = true;
        startGamepadLoop();
    }
    gamepadInitialized = true;
}

function updateGamepadStatus(connected) {
    const statusEl = document.getElementById('gamepad-status');
    const statusElRight = document.getElementById('gamepad-status-right');
    const text = connected ? '🎮 GP-LINK ACTIVE' : '🎮 GP-LINK LOST';
    const color = connected ? '#0aff0a' : '#ff2a2a';
    
    if (statusEl) {
        statusEl.textContent = text;
        statusEl.style.color = color;
    }
    if (statusElRight) {
        statusElRight.textContent = text;
        statusElRight.style.color = color;
    }
}

function startGamepadLoop() {
    if (!gamepadConnected) return;

    const gamepads = navigator.getGamepads();
    const gp = gamepads[0];

    if (gp) {
        const now = Date.now();
        if (now - lastEmitTime > EMIT_INTERVAL) {
            const data = {
                left_stick_y: Math.abs(gp.axes[1]) > 0.15 ? -gp.axes[1] : 0,
                right_stick_y: Math.abs(gp.axes[3]) > 0.15 ? -gp.axes[3] : 0,
                right_stick_x: Math.abs(gp.axes[2]) > 0.15 ? gp.axes[2] : 0,
                left_trigger: gp.buttons[6].value,
                right_trigger: gp.buttons[7].value
            };

            if (JSON.stringify(data) !== JSON.stringify(lastGamepadState)) {
                if (Object.values(data).some(v => Math.abs(v) > 0.1)) {
                    socket.emit('gamepad_data', data);
                }
                lastGamepadState = data;
                lastEmitTime = now;
            }
        }
    }

    requestAnimationFrame(startGamepadLoop);
}

// ==================== SECURITY AUDIT LOGS ====================
window.initLoginHistory = async function() {
    throttleCameraFeed(false);
    const tableBody = document.getElementById('login-history-table-body');
    if (!tableBody) return;

    tableBody.innerHTML = `<tr><td colspan="5" style="padding: 20px; text-align: center; color: #00f3ff;">CONNECTING TO CORE DATAFEED...</td></tr>`;
    try {
        const res = await fetch('/api/login-history');
        const data = await res.json();
        
        if (!data.history || data.history.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="5" style="padding: 20px; text-align: center; color: #666;">No recorded session entries.</td></tr>`;
            return;
        }

        tableBody.innerHTML = '';
        data.history.forEach(entry => {
            const tr = document.createElement('tr');
            tr.style.borderBottom = '1px solid rgba(0, 243, 255, 0.1)';
            const formattedTime = new Date(entry.login_time).toISOString().replace('T', ' ').substring(0, 19);
            const statusBadge = entry.success 
                ? `<span class="badge badge-success" style="background: rgba(0, 255, 100, 0.1); color: #00ff66; padding: 4px 8px; border-radius: 3px; border: 1px solid rgba(0, 255, 100, 0.3);">SUCCESS</span>`
                : `<span class="badge badge-danger" style="background: rgba(255, 50, 50, 0.1); color: #ff3e3e; padding: 4px 8px; border-radius: 3px; border: 1px solid rgba(255, 50, 50, 0.3);">FAILED</span>`;

            tr.innerHTML = `
                <td style="padding: 12px; color: #aaa; font-family: monospace;">${entry.id}</td>
                <td style="padding: 12px; color: #00f3ff; font-weight: bold; font-family: monospace;">${entry.ip_address}</td>
                <td style="padding: 12px; color: #ccc; font-family: monospace; font-size: 0.85rem; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${entry.user_agent}">${entry.user_agent}</td>
                <td style="padding: 12px; color: #888; font-family: monospace;">${formattedTime}</td>
                <td style="padding: 12px; color: #fff; font-family: monospace;">${statusBadge}</td>
            `;
            tableBody.appendChild(tr);
        });
    } catch (e) {
        console.error("Failed to load login history:", e);
        tableBody.innerHTML = `<tr><td colspan="5" style="padding: 20px; text-align: center; color: #ff0055;">ERROR RETRIEVING SESSION DATA</td></tr>`;
    }
};

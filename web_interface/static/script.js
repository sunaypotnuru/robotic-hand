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

// Initialize based on active page
document.addEventListener('DOMContentLoaded', () => {
    initSocketIO();

    // Page-specific initializers
    if (document.getElementById('telemetry-chart')) {
        initTelemetryChart();
    }

    if (document.getElementById('video-feed')) {
        initDashboardControls();
        initDigitalTwin();
        initVirtualJoystick();
    }

    if (document.getElementById('toggle-track')) {
        initSettingsControls();
    }

    if (document.getElementById('motor-2')) {
        initCalibrationControls();
    }

    initVoiceCommands();
    initGamepad();
    initSidebar();
});

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
}

function updateTelemetryUI() {
    const distEl = document.getElementById('distance-value');
    if (distEl) distEl.textContent = `${robotState.sensors.distance} cm`;

    ['x', 'y', 'z'].forEach(axis => {
        const el = document.getElementById(`accel-${axis}-value`);
        if (el) el.textContent = robotState.sensors[`accel_${axis}`].toFixed(2);
    });

    updateDigitalTwin();
}

// ==================== DIGITAL TWIN (THREE.JS) ====================

function initDigitalTwin() {
    console.log("🛠️ Initializing Three.js scene...");
    const container = document.querySelector('.digital-twin-container');
    const canvas = document.getElementById('digital-twin');
    if (!container || !canvas) return;

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

        // Expose for browser subagent debugging
        window.lunaArm = armModel;
        window.lunaJoints = joints;

        console.log("🤖 LUNA GLB LOADED. Joints detected:", Object.keys(joints));
    }, undefined, (error) => {
        console.error("❌ GLB LOAD FAILED:", error);
    });

    animateDigitalTwin();

    window.addEventListener('resize', () => {
        const width = container.clientWidth;
        const height = container.clientHeight;
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
        renderer.setSize(width, height);
    });
}

function animateDigitalTwin() {
    requestAnimationFrame(animateDigitalTwin);
    if (renderer && scene && camera) {
        renderer.render(scene, camera);
    }
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

    const inst = nipplejs.create({
        zone: zone,
        mode: 'static',
        position: { left: '50%', top: '50%' },
        color: '#00f3ff',
        size: 100
    });

    inst.on('move', (evt, data) => {
        if (data.vector) {
            socket.emit('joystick_move', { x: data.vector.x, y: data.vector.y });
        }
    });

    inst.on('end', () => socket.emit('joystick_move', { x: 0, y: 0 }));
}

// ==================== SETTINGS LOGIC ====================

function initSettingsControls() {
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
}

// ==================== DIAGNOSTICS LOGIC ====================

function initCalibrationControls() {
    for (let i = 2; i <= 9; i++) {
        const slider = document.getElementById(`motor-${i}`);
        const valueEl = document.getElementById(`motor-${i}-value`);
        if (slider) {
            slider.addEventListener('input', (e) => {
                const angle = parseInt(e.target.value);
                if (valueEl) valueEl.textContent = angle;
                socket.emit('motor_command', { motor_id: i, angle: angle });
            });
        }
    }
}

function syncUIWithState() {
    for (let i = 2; i <= 9; i++) {
        const slider = document.getElementById(`motor-${i}`);
        const valueEl = document.getElementById(`motor-${i}-value`);
        if (slider && robotState.motors[i] !== undefined) {
            slider.value = robotState.motors[i];
            if (valueEl) valueEl.textContent = robotState.motors[i];
        }
    }
}

// ==================== VOICE COMMANDS ====================

function initVoiceCommands() {
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
}

// ==================== GAMEPAD CONTROL ====================

function initGamepad() {
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
}

function updateGamepadStatus(connected) {
    const statusEl = document.getElementById('gamepad-status');
    if (statusEl) {
        statusEl.textContent = connected ? '🎮 GP-LINK ACTIVE' : '🎮 GP-LINK LOST';
        statusEl.style.color = connected ? '#0aff0a' : '#ff2a2a';
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

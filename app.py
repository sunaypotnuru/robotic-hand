import os
import sys
import threading
import time
import json
import queue
import logging
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, Response, jsonify, request, redirect, url_for, flash
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import serial
import serial.tools.list_ports
import config

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=getattr(logging, config.LOG_LEVEL), format=config.LOG_FORMAT)
logger = logging.getLogger("LUNA")

# Add web_interface to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'web_interface'))

from ai_modules.object_detect import ObjectDetector
from ai_modules.hand_tracking import HandTracker
from ai_modules.voice_cmd import VoiceCommandProcessor
from ai_modules.kinematics import SimpleKinematics

# Initialize Flask App
app = Flask(__name__, 
            template_folder='web_interface/templates',
            static_folder='web_interface/static')

# Configuration from .env
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'luna_robotic_arm_secret_key_2024')

# Database Configuration (Supports MySQL and Supabase/PostgreSQL)
db_url = os.getenv('DATABASE_URL')
if not db_url:
    # Fallback to individual components (MySQL legacy)
    db_url = f"mysql+mysqlconnector://{os.getenv('MYSQL_USER')}:{os.getenv('MYSQL_PASSWORD')}@{os.getenv('MYSQL_HOST', 'localhost')}/{os.getenv('MYSQL_DATABASE', 'luna_db')}"

# SQLAlchemy 1.4+ / 2.0+ requires 'postgresql://' instead of 'postgres://'
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

# Upload settings
UPLOAD_FOLDER = os.path.join(app.root_path, 'web_interface', 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Initialize Extensions
db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# ==================== DATABASE MODELS ====================

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.Enum('admin', 'operator', name='user_roles'), nullable=False, default='operator')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Profile Info
    full_name = db.Column(db.String(100))
    bio = db.Column(db.Text)
    photo_url = db.Column(db.String(200))
    linkedin_url = db.Column(db.String(200))
    github_url = db.Column(db.String(200))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class TeamMember(db.Model):
    __tablename__ = 'team_members'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(100), nullable=False)
    bio = db.Column(db.Text)
    photo_url = db.Column(db.String(200))
    linkedin_url = db.Column(db.String(200))
    github_url = db.Column(db.String(200))
    display_order = db.Column(db.Integer, default=0)

class SiteContent(db.Model):
    __tablename__ = 'site_content'
    id = db.Column(db.Integer, primary_key=True)
    page_section = db.Column(db.String(100), unique=True, nullable=False)
    content_text = db.Column(db.Text, nullable=False)

class MissionLog(db.Model):
    __tablename__ = 'mission_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    command = db.Column(db.String(50), nullable=False)
    robot_state = db.Column(db.JSON, nullable=False)

    user = db.relationship('User', backref=db.backref('logs', cascade='all, delete-orphan'))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==================== HELPERS ====================

def log_mission(command_type, details, user_id=None):
    """Log robotic actions to the database.
    
    Args:
        command_type: Type of command (motor, batch, system, etc.)
        details: Dict of command details to store as JSON.
        user_id: Optional explicit user ID. If None, falls back to current
                 request user, then first admin in DB.
    """
    with app.app_context():
        try:
            resolved_id = user_id
            if resolved_id is None:
                from flask import has_request_context
                if has_request_context() and current_user.is_authenticated:
                    resolved_id = current_user.id
                else:
                    # Background thread fallback: use first admin
                    system_user = User.query.filter_by(role='admin').first()
                    if system_user:
                        resolved_id = system_user.id
            
            if resolved_id:
                log = MissionLog(
                    user_id=resolved_id,
                    command=command_type,
                    robot_state=details
                )
                db.session.add(log)
                db.session.commit()
        except Exception as e:
            logger.error(f"[WARN] Mission log failed: {e}")
            db.session.rollback()

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Admin clearance required for this operation.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== ROBOT STATE ====================

# Global Robot State
robot_state = {
    'motors': {
        2: 90,   # Main Pivot (Elbow)
        3: 90,   # Wrist Pitch
        4: 90,   # Wrist Roll
        5: 0,    # Thumb
        6: 0,    # Index
        7: 0,    # Middle
        8: 0,    # Ring
        9: 0,    # Pinky
    },
    'sensors': {
        'distance': 9999,  # cm
        'accel_x': 0.0,
        'accel_y': 0.0,
        'accel_z': 0.0,
    },
    'emergency_stop': False,
    'connected': False,
    'camera_active': False,
    'target_motors': {  # Targets for smooth AI motion
        2: 90, 3: 90, 4: 90, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0
    },
}

# Serial Communication
arduino_serial = None
serial_thread = None
serial_lock = threading.Lock()
serial_queue = queue.Queue()

# AI Modules
object_detector = None
hand_tracker = None
voice_processor = None
kinematics = SimpleKinematics(link_length=28.0)  # 28cm forearm

# Configuration
SERIAL_PORT = config.SERIAL_PORT
BAUD_RATE = config.BAUD_RATE
SERIAL_TIMEOUT = config.SERIAL_TIMEOUT

# Camera
camera = None
camera_lock = threading.Lock()

# Import cv2 at module level for video streaming
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.warning("[WARN] OpenCV not available - video feed will be disabled")


def find_arduino_port():
    """Auto-detect Arduino Mega port"""
    ports = serial.tools.list_ports.comports()
    for port in ports:
        # Common identifiers for Arduino Mega
        if 'Arduino' in port.description or 'USB Serial' in port.description or 'CH340' in port.description:
            return port.device
    # Fallback: try COM3-COM10 on Windows
    if sys.platform == 'win32':
        for i in range(3, 11):
            try:
                test_port = f'COM{i}'
                test_serial = serial.Serial(test_port, BAUD_RATE, timeout=0.1)
                test_serial.close()
                return test_port
            except:
                continue
    return None


def init_serial_connection():
    """Initialize serial connection to Arduino"""
    global arduino_serial, SERIAL_PORT
    
    if SERIAL_PORT is None:
        SERIAL_PORT = find_arduino_port()
    
    if SERIAL_PORT is None:
        logger.warning("[WARN] No Arduino port detected. Running in simulation mode.")
        robot_state['connected'] = False
        return False
    
    try:
        arduino_serial = serial.Serial(
            SERIAL_PORT, 
            BAUD_RATE, 
            timeout=SERIAL_TIMEOUT,
            write_timeout=1.0
        )
        time.sleep(2)  # Wait for Arduino to initialize
        robot_state['connected'] = True
        logger.info(f"[OK] Connected to Arduino on {SERIAL_PORT}")
        return True
    except Exception as e:
        logger.error(f"[ERROR] Serial connection error: {e}")
        robot_state['connected'] = False
        return False


def send_motor_command(motor_id, angle, force=False):
    """
    Send motor command to Arduino
    CRITICAL: Never send commands to ID 0 or 1 (removed shoulder)
    """
    # Safety check: Block IDs 0 and 1
    if motor_id in [0, 1]:
        print(f"[WARN] BLOCKED: Attempted to control removed motor ID {motor_id}")
        return False
    
    # Validate motor ID range
    if motor_id < 2 or motor_id > 9:
        print(f"[WARN] INVALID: Motor ID {motor_id} out of range (2-9)")
        return False
    
    # Validate angle range
    angle = max(0, min(180, int(angle)))
    
    # Emergency stop check
    if robot_state['emergency_stop'] and not force:
        logger.warning("[STOP] EMERGENCY STOP ACTIVE - Command blocked")
        return False
    
    # Update state
    robot_state['motors'][motor_id] = angle
    
    # Add to serial queue
    command = f"M:{motor_id}:{angle}\n"
    serial_queue.put(command)
    
    # Log the mission
    log_mission('motor', {'motor_id': motor_id, 'angle': angle, 'timestamp': time.time()})
    
    return True


def send_batch_commands(commands_dict):
    """Send multiple motor commands in batch format: B:ID:ANGLE:ID:ANGLE..."""
    # Filter out IDs 0 and 1
    valid_commands = {k: v for k, v in commands_dict.items() if k not in [0, 1] and 2 <= k <= 9}
    
    if not valid_commands:
        return False
    
    if robot_state['emergency_stop']:
        logger.warning("[STOP] EMERGENCY STOP ACTIVE - Batch command blocked")
        return False
    
    # Build batch command
    batch_parts = ["B"]
    for motor_id, angle in valid_commands.items():
        angle = max(0, min(180, int(angle)))
        robot_state['motors'][motor_id] = angle
        batch_parts.append(f"{motor_id}:{angle}")
    
    command = ":".join(batch_parts) + "\n"
    serial_queue.put(command)
    
    # Log the mission
    log_mission('batch', {'commands': valid_commands, 'timestamp': time.time()})
    
    return True


def serial_writer_thread():
    """Background thread to process serial command queue"""
    logger.info("[THREAD] Serial writer thread started")
    
    while True:
        try:
            command = serial_queue.get(timeout=1.0)
            if arduino_serial and arduino_serial.is_open:
                with serial_lock:
                    arduino_serial.write(command.encode('utf-8'))
                logger.debug(f"[OUT] Sent: {command.strip()}")
            else:
                logger.debug(f"[SIM] Simulated: {command.strip()}")
            serial_queue.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            logger.error(f"[ERROR] Serial write error: {e}")
            time.sleep(0.1)


def emergency_stop():
    """Trigger emergency stop"""
    robot_state['emergency_stop'] = True
    # Send emergency stop to all motors (set to safe position)
    safe_commands = {2: 90, 3: 90, 4: 90}  # Center positions
    send_batch_commands(safe_commands)
    socketio.emit('emergency_stop', {'active': True})
    logger.critical("[STOP] EMERGENCY STOP ACTIVATED")


def serial_reader_thread():
    """Background thread to read telemetry from Arduino"""
    
    while True:
        if arduino_serial and arduino_serial.is_open:
            try:
                if arduino_serial.in_waiting:
                    line = arduino_serial.readline().decode('utf-8', errors='ignore').strip()
                    
                    # Parse sensor data from ESP32 (forwarded by Arduino)
                    if line.startswith("SENSOR DATA: <"):
                        # Format: <D:150,AX:0.5>
                        try:
                            data_str = line.replace("SENSOR DATA: <", "").replace(">", "")
                            parts = data_str.split(',')
                            
                            for part in parts:
                                if part.startswith('D:'):
                                    distance = int(float(part.split(':')[1]))
                                    robot_state['sensors']['distance'] = distance
                                    
                                    # Safety check: Emergency stop if too close
                                    if distance < 10 and not robot_state['emergency_stop']:
                                        emergency_stop()
                                        
                                elif part.startswith('AX:'):
                                    robot_state['sensors']['accel_x'] = float(part.split(':')[1])
                                elif part.startswith('AY:'):
                                    robot_state['sensors']['accel_y'] = float(part.split(':')[1])
                                elif part.startswith('AZ:'):
                                    robot_state['sensors']['accel_z'] = float(part.split(':')[1])
                            
                            # Emit telemetry update
                            socketio.emit('telemetry_update', robot_state['sensors'])
                            
                        except Exception as e:
                            logger.warning(f"[WARN] Parse error: {e}")
                    
                    # Parse motor feedback
                    elif "Moving" in line:
                        logger.debug(f"[IN] Arduino: {line}")
                        
            except Exception as e:
                logger.error(f"[ERROR] Serial read error: {e}")
                time.sleep(0.1)
        else:
            time.sleep(1)


def generate_frames():
    """Video streaming generator with AI processing"""
    global camera, object_detector, hand_tracker
    
    if not CV2_AVAILABLE:
        return
    
    # Initialize camera
    if camera is None:
        try:
            camera = cv2.VideoCapture(0)
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            robot_state['camera_active'] = True
        except Exception as e:
            logger.error(f"[ERROR] Camera error: {e}")
            return
    
    # Initialize AI modules if needed
    if object_detector is None:
        object_detector = ObjectDetector()
    if hand_tracker is None:
        hand_tracker = HandTracker()
    
    while True:
        with camera_lock:
            success, frame = camera.read()
            if not success:
                break
            
            # Process with AI
            if object_detector:
                frame = object_detector.process_frame(frame)
            if hand_tracker:
                frame = hand_tracker.process_frame(frame)
            
            # Encode frame
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                continue
            frame_bytes = buffer.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


# ==================== FLASK ROUTES ====================

# ==================== AUTH ROUTES (SPA API) ====================

@app.route('/api/auth-status', methods=['GET'])
def auth_status():
    if current_user.is_authenticated:
        return jsonify({
            'authenticated': True,
            'user': {
                'username': current_user.username,
                'role': current_user.role,
                'full_name': current_user.full_name
            }
        })
    else:
        return jsonify({'authenticated': False})

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    user = User.query.filter_by(username=username).first()
    
    if user and user.check_password(password):
        login_user(user)
        return jsonify({
            'success': True,
            'user': {
                'username': user.username,
                'role': user.role,
                'full_name': user.full_name
            }
        })
    else:
        return jsonify({'success': False, 'message': 'Invalid Operator ID or Encryption Key'}), 401

@app.route('/api/logout', methods=['POST'])
def api_logout():
    logout_user()
    return jsonify({'success': True})

# Legacy fallback routes redirect to SPA
@app.route('/login', methods=['GET'])
def login():
    return redirect(url_for('index', **request.args))

@app.route('/register', methods=['GET', 'POST'])
def register():
    # Keep register page functional for now, or redirect to SPA if it has a register section
    return redirect(url_for('index'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# ==================== PUBLIC ROUTES ====================

@app.route('/')
def index():
    """Single Page Application Root"""
    return render_template('base.html')


@app.route('/about')
def about():
    """About page (Dynamic)"""
    desc = SiteContent.query.filter_by(page_section='about_description').first()
    return render_template('about.html', 
                          description=desc.content_text if desc else None)


@app.route('/contact')
def contact():
    """Contact page (Dynamic)"""
    email = SiteContent.query.filter_by(page_section='contact_email').first()
    phone = SiteContent.query.filter_by(page_section='contact_phone').first()
    address = SiteContent.query.filter_by(page_section='contact_address').first()
    github = SiteContent.query.filter_by(page_section='contact_github').first()
    linkedin = SiteContent.query.filter_by(page_section='contact_linkedin').first()
    university = SiteContent.query.filter_by(page_section='institution_website').first()
    return render_template('contact.html',
                          email=email.content_text if email else None,
                          phone=phone.content_text if phone else None,
                          address=address.content_text if address else None,
                          github=github.content_text if github else None,
                          linkedin=linkedin.content_text if linkedin else None,
                          university=university.content_text if university else None)


@app.route('/features')
def features():
    """Features page (Dynamic)"""
    hardware = SiteContent.query.filter_by(page_section='tech_specs_hardware').first()
    brain = SiteContent.query.filter_by(page_section='tech_specs_brain').first()
    return render_template('features.html', 
                          hardware=hardware.content_text if hardware else None,
                          brain=brain.content_text if brain else None)


@app.route('/team')
def team():
    """Team page (Dynamic)"""
    members = TeamMember.query.order_by(TeamMember.display_order).all()
    return render_template('team.html', members=members)

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html')

@app.route('/diagnostics')
@login_required
def diagnostics():
    return render_template('diagnostics.html')



@app.route('/video_feed')
def video_feed():
    """Video streaming route"""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/state')
def get_state():
    """Get current robot state"""
    return jsonify(robot_state)


@app.route('/api/motors', methods=['POST'])
def set_motor():
    """Set motor angle via REST API"""
    from flask import request
    data = request.json
    motor_id = data.get('motor_id')
    angle = data.get('angle')
    
    if motor_id is None or angle is None:
        return jsonify({'error': 'Missing motor_id or angle'}), 400
    
    success = send_motor_command(motor_id, angle)
    return jsonify({'success': success})


# ==================== SOCKET.IO EVENTS ====================

@socketio.on('connect')
def handle_connect():
    """Client connected"""
    print(">>> Client connected")
    emit('state_update', robot_state)
    emit('connection_status', {'connected': robot_state['connected']})


@socketio.on('disconnect')
def handle_disconnect():
    """Client disconnected"""
    print("<<< Client disconnected")


@socketio.on('motor_command')
def handle_motor_command(data):
    """Handle motor command from client"""
    if not current_user.is_authenticated:
        return
        
    motor_id = data.get('motor_id')
    angle = data.get('angle')
    
    if motor_id is not None and angle is not None:
        success = send_motor_command(motor_id, angle)
        if success:
            log_mission('MOTOR_DIRECT', {'motor_id': motor_id, 'angle': angle})
            
        emit('command_response', {'success': success, 'motor_id': motor_id, 'angle': angle})
        socketio.emit('state_update', robot_state)


@socketio.on('batch_command')
def handle_batch_command(data):
    """Handle batch motor commands"""
    commands = data.get('commands', {})
    success = send_batch_commands(commands)
    emit('command_response', {'success': success, 'type': 'batch'})
    socketio.emit('state_update', robot_state)


@socketio.on('joystick_move')
def handle_joystick(data):
    """Handle virtual joystick input (velocity control)"""
    if not current_user.is_authenticated:
        return
        
    x = data.get('x', 0.0)  # -1.0 to 1.0
    y = data.get('y', 0.0)  # -1.0 to 1.0
    
    # Velocity control: Update position based on joystick
    speed_factor = 2.0  # Degrees per update
    
    moved = False
    # X-axis: Wrist Roll (ID 4)
    if abs(x) > 0.1:
        current_roll = robot_state['motors'][4]
        new_roll = current_roll + (x * speed_factor)
        new_roll = max(0, min(180, new_roll))
        send_motor_command(4, new_roll)
        moved = True
    
    # Y-axis: Main Pivot (ID 2) - Up/Down
    if abs(y) > 0.1:
        current_pivot = robot_state['motors'][2]
        new_pivot = current_pivot - (y * speed_factor)  # Negative because up = decrease angle
        new_pivot = max(0, min(180, new_pivot))
        send_motor_command(2, new_pivot)
        moved = True
    
    if moved:
        # Throttled logging might be better for joystick, but for now simple log
        pass 

    socketio.emit('state_update', robot_state)


@socketio.on('object_click')
def handle_object_click(data):
    """Handle click-to-pick: Calculate angle to point at object"""
    # Object position in frame (normalized 0-1)
    obj_x = data.get('x', 0.5)
    obj_y = data.get('y', 0.5)
    
    # Convert Y position to pivot angle
    # Top of frame (y=0) = 0, Bottom (y=1) = 180 (degrees)
    target_angle = obj_y * 180
    target_angle = max(0, min(180, target_angle))
    
    send_motor_command(2, target_angle)
    socketio.emit('state_update', robot_state)


@socketio.on('gesture_update')
def handle_gesture_update(data):
    """Handle hand gesture mimicry from MediaPipe"""
    # Map MediaPipe landmarks to motor angles
    gestures = data.get('gestures', {})
    
    # Example: Map finger fold to hand servos
    if 'fingers' in gestures:
        fingers = gestures['fingers']
        for i, fold_ratio in enumerate(fingers[:5]):  # 5 fingers
            motor_id = 5 + i  # IDs 5-9
            # Convert fold ratio (0-1) to angle (0-180)
            angle = int(fold_ratio * 180)
            send_motor_command(motor_id, angle)
    
    socketio.emit('state_update', robot_state)


@socketio.on('voice_command')
def handle_voice_command(data):
    """Handle processed voice command by setting targets"""
    command_data = data.get('command')
    if isinstance(command_data, dict) and 'motor_values' in command_data:
        targets = command_data['motor_values']
        for motor_id, angle in targets.items():
            if 2 <= int(motor_id) <= 9:
                robot_state['target_motors'][int(motor_id)] = angle
        logger.info(f"[VOICE] Voice Targets: {targets}")
    
    socketio.emit('state_update', robot_state)


@socketio.on('emergency_stop')
def handle_emergency_stop():
    """Handle emergency stop request"""
    emergency_stop()


@socketio.on('home_position')
def handle_home():
    """Move to home position"""
    home_position()


@socketio.on('toggle_voice')
def handle_toggle_voice(data):
    """Toggle voice listening on/off"""
    enable = data.get('enable', False)
    
    if voice_processor:
        if enable:
            voice_processor.start_listening()
            socketio.emit('voice_status', {'listening': True, 'status': 'Listening...'})
        else:
            voice_processor.stop_listening()
            socketio.emit('voice_status', {'listening': False, 'status': 'Stopped'})
    else:
        socketio.emit('voice_status', {'listening': False, 'status': 'Not available'})


# Global control flags for command execution loop
track_mode_enabled = False
mimic_mode_enabled = False


@socketio.on('toggle_track_mode')
def handle_toggle_track_mode(data):
    """Toggle object tracking mode"""
    global track_mode_enabled
    track_mode_enabled = data.get('enable', False)
    socketio.emit('track_mode_status', {'enabled': track_mode_enabled})
    logger.info(f"[TRACK] Track mode: {'ON' if track_mode_enabled else 'OFF'}")


@socketio.on('toggle_mimic_mode')
def handle_toggle_mimic_mode(data):
    """Toggle hand mimicry mode"""
    global mimic_mode_enabled
    mimic_mode_enabled = data.get('enable', False)
    socketio.emit('mimic_mode_status', {'enabled': mimic_mode_enabled})
    logger.info(f"[MIMIC] Mimic mode: {'ON' if mimic_mode_enabled else 'OFF'}")


@socketio.on('gamepad_data')
def handle_gamepad_data(data):
    """
    Handle gamepad input from frontend (Anti-Gravity Velocity Control)
    Moves motors smoothly by adding/subtracting from current position based on stick pressure.
    """
    
    if robot_state['emergency_stop']:
        return
    
    # Extract gamepad values
    left_stick_y = data.get('left_stick_y', 0.0)  # -1.0 to 1.0
    right_stick_y = data.get('right_stick_y', 0.0)
    right_stick_x = data.get('right_stick_x', 0.0)
    left_trigger = data.get('left_trigger', 0.0)  # 0.0 to 1.0
    right_trigger = data.get('right_trigger', 0.0)
    
    # Velocity Control Parameters from Config
    SPEED = config.JOYSTICK_SPEED_FACTOR
    
    deadzone = config.JOYSTICK_DEADZONE
    
    # --- Velocity Control Logic ---
    
    # 1. Main Pivot (Elbow) - ID 2
    # Left Stick Y: Up (negative) -> Decrease Angle (Raise Arm)
    if abs(left_stick_y) > deadzone:
        current = robot_state['motors'][2]
        # Calculate velocity: Stick Value * Speed
        # Invert stick because Up is usually negative on gamepads
        velocity = -left_stick_y * SPEED 
        new_pos = current + velocity
        
        # Clamp strictly 0-180
        new_pos = max(0, min(180, new_pos))
        
        # Only send if changed
        if int(new_pos) != int(current):
            send_motor_command(2, new_pos)
            
    # 2. Wrist Pitch - ID 3
    # Right Stick Y: Up (negative) -> Decrease Angle (Tilt Up)
    if abs(right_stick_y) > deadzone:
        current = robot_state['motors'][3]
        velocity = -right_stick_y * SPEED
        new_pos = current + velocity
        new_pos = max(0, min(180, new_pos))
        if int(new_pos) != int(current):
            send_motor_command(3, new_pos)

    # 3. Wrist Roll - ID 4
    # Right Stick X: Left/Right -> Roll
    if abs(right_stick_x) > deadzone:
        current = robot_state['motors'][4]
        velocity = right_stick_x * SPEED
        new_pos = current + velocity
        new_pos = max(0, min(180, new_pos))
        if int(new_pos) != int(current):
            send_motor_command(4, new_pos)
            
    # 4. Hand Control (Triggers)
    # Analog Control involved? For now, digital threshold is safer for claws
    if left_trigger > 0.5:
        # Open Hand
        batch = {i: 0 for i in range(5, 10)}
        send_batch_commands(batch)
        
    if right_trigger > 0.5:
        # Close Hand
        batch = {i: 180 for i in range(5, 10)}
        send_batch_commands(batch)
        
    socketio.emit('state_update', robot_state)


def command_execution_loop():
    """
    Main command execution loop - processes AI-generated commands (Gemini + others)
    """
    
    
    while True:
        try:
            # 1. Smoothly follow target_motors -- batch all changes per iteration
            batch_moves = {}
            for motor_id, target in robot_state['target_motors'].items():
                current = robot_state['motors'][motor_id]
                if abs(current - target) > 0.5:
                    step = 2.0  # Max degrees per loop
                    new_pos = min(target, current + step) if target > current else max(target, current - step)
                    batch_moves[motor_id] = new_pos
            if batch_moves:
                send_batch_commands(batch_moves)
            
            # ========== VOICE/AI COMMAND HANDLING ==========
            # Use get() with a short timeout directly -- avoids TOCTOU race
            # on command_queue.empty() check.
            if voice_processor:
                command = voice_processor.get_command(timeout=0.05)
                if command:
                    cmd_type = command.get('type')
                    print(f"[BRAIN] Processing Command: {cmd_type}")

                    # --- GEMINI INTELLIGENT COMMANDS ---
                    if cmd_type == 'gemini_command':
                        # 1. Speak the AI response first
                        response_text = command.get('response_text')
                        if response_text and voice_processor:
                             voice_processor.speak(response_text, 
                                                lambda text: socketio.emit('robot_speech', {'text': text}))
                        
                        # 2. Execute Motor Movements
                        motor_values = command.get('motor_values', {})
                        if motor_values:
                            # Filter safe IDs
                            safe_moves = {int(k): v for k, v in motor_values.items() if int(k) >= 2}
                            if safe_moves:
                                send_batch_commands(safe_moves)
                    
                    # --- LEGACY/FALLBACK COMMANDS ---
                    elif cmd_type == 'motor':
                        motor_id = command.get('motor_id')
                        val = command.get('value')
                        if val == 'relative':
                            curr = robot_state['motors'].get(motor_id, 90)
                            send_motor_command(motor_id, curr + command.get('delta', 0))
                        else:
                            send_motor_command(motor_id, val)
                            
                    elif cmd_type == 'hand':
                        val = command.get('value', 0)
                        batch = {i: val for i in command.get('fingers', [])}
                        send_batch_commands(batch)
                        
                    elif cmd_type == 'system':
                        action = command.get('action')
                        if action == 'emergency_stop': emergency_stop()
                        elif action == 'home_position': home_position()
                    
                    socketio.emit('state_update', robot_state)

            
            # ========== VISION HANDLING - TRACK MODE ==========
            if track_mode_enabled and object_detector:
                detections = object_detector.get_detections()
                
                # Find target objects (cup, bottle, etc.)
                target_classes = ['cup', 'bottle', 'bowl', 'book', 'cell phone']
                target_detection = None
                
                for detection in detections:
                    if detection['class_name'].lower() in target_classes:
                        target_detection = detection
                        break
                
                if target_detection:
                    # Get normalized Y position (0-1)
                    # Assuming frame is 640x480
                    center_y = target_detection['center'][1]
                    y_normalized = center_y / 480.0  # Normalize to 0-1
                    
                    # Calculate angle using kinematics
                    target_angle = kinematics.image_y_to_angle(y_normalized)
                    
                    # Move main pivot to track object
                    current_angle = robot_state['motors'][2]
                    if abs(current_angle - target_angle) > 2:  # Deadband
                        send_motor_command(2, target_angle)
                        print(f"[TRACK] Tracking: Moving pivot to {target_angle} deg")
                        
                        # TTS feedback (throttled to avoid spam)
                        if not hasattr(command_execution_loop, 'last_track_speech') or \
                           time.time() - command_execution_loop.last_track_speech > 3:
                            if voice_processor:
                                voice_processor.speak("Target acquired", 
                                                    lambda text: socketio.emit('robot_speech', {'text': text}))
                            command_execution_loop.last_track_speech = time.time()
            
            # ========== VISION HANDLING - MIMIC MODE ==========
            if mimic_mode_enabled and hand_tracker:
                gestures = hand_tracker.get_gestures()
                
                if 'fingers' in gestures:
                    fingers = gestures['fingers']
                    
                    # Map finger fold ratios (0-1) to servo angles (0-180)
                    finger_commands = {}
                    for i, fold_ratio in enumerate(fingers[:5]):  # 5 fingers
                        motor_id = 5 + i  # IDs 5-9
                        angle = int(fold_ratio * 180)
                        finger_commands[motor_id] = angle
                    
                    # Send batch command for all fingers
                    if finger_commands:
                        send_batch_commands(finger_commands)
                        # Throttle updates to avoid spam
                        time.sleep(0.1)
            
            # Small delay to prevent CPU spinning
            time.sleep(0.05)
            
        except Exception as e:
            print(f"[ERROR] Command execution error: {e}")
            time.sleep(0.1)


def home_position():
    """Move all motors to safe home position"""
    home_commands = {
        2: 90,   # Main Pivot: Center
        3: 90,   # Wrist Pitch: Center
        4: 90,   # Wrist Roll: Center
        5: 0,    # Fingers: Open
        6: 0,
        7: 0,
        8: 0,
        9: 0,
    }
    send_batch_commands(home_commands)


# ==================== INITIALIZATION ====================

# ==================== ADMIN & OPERATOR ROUTES ====================

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    user_count = User.query.count()
    team_count = TeamMember.query.count()
    log_count = MissionLog.query.count()
    return render_template('admin/dashboard.html',
                           user_count=user_count,
                           team_count=team_count,
                           log_count=log_count)

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/users/add', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_user_add():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return redirect(url_for('admin_user_add'))
        user = User(username=username, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('User created.', 'success')
        return redirect(url_for('admin_users'))
    return render_template('admin/user_form.html', user=None)

@app.route('/admin/users/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_user_edit(id):
    user = User.query.get_or_404(id)
    if request.method == 'POST':
        user.username = request.form['username']
        user.role = request.form['role']
        if request.form['password']:
            user.set_password(request.form['password'])
        db.session.commit()
        flash('User updated.', 'success')
        return redirect(url_for('admin_users'))
    return render_template('admin/user_form.html', user=user)

@app.route('/admin/users/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def admin_user_delete(id):
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash('You cannot delete yourself.', 'danger')
        return redirect(url_for('admin_users'))
    
    # Explicitly iterate and delete all mission logs for this user to avoid SQLite/PgBouncer FK errors
    try:
        logs = MissionLog.query.filter_by(user_id=user.id).all()
        for log in logs:
            db.session.delete(log)
        db.session.commit()
        db.session.delete(user)
        db.session.commit()
        flash('User deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] User deletion failed: {e}")
        flash(f'Database error during deletion.', 'danger')

    return redirect(url_for('admin_users'))

@app.route('/admin/team')
@login_required
@admin_required
def admin_team():
    members = TeamMember.query.order_by(TeamMember.display_order).all()
    return render_template('admin/team_list.html', members=members)

@app.route('/admin/team/add', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_team_add():
    if request.method == 'POST':
        name = request.form['name']
        role = request.form['role']
        bio = request.form['bio']
        linkedin = request.form.get('linkedin_url', '')
        github = request.form.get('github_url', '')
        display_order = int(request.form.get('display_order', 0))
        
        photo_url = ''
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filename = f"{int(time.time())}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                photo_url = f'/static/uploads/{filename}'
        
        member = TeamMember(
            name=name,
            role=role,
            bio=bio,
            photo_url=photo_url,
            linkedin_url=linkedin,
            github_url=github,
            display_order=display_order
        )
        db.session.add(member)
        db.session.commit()
        flash('Team member added.', 'success')
        return redirect(url_for('admin_team'))
    return render_template('admin/team_form.html', member=None)

@app.route('/admin/team/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_team_edit(id):
    member = TeamMember.query.get_or_404(id)
    if request.method == 'POST':
        member.name = request.form['name']
        member.role = request.form['role']
        member.bio = request.form['bio']
        member.linkedin_url = request.form.get('linkedin_url', '')
        member.github_url = request.form.get('github_url', '')
        member.display_order = int(request.form.get('display_order', 0))
        
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '' and allowed_file(file.filename):
                if member.photo_url and member.photo_url.startswith('/static/uploads/'):
                    old_path = os.path.join(app.root_path, 'web_interface', member.photo_url.lstrip('/'))
                    if os.path.exists(old_path):
                        os.remove(old_path)
                filename = secure_filename(file.filename)
                filename = f"{int(time.time())}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                member.photo_url = f'/static/uploads/{filename}'
        
        db.session.commit()
        flash('Team member updated.', 'success')
        return redirect(url_for('admin_team'))
    return render_template('admin/team_form.html', member=member)

@app.route('/admin/team/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def admin_team_delete(id):
    member = TeamMember.query.get_or_404(id)
    if member.photo_url and member.photo_url.startswith('/static/uploads/'):
        path = os.path.join(app.root_path, 'web_interface', member.photo_url.lstrip('/'))
        if os.path.exists(path):
            os.remove(path)
    db.session.delete(member)
    db.session.commit()
    flash('Team member deleted.', 'success')
    return redirect(url_for('admin_team'))

@app.route('/admin/content')
@login_required
@admin_required
def admin_content():
    contents = SiteContent.query.order_by(SiteContent.page_section).all()
    return render_template('admin/content_list.html', contents=contents)

@app.route('/admin/content/edit/<string:section>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_content_edit(section):
    content = SiteContent.query.filter_by(page_section=section).first()
    if not content:
        content = SiteContent(page_section=section, content_text='')
    if request.method == 'POST':
        content.content_text = request.form['content_text']
        db.session.add(content)
        db.session.commit()
        flash('Content updated.', 'success')
        return redirect(url_for('admin_content'))
    return render_template('admin/content_form.html', section=section, content=content)

@app.route('/admin/logs')
@login_required
@admin_required
def admin_logs():
    page = request.args.get('page', 1, type=int)
    logs = MissionLog.query.order_by(MissionLog.timestamp.desc()).paginate(page=page, per_page=50, error_out=False)
    return render_template('admin/logs.html', logs=logs)

@app.route('/logs')
@login_required
def mission_logs():
    page = request.args.get('page', 1, type=int)
    if current_user.role == 'admin':
        logs = MissionLog.query.order_by(MissionLog.timestamp.desc()).paginate(page=page, per_page=50, error_out=False)
    else:
        logs = MissionLog.query.filter_by(user_id=current_user.id).order_by(MissionLog.timestamp.desc()).paginate(page=page, per_page=50, error_out=False)
    return render_template('logs.html', logs=logs)

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

@app.route('/profile/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm = request.form['confirm_password']
        
        if not current_user.check_password(current_password):
            flash('Current encryption key is incorrect.', 'danger')
        elif new_password != confirm:
            flash('New encryption keys do not match.', 'danger')
        else:
            current_user.set_password(new_password)
            db.session.commit()
            flash('Encryption key updated successfully.', 'success')
            return redirect(url_for('profile'))
    return render_template('change_password.html')

def init_ai_modules():
    """Initialize AI modules in background"""
    global object_detector, hand_tracker, voice_processor
    
    logger.info("[AI] Initializing AI modules...")
    
    try:
        object_detector = ObjectDetector()
        logger.info("[OK] Object Detector ready")
    except Exception as e:
        logger.error(f"[WARN] Object Detector error: {e}")
    
    try:
        hand_tracker = HandTracker()
        logger.info("[OK] Hand Tracker ready")
    except Exception as e:
        logger.error(f"[WARN] Hand Tracker error: {e}")
    
    try:
        voice_processor = VoiceCommandProcessor()
        logger.info("[OK] Voice Processor ready")
    except Exception as e:
        logger.error(f"[WARN] Voice Processor error: {e}")


if __name__ == '__main__':
    print("=" * 50)
    print("[START] LUNA Robotic Arm - Starting System")
    # Initialize Database
    with app.app_context():
        try:
            db.create_all()
            logger.info("[DB] Database tables verified/created")
        except Exception as e:
            logger.error(f"[ERROR] Database initialization failed: {e}")

    # Initialize serial connection
    init_serial_connection()
    
    # Start serial writer thread
    writer_thread = threading.Thread(target=serial_writer_thread, daemon=True)
    writer_thread.start()
    logger.info("[OK] Serial writer thread started")
    
    # Start serial reader thread
    if robot_state['connected']:
        serial_thread = threading.Thread(target=serial_reader_thread, daemon=True)
        serial_thread.start()
        logger.info("[OK] Serial reader thread started")
    
    # Initialize AI modules (non-blocking)
    ai_thread = threading.Thread(target=init_ai_modules, daemon=True)
    ai_thread.start()
    
    # Wait for AI modules to initialize
    time.sleep(3)
    
    # Start command execution loop (the "brain")
    command_thread = threading.Thread(target=command_execution_loop, daemon=True)
    command_thread.start()
    logger.info("[OK] Command execution loop started")
    
    # Move to home position
    time.sleep(1)
    home_position()
    
    print("\n[WEB] Starting Flask server on http://localhost:5000")
    print("[VIDEO] Video feed: http://localhost:5000/video_feed")
    print("\n[INFO] Press Ctrl+C to stop\n")
    
    # Run Flask app
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=True, allow_unsafe_werkzeug=True)


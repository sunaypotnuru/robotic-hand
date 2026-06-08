from typing import Dict, Optional, List, Tuple, Union, Any
import os
import sys
import threading
import time
import json
import queue
import logging
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, Response, jsonify, request, redirect, url_for, flash, send_from_directory
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
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

from web_interface.ai_modules.object_detect import ObjectDetector
from web_interface.ai_modules.hand_tracking import HandTracker
from web_interface.ai_modules.voice_cmd import VoiceCommandProcessor
from web_interface.ai_modules.kinematics import SimpleKinematics
from web_interface.ai_modules.motion_recorder import MotionRecorder
from web_interface.ai_modules.vision_processor import VisionProcessor
from web_interface.ai_modules.webrtc_signaling import WebRTCSignalingNamespace

try:
    from web_interface.ai_modules.path_planner import PathPlanner
except Exception as e:
    logger.error(f"[IMPORT] Failed to import PathPlanner: {e}")
    PathPlanner = None

try:
    from web_interface.ai_modules.macro_executor import MacroExecutor
except Exception as e:
    logger.error(f"[IMPORT] Failed to import MacroExecutor: {e}")
    MacroExecutor = None

from utils.validators import InputValidator

# Global control flags for command execution loop
track_mode_enabled = False
mimic_mode_enabled = False
teach_mode_enabled = False

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
    'connect_args': {'connect_timeout': 5} if 'postgresql' in (db_url or '') else {},
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

# Initialize Rate Limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Initialize Security Headers (Talisman)
csp = {
    'default-src': "'self'",
    'script-src': [
        "'self'",
        "'unsafe-inline'",  # Required for inline scripts
        'cdn.socket.io',
        'cdn.jsdelivr.net',
        'cdnjs.cloudflare.com',
        'unpkg.com'
    ],
    'style-src': [
        "'self'",
        "'unsafe-inline'",
        'fonts.googleapis.com'
    ],
    'font-src': [
        "'self'",
        'fonts.gstatic.com'
    ],
    'img-src': "'self' data: blob:",
    'connect-src': "'self' ws: wss: https://assets2.lottiefiles.com https://assets3.lottiefiles.com https://lottie.host"
}

Talisman(app,
    content_security_policy=csp,
    force_https=False,  # Set True in production
    strict_transport_security=True,
    session_cookie_secure=False,  # Set True in production with HTTPS
    session_cookie_samesite='Lax'
)

# ==================== DATABASE MODELS ====================

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='operator')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Profile Info
    full_name = db.Column(db.String(100))
    bio = db.Column(db.Text)
    photo_url = db.Column(db.String(200))
    linkedin_url = db.Column(db.String(200))
    github_url = db.Column(db.String(200))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

class SiteContent(db.Model):
    __tablename__ = 'site_content'
    id = db.Column(db.Integer, primary_key=True)
    page_section = db.Column(db.String(100), unique=True, nullable=False)
    content_text = db.Column(db.Text, nullable=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

class MissionLog(db.Model):
    __tablename__ = 'mission_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    command = db.Column(db.String(50), nullable=False)
    robot_state = db.Column(db.JSON, nullable=False)

    user = db.relationship('User', backref=db.backref('logs', cascade='all, delete-orphan'))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

class LoginHistory(db.Model):
    __tablename__ = 'login_history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    ip_address = db.Column(db.String(45), nullable=False)
    user_agent = db.Column(db.String(255), nullable=False)
    login_time = db.Column(db.DateTime, default=datetime.utcnow)
    success = db.Column(db.Boolean, default=True)
    
    user = db.relationship('User', backref=db.backref('login_history', lazy='dynamic', cascade='all, delete'))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==================== HELPERS ====================

log_queue = queue.Queue()

def log_mission(command_type: str, details: Dict[str, Any], user_id: Optional[int] = None) -> None:
    """
    Log robotic actions to the database using an asynchronous thread-safe batch queue (B5)
    """
    resolved_id = user_id
    if resolved_id is None:
        try:
            from flask import has_request_context
            if has_request_context() and current_user.is_authenticated:
                resolved_id = current_user.id
        except Exception:
            pass
            
    log_queue.put({
        'user_id': resolved_id,
        'command': command_type,
        'robot_state': details,
        'timestamp': datetime.utcnow()
    })

def async_batch_logger_thread():
    """
    Background worker periodically flushing queued mission logs to the database every 5 seconds (B5)
    """
    logger.info("[THREAD] Async batch DB logger thread initialized")
    while True:
        time.sleep(5)
        logs_to_write = []
        while not log_queue.empty():
            try:
                logs_to_write.append(log_queue.get_nowait())
            except queue.Empty:
                break
        
        if logs_to_write:
            with app.app_context():
                try:
                    system_user = User.query.filter_by(role='admin').first()
                    system_id = system_user.id if system_user else None
                    
                    for log_data in logs_to_write:
                        uid = log_data['user_id'] or system_id
                        if uid:
                            log_entry = MissionLog(
                                user_id=uid,
                                command=log_data['command'],
                                robot_state=log_data['robot_state'],
                                timestamp=log_data['timestamp']
                            )
                            db.session.add(log_entry)
                    db.session.commit()
                    logger.debug(f"[DB] Successfully batch-committed {len(logs_to_write)} mission logs.")
                except Exception as e:
                    db.session.rollback()
                    logger.error(f"[ERROR] Asynchronous batch logging failed: {e}")

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

# Serial Communication & Bimanual Arm Support (Resolved Feature 4)
arduino_serial = None
serial_thread = None
serial_lock = threading.Lock()
serial_queue = queue.Queue()

# Dual-Arm Bimanual Queues and Connection Holders
arduino_left = None
arduino_right = None
left_serial_queue = queue.Queue()
right_serial_queue = queue.Queue()
left_serial_lock = threading.Lock()
right_serial_lock = threading.Lock()

ping_failures = 0
last_pong_time = time.time()  # Track last watchdog response (Fix Bug 1)

def serial_heartbeat_thread():
    """
    Watchdog thread verifying serial connection and executing recovery if 3 consecutive failures occur (B1/A1 Upgrade - Fix Bug 1)
    """
    global arduino_serial, ping_failures, last_pong_time
    logger.info("[THREAD] Serial heartbeat watchdog active using PING/PONG protocol")
    last_pong_time = time.time()
    while True:
        time.sleep(5)
        if not robot_state['connected']:
            continue
        try:
            with serial_lock:
                if arduino_serial and arduino_serial.is_open:
                    # Write ping command
                    arduino_serial.write(b"PING\n")
                    logger.debug("[WATCHDOG] Sent PING to main serial port")
            
            # Wait 1.5 seconds for reader thread to process response
            time.sleep(1.5)
            
            # Watchdog timeout check (allow 7.5 seconds of silence)
            if time.time() - last_pong_time > 7.5:
                logger.warning(f"[WATCHDOG] Watchdog detected heartbeat timeout. Last pong was {time.time() - last_pong_time:.1f}s ago")
                ping_failures += 1
            else:
                ping_failures = 0
            
            if ping_failures >= 3:
                logger.warning("⚠️ Serial watchdog detected 3 failed heartbeats. Re-initializing connection...")
                ping_failures = 0
                with serial_lock:
                    if arduino_serial:
                        try:
                            arduino_serial.close()
                        except Exception:
                            pass
                    init_serial_connection()
        except Exception as e:
            logger.error(f"[WATCHDOG] Watchdog exception: {e}")
            ping_failures += 1


# AI Modules
object_detector = None
hand_tracker = None
voice_processor = None
vision_processor = VisionProcessor()
kinematics = SimpleKinematics(link_length=28.0)  # 28cm forearm
motion_recorder = MotionRecorder()  # Motion recording system

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
    """Initialize serial connections to one or two Arduinos (Bimanual support - COM3, COM4) (Feature 3.4)"""
    global arduino_serial, arduino_left, arduino_right, SERIAL_PORT
    global right_serial_lock, left_serial_lock, serial_lock
    
    # Initialize bimanual left arm (COM3)
    try:
        arduino_left = serial.Serial('COM3', BAUD_RATE, timeout=SERIAL_TIMEOUT, write_timeout=1.0)
        time.sleep(1)
        logger.info("[OK] Connected to Left Arm on COM3")
    except Exception as e:
        logger.info("[SIM] Left arm COM3 not connected. Single or simulation mode.")
        arduino_left = None

    # Initialize bimanual right arm (COM4)
    try:
        arduino_right = serial.Serial('COM4', BAUD_RATE, timeout=SERIAL_TIMEOUT, write_timeout=1.0)
        time.sleep(1)
        logger.info("[OK] Connected to Right Arm on COM4")
    except Exception as e:
        logger.info("[SIM] Right arm COM4 not connected.")
        arduino_right = None

    # Standard Fallback single arm setup
    if arduino_right is None:
        if SERIAL_PORT is None:
            SERIAL_PORT = find_arduino_port()
        
        if SERIAL_PORT is not None:
            try:
                arduino_serial = serial.Serial(
                    SERIAL_PORT, 
                    BAUD_RATE, 
                    timeout=SERIAL_TIMEOUT,
                    write_timeout=1.0
                )
                time.sleep(2)  # Wait for Arduino to initialize
                arduino_right = arduino_serial
                # Unify write locks if standard port is shared by right arm (Fix Bug 1)
                right_serial_lock = serial_lock
                robot_state['connected'] = True
                logger.info(f"[OK] Connected to Standard Arm on {SERIAL_PORT}")
                return True
            except Exception as e:
                logger.error(f"[ERROR] Serial connection error: {e}")
                robot_state['connected'] = False
                return False
        else:
            logger.warning("[WARN] No Arduino port detected. Running in simulation mode.")
            robot_state['connected'] = False
            return False
    else:
        arduino_serial = arduino_right
        # Unify write locks (Fix Bug 1)
        right_serial_lock = serial_lock
        robot_state['connected'] = True
        return True
def send_motor_command_arm(arm_id: str, motor_id: int, angle: int, force: bool = False) -> bool:
    """
    Send motor command to a specific arm (left or right) (Feature 3.4)
    """
    # Safety checks
    if motor_id in [0, 1]:
        logger.warning(f"[WARN] BLOCKED: Attempted to control removed motor ID {motor_id}")
        return False
    if motor_id < 2 or motor_id > 9:
        logger.warning(f"[WARN] INVALID: Motor ID {motor_id} out of range (2-9)")
        return False
    angle = max(0, min(180, int(angle)))
    
    if robot_state['emergency_stop'] and not force:
        logger.warning("[STOP] EMERGENCY STOP ACTIVE - Command blocked")
        return False

    command = f"M:{motor_id}:{angle}\n"
    
    if arm_id.lower() == 'left':
        if arduino_left:
            left_serial_queue.put(command)
            logger.debug(f"[OUT-L] Queued command: {command.strip()}")
            return True
        else:
            # Fallback to simulation
            logger.debug(f"[SIM-L] Simulated Left: {command.strip()}")
            return True
    else:
        if arduino_right:
            right_serial_queue.put(command)
            logger.debug(f"[OUT-R] Queued command: {command.strip()}")
            return True
        else:
            logger.debug(f"[SIM-R] Simulated Right: {command.strip()}")
            return True

def wait_for_arm(arm_id: str, timeout: float = 2.0) -> bool:
    """
    Bimanual sync primitive: Blocks execution until all pending commands in arm_id queue are sent (Feature 3.4)
    """
    start_time = time.time()
    q = left_serial_queue if arm_id.lower() == 'left' else right_serial_queue
    while not q.empty():
        if time.time() - start_time > timeout:
            logger.warning(f"[SYNC] Timeout waiting for arm {arm_id} to complete movements.")
            return False
        time.sleep(0.01)
    return True

def send_motor_command(motor_id: int, angle: int, force: bool = False) -> bool:
    """Send standard motor command to the default right arm"""
    # Boundary checks before modifying state (Fix Bug 9)
    if motor_id < 2 or motor_id > 9:
        logger.warning(f"[WARN] INVALID: Motor ID {motor_id} out of range (2-9)")
        return False
    # Clamp angle first to prevent out-of-bounds state pollution
    angle = max(0, min(180, int(angle)))
    # Update default state
    robot_state['motors'][motor_id] = angle
    # Record frame if recording
    motion_recorder.record_frame(robot_state['motors'])
    # Log direct mission
    log_mission('motor', {'motor_id': motor_id, 'angle': angle, 'timestamp': time.time()})
    return send_motor_command_arm('right', motor_id, angle, force)

def send_batch_commands(commands_dict: Dict[int, int]) -> bool:
    """
    Send multiple motor commands in batch format to the default right arm
    """
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
    
    if arduino_right:
        right_serial_queue.put(command)
    else:
        serial_queue.put(command)
    
    # Log the mission
    log_mission('batch', {'commands': valid_commands, 'timestamp': time.time()})
    return True

def serial_writer_thread():
    """Background thread to process legacy/standard serial command queue"""
    logger.info("[THREAD] Legacy Serial writer thread started")
    while True:
        try:
            command = serial_queue.get(timeout=1.0)
            if arduino_serial and arduino_serial.is_open:
                with serial_lock:
                    arduino_serial.write(command.encode('utf-8'))
                logger.debug(f"[OUT] Sent standard: {command.strip()}")
            serial_queue.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            logger.error(f"[ERROR] Standard serial write error: {e}")

def left_serial_writer_thread():
    """Background thread to process left arm serial queue"""
    logger.info("[THREAD] Left Arm serial writer started")
    while True:
        try:
            command = left_serial_queue.get(timeout=1.0)
            if arduino_left and arduino_left.is_open:
                with left_serial_lock:
                    arduino_left.write(command.encode('utf-8'))
                logger.debug(f"[OUT-L] Sent Left: {command.strip()}")
            left_serial_queue.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            logger.error(f"[ERROR] Left serial write failed: {e}")

def right_serial_writer_thread():
    """Background thread to process right arm serial queue"""
    logger.info("[THREAD] Right Arm serial writer started")
    while True:
        try:
            command = right_serial_queue.get(timeout=1.0)
            if arduino_right and arduino_right.is_open:
                with right_serial_lock:
                    arduino_right.write(command.encode('utf-8'))
                logger.debug(f"[OUT-R] Sent Right: {command.strip()}")
            right_serial_queue.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            logger.error(f"[ERROR] Right serial write failed: {e}")


def emergency_stop() -> None:
    """
    Trigger emergency stop - move ALL motors to safe position.
    
    Sets emergency_stop flag and moves:
    - Motors 2-4 to center position (90°)
    - Motors 5-9 to open position (0°)
    
    Emits 'emergency_stop' event to all connected clients.
    """
    robot_state['emergency_stop'] = True
    
    # Flush and empty all pending serial queues to prioritize safety frame (A4 Upgrade)
    for q in [serial_queue, left_serial_queue, right_serial_queue]:
        while not q.empty():
            try:
                q.get_nowait()
            except Exception:
                break
                
    # Send emergency stop to all motors (set to safe position)
    safe_commands = {
        2: 90,   # Main Pivot: Center
        3: 90,   # Wrist Pitch: Center
        4: 90,   # Wrist Roll: Center
        5: 0,    # Fingers: Open (safe position)
        6: 0,
        7: 0,
        8: 0,
        9: 0,
    }
    send_batch_commands(safe_commands)
    if 'macro_executor' in globals() and macro_executor:
        macro_executor.cancel_macro()
    socketio.emit('emergency_stop', {'active': True})
    logger.critical("[STOP] EMERGENCY STOP ACTIVATED - All motors to safe position")


def serial_reader_thread():
    """Background thread to read telemetry from Arduino (Fix Bug 1)"""
    global last_pong_time
    while True:
        if arduino_serial and arduino_serial.is_open:
            try:
                if arduino_serial.in_waiting:
                    line = arduino_serial.readline().decode('utf-8', errors='ignore').strip()
                    
                    # Intercept PONG watchdog response (Fix Bug 1)
                    if "PONG" in line or "STATUS" in line or "OK" in line or "SYSTEM" in line:
                        last_pong_time = time.time()
                        logger.debug(f"[WATCHDOG] Received heartbeat pong: '{line}'")
                        continue
                    
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
    """Video streaming generator with AI processing (B2 thread safe)"""
    global camera, vision_processor
    
    if not CV2_AVAILABLE:
        return
    
    # Initialize camera with thread safety (double-check locking pattern)
    if camera is None:
        with camera_lock:
            if camera is None:  # Double-check inside lock
                try:
                    camera = cv2.VideoCapture(0)
                    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    robot_state['camera_active'] = True
                except Exception as e:
                    logger.error(f"[ERROR] Camera error: {e}")
                    return
    
    # Initialize VisionProcessor lazy style
    if vision_processor and not vision_processor.initialized:
        vision_processor.initialize()
    
    while True:
        frame = None
        # Read the frame inside lock and release immediately (B2)
        with camera_lock:
            if camera is not None and camera.isOpened():
                success, frame = camera.read()
                if not success:
                    frame = None
            else:
                frame = None
        
        if frame is None:
            time.sleep(0.03)  # Small delay if frame is not ready
            continue
        
        # Process frame sequentially inside unified processor outside lock
        if vision_processor:
            frame = vision_processor.process_frame(frame)
        
        # Encode frame outside lock
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
    try:
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
    except Exception as e:
        logger.warning(f"[AUTH] auth-status DB error (DB may be paused): {e}")
        return jsonify({'authenticated': False})

@app.route('/api/login', methods=['POST'])
@limiter.limit("5 per minute")  # Prevent brute force attacks
def api_login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            logger.info(f"[AUTH] Successful login: {username}")
            
            # Log Successful Login History
            try:
                history = LoginHistory(
                    user_id=user.id,
                    ip_address=request.remote_addr or '127.0.0.1',
                    user_agent=request.headers.get('User-Agent', 'Unknown')[:255],
                    success=True
                )
                db.session.add(history)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error(f"[AUTH] Error logging success history: {e}")
                
            return jsonify({
                'success': True,
                'user': {
                    'username': user.username,
                    'role': user.role,
                    'full_name': user.full_name
                }
            })
        else:
            logger.warning(f"[AUTH] Failed login attempt: {username}")
            
            # Log Failed Login History
            try:
                history = LoginHistory(
                    user_id=user.id if user else None,
                    ip_address=request.remote_addr or '127.0.0.1',
                    user_agent=request.headers.get('User-Agent', 'Unknown')[:255],
                    success=False
                )
                db.session.add(history)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error(f"[AUTH] Error logging failure history: {e}")
                
            return jsonify({'success': False, 'message': 'Invalid Operator ID or Encryption Key'}), 401
    except Exception as e:
        logger.error(f"[AUTH] Login DB error (DB may be paused): {e}")
        return jsonify({'success': False, 'message': 'Database unavailable. Please try again later.'}), 503

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
    """About page (DB-resilient)"""
    try:
        desc = SiteContent.query.filter_by(page_section='about_description').first()
        description = desc.content_text if desc else None
    except Exception:
        description = None
    return render_template('about.html', description=description)


@app.route('/contact')
def contact():
    """Contact page (DB-resilient)"""
    def safe_get(section):
        try:
            item = SiteContent.query.filter_by(page_section=section).first()
            return item.content_text if item else None
        except Exception:
            return None
    return render_template('contact.html',
                          email=safe_get('contact_email'),
                          phone=safe_get('contact_phone'),
                          address=safe_get('contact_address'),
                          github=safe_get('contact_github'),
                          linkedin=safe_get('contact_linkedin'),
                          university=safe_get('institution_website'))


@app.route('/features')
def features():
    """Features page (DB-resilient)"""
    def safe_get(section):
        try:
            item = SiteContent.query.filter_by(page_section=section).first()
            return item.content_text if item else None
        except Exception:
            return None
    return render_template('features.html',
                          hardware=safe_get('tech_specs_hardware'),
                          brain=safe_get('tech_specs_brain'))


@app.route('/team')
def team():
    """Team page (DB-resilient)"""
    try:
        members = TeamMember.query.order_by(TeamMember.display_order).all()
    except Exception:
        members = []
    return render_template('team.html', members=members)

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html')

@app.route('/diagnostics')
@login_required
def diagnostics():
    """Render the interactive system diagnostics and telemetry dashboard"""
    report_path = 'docs/luna_diagnostic_report.json'
    if not os.path.exists(report_path):
        try:
            import subprocess
            subprocess.run(['python', 'utils/diagnose_system.py'], check=True)
        except Exception as e:
            logger.error(f"[DIAGNOSTICS] Failed to auto-generate report: {e}")
    
    report_data = {}
    if os.path.exists(report_path):
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                report_data = json.load(f)
        except Exception as e:
            logger.error(f"[DIAGNOSTICS] Error reading report: {e}")
            
    return render_template('diagnostics.html', report=report_data)



@app.route('/video_feed')
def video_feed():
    """Video streaming route"""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/api/state')
def get_state():
    """Get current robot state"""
    return jsonify(robot_state)


@app.route('/api/sensors')
def get_sensors():
    """Get current sensor readings"""
    return jsonify(robot_state['sensors'])


@app.route('/api/motors', methods=['POST'])
def set_motor():
    """Set motor angle via REST API"""
    data = request.json
    motor_id = data.get('motor_id')
    angle = data.get('angle')
    if motor_id is None or angle is None:
        return jsonify({'error': 'Missing motor_id or angle'}), 400
    success = send_motor_command(motor_id, angle)
    return jsonify({'success': success, 'motor_id': motor_id, 'angle': robot_state['motors'].get(motor_id)})


@app.route('/api/batch', methods=['POST'])
def api_batch():
    """Batch motor commands via REST API"""
    data = request.json
    commands = data.get('commands', {})
    if not commands:
        return jsonify({'error': 'Missing commands dict'}), 400
    success = send_batch_commands(commands)
    return jsonify({'success': success, 'motors': robot_state['motors']})


@app.route('/api/home', methods=['POST'])
def api_home():
    """Move to home position via REST API"""
    home_position()
    return jsonify({'success': True, 'message': 'Returning to home position', 'motors': robot_state['motors']})


@app.route('/api/emergency_stop', methods=['POST'])
def api_emergency_stop():
    """Trigger emergency stop via REST API"""
    emergency_stop()
    return jsonify({'success': True, 'message': 'Emergency stop activated', 'emergency_stop': True})


@app.route('/api/recordings')
@login_required
def api_recordings():
    """List all saved recordings via REST API"""
    recordings = motion_recorder.list_recordings()
    return jsonify({'recordings': recordings, 'count': len(recordings)})


@app.route('/api/profile')
@login_required
def api_profile():
    """Get current user profile data for SPA"""
    try:
        log_count = MissionLog.query.filter_by(user_id=current_user.id).count()
    except Exception:
        log_count = 0
    return jsonify({
        'username': current_user.username,
        'full_name': current_user.full_name,
        'role': current_user.role,
        'bio': current_user.bio,
        'photo_url': current_user.photo_url,
        'linkedin_url': current_user.linkedin_url,
        'github_url': current_user.github_url,
        'created_at': current_user.created_at.isoformat() if current_user.created_at else None,
        'log_count': log_count
    })


@app.route('/api/logs')
@login_required
def api_logs():
    """Get mission logs for SPA (paginated)"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        if current_user.role == 'admin':
            pagination = MissionLog.query.order_by(MissionLog.timestamp.desc()).paginate(
                page=page, per_page=per_page, error_out=False)
        else:
            pagination = MissionLog.query.filter_by(user_id=current_user.id).order_by(
                MissionLog.timestamp.desc()).paginate(page=page, per_page=per_page, error_out=False)
        logs = [{
            'id': log.id,
            'timestamp': log.timestamp.isoformat(),
            'command': log.command,
            'robot_state': log.robot_state
        } for log in pagination.items]
        return jsonify({
            'logs': logs,
            'page': page,
            'pages': pagination.pages,
            'total': pagination.total,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        })
    except Exception as e:
        logger.warning(f"[LOGS] DB error fetching logs: {e}")
        return jsonify({'logs': [], 'page': 1, 'pages': 0, 'total': 0, 'has_next': False, 'has_prev': False})


# ==================== SOCKET.IO EVENTS ====================

# Mount the WebRTC signaling namespace for remote controls (Feature 3.5)
socketio.on_namespace(WebRTCSignalingNamespace('/remote'))

# Global Path Planner Instance
path_planner = PathPlanner() if PathPlanner else None

def handle_macro_action(action, target, duration=0.0):
    """Callback to execute macro commands via physical serial outputs (A2 Upgrade)"""
    if action == "move" and target:
        if isinstance(target, dict):
            safe_moves = {int(k): v for k, v in target.items() if int(k) >= 2}
            send_batch_commands(safe_moves)
        elif isinstance(target, (list, tuple)) and len(target) == 3:
            # Convert 3D coordinates (x, y, z) to actual 4-DOF servo angles using kinematics limits (Feature 6.2)
            x, y, z = target
            pivot_angle = kinematics.position_to_angle(y)
            
            radius = kinematics.link_length
            pitch = int(max(0, min(180, (z + radius) / (2.0 * radius) * 180.0)))
            roll = int(max(0, min(180, (x + radius) / (2.0 * radius) * 180.0)))
            
            safe_moves = {2: int(pivot_angle), 3: pitch, 4: roll}
            send_batch_commands(safe_moves)
            logger.info(f"[MACRO IK] Mapped coordinates {target} -> Joint Angles: {safe_moves}")
    elif action == "grab":
        batch = {i: 180 for i in range(5, 10)}
        send_batch_commands(batch)
    elif action == "release":
        batch = {i: 0 for i in range(5, 10)}
        send_batch_commands(batch)
    elif action == "wait":
        # Let the macro executor thread manage the sleep with cancellation checks (Fix Bug 7)
        pass

# Global Macro Executor Instance (Feature 3)
macro_executor = MacroExecutor(socketio=socketio, command_sender=handle_macro_action) if MacroExecutor else None

@socketio.on('plan_path')
def handle_plan_path(data):
    """Handle custom 3D occupancy path planning A*/RRT request (Feature 3.1)"""
    if not path_planner:
        logger.warning("[PLANNER] Path planner not initialized.")
        emit('command_error', {'error': 'Path planner is not available.'})
        return
    start = data.get('start', (0.0, 0.0, 0.0))
    target = data.get('target', (10.0, 20.0, 0.0))
    obstacles = data.get('obstacles', [])
    
    # Re-initialize planner workspace and load current obstacles dynamically
    path_planner.set_workspace()
    for obs in obstacles:
        pos = obs.get('pos', (0.0, 0.0, 0.0))
        size = obs.get('size', (1.0, 1.0, 1.0))
        path_planner.add_obstacle(pos, size)
        
    path_points = path_planner.plan_path(start, target)
    emit('path_points', {'points': path_points})
    logger.info(f"[PLANNER] Dispatched {len(path_points)} path waypoints back to frontend.")

@socketio.on('execute_path')
def handle_execute_path(data):
    """Execute planned path waypoints as a macro sequence (Feature 1)"""
    if not path_planner or not macro_executor:
        logger.warning("[PLANNER] Path planner or Macro executor not initialized.")
        emit('command_error', {'error': 'Path planner or Macro executor is not available.'})
        return
    points = data.get('points', [])
    if not points:
        logger.warning("[PLANNER] Cannot execute empty path trajectory.")
        return
        
    logger.info(f"[PLANNER] Converting {len(points)} waypoints to joint trajectory...")
    trajectory = path_planner.get_joint_trajectory(points)
    
    # Map joint commands to macro action steps
    macro_steps = []
    for cmd in trajectory:
        macro_steps.append({
            "type": "move",
            "target": cmd,
            "duration": 0.5
        })
        
    logger.info(f"[PLANNER] Dispatched {len(macro_steps)} macro steps for path trajectory execution.")
    macro_executor.start_macro(macro_steps)

@socketio.on('run_macro')
def handle_run_macro(data):
    """Trigger a custom macro sequence (Feature 3)"""
    if not macro_executor:
        logger.warning("[MACRO] Macro executor not initialized.")
        emit('command_error', {'error': 'Macro executor is not available.'})
        return
    actions = data.get('actions', [])
    if actions:
        macro_executor.start_macro(actions)
        logger.info(f"[MACRO] Started custom macro with {len(actions)} steps.")

@socketio.on('cancel_macro')
def handle_cancel_macro():
    """Cancel any active running macro"""
    if macro_executor:
        macro_executor.cancel_macro()
        logger.info("[MACRO] Macro execution cancelled by operator command.")

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
@limiter.limit("100 per minute")  # Prevent command spam
def handle_motor_command(data):
    """Handle motor command from client with validation"""
    if not current_user.is_authenticated:
        return
    
    # Validate input
    try:
        InputValidator.validate_motor_command(data)
    except Exception as e:
        emit('command_error', {'error': str(e)})
        return
        
    motor_id = data.get('motor_id')
    angle = data.get('angle')
    
    if motor_id is not None and angle is not None:
        success = send_motor_command(motor_id, angle)
        if success:
            log_mission('MOTOR_DIRECT', {'motor_id': motor_id, 'angle': angle})
            
        emit('command_response', {'success': success, 'motor_id': motor_id, 'angle': angle})
        socketio.emit('state_update', robot_state)

@socketio.on('motor_command_arm')
@limiter.limit("100 per minute")
def handle_motor_command_arm(data):
    """Handle motor command for a specific arm (left/right) from client with validation (Feature 3.4)"""
    if not current_user.is_authenticated:
        return
    
    # Validate input
    try:
        InputValidator.validate_motor_command(data)
    except Exception as e:
        emit('command_error', {'error': str(e)})
        return
        
    arm_id = data.get('arm_id', 'right')
    motor_id = data.get('motor_id')
    angle = data.get('angle')
    
    if motor_id is not None and angle is not None:
        success = send_motor_command_arm(arm_id, motor_id, angle)
        if success:
            log_mission('MOTOR_DIRECT_ARM', {'arm_id': arm_id, 'motor_id': motor_id, 'angle': angle})
            
        emit('command_response', {'success': success, 'arm_id': arm_id, 'motor_id': motor_id, 'angle': angle})
        
        # Store individual arm states
        if arm_id.lower() == 'left':
            if 'left_motors' not in robot_state:
                robot_state['left_motors'] = {i: 90 for i in range(2, 10)}
            robot_state['left_motors'][motor_id] = angle
        else:
            robot_state['motors'][motor_id] = angle
            
        socketio.emit('state_update', robot_state)


@socketio.on('batch_command')
def handle_batch_command(data):
    """Handle batch motor commands with validation"""
    # Validate input
    try:
        InputValidator.validate_batch_command(data)
    except Exception as e:
        emit('command_error', {'error': str(e)})
        return
    
    commands = data.get('commands', {})
    success = send_batch_commands(commands)
    emit('command_response', {'success': success, 'type': 'batch'})
    socketio.emit('state_update', robot_state)


@socketio.on('joystick_move')
def handle_joystick(data):
    """Handle virtual joystick input (velocity control) with validation"""
    if not current_user.is_authenticated:
        return
    
    # Validate input
    try:
        InputValidator.validate_joystick_input(data)
    except Exception as e:
        emit('command_error', {'error': str(e)})
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
    global teach_mode_enabled
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
            
    # Record Teach Frame if Teach-by-Demonstration is enabled (Feature 6.1 Upgrade)
    if teach_mode_enabled:
        try:
            motion_recorder.record_teach_frame(gestures, robot_state['motors'])
        except Exception as e:
            logger.error(f"[TEACH] Frame recording error: {e}")
    
    socketio.emit('state_update', robot_state)


@socketio.on('toggle_teach_mode')
def handle_toggle_teach_mode(data):
    """Toggle Teach-by-Demonstration sequence recording (Feature 6.1 Upgrade)"""
    global teach_mode_enabled
    enable = data.get('enable', False)
    teach_mode_enabled = enable
    if enable:
        motion_recorder.start_recording(teach_mode=True)
    else:
        motion_recorder.stop_recording()
    socketio.emit('teach_mode_status', {'enabled': teach_mode_enabled})
    logger.info(f"[TEACH] Teach Mode toggled to: {'ON' if teach_mode_enabled else 'OFF'}")


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


# ==================== MOTION RECORDING EVENTS ====================

@socketio.on('start_recording')
def handle_start_recording():
    """Start recording motor movements"""
    if not current_user.is_authenticated:
        return
    
    motion_recorder.start_recording()
    emit('recording_status', {'recording': True, 'message': 'Recording started'})
    logger.info("[RECORDER] Recording started by user")


@socketio.on('stop_recording')
def handle_stop_recording(data):
    """Stop recording and save sequence with validation"""
    if not current_user.is_authenticated:
        return
    
    sequence = motion_recorder.stop_recording()
    name = data.get('name', f'sequence_{int(time.time())}')
    
    # Validate recording name
    try:
        InputValidator.validate_recording_name(name)
    except Exception as e:
        emit('recording_saved', {'success': False, 'error': str(e)})
        return
    
    try:
        filepath = motion_recorder.save_sequence(name)
        emit('recording_saved', {
            'success': True,
            'name': name,
            'frames': len(sequence),
            'filepath': filepath
        })
        logger.info(f"[RECORDER] Sequence saved: {name} ({len(sequence)} frames)")
    except Exception as e:
        emit('recording_saved', {
            'success': False,
            'error': str(e)
        })
        logger.error(f"[RECORDER] Save failed: {e}")


@socketio.on('list_recordings')
def handle_list_recordings():
    """List all available recordings"""
    if not current_user.is_authenticated:
        return
    
    recordings = motion_recorder.list_recordings()
    emit('recordings_list', {'recordings': recordings})


@socketio.on('playback_sequence')
def handle_playback_sequence(data):
    """Play back a recorded sequence with validation"""
    if not current_user.is_authenticated:
        return
    
    filename = data.get('filename')
    if not filename:
        emit('playback_status', {'success': False, 'error': 'No filename provided'})
        return
    
    # Validate filename
    try:
        InputValidator.validate_filename(filename)
    except Exception as e:
        emit('playback_status', {'success': False, 'error': str(e)})
        return
    
    try:
        sequence_data = motion_recorder.load_sequence(filename)
        # Start playback in separate thread
        threading.Thread(
            target=playback_sequence_thread,
            args=(sequence_data['sequence'],),
            daemon=True
        ).start()
        
        emit('playback_status', {
            'success': True,
            'message': f"Playing back: {sequence_data['name']}"
        })
    except Exception as e:
        emit('playback_status', {'success': False, 'error': str(e)})
        logger.error(f"[RECORDER] Playback failed: {e}")


@socketio.on('delete_recording')
def handle_delete_recording(data):
    """Delete a recording with validation (admin only)"""
    if not current_user.is_authenticated or current_user.role != 'admin':
        emit('delete_status', {'success': False, 'error': 'Admin access required'})
        return
    
    filename = data.get('filename')
    if not filename:
        emit('delete_status', {'success': False, 'error': 'No filename provided'})
        return
    
    # Validate filename
    try:
        InputValidator.validate_filename(filename)
    except Exception as e:
        emit('delete_status', {'success': False, 'error': str(e)})
        return
    
    success = motion_recorder.delete_recording(filename)
    emit('delete_status', {'success': success, 'filename': filename})


@socketio.on('toggle_camera')
def handle_toggle_camera(data):
    """Toggle camera on/off (Fix Bug 2.6)"""
    global camera
    enable = data.get('enable', True) if isinstance(data, dict) else True
    if not CV2_AVAILABLE:
        emit('camera_status', {'active': False, 'error': 'OpenCV not available'})
        return
    try:
        if enable and camera is None:
            with camera_lock:
                camera = cv2.VideoCapture(config.CAMERA_INDEX)
                if camera.isOpened():
                    camera.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
                    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
                    robot_state['camera_active'] = True
                    emit('camera_status', {'active': True})
                    logger.info("[CAMERA] Camera started")
                else:
                    camera.release()
                    camera = None
                    robot_state['camera_active'] = False
                    emit('camera_status', {'active': False, 'error': 'Camera not found'})
        elif not enable and camera is not None:
            with camera_lock:
                camera.release()
                camera = None
                robot_state['camera_active'] = False
            emit('camera_status', {'active': False})
            logger.info("[CAMERA] Camera stopped")
        else:
            emit('camera_status', {'active': robot_state['camera_active']})
    except Exception as e:
        logger.error(f"[CAMERA] Toggle error: {e}")
        emit('camera_status', {'active': False, 'error': str(e)})


@socketio.on('update_ai_personality')
def handle_update_ai_personality(data):
    """Update AI voice/personality settings (Fix Bug 2.7)"""
    if voice_processor:
        tone = data.get('tone', 'professional')
        response_length = data.get('response_length', 'brief')
        prompt = data.get('prompt', '')
        # Store as attributes for future use in voice prompts
        voice_processor.personality_tone = tone
        voice_processor.response_length = response_length
        voice_processor.system_prompt = prompt
        emit('ai_personality_updated', {'success': True, 'tone': tone, 'response_length': response_length, 'prompt': prompt})
        logger.info(f"[AI] Personality updated: tone={tone}, length={response_length}, prompt={len(prompt)} chars")
    else:
        emit('ai_personality_updated', {'success': False, 'error': 'Voice processor not available'})


@socketio.on('reset_emergency_stop')
def handle_reset_estop():
    """Reset emergency stop flag to resume operations"""
    robot_state['emergency_stop'] = False
    socketio.emit('emergency_stop_reset', {'emergency_stop': False})
    socketio.emit('state_update', robot_state)
    logger.info("[SAFETY] Emergency stop reset by user")


@socketio.on('get_recordings')
def handle_get_recordings():
    """Alias for list_recordings (frontend compatibility)"""
    if not current_user.is_authenticated:
        return
    recordings = motion_recorder.list_recordings()
    emit('recordings_list', {'recordings': recordings})


def playback_sequence_thread(sequence: List[Dict]):
    """
    Play back a recorded sequence in a background thread.
    
    Args:
        sequence: List of frames with timestamps and motor positions
    """
    logger.info(f"[PLAYBACK] Starting playback of {len(sequence)} frames")
    
    start_time = time.time()
    for frame in sequence:
        target_time = frame['timestamp']
        motors = frame['motors']
        
        # Wait until the correct time
        while (time.time() - start_time) < target_time:
            time.sleep(0.01)
        
        # Send batch command
        send_batch_commands(motors)
    
    logger.info("[PLAYBACK] Playback complete")
    socketio.emit('playback_complete', {'message': 'Playback finished'})


@socketio.on('gamepad_data')
def handle_gamepad_data(data):
    """
    Handle gamepad input from frontend with validation (Anti-Gravity Velocity Control)
    Moves motors smoothly by adding/subtracting from current position based on stick pressure.
    """
    
    if robot_state['emergency_stop']:
        return
    
    # Validate gamepad input
    try:
        InputValidator.validate_gamepad_input(data)
    except Exception as e:
        emit('command_error', {'error': str(e)})
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
    Main command execution loop - processes AI-generated commands (Ollama/Gemini + others)
    """
    last_time = time.perf_counter()
    
    while True:
        try:
            # 1. Smoothly follow target_motors using Delta-Time Interpolation (B3)
            current_time = time.perf_counter()
            dt = current_time - last_time
            last_time = current_time
            dt = min(0.1, dt)  # Clamp dt to prevent jumps
            
            batch_moves = {}
            speed = 45.0  # Degrees per second
            for motor_id, target in robot_state['target_motors'].items():
                current = robot_state['motors'][motor_id]
                diff = target - current
                if abs(diff) > 0.1:
                    step = speed * dt
                    if abs(diff) <= step:
                        new_pos = target
                    else:
                        new_pos = current + (step if diff > 0 else -step)
                    batch_moves[motor_id] = int(new_pos)
            if batch_moves:
                send_batch_commands(batch_moves)
            
            # ========== VOICE/AI COMMAND HANDLING ==========
            if voice_processor:
                command = voice_processor.get_command(timeout=0.05)
                if command:
                    cmd_type = command.get('type')
                    print(f"[BRAIN] Processing Command: {cmd_type}")

                    # --- OLLAMA & GEMINI INTELLIGENT COMMANDS ---
                    if cmd_type in ['gemini_command', 'ollama_command']:
                        # 1. Speak the AI response first
                        response_text = command.get('response_text')
                        if response_text and voice_processor:
                             voice_processor.speak(response_text, 
                                                lambda text: socketio.emit('robot_speech', {'text': text}))
                        
                        # 2. Execute Motor Movements
                        motor_values = command.get('motor_values', {})
                        if motor_values:
                            safe_moves = {int(k): v for k, v in motor_values.items() if int(k) >= 2}
                            if safe_moves:
                                send_batch_commands(safe_moves)
                    
                    elif cmd_type == 'macro_sequence':
                        # 1. Speak the action notification
                        response_text = command.get('response_text', "Initializing multi-step macro sequence.")
                        if response_text and voice_processor:
                             voice_processor.speak(response_text, 
                                                 lambda text: socketio.emit('robot_speech', {'text': text}))
                        
                        # 2. Start macro sequence in the background macro executor thread
                        actions = command.get('actions', [])
                        if actions and macro_executor:
                            macro_executor.start_macro(actions)
                    
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
                    # Reset lost frame counter
                    command_execution_loop.lost_frames = 0
                    
                    # Get normalized Y position (0-1) (A3 Upgrade)
                    center_x = target_detection['center'][0]
                    center_y = target_detection['center'][1]
                    y_normalized = center_y / float(config.CAMERA_HEIGHT)  # Normalize to 0-1
                    
                    # Calculate angle using kinematics
                    target_angle = kinematics.image_y_to_angle(y_normalized)
                    
                    # Move main pivot to track object
                    current_angle = robot_state['motors'][2]
                    if abs(current_angle - target_angle) > 2:  # Deadband
                        send_motor_command(2, target_angle)
                        print(f"[TRACK] Tracking: Moving pivot to {target_angle} deg")
                        
                        # TTS feedback (throttled to avoid spam)
                        if not hasattr(command_execution_loop, 'last_track_speech') or \
                           time.time() - command_execution_loop.last_track_speech > 6:
                            if voice_processor:
                                voice_processor.speak("Target acquired, locking position.", 
                                                    lambda text: socketio.emit('robot_speech', {'text': text}))
                            command_execution_loop.last_track_speech = time.time()
                    
                    # --- AUTONOMOUS GRAB PROTOCOL ---
                    if not hasattr(command_execution_loop, 'stable_frames'):
                        command_execution_loop.stable_frames = 0
                    if not hasattr(command_execution_loop, 'is_grabbed'):
                        command_execution_loop.is_grabbed = False
                        
                    # Center limits: 240 <= center_x <= 400 (centered horizontally)
                    if 240 <= center_x <= 400 and not command_execution_loop.is_grabbed:
                        command_execution_loop.stable_frames += 1
                        print(f"[AUTONOMOUS GRAB] stable frames: {command_execution_loop.stable_frames}/12")
                    else:
                        command_execution_loop.stable_frames = max(0, command_execution_loop.stable_frames - 1)
                        
                    # Trigger autonomous grab sequence when target is stable
                    if command_execution_loop.stable_frames >= 12 and not command_execution_loop.is_grabbed:
                        command_execution_loop.is_grabbed = True
                        command_execution_loop.stable_frames = 0
                        
                        print("[AUTONOMOUS GRAB] >>> STARTING PICK-AND-LIFT SEQUENCE <<<")
                        if voice_processor:
                            voice_processor.speak("Target locked. Initiating autonomous grab sequence.", 
                                                lambda text: socketio.emit('robot_speech', {'text': text}))
                            
                        # Step 1: Open fingers fully to prepare grab (Servos 5-9 to 0 degrees)
                        if not robot_state.get('emergency_stop'):
                            send_batch_commands({5: 0, 6: 0, 7: 0, 8: 0, 9: 0})
                            time.sleep(0.8)
                        
                        # Step 2: Pitch wrist forward towards target (Servo 3 to 120 degrees)
                        if not robot_state.get('emergency_stop'):
                            send_motor_command(3, 120)
                            time.sleep(1.0)
                        
                        # Step 3: Securely clench all fingers (Servos 5-9 to 180 degrees)
                        if not robot_state.get('emergency_stop'):
                            send_batch_commands({5: 180, 6: 180, 7: 180, 8: 180, 9: 180})
                            time.sleep(1.2)
                        
                        # Step 4: Lift the arm with secured target (Servo 3 to 50 degrees)
                        if not robot_state.get('emergency_stop'):
                            send_motor_command(3, 50)
                            time.sleep(0.8)
                        
                        if not robot_state.get('emergency_stop'):
                            if voice_processor:
                                voice_processor.speak("Target secured. Secure lift protocol complete.", 
                                                    lambda text: socketio.emit('robot_speech', {'text': text}))
                else:
                    # Target lost counter
                    if not hasattr(command_execution_loop, 'lost_frames'):
                        command_execution_loop.lost_frames = 0
                    command_execution_loop.lost_frames += 1
                    
                    if command_execution_loop.lost_frames >= 40:
                        # Reset grab status if target has been missing for ~2 seconds
                        if hasattr(command_execution_loop, 'is_grabbed') and command_execution_loop.is_grabbed:
                            command_execution_loop.is_grabbed = False
                            print("[AUTONOMOUS GRAB] Target lost. Resetting grab protocol.")
                            if voice_processor:
                                voice_processor.speak("Target lost. Resetting grab protocol.", 
                                                    lambda text: socketio.emit('robot_speech', {'text': text}))
            
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


def home_position() -> None:
    """
    Move all motors to safe home position.
    
    Home position:
    - Motors 2-4: Center (90°)
    - Motors 5-9: Open (0°)
    """
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
    try:
        user_count = User.query.count()
        team_count = TeamMember.query.count()
        log_count = MissionLog.query.count()
        history_count = LoginHistory.query.count()
    except Exception:
        user_count = team_count = log_count = history_count = 0
    return render_template('admin/dashboard.html',
                           user_count=user_count,
                           team_count=team_count,
                           log_count=log_count,
                           history_count=history_count)

@app.route('/admin/call-graph')
@login_required
@admin_required
def admin_call_graph():
    """Serve the interactive Graphify system call graph"""
    try:
        # Check if the graph HTML exists, if not generate it on the fly!
        if not os.path.exists('docs/LUNA_Call_Graph.html'):
            try:
                # Run the graph generator script
                import subprocess
                subprocess.run(['python', 'utils/luna_make_graph.py'], check=True)
            except Exception as e:
                logger.error(f"[GRAPHIFY] Failed to auto-generate graph: {e}")
        
        return send_from_directory('docs', 'LUNA_Call_Graph.html')
    except Exception as e:
        logger.error(f"[GRAPHIFY] Error serving call graph: {e}")
        return "System Call Graph is temporarily unavailable.", 500

@app.route('/admin/login-history')
@login_required
@admin_required
def admin_login_history():
    """Admin view of all login attempts"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 30
        pagination = LoginHistory.query.order_by(LoginHistory.login_time.desc()).paginate(
            page=page, per_page=per_page, error_out=False)
        history_items = pagination.items
    except Exception as e:
        logger.error(f"[HISTORY] DB error fetching login history: {e}")
        history_items = []
        pagination = None
        
    return render_template('admin/login_history.html', history=history_items, pagination=pagination)

@app.route('/api/login-history')
@login_required
def api_login_history():
    """Get current user's login history (SPA API)"""
    try:
        history = LoginHistory.query.filter_by(user_id=current_user.id).order_by(
            LoginHistory.login_time.desc()).limit(10).all()
        data = [{
            'id': h.id,
            'ip_address': h.ip_address,
            'user_agent': h.user_agent,
            'login_time': h.login_time.isoformat(),
            'success': h.success
        } for h in history]
        return jsonify({'success': True, 'history': data})
    except Exception as e:
        logger.error(f"[HISTORY] API error fetching user history: {e}")
        return jsonify({'success': False, 'history': []}), 500

@app.route('/login-history')
@login_required
def login_history():
    """User audit logs page showing individual session histories (Resolved login history page)"""
    try:
        history = LoginHistory.query.filter_by(user_id=current_user.id).order_by(LoginHistory.login_time.desc()).limit(50).all()
    except Exception as e:
        logger.error(f"[HISTORY] User view DB error: {e}")
        history = []
    return render_template('login_history_user.html', history=history)



@app.route('/api/diagnostics/run')
@login_required
def api_run_diagnostics():
    """API endpoint to run a fresh diagnostic profile and return results"""
    try:
        import subprocess
        subprocess.run(['python', 'utils/diagnose_system.py'], check=True)
        report_path = 'docs/luna_diagnostic_report.json'
        if os.path.exists(report_path):
            with open(report_path, 'r', encoding='utf-8') as f:
                report_data = json.load(f)
            return jsonify({'success': True, 'report': report_data})
    except Exception as e:
        logger.error(f"[DIAGNOSTICS] API run failed: {e}")
    return jsonify({'success': False, 'message': 'Failed to execute diagnostic profiler.'})

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
    """User mission logs (DB-resilient)"""
    try:
        page = request.args.get('page', 1, type=int)
        if current_user.role == 'admin':
            logs = MissionLog.query.order_by(MissionLog.timestamp.desc()).paginate(page=page, per_page=50, error_out=False)
        else:
            logs = MissionLog.query.filter_by(user_id=current_user.id).order_by(MissionLog.timestamp.desc()).paginate(page=page, per_page=50, error_out=False)
    except Exception as e:
        logger.warning(f"[LOGS] DB unavailable: {e}")
        logs = None
    return render_template('logs.html', logs=logs)

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

# Support both /change-password and /profile/change-password
@app.route('/change-password', methods=['GET', 'POST'])
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
        elif len(new_password) < 6:
            flash('New encryption key must be at least 6 characters.', 'danger')
        else:
            try:
                current_user.set_password(new_password)
                db.session.commit()
                flash('Encryption key updated successfully.', 'success')
                return redirect(url_for('profile'))
            except Exception as e:
                db.session.rollback()
                flash('Database error. Please try again.', 'danger')
    return render_template('change_password.html')

def init_ai_modules():
    """Initialize AI modules in background"""
    global object_detector, hand_tracker, voice_processor, vision_processor
    
    logger.info("[AI] Initializing AI modules...")
    
    try:
        if vision_processor:
            vision_processor.initialize()
            logger.info("[OK] Unified Vision Processor ready")
    except Exception as e:
        logger.error(f"[WARN] Vision Processor error: {e}")
    
    try:
        voice_processor = VoiceCommandProcessor()
        logger.info("[OK] Voice Processor ready")
    except Exception as e:
        logger.error(f"[WARN] Voice Processor error: {e}")


if __name__ == '__main__':
    print("=" * 50)
    print("[START] LUNA Robotic Arm - Starting System")
    
    # Check if this is the reloader parent or the active worker
    is_main_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug
    
    if is_main_process:
        # Initialize Database
        with app.app_context():
            try:
                db.create_all()
                logger.info("[DB] Database tables verified/created")
            except Exception as e:
                logger.error(f"[WARN] Database initialization failed (DB may be paused/offline): {e}")
                logger.warning("[WARN] System will run in OFFLINE mode — authentication disabled, robot control still works")

        # Initialize serial connection
        init_serial_connection()
        
        # Start serial writer threads
        writer_thread = threading.Thread(target=serial_writer_thread, daemon=True)
        writer_thread.start()
        
        left_writer_thread = threading.Thread(target=left_serial_writer_thread, daemon=True)
        left_writer_thread.start()
        
        right_writer_thread = threading.Thread(target=right_serial_writer_thread, daemon=True)
        right_writer_thread.start()
        logger.info("[OK] Bimanual Serial writer threads started")
        
        # Start serial heartbeat watchdog thread (B1)
        heartbeat_thread = threading.Thread(target=serial_heartbeat_thread, daemon=True)
        heartbeat_thread.start()
        logger.info("[OK] Serial heartbeat watchdog thread started")
        
        # Start asynchronous database logging worker (B5)
        db_logger_thread = threading.Thread(target=async_batch_logger_thread, daemon=True)
        db_logger_thread.start()
        logger.info("[OK] Async batch logger thread started")
        
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
    else:
        print("[RELOADER] Reloader parent process started. Waiting for worker process...")
    
    # Run Flask app
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=True, allow_unsafe_werkzeug=True)


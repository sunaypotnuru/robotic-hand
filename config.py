"""
LUNA Robotic Arm - Configuration File
"""

# Serial Communication
SERIAL_PORT = None  # Auto-detect if None
BAUD_RATE = 115200
SERIAL_TIMEOUT = 1.0

# Motor Configuration
MOTOR_IDS = {
    'main_pivot': 2,      # Elbow (DS51150, 7.4V)
    'wrist_pitch': 3,     # Wrist Pitch (DS5180, 7.4V)
    'wrist_roll': 4,      # Wrist Roll (DS5180, 7.4V)
    'thumb': 5,           # Thumb (6V)
    'index': 6,           # Index (6V)
    'middle': 7,          # Middle (6V)
    'ring': 8,            # Ring (6V)
    'pinky': 9,           # Pinky (6V)
}

# REMOVED MOTORS (Do not use)
REMOVED_MOTOR_IDS = [0, 1]  # Shoulder assembly removed

# Safety Configuration
EMERGENCY_STOP_DISTANCE = 10  # cm
MIN_ANGLE = 0
MAX_ANGLE = 180

# Kinematics
FOREARM_LENGTH = 28.0  # cm (single link)

# Camera Configuration
CAMERA_INDEX = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30

# AI Model Paths
YOLO_MODEL_PATH = 'yolov8n.pt'  # Will download if not found
MEDIAPIPE_MODEL_COMPLEXITY = 1  # 0, 1, or 2

# Joystick Control
JOYSTICK_SPEED_FACTOR = 2.0  # Degrees per update
JOYSTICK_DEADZONE = 0.1

# Voice Commands
VOICE_MODEL = 'base'  # 'tiny', 'base', 'small', 'medium', 'large'
VOICE_LANGUAGE = 'en'
VOICE_TIMEOUT = 3.0

# Web Server
HOST = '0.0.0.0'
PORT = 5000
DEBUG = False

# Home Position (angles in degrees)
HOME_POSITION = {
    2: 90,   # Main Pivot
    3: 90,   # Wrist Pitch
    4: 90,   # Wrist Roll
    5: 0,    # Thumb
    6: 0,    # Index
    7: 0,    # Middle
    8: 0,    # Ring
    9: 0,    # Pinky
}

# System Logging
LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'


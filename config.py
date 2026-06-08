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

# ==================== AI MODEL CONFIGURATION ====================

# Dual YOLO System
USE_DUAL_YOLO = True  # Set False to use MediaPipe fallback

# Object Detection Model (YOLOv8m - Medium)
YOLO_OBJECT_MODEL_PATH = 'models/yolov8m.pt'  # Will download if not found
OBJECT_CONFIDENCE_THRESHOLD = 0.5
OBJECT_IOU_THRESHOLD = 0.45

# Hand Detection Model (YOLOv8n-pose - Nano with Pose)
YOLO_HAND_MODEL_PATH = 'models/yolov8n-hand.pt'  # Will download if not found
HAND_CONFIDENCE_THRESHOLD = 0.7  # Higher for safety
HAND_IOU_THRESHOLD = 0.45

# Legacy Models (Fallback) - DEPRECATED
# YOLO_MODEL_PATH = 'yolov8n.pt'  # No longer used - models are in models/ folder
MEDIAPIPE_MODEL_COMPLEXITY = 1  # 0, 1, or 2

# Performance Tuning
PROCESS_EVERY_N_FRAMES = 2  # Skip frames for performance (1 = process every frame)
PARALLEL_INFERENCE = True    # Run both models in parallel

# Gesture Recognition
GESTURE_CONFIDENCE_THRESHOLD = 0.6
GESTURE_THRESHOLD_FINGER_EXTENDED = 0.15  # Distance ratio for extended finger
WAVE_DETECTION_FRAMES = 10                # Frames to detect wave
WAVE_AMPLITUDE_THRESHOLD = 50              # Pixels of horizontal movement

# Target Objects (for robotic interaction)
TARGET_OBJECTS = [
    'cup', 'bottle', 'bowl', 'book', 'cell phone',
    'remote', 'scissors', 'spoon', 'fork', 'knife',
    'mouse', 'keyboard', 'potted plant', 'teddy bear'
]

# Gesture to Command Mapping
GESTURE_COMMANDS = {
    'open_palm': {'hand': {5: 0, 6: 0, 7: 0, 8: 0, 9: 0}},           # Open hand
    'closed_fist': {'hand': {5: 180, 6: 180, 7: 180, 8: 180, 9: 180}}, # Close hand
    'pointing': {'motor': {2: 90}},                                    # Center arm
    'peace': {'motor': {4: 45}},                                       # Wrist roll
    'thumbs_up': {'system': 'home_position'},                          # Home position
    'wave': {'system': 'emergency_stop'},                              # Emergency stop
}

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


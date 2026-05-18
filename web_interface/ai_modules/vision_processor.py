"""
LUNA Vision Processing Module
Orchestrates hand tracking and object detection models sequentially on incoming video streams.
"""
import logging
import threading
from ai_modules.object_detect import ObjectDetector
from ai_modules.hand_tracking import HandTracker

logger = logging.getLogger("LUNA.VisionProcessor")

class VisionProcessor:
    def __init__(self):
        self.object_detector = None
        self.hand_tracker = None
        self.frame_lock = threading.Lock()
        self.latest_frame = None
        self.initialized = False

    def initialize(self):
        """Lazy-initialize model detectors sequentially to conserve GPU memory"""
        if self.initialized:
            return
        logger.info("[VISION] Initializing unified vision pipelines...")
        try:
            self.object_detector = ObjectDetector()
            logger.info("[VISION] Object Detector attached to VisionProcessor")
        except Exception as e:
            logger.error(f"[VISION] Error binding ObjectDetector: {e}")
            
        try:
            self.hand_tracker = HandTracker()
            logger.info("[VISION] Hand Tracker attached to VisionProcessor")
        except Exception as e:
            logger.error(f"[VISION] Error binding HandTracker: {e}")
            
        self.initialized = True
        logger.info("[VISION] VisionProcessor initialized successfully")

    def process_frame(self, frame):
        """Processes incoming frames sequentially through YOLO and MediaPipe pipelines"""
        if not self.initialized:
            self.initialize()
            
        with self.frame_lock:
            # 1. Detect objects using YOLO
            if self.object_detector:
                try:
                    frame = self.object_detector.process_frame(frame)
                except Exception as e:
                    logger.debug(f"[VISION] YOLO execution warning: {e}")
                    
            # 2. Track hands using MediaPipe
            if self.hand_tracker:
                try:
                    frame = self.hand_tracker.process_frame(frame)
                except Exception as e:
                    logger.debug(f"[VISION] MediaPipe execution warning: {e}")
                    
            self.latest_frame = frame
            return frame

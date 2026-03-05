"""
LUNA Hand Detection Module
YOLOv8n-pose for hand detection and keypoint extraction
"""

import cv2
import numpy as np
import threading
import time
import os

# Resolve model path relative to this file's directory
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_MODEL = os.path.join(_BASE_DIR, '..', '..', 'models', 'yolov8n-hand.pt')


class HandDetector:
    """
    YOLOv8n-pose Hand Detector with 21 keypoints
    """
    
    # MediaPipe-compatible keypoint indices
    KEYPOINT_NAMES = [
        'wrist',
        'thumb_cmc', 'thumb_mcp', 'thumb_ip', 'thumb_tip',
        'index_mcp', 'index_pip', 'index_dip', 'index_tip',
        'middle_mcp', 'middle_pip', 'middle_dip', 'middle_tip',
        'ring_mcp', 'ring_pip', 'ring_dip', 'ring_tip',
        'pinky_mcp', 'pinky_pip', 'pinky_dip', 'pinky_tip'
    ]
    
    # Finger indices for easy access
    FINGER_INDICES = {
        'thumb': [1, 2, 3, 4],
        'index': [5, 6, 7, 8],
        'middle': [9, 10, 11, 12],
        'ring': [13, 14, 15, 16],
        'pinky': [17, 18, 19, 20]
    }
    
    def __init__(self, model_path=None, confidence_threshold=0.7):
        """
        Initialize YOLOv8n-pose detector
        
        Args:
            model_path: Path to YOLOv8 pose model
            confidence_threshold: Minimum confidence for detection
        """
        if model_path is None:
            model_path = _DEFAULT_MODEL
            
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.iou_threshold = 0.45
        
        self.model = None
        self.detections = []
        self.lock = threading.Lock()
        self.fps = 0
        self.last_inference_time = 0
        self.frame_count = 0
        self.skip_frames = 2  # Process every other frame
        
        # Check if model file exists
        if not os.path.exists(model_path):
            print(f"⚠️  Hand detection model not found: {model_path}")
            print(f"   Download with: wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n-pose.pt")
            print(f"   Place in: {os.path.dirname(model_path)}/")
            print(f"   Rename to: yolov8n-hand.pt")
            print(f"   Falling back to MediaPipe for hand tracking")
            return
        
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_path)
            print(f"✅ YOLOv8 Hand Detector loaded: {self.model_path}")
            
            # Warm up the model
            dummy = np.zeros((640, 640, 3), dtype=np.uint8)
            self.model(dummy, verbose=False)
            
        except Exception as e:
            print(f"⚠️  YOLOv8 hand detector initialization error: {e}")
            print("   Falling back to MediaPipe for hand tracking")
    
    def process_frame(self, frame):
        """
        Process frame with YOLOv8-pose and extract hand keypoints
        
        Args:
            frame: Input BGR frame
            
        Returns:
            Annotated frame with hand keypoints and connections
        """
        if self.model is None:
            return frame
        
        # Frame skipping for performance
        self.frame_count += 1
        if self.frame_count % self.skip_frames != 0:
            return self._draw_detections(frame.copy())
        
        try:
            start_time = time.time()
            
            # Run YOLOv8 inference
            results = self.model(
                frame,
                verbose=False,
                conf=self.confidence_threshold,
                iou=self.iou_threshold
            )
            
            # Calculate FPS
            inference_time = time.time() - start_time
            self.fps = 0.9 * self.fps + 0.1 * (1.0 / inference_time) if self.fps else 1.0 / inference_time
            
            # Extract detections and keypoints
            detections = []
            annotated_frame = frame.copy()
            
            if len(results) > 0 and hasattr(results[0], 'keypoints') and results[0].keypoints is not None:
                boxes = results[0].boxes
                keypoints = results[0].keypoints
                
                for i, box in enumerate(boxes):
                    # Get box coordinates
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    confidence = float(box.conf[0].cpu().numpy())
                    
                    # Get keypoints (21 points with x, y, confidence)
                    kp_data = keypoints[i].data[0].cpu().numpy()
                    
                    # Filter low-confidence keypoints
                    visible_kp = []
                    for kp in kp_data:
                        x, y, conf = kp
                        visible_kp.append({
                            'x': int(x),
                            'y': int(y),
                            'confidence': float(conf),
                            'visible': conf > 0.5
                        })
                    
                    # Store detection
                    detection = {
                        'bbox': [int(x1), int(y1), int(x2), int(y2)],
                        'center': [int((x1 + x2) / 2), int((y1 + y2) / 2)],
                        'confidence': confidence,
                        'keypoints': visible_kp,
                        'timestamp': time.time()
                    }
                    detections.append(detection)
                    
                    # Draw hand
                    self._draw_hand(annotated_frame, detection)
            
            # Update detections
            with self.lock:
                self.detections = detections
            
            return annotated_frame
            
        except Exception as e:
            print(f"⚠️  Hand detection error: {e}")
            return frame
    
    def _draw_hand(self, frame, detection):
        """Draw hand bounding box and keypoints"""
        x1, y1, x2, y2 = detection['bbox']
        keypoints = detection['keypoints']
        
        # Draw bounding box
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        # Draw keypoints
        for i, kp in enumerate(keypoints):
            if kp['visible']:
                cv2.circle(frame, (kp['x'], kp['y']), 4, (0, 255, 255), -1)
        
        # Draw connections (simplified hand skeleton)
        connections = [
            (0, 1), (1, 2), (2, 3), (3, 4),           # Thumb
            (0, 5), (5, 6), (6, 7), (7, 8),           # Index
            (0, 9), (9, 10), (10, 11), (11, 12),      # Middle
            (0, 13), (13, 14), (14, 15), (15, 16),    # Ring
            (0, 17), (17, 18), (18, 19), (19, 20)     # Pinky
        ]
        
        for start, end in connections:
            if (start < len(keypoints) and end < len(keypoints) and
                keypoints[start]['visible'] and keypoints[end]['visible']):
                cv2.line(frame,
                        (keypoints[start]['x'], keypoints[start]['y']),
                        (keypoints[end]['x'], keypoints[end]['y']),
                        (0, 255, 0), 2)
    
    def _draw_detections(self, frame):
        """Draw stored detections on frame (for skipped frames)"""
        with self.lock:
            detections = self.detections.copy()
        
        annotated = frame.copy()
        for detection in detections:
            self._draw_hand(annotated, detection)
        
        # Add FPS counter
        cv2.putText(annotated, f"Hand FPS: {self.fps:.1f}",
                   (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        return annotated
    
    def get_detections(self):
        """Get current hand detections"""
        with self.lock:
            return self.detections.copy()
    
    def get_primary_hand(self):
        """Get the most prominent hand (closest to center)"""
        with self.lock:
            if not self.detections:
                return None
            
            # Find hand closest to frame center
            frame_center = (320, 240)
            best_hand = None
            min_distance = float('inf')
            
            for hand in self.detections:
                center = hand['center']
                distance = ((center[0] - frame_center[0])**2 +
                           (center[1] - frame_center[1])**2) ** 0.5
                if distance < min_distance:
                    min_distance = distance
                    best_hand = hand
            
            return best_hand

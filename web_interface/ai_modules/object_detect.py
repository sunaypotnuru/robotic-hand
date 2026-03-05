"""
LUNA Object Detection Module
YOLOv8 for Object Tracking and Click-to-Pick
"""

import cv2
import numpy as np
import threading
import os

# Resolve YOLO model path relative to this file's directory so the app
# can be started from any working directory.
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_MODEL = os.path.join(_BASE_DIR, '..', '..', 'models', 'yolov8m.pt')


class ObjectDetector:
    """
    YOLOv8 Object Detector for robotic arm control
    """
    
    def __init__(self, model_path=None, confidence_threshold=0.5):
        """
        Initialize YOLOv8 detector
        
        Args:
            model_path: Path to YOLOv8 model file
            confidence_threshold: Minimum confidence for detection
        """
        if model_path is None:
            model_path = _DEFAULT_MODEL
        
        self.confidence_threshold = confidence_threshold
        self.model = None
        self.detections = []
        self.lock = threading.Lock()
        
        try:
            from ultralytics import YOLO
            # Load YOLOv8 model (will download if not found)
            self.model = YOLO(model_path)
            print(f"✅ YOLOv8 model loaded: {model_path}")
        except Exception as e:
            print(f"⚠️  YOLOv8 initialization error: {e}")
            print("   Running without object detection")
    
    def process_frame(self, frame):
        """
        Process frame with YOLOv8 and draw bounding boxes
        
        Args:
            frame: Input BGR frame
            
        Returns:
            Annotated frame with bounding boxes
        """
        if self.model is None:
            return frame
        
        try:
            # Run YOLOv8 inference
            results = self.model(frame, verbose=False, conf=self.confidence_threshold)
            
            # Extract detections
            detections = []
            annotated_frame = frame.copy()
            
            if len(results) > 0 and results[0].boxes is not None:
                boxes = results[0].boxes
                
                for box in boxes:
                    # Get box coordinates
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    confidence = box.conf[0].cpu().numpy()
                    class_id = int(box.cls[0].cpu().numpy())
                    class_name = self.model.names[class_id]
                    
                    # Store detection
                    detection = {
                        'bbox': [int(x1), int(y1), int(x2), int(y2)],
                        'center': [int((x1 + x2) / 2), int((y1 + y2) / 2)],
                        'confidence': float(confidence),
                        'class_id': class_id,
                        'class_name': class_name,
                    }
                    detections.append(detection)
                    
                    # Draw bounding box
                    cv2.rectangle(annotated_frame, 
                                (int(x1), int(y1)), 
                                (int(x2), int(y2)), 
                                (0, 255, 0), 2)
                    
                    # Draw label
                    label = f"{class_name} {confidence:.2f}"
                    label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
                    cv2.rectangle(annotated_frame,
                                (int(x1), int(y1) - label_size[1] - 10),
                                (int(x1) + label_size[0], int(y1)),
                                (0, 255, 0), -1)
                    cv2.putText(annotated_frame, label,
                              (int(x1), int(y1) - 5),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
                    
                    # Draw center point
                    cv2.circle(annotated_frame,
                             (detection['center'][0], detection['center'][1]),
                             5, (255, 0, 0), -1)
            
            # Update detections
            with self.lock:
                self.detections = detections
            
            return annotated_frame
            
        except Exception as e:
            print(f"⚠️  Object detection error: {e}")
            return frame
    
    def get_detections(self):
        """
        Get current detections
        
        Returns:
            List of detection dictionaries
        """
        with self.lock:
            return self.detections.copy()
    
    def get_detection_at_point(self, x, y):
        """
        Get detection at specific point (for click-to-pick)
        
        Args:
            x, y: Click coordinates
            
        Returns:
            Detection dictionary or None
        """
        with self.lock:
            for detection in self.detections:
                x1, y1, x2, y2 = detection['bbox']
                if x1 <= x <= x2 and y1 <= y <= y2:
                    return detection
        return None
    
    def get_normalized_position(self, detection):
        """
        Get normalized position (0-1) of detection center
        
        Args:
            detection: Detection dictionary
            
        Returns:
            (x_normalized, y_normalized) or None
        """
        if detection is None:
            return None
        
        # This would need frame dimensions - simplified for now
        # In practice, pass frame dimensions to this method
        center = detection['center']
        # Normalized coordinates would be: (center_x / frame_width, center_y / frame_height)
        return center


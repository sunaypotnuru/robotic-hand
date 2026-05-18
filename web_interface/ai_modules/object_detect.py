"""
LUNA Object Detection Module
YOLOv8 for Object Tracking and Click-to-Pick with TensorRT GPU Acceleration
"""

import cv2
import numpy as np
import threading
import os
import torch

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_MODEL = os.path.join(_BASE_DIR, '..', '..', 'models', 'yolov8x.pt')


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
        self.frame_counter = 0
        self.last_annotated_frame = None
        
        try:
            from ultralytics import YOLO
            
            # Detect GPU / CUDA capability
            device = 0 if torch.cuda.is_available() else 'cpu'
            engine_path = model_path.replace('.pt', '.engine')
            
            if device == 0:
                # If engine file does not exist, attempt to export it for GPU acceleration
                if not os.path.exists(engine_path) and model_path.endswith('.pt') and os.path.exists(model_path):
                    try:
                        print("🚀 Exporting YOLOv8 model to TensorRT engine format on GPU...")
                        temp_model = YOLO(model_path)
                        temp_model.export(format='engine', device=0)
                    except Exception as ex:
                        print(f"⚠️  TensorRT Export failed: {ex}")
                
                if os.path.exists(engine_path):
                    try:
                        self.model = YOLO(engine_path)
                        model_path = engine_path
                        print(f"🚀 Loading TensorRT GPU accelerated engine: {model_path}")
                    except Exception as te:
                        print(f"⚠️ TensorRT Engine loading failed: {te}, falling back to standard PyTorch model")
            
            if self.model is None:
                # Load the PyTorch fallback model
                self.model = YOLO(model_path)
            print(f"✅ YOLOv8 model loaded: {model_path} (on {device if device == 'cpu' else 'GPU:0'})")
        except Exception as e:
            print(f"⚠️  YOLOv8 initialization error: {e}")
            print("   Running without object detection")
    
    def process_frame(self, frame):
        """
        Process frame with YOLOv8 and draw bounding boxes (w/ Frame Skipping O1)
        
        Args:
            frame: Input BGR frame
            
        Returns:
            Annotated frame with bounding boxes
        """
        if self.model is None:
            return frame
        
        self.frame_counter += 1
        
        # Frame Skipping (Process every 3rd frame - O1)
        if self.frame_counter % 3 != 0 and self.last_annotated_frame is not None:
            return self.last_annotated_frame
        
        try:
            # Run YOLOv8 inference (forces CUDA/GPU execution if device engine is loaded)
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
            
            # Update detections in a thread-safe manner
            with self.lock:
                self.detections = detections
            
            self.last_annotated_frame = annotated_frame
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
    
    def get_normalized_position(self, detection, frame_width=640, frame_height=480):
        """
        Get normalized position (0-1) of detection center (Resolved O2)
        
        Args:
            detection: Detection dictionary
            frame_width: Bounding frame width
            frame_height: Bounding frame height
            
        Returns:
            (x_normalized, y_normalized) or None
        ```
        """
        if detection is None:
            return None
        
        center = detection['center']
        x_norm = float(center[0]) / max(1.0, float(frame_width))
        y_norm = float(center[1]) / max(1.0, float(frame_height))
        return x_norm, y_norm

"""
LUNA Hand Tracking Module
MediaPipe for Hand Gesture Mimicry
"""

import cv2
import mediapipe as mp
import numpy as np
import threading


class HandTracker:
    """
    MediaPipe Hand Tracking for gesture mimicry
    """
    
    def __init__(self, max_hands=1, min_detection_confidence=0.5, min_tracking_confidence=0.5):
        """
        Initialize MediaPipe hand tracker
        
        Args:
            max_hands: Maximum number of hands to detect
            min_detection_confidence: Minimum confidence for detection
            min_tracking_confidence: Minimum confidence for tracking
        """
        self.max_hands = max_hands
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        
        # Initialize MediaPipe
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils
        self.hands = None
        self.landmarks = []
        self.gestures = {}
        self.lock = threading.Lock()
        
        try:
            self.hands = self.mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=max_hands,
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
                model_complexity=1
            )
            print("✅ MediaPipe Hand Tracker initialized")
        except Exception as e:
            print(f"⚠️  MediaPipe initialization error: {e}")
    
    def process_frame(self, frame):
        """
        Process frame with MediaPipe and extract hand landmarks
        
        Args:
            frame: Input BGR frame
            
        Returns:
            Annotated frame with hand landmarks
        """
        if self.hands is None:
            return frame
        
        try:
            # Convert BGR to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb_frame.flags.writeable = False
            
            # Process with MediaPipe
            results = self.hands.process(rgb_frame)
            
            # Convert back to BGR
            rgb_frame.flags.writeable = True
            annotated_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR)
            
            # Extract landmarks and gestures
            landmarks = []
            gestures = {}
            
            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    # Draw landmarks
                    self.mp_drawing.draw_landmarks(
                        annotated_frame,
                        hand_landmarks,
                        self.mp_hands.HAND_CONNECTIONS,
                        self.mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2),
                        self.mp_drawing.DrawingSpec(color=(0, 0, 255), thickness=2)
                    )
                    
                    # Extract landmark positions
                    hand_points = []
                    for landmark in hand_landmarks.landmark:
                        h, w, _ = frame.shape
                        x = int(landmark.x * w)
                        y = int(landmark.y * h)
                        z = landmark.z
                        hand_points.append([x, y, z])
                    
                    landmarks.append(hand_points)
                    
                    # Calculate finger fold ratios
                    finger_folds = self._calculate_finger_folds(hand_points)
                    gestures['fingers'] = finger_folds
            
            # Update state
            with self.lock:
                self.landmarks = landmarks
                self.gestures = gestures
            
            return annotated_frame
            
        except Exception as e:
            print(f"⚠️  Hand tracking error: {e}")
            return frame
    
    def _calculate_finger_folds(self, landmarks):
        """
        Calculate finger fold ratios (0 = open, 1 = closed)
        
        Args:
            landmarks: List of 21 landmark points
            
        Returns:
            List of 5 fold ratios (thumb, index, middle, ring, pinky)
        """
        if len(landmarks) < 21:
            return [0.0, 0.0, 0.0, 0.0, 0.0]
        
        # MediaPipe hand landmark indices
        # Thumb: 4 (tip), 3 (IP), 2 (MCP)
        # Index: 8 (tip), 6 (PIP), 5 (MCP)
        # Middle: 12 (tip), 10 (PIP), 9 (MCP)
        # Ring: 16 (tip), 14 (PIP), 13 (MCP)
        # Pinky: 20 (tip), 18 (PIP), 17 (MCP)
        
        finger_folds = []
        
        # Thumb (special case - different angle)
        thumb_tip = np.array(landmarks[4][:2])
        thumb_ip = np.array(landmarks[3][:2])
        thumb_mcp = np.array(landmarks[2][:2])
        thumb_dist = np.linalg.norm(thumb_tip - thumb_mcp)
        thumb_ref = np.linalg.norm(thumb_ip - thumb_mcp)
        thumb_fold = max(0, min(1, 1 - (thumb_dist / (thumb_ref * 2.5)) if thumb_ref > 0 else 0))
        finger_folds.append(thumb_fold)
        
        # Other fingers
        finger_indices = [
            (8, 6, 5),   # Index
            (12, 10, 9), # Middle
            (16, 14, 13), # Ring
            (20, 18, 17) # Pinky
        ]
        
        for tip_idx, pip_idx, mcp_idx in finger_indices:
            tip = np.array(landmarks[tip_idx][:2])
            pip = np.array(landmarks[pip_idx][:2])
            mcp = np.array(landmarks[mcp_idx][:2])
            
            # Distance from tip to MCP
            tip_to_mcp = np.linalg.norm(tip - mcp)
            # Reference distance (PIP to MCP)
            pip_to_mcp = np.linalg.norm(pip - mcp)
            
            # Fold ratio: 0 = fully extended, 1 = fully closed
            fold_ratio = max(0, min(1, 1 - (tip_to_mcp / (pip_to_mcp * 2.0)) if pip_to_mcp > 0 else 0))
            finger_folds.append(fold_ratio)
        
        return finger_folds
    
    def get_gestures(self):
        """
        Get current gesture data
        
        Returns:
            Dictionary with gesture information
        """
        with self.lock:
            return self.gestures.copy()
    
    def get_landmarks(self):
        """
        Get current hand landmarks
        
        Returns:
            List of landmark arrays
        """
        with self.lock:
            return self.landmarks.copy()


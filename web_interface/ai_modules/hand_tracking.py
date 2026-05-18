"""
LUNA Hand Tracking & Arm Pose Module
MediaPipe for Joint Gesture Mimicry & Full Arm Pose Tracking to Shoulder with GPU Acceleration Fallback
"""

import cv2
import numpy as np
import threading


class HandTracker:
    """
    MediaPipe Hand & Arm Pose Tracking for gesture mimicry and telemetry
    """
    
    def __init__(self, max_hands=1, min_detection_confidence=0.5, min_tracking_confidence=0.5):
        """
        Initialize MediaPipe hand & pose tracker
        
        Args:
            max_hands: Maximum number of hands to detect
            min_detection_confidence: Minimum confidence for detection
            min_tracking_confidence: Minimum confidence for tracking
        """
        self.max_hands = max_hands
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        
        # Initialize landmarks and gestures
        self.landmarks = []
        self.gestures = {}
        self.lock = threading.Lock()
        self.hands = None
        self.pose = None
        
        try:
            import mediapipe as mp
            self.mp_hands = mp.solutions.hands
            self.mp_pose = mp.solutions.pose
            self.mp_drawing = mp.solutions.drawing_utils
            
            # Initialize Hand Tracking with GPU acceleration fallback (Part 2.2)
            try:
                self.hands = self.mp_hands.Hands(
                    static_image_mode=False,
                    max_num_hands=max_hands,
                    min_detection_confidence=min_detection_confidence,
                    min_tracking_confidence=min_tracking_confidence,
                    model_complexity=2,
                    enable_gpu=True
                )
                print("🚀 MediaPipe Hands loaded with GPU acceleration delegates.")
            except Exception:
                self.hands = self.mp_hands.Hands(
                    static_image_mode=False,
                    max_num_hands=max_hands,
                    min_detection_confidence=min_detection_confidence,
                    min_tracking_confidence=min_tracking_confidence,
                    model_complexity=1
                )
                print("ℹ️ MediaPipe Hands running on standard CPU execution thread.")
            
            # Initialize Full Body Pose Solution (For Shoulder-to-Wrist tracking)
            self.pose = self.mp_pose.Pose(
                static_image_mode=False,
                model_complexity=1,
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence
            )
            print("✅ MediaPipe Hand & full-arm Pose Tracker initialized")
        except Exception as e:
            print(f"⚠️  MediaPipe initialization error: {e}")
            
    def _calculate_angle(self, p1, p2, p3):
        """
        Calculate the angle between p1-p2 and p3-p2 (where p2 is the vertex)
        """
        try:
            v1 = np.array(p1[:2]) - np.array(p2[:2])
            v2 = np.array(p3[:2]) - np.array(p2[:2])
            
            v1_norm = v1 / np.linalg.norm(v1)
            v2_norm = v2 / np.linalg.norm(v2)
            
            dot_product = np.dot(v1_norm, v2_norm)
            dot_product = np.clip(dot_product, -1.0, 1.0)
            angle_rad = np.arccos(dot_product)
            return float(np.degrees(angle_rad))
        except Exception:
            return 0.0
            
    def detect_handedness(self, landmarks):
        """
        Detect if the hand is left or right based on landmark orientation (Resolved H1)
        """
        if len(landmarks) < 21:
            return 'right'
        
        # Landmark 17 (Pinky MCP) x vs Landmark 2 (Thumb MCP) x
        if landmarks[17][0] > landmarks[2][0]:
            return 'right'
        return 'left'
    
    def process_frame(self, frame):
        """
        Process frame with MediaPipe Pose and Hands, rendering full arm-to-shoulder markings
        
        Args:
            frame: Input BGR frame
            
        Returns:
            Annotated frame with hand and arm landmarks
        """
        if self.hands is None:
            return frame
        
        try:
            # Convert BGR to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb_frame.flags.writeable = False
            
            # Process Pose and Hands
            pose_results = None
            if self.pose is not None:
                pose_results = self.pose.process(rgb_frame)
                
            results = self.hands.process(rgb_frame)
            
            # Convert back to BGR
            rgb_frame.flags.writeable = True
            annotated_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR)
            
            h, w, _ = frame.shape
            pose_points = {}
            arm_telemetry = {}
            
            # 1. Process & Draw Pose (Shoulder -> Elbow -> Wrist)
            if pose_results and pose_results.pose_landmarks:
                # Key landmarks: Left shoulder (11), Right shoulder (12), Left elbow (13), Right elbow (14), Left wrist (15), Right wrist (16)
                for idx in [11, 12, 13, 14, 15, 16]:
                    lm = pose_results.pose_landmarks.landmark[idx]
                    if lm.visibility > 0.5:
                        x = int(lm.x * w)
                        y = int(lm.y * h)
                        z = lm.z
                        pose_points[idx] = (x, y, z)
                
                # Render tracking lines up to the shoulder
                # Left Arm
                if 11 in pose_points and 13 in pose_points:
                    cv2.line(annotated_frame, pose_points[11][:2], pose_points[13][:2], (0, 255, 0), 3)
                    cv2.circle(annotated_frame, pose_points[11][:2], 6, (0, 0, 255), -1)
                    cv2.circle(annotated_frame, pose_points[13][:2], 6, (0, 0, 255), -1)
                if 13 in pose_points and 15 in pose_points:
                    cv2.line(annotated_frame, pose_points[13][:2], pose_points[15][:2], (0, 255, 0), 3)
                    cv2.circle(annotated_frame, pose_points[15][:2], 6, (0, 0, 255), -1)
                
                # Right Arm
                if 12 in pose_points and 14 in pose_points:
                    cv2.line(annotated_frame, pose_points[12][:2], pose_points[14][:2], (0, 255, 0), 3)
                    cv2.circle(annotated_frame, pose_points[12][:2], 6, (0, 0, 255), -1)
                    cv2.circle(annotated_frame, pose_points[14][:2], 6, (0, 0, 255), -1)
                if 14 in pose_points and 16 in pose_points:
                    cv2.line(annotated_frame, pose_points[14][:2], pose_points[16][:2], (0, 255, 0), 3)
                    cv2.circle(annotated_frame, pose_points[16][:2], 6, (0, 0, 255), -1)
                
                # Calculate flexion telemetry for both arms
                if 11 in pose_points and 13 in pose_points and 15 in pose_points:
                    elbow_angle = self._calculate_angle(pose_points[11], pose_points[13], pose_points[15])
                    shoulder_angle = self._calculate_angle(pose_points[13], pose_points[11], [pose_points[11][0], pose_points[11][1] + 100, 0])
                    arm_telemetry['left'] = {
                        'elbow_angle': round(elbow_angle, 1),
                        'shoulder_angle': round(shoulder_angle, 1)
                    }
                if 12 in pose_points and 14 in pose_points and 16 in pose_points:
                    elbow_angle = self._calculate_angle(pose_points[12], pose_points[14], pose_points[16])
                    shoulder_angle = self._calculate_angle(pose_points[14], pose_points[12], [pose_points[12][0], pose_points[12][1] + 100, 0])
                    arm_telemetry['right'] = {
                        'elbow_angle': round(elbow_angle, 1),
                        'shoulder_angle': round(shoulder_angle, 1)
                    }
            
            # 2. Process & Draw Hands
            landmarks = []
            gestures = {'arm_telemetry': arm_telemetry, 'handedness': 'right'}
            
            if results.multi_hand_landmarks:
                for h_idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                    # Draw landmarks on top of arm pose skeleton
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
                        x = int(landmark.x * w)
                        y = int(landmark.y * h)
                        z = landmark.z
                        hand_points.append([x, y, z])
                    
                    landmarks.append(hand_points)
                    
                    # Extract Handedness
                    handedness = 'right'
                    if results.multi_handedness:
                        handedness = results.multi_handedness[h_idx].classification[0].label.lower()
                    else:
                        handedness = self.detect_handedness(hand_points)
                    
                    gestures['handedness'] = handedness
                    
                    # Calculate finger fold ratios with normalized sizes
                    finger_folds = self._calculate_finger_folds(hand_points, handedness)
                    gestures['fingers'] = finger_folds
                    
                    # Connection visualizer: Draw wrist connection to detected pose elbow
                    if len(hand_points) > 0 and 13 in pose_points:
                        wrist_point = hand_points[0][:2]
                        left_dist = np.linalg.norm(np.array(wrist_point) - np.array(pose_points[13][:2]))
                        right_dist = np.linalg.norm(np.array(wrist_point) - np.array(pose_points[14][:2])) if 14 in pose_points else 9999
                        target_elbow = pose_points[13][:2] if left_dist < right_dist else pose_points[14][:2]
                        cv2.line(annotated_frame, wrist_point, target_elbow, (0, 255, 0), 3)
            
            # Update state
            with self.lock:
                self.landmarks = landmarks
                self.gestures = gestures
            
            return annotated_frame
            
        except Exception as e:
            print(f"⚠️  Hand/Pose tracking error: {e}")
            return frame
    
    def _calculate_finger_folds(self, landmarks, handedness='right'):
        """
        Calculate finger fold ratios (0 = open, 1 = closed) (Resolved H2 with normalization)
        """
        if len(landmarks) < 21:
            return [0.0, 0.0, 0.0, 0.0, 0.0]
        
        finger_folds = []
        
        # Calculate Hand Bounding Box Diagonal for dynamic normalization (H2)
        xs = [lm[0] for lm in landmarks]
        ys = [lm[1] for lm in landmarks]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        hand_diagonal = np.sqrt((max_x - min_x)**2 + (max_y - min_y)**2)
        if hand_diagonal == 0:
            hand_diagonal = 1.0
        
        # 1. Thumb fold (with handedness mirror compensation - H1)
        thumb_tip = np.array(landmarks[4][:2])
        thumb_mcp = np.array(landmarks[2][:2])
        thumb_dist = np.linalg.norm(thumb_tip - thumb_mcp)
        
        thumb_norm_dist = thumb_dist / hand_diagonal
        if handedness == 'left':
            # Mirror inverse mapping for left hand thumb fold logic
            thumb_fold = max(0.0, min(1.0, (thumb_norm_dist - 0.12) / 0.28))
        else:
            thumb_fold = max(0.0, min(1.0, 1.0 - (thumb_norm_dist - 0.12) / 0.28))
            
        finger_folds.append(thumb_fold)
        
        # 2. Other fingers (Index, Middle, Ring, Pinky)
        finger_indices = [
            (8, 5),   # Index Tip, Index MCP
            (12, 9),  # Middle Tip, Middle MCP
            (16, 13), # Ring Tip, Ring MCP
            (20, 17)  # Pinky Tip, Pinky MCP
        ]
        
        for tip_idx, mcp_idx in finger_indices:
            tip = np.array(landmarks[tip_idx][:2])
            mcp = np.array(landmarks[mcp_idx][:2])
            
            tip_to_mcp = np.linalg.norm(tip - mcp)
            norm_dist = tip_to_mcp / hand_diagonal
            
            # Map normalized distance to 0-1 fold ratio
            # Fully closed is typically ~0.15, fully open is ~0.48
            fold_ratio = max(0.0, min(1.0, 1.0 - (norm_dist - 0.15) / 0.33))
            finger_folds.append(fold_ratio)
        
        return finger_folds
    
    def get_gestures(self):
        """
        Get current gesture and arm pose telemetry
        """
        with self.lock:
            return self.gestures.copy()
    
    def get_landmarks(self):
        """
        Get current hand landmarks
        """
        with self.lock:
            return self.landmarks.copy()

"""
LUNA Gesture Recognition Module
Classifies hand gestures from 21 keypoints
"""

import numpy as np
import time
from collections import deque


class GestureClassifier:
    """
    Classify hand gestures from 21 keypoints
    """
    
    def __init__(self, threshold=0.15, wave_frames=10, wave_threshold=50):
        """
        Initialize gesture classifier
        
        Args:
            threshold: Distance ratio for extended finger
            wave_frames: Number of frames to detect wave
            wave_threshold: Pixels of horizontal movement for wave
        """
        self.threshold = threshold
        self.wave_frames = wave_frames
        self.wave_threshold = wave_threshold
        
        # Store recent wrist positions for wave detection
        self.wrist_history = deque(maxlen=self.wave_frames)
        
        # Cache for gesture smoothing
        self.gesture_history = deque(maxlen=5)
        self.last_gesture = 'unknown'
        self.gesture_confidence = 0.0
    
    def classify(self, hand_data):
        """
        Classify gesture from hand keypoints
        
        Args:
            hand_data: Dictionary with 'keypoints' list
            
        Returns:
            gesture_name, confidence
        """
        if not hand_data or 'keypoints' not in hand_data:
            return 'unknown', 0.0
        
        keypoints = hand_data['keypoints']
        
        # Extract visible keypoints with coordinates
        points = []
        for kp in keypoints:
            if kp['visible']:
                points.append([kp['x'], kp['y']])
            else:
                points.append([0, 0])
        
        if len(points) < 21:
            return 'unknown', 0.0
        
        points = np.array(points)
        
        # Detect gestures
        gestures = {}
        
        # Check each gesture
        gestures['open_palm'] = self._is_open_palm(points)
        gestures['closed_fist'] = self._is_closed_fist(points)
        gestures['pointing'] = self._is_pointing(points)
        gestures['peace'] = self._is_peace_sign(points)
        gestures['thumbs_up'] = self._is_thumbs_up(points)
        gestures['wave'] = self._is_wave(hand_data)
        
        # Find gesture with highest confidence
        best_gesture = 'unknown'
        best_confidence = 0.0
        
        for gesture, confidence in gestures.items():
            if confidence > best_confidence:
                best_confidence = confidence
                best_gesture = gesture
        
        # Smooth with history
        if best_confidence > 0.6:
            self.gesture_history.append(best_gesture)
        
        if len(self.gesture_history) > 0:
            # Return most common gesture in history
            from collections import Counter
            counter = Counter(self.gesture_history)
            smoothed_gesture = counter.most_common(1)[0][0]
            self.gesture_confidence = best_confidence
            self.last_gesture = smoothed_gesture
            return smoothed_gesture, best_confidence
        
        return best_gesture, best_confidence
    
    def _is_open_palm(self, points):
        """Check if hand is open palm (all fingers extended)"""
        finger_tips = [4, 8, 12, 16, 20]   # Tip indices
        finger_mcps = [1, 5, 9, 13, 17]    # Base indices
        
        extended_count = 0
        total_confidence = 0
        
        for tip, mcp in zip(finger_tips, finger_mcps):
            if np.array_equal(points[tip], [0, 0]) or np.array_equal(points[mcp], [0, 0]):
                continue
            
            # Distance from tip to MCP
            distance = np.linalg.norm(points[tip] - points[mcp])
            # Reference distance (wrist to MCP for scale)
            wrist_to_mcp = np.linalg.norm(points[mcp] - points[0]) if not np.array_equal(points[0], [0, 0]) else 100
            
            if wrist_to_mcp > 0:
                ratio = distance / wrist_to_mcp
                if ratio > self.threshold:
                    extended_count += 1
                    total_confidence += min(1.0, ratio * 2)
        
        if extended_count >= 4:
            return total_confidence / 5.0
        return 0.0
    
    def _is_closed_fist(self, points):
        """Check if hand is closed fist (all fingers curled)"""
        finger_tips = [4, 8, 12, 16, 20]
        finger_mcps = [1, 5, 9, 13, 17]
        
        curled_count = 0
        total_confidence = 0
        
        for tip, mcp in zip(finger_tips, finger_mcps):
            if np.array_equal(points[tip], [0, 0]) or np.array_equal(points[mcp], [0, 0]):
                continue
            
            distance = np.linalg.norm(points[tip] - points[mcp])
            wrist_to_mcp = np.linalg.norm(points[mcp] - points[0]) if not np.array_equal(points[0], [0, 0]) else 100
            
            if wrist_to_mcp > 0:
                ratio = distance / wrist_to_mcp
                if ratio < self.threshold * 0.7:
                    curled_count += 1
                    total_confidence += min(1.0, (1 - ratio) * 2)
        
        if curled_count >= 4:
            return total_confidence / 5.0
        return 0.0
    
    def _is_pointing(self, points):
        """Check if index finger extended, others curled"""
        if np.array_equal(points[8], [0, 0]):  # Index tip invisible
            return 0.0
        
        # Check index extended
        index_tip = points[8]
        index_mcp = points[5]
        index_dist = np.linalg.norm(index_tip - index_mcp)
        
        # Check others curled
        other_fingers = [(12, 9), (16, 13), (20, 17)]  # (tip, mcp) for middle, ring, pinky
        others_curled = 0
        
        for tip_idx, mcp_idx in other_fingers:
            if np.array_equal(points[tip_idx], [0, 0]) or np.array_equal(points[mcp_idx], [0, 0]):
                continue
            dist = np.linalg.norm(points[tip_idx] - points[mcp_idx])
            wrist_to_mcp = np.linalg.norm(points[mcp_idx] - points[0])
            if wrist_to_mcp > 0 and (dist / wrist_to_mcp) < self.threshold:
                others_curled += 1
        
        if others_curled >= 2:  # At least two other fingers curled
            return 0.8
        return 0.0
    
    def _is_peace_sign(self, points):
        """Check for peace sign (index and middle extended)"""
        if np.array_equal(points[8], [0, 0]) or np.array_equal(points[12], [0, 0]):
            return 0.0
        
        # Check index and middle extended
        index_tip = points[8]
        index_mcp = points[5]
        middle_tip = points[12]
        middle_mcp = points[9]
        
        index_dist = np.linalg.norm(index_tip - index_mcp)
        middle_dist = np.linalg.norm(middle_tip - middle_mcp)
        
        wrist_to_index = np.linalg.norm(points[5] - points[0])
        wrist_to_middle = np.linalg.norm(points[9] - points[0])
        
        if wrist_to_index == 0 or wrist_to_middle == 0:
            return 0.0
        
        index_ratio = index_dist / wrist_to_index
        middle_ratio = middle_dist / wrist_to_middle
        
        # Check ring and pinky curled
        ring_curled = True
        pinky_curled = True
        
        if not np.array_equal(points[16], [0, 0]):
            ring_dist = np.linalg.norm(points[16] - points[13])
            ring_ratio = ring_dist / wrist_to_middle if wrist_to_middle > 0 else 1
            ring_curled = ring_ratio < self.threshold
        
        if not np.array_equal(points[20], [0, 0]):
            pinky_dist = np.linalg.norm(points[20] - points[17])
            pinky_ratio = pinky_dist / wrist_to_middle if wrist_to_middle > 0 else 1
            pinky_curled = pinky_ratio < self.threshold
        
        if (index_ratio > self.threshold and 
            middle_ratio > self.threshold and 
            ring_curled and pinky_curled):
            return 0.9
        return 0.0
    
    def _is_thumbs_up(self, points):
        """Check for thumbs up gesture"""
        if np.array_equal(points[4], [0, 0]):  # Thumb tip
            return 0.0
        
        # Thumb should be up (higher y than wrist)
        thumb_tip = points[4]
        wrist = points[0]
        
        if np.array_equal(wrist, [0, 0]):
            return 0.0
        
        # Check if thumb is above wrist (lower y value in image coordinates)
        thumb_above = thumb_tip[1] < wrist[1] - 20
        
        # All other fingers should be curled
        other_fingers = [8, 12, 16, 20]  # Tips
        others_curled = 0
        
        for tip_idx in other_fingers:
            if np.array_equal(points[tip_idx], [0, 0]):
                continue
            # Check if curled (tip close to palm)
            mcp_idx = tip_idx - 3  # Approximate MCP
            if mcp_idx < 5:
                mcp_idx = 5
            dist = np.linalg.norm(points[tip_idx] - points[mcp_idx])
            wrist_to_mcp = np.linalg.norm(points[mcp_idx] - wrist)
            if wrist_to_mcp > 0 and (dist / wrist_to_mcp) < self.threshold:
                others_curled += 1
        
        if thumb_above and others_curled >= 3:
            return 0.85
        return 0.0
    
    def _is_wave(self, hand_data):
        """Detect waving motion (horizontal movement)"""
        wrist = None
        for kp in hand_data['keypoints']:
            if kp['visible']:
                wrist = (kp['x'], kp['y'])
                break
        
        if not wrist:
            return 0.0
        
        self.wrist_history.append(wrist)
        
        if len(self.wrist_history) < self.wave_frames:
            return 0.0
        
        # Calculate horizontal movement
        x_positions = [pos[0] for pos in self.wrist_history]
        x_min = min(x_positions)
        x_max = max(x_positions)
        x_range = x_max - x_min
        
        # Check for oscillation (wave pattern)
        if x_range > self.wave_threshold:
            # Count direction changes
            changes = 0
            for i in range(1, len(x_positions)):
                if i > 1 and ((x_positions[i-1] - x_positions[i-2]) *
                               (x_positions[i] - x_positions[i-1]) < 0):
                    changes += 1
            
            if changes >= 3:  # Multiple direction changes
                return min(1.0, x_range / (self.wave_threshold * 2))
        
        return 0.0
    
    def get_command_from_gesture(self, gesture):
        """
        Map gesture to robot command
        
        Args:
            gesture: Gesture name
            
        Returns:
            Command dictionary
        """
        gesture_commands = {
            'open_palm': {'hand': {5:0, 6:0, 7:0, 8:0, 9:0}},
            'closed_fist': {'hand': {5:180, 6:180, 7:180, 8:180, 9:180}},
            'pointing': {'motor': {2: 90}},
            'peace': {'motor': {4: 45}},
            'thumbs_up': {'system': 'home_position'},
            'wave': {'system': 'emergency_stop'}
        }
        return gesture_commands.get(gesture, {})

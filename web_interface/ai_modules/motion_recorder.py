"""
LUNA Motion Recording Module
Records and plays back motor sequences, supporting local gesture Teach-by-Demonstration modes.
"""

import json
import time
from datetime import datetime
from typing import List, Dict, Optional
import os


def operator_to_robot(pose: Dict) -> Dict[int, int]:
    """
    Inverse mapping function translating operator's joint angles into LUNA motor commands (Resolved Feature 3.2)
    
    Args:
        pose: Dict containing 'elbow_angle', 'shoulder_angle', and 'fingers' fold list.
        
    Returns:
        Dict of motor IDs mapped to target angles.
    """
    motor_commands = {i: 90 for i in range(2, 10)}
    
    # 1. Fingers (1:1 mapping from 0.0-1.0 folds to 0-180 degree angles)
    fingers = pose.get('fingers', [0.0] * 5)
    for idx, fold in enumerate(fingers[:5]):
        motor_commands[5 + idx] = int(fold * 180)
        
    # 2. Elbow flexion maps to primary pivot Elbow (ID 2)
    elbow = pose.get('elbow_angle', 90.0)
    motor_commands[2] = int(max(0, min(180, elbow)))
    
    # 3. Average elbow and shoulder data determines Wrist Pitch (ID 3)
    shoulder = pose.get('shoulder_angle', 90.0)
    wrist_pitch = (elbow + shoulder) / 2.0
    motor_commands[3] = int(max(0, min(180, wrist_pitch)))
    
    return motor_commands


class MotionRecorder:
    """
    Records motor positions and operator telemetry over time for demonstration playbacks.
    """
    
    def __init__(self, recordings_dir: str = 'recordings', teachings_dir: str = 'teachings'):
        """
        Initialize motion recorder.
        
        Args:
            recordings_dir: Directory to store basic motor playbacks
            teachings_dir: Directory to save operator demonstration runs
        """
        self.is_recording = False
        self.recorded_sequence: List[Dict] = []
        self.start_time: Optional[float] = None
        self.recordings_dir = recordings_dir
        self.teachings_dir = teachings_dir
        self.teach_mode = False
        
        # Create directories
        for d in [self.recordings_dir, self.teachings_dir]:
            if not os.path.exists(d):
                os.makedirs(d)
                print(f"✅ Created system directory: {d}")
    
    def start_recording(self, teach_mode: bool = False) -> None:
        """Start recording motor/operator positions"""
        self.is_recording = True
        self.teach_mode = teach_mode
        self.recorded_sequence = []
        self.start_time = time.time()
        print(f"[RECORDER] Recording started (Teach Mode: {teach_mode})")
    
    def record_frame(self, motor_state: Dict[int, int]) -> None:
        """
        Record standard motor positions.
        """
        if self.is_recording and not self.teach_mode and self.start_time is not None:
            timestamp = time.time() - self.start_time
            self.recorded_sequence.append({
                'timestamp': timestamp,
                'motors': motor_state.copy()
            })

    def record_teach_frame(self, operator_pose: Dict, robot_state: Dict[int, int]) -> None:
        """
        Record frame under Teach Mode (Resolved 3.2)
        """
        if self.is_recording and self.teach_mode and self.start_time is not None:
            timestamp = time.time() - self.start_time
            self.recorded_sequence.append({
                'timestamp': timestamp,
                'operator_pose': operator_pose.copy(),
                'robot_state': robot_state.copy()
            })
    
    def stop_recording(self) -> List[Dict]:
        """
        Stop recording and return sequence.
        """
        self.is_recording = False
        print(f"[RECORDER] stopped. {len(self.recorded_sequence)} frames captured")
        return self.recorded_sequence
    
    def save_sequence(self, name: str, filename: Optional[str] = None) -> str:
        """
        Save recorded sequence to file.
        """
        if filename is None:
            filename = f"{name.replace(' ', '_')}_{int(time.time())}"
        
        target_dir = self.teachings_dir if self.teach_mode else self.recordings_dir
        filepath = os.path.join(target_dir, f"{filename}.json")
        
        data = {
            'name': name,
            'created': datetime.now().isoformat(),
            'duration': self.recorded_sequence[-1]['timestamp'] if self.recorded_sequence else 0,
            'frames': len(self.recorded_sequence),
            'teach_mode': self.teach_mode,
            'sequence': self.recorded_sequence
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"[RECORDER] Sequence saved: {filepath}")
        return filepath
    
    def load_sequence(self, filename: str, is_teach: bool = False) -> Dict:
        """
        Load sequence from file.
        """
        if not filename.endswith('.json'):
            filename += '.json'
        
        target_dir = self.teachings_dir if is_teach else self.recordings_dir
        filepath = os.path.join(target_dir, filename)
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        print(f"[RECORDER] Sequence loaded: {data['name']} ({data['frames']} frames)")
        return data
    
    def list_recordings(self) -> List[Dict[str, str]]:
        """List all recordings"""
        recordings = []
        if not os.path.exists(self.recordings_dir):
            return recordings
        
        for filename in os.listdir(self.recordings_dir):
            if filename.endswith('.json'):
                try:
                    filepath = os.path.join(self.recordings_dir, filename)
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                    
                    recordings.append({
                        'filename': filename,
                        'name': data.get('name', 'Unknown'),
                        'created': data.get('created', 'Unknown'),
                        'duration': data.get('duration', 0),
                        'frames': data.get('frames', 0),
                        'teach_mode': data.get('teach_mode', False)
                    })
                except Exception as e:
                    print(f"[WARN] Could not load {filename}: {e}")
        
        return sorted(recordings, key=lambda x: x['created'], reverse=True)

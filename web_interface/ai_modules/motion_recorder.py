"""
LUNA Motion Recording Module
Records and plays back motor sequences
"""

import json
import time
from datetime import datetime
from typing import List, Dict, Optional
import os


class MotionRecorder:
    """
    Records motor positions over time and plays them back.
    Useful for teaching the robot complex movements.
    """
    
    def __init__(self, recordings_dir: str = 'recordings'):
        """
        Initialize motion recorder.
        
        Args:
            recordings_dir: Directory to store recordings
        """
        self.is_recording = False
        self.recorded_sequence: List[Dict] = []
        self.start_time: Optional[float] = None
        self.recordings_dir = recordings_dir
        
        # Create recordings directory if it doesn't exist
        if not os.path.exists(recordings_dir):
            os.makedirs(recordings_dir)
            print(f"✅ Created recordings directory: {recordings_dir}")
    
    def start_recording(self) -> None:
        """Start recording motor positions"""
        self.is_recording = True
        self.recorded_sequence = []
        self.start_time = time.time()
        print("[RECORDER] Recording started")
    
    def record_frame(self, motor_state: Dict[int, int]) -> None:
        """
        Record current motor positions.
        
        Args:
            motor_state: Dictionary of motor IDs to angles
        """
        if self.is_recording and self.start_time is not None:
            timestamp = time.time() - self.start_time
            self.recorded_sequence.append({
                'timestamp': timestamp,
                'motors': motor_state.copy()
            })
    
    def stop_recording(self) -> List[Dict]:
        """
        Stop recording and return the sequence.
        
        Returns:
            List of recorded frames
        """
        self.is_recording = False
        print(f"[RECORDER] Recording stopped. {len(self.recorded_sequence)} frames captured")
        return self.recorded_sequence
    
    def save_sequence(self, name: str, filename: Optional[str] = None) -> str:
        """
        Save recorded sequence to file.
        
        Args:
            name: Human-readable name for the sequence
            filename: Optional custom filename (without extension)
        
        Returns:
            Path to saved file
        """
        if filename is None:
            filename = f"{name.replace(' ', '_')}_{int(time.time())}"
        
        filepath = os.path.join(self.recordings_dir, f"{filename}.json")
        
        data = {
            'name': name,
            'created': datetime.now().isoformat(),
            'duration': self.recorded_sequence[-1]['timestamp'] if self.recorded_sequence else 0,
            'frames': len(self.recorded_sequence),
            'sequence': self.recorded_sequence
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"[RECORDER] Sequence saved: {filepath}")
        return filepath
    
    def load_sequence(self, filename: str) -> Dict:
        """
        Load a recorded sequence from file.
        
        Args:
            filename: Name of file to load (with or without .json extension)
        
        Returns:
            Dictionary with sequence data
        """
        if not filename.endswith('.json'):
            filename += '.json'
        
        filepath = os.path.join(self.recordings_dir, filename)
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        print(f"[RECORDER] Sequence loaded: {data['name']} ({data['frames']} frames)")
        return data
    
    def list_recordings(self) -> List[Dict[str, str]]:
        """
        List all available recordings.
        
        Returns:
            List of recording metadata
        """
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
                        'frames': data.get('frames', 0)
                    })
                except Exception as e:
                    print(f"[WARN] Could not load {filename}: {e}")
        
        return sorted(recordings, key=lambda x: x['created'], reverse=True)
    
    def delete_recording(self, filename: str) -> bool:
        """
        Delete a recording file.
        
        Args:
            filename: Name of file to delete
        
        Returns:
            True if deleted successfully
        """
        if not filename.endswith('.json'):
            filename += '.json'
        
        filepath = os.path.join(self.recordings_dir, filename)
        
        try:
            os.remove(filepath)
            print(f"[RECORDER] Deleted: {filename}")
            return True
        except Exception as e:
            print(f"[ERROR] Could not delete {filename}: {e}")
            return False


if __name__ == '__main__':
    # Test the recorder
    print("\n--- MOTION RECORDER TEST ---")
    
    recorder = MotionRecorder()
    
    # Simulate recording
    recorder.start_recording()
    
    # Simulate some motor movements
    for i in range(10):
        motors = {
            2: 90 + i * 5,
            3: 90,
            4: 90 - i * 3,
            5: i * 10,
            6: i * 10,
            7: i * 10,
            8: i * 10,
            9: i * 10
        }
        recorder.record_frame(motors)
        time.sleep(0.1)
    
    # Stop and save
    sequence = recorder.stop_recording()
    print(f"Recorded {len(sequence)} frames")
    
    filepath = recorder.save_sequence("Test Sequence", "test_recording")
    print(f"Saved to: {filepath}")
    
    # Load it back
    loaded = recorder.load_sequence("test_recording")
    print(f"Loaded: {loaded['name']}")
    print(f"Duration: {loaded['duration']:.2f}s")
    
    # List all recordings
    recordings = recorder.list_recordings()
    print(f"\nAvailable recordings: {len(recordings)}")
    for rec in recordings:
        print(f"  - {rec['name']} ({rec['frames']} frames, {rec['duration']:.2f}s)")

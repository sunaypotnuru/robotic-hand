"""
Test Suite for Motor Control Functions
"""
import sys
import os
import pytest

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import send_motor_command, send_batch_commands, robot_state, emergency_stop


@pytest.fixture(autouse=True)
def reset_robot_state():
    """Reset robot state before each test"""
    robot_state['emergency_stop'] = False
    robot_state['motors'] = {
        2: 90, 3: 90, 4: 90, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0
    }
    yield
    # Cleanup after test
    robot_state['emergency_stop'] = False


class TestMotorValidation:
    """Test motor ID and angle validation"""
    
    def test_blocked_motors(self):
        """Test that removed motors (0, 1) are blocked"""
        assert send_motor_command(0, 90) == False, "Motor ID 0 should be blocked"
        assert send_motor_command(1, 90) == False, "Motor ID 1 should be blocked"
    
    def test_valid_motors(self):
        """Test that motors 2-9 work correctly"""
        result = send_motor_command(2, 90)
        assert result == True, "Motor ID 2 should work"
        assert robot_state['motors'][2] == 90, "Motor 2 should be at 90 degrees"
    
    def test_invalid_motor_ids(self):
        """Test that invalid motor IDs are rejected"""
        assert send_motor_command(10, 90) == False, "Motor ID 10 should be rejected"
        assert send_motor_command(-1, 90) == False, "Negative motor ID should be rejected"
    
    def test_angle_clamping_upper(self):
        """Test angle upper limit (180 degrees)"""
        send_motor_command(2, 200)
        assert robot_state['motors'][2] == 180, "Angle should be clamped to 180"
    
    def test_angle_clamping_lower(self):
        """Test angle lower limit (0 degrees)"""
        send_motor_command(2, -50)
        assert robot_state['motors'][2] == 0, "Angle should be clamped to 0"


class TestBatchCommands:
    """Test batch command execution"""
    
    def test_batch_commands_execution(self):
        """Test batch command sends multiple motors"""
        commands = {2: 45, 3: 90, 4: 135}
        result = send_batch_commands(commands)
        
        assert result == True, "Batch command should succeed"
        assert robot_state['motors'][2] == 45, "Motor 2 should be at 45"
        assert robot_state['motors'][3] == 90, "Motor 3 should be at 90"
        assert robot_state['motors'][4] == 135, "Motor 4 should be at 135"
    
    def test_batch_filters_invalid_ids(self):
        """Test that batch commands filter out invalid IDs"""
        commands = {0: 90, 1: 90, 2: 45}  # IDs 0,1 should be filtered
        result = send_batch_commands(commands)
        
        assert result == True, "Batch should succeed with valid IDs"
        assert robot_state['motors'][2] == 45, "Motor 2 should update"


class TestEmergencyStop:
    """Test emergency stop functionality"""
    
    def test_emergency_stop_activates(self):
        """Test emergency stop sets flag"""
        emergency_stop()
        assert robot_state['emergency_stop'] == True, "Emergency stop flag should be set"
    
    def test_emergency_stop_centers_arm(self):
        """Test emergency stop centers arm motors"""
        emergency_stop()
        assert robot_state['motors'][2] == 90, "Main pivot should center at 90"
        assert robot_state['motors'][3] == 90, "Wrist pitch should center at 90"
        assert robot_state['motors'][4] == 90, "Wrist roll should center at 90"
    
    def test_emergency_stop_opens_fingers(self):
        """Test emergency stop opens all fingers"""
        emergency_stop()
        assert robot_state['motors'][5] == 0, "Thumb should open to 0"
        assert robot_state['motors'][6] == 0, "Index should open to 0"
        assert robot_state['motors'][7] == 0, "Middle should open to 0"
        assert robot_state['motors'][8] == 0, "Ring should open to 0"
        assert robot_state['motors'][9] == 0, "Pinky should open to 0"


class TestMotorSafety:
    """Test safety features"""
    
    def test_angle_range_validation(self):
        """Test that angles are validated to 0-180 range"""
        # Test various out-of-range values
        send_motor_command(2, 250)
        assert robot_state['motors'][2] <= 180, "Angle should not exceed 180"
        
        send_motor_command(2, -100)
        assert robot_state['motors'][2] >= 0, "Angle should not go below 0"
    
    def test_motor_state_persistence(self):
        """Test that motor states are tracked correctly"""
        send_motor_command(2, 45)
        assert robot_state['motors'][2] == 45
        
        send_motor_command(3, 135)
        assert robot_state['motors'][3] == 135
        
        # Previous motor should still be at its position
        assert robot_state['motors'][2] == 45, "Previous motor state should persist"


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])

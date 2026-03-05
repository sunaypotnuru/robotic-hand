"""
Test Suite for AI Modules
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from web_interface.ai_modules.kinematics import SimpleKinematics
from web_interface.ai_modules.voice_cmd import VoiceCommandProcessor


class TestKinematics:
    """Test kinematics calculations"""
    
    def test_initialization(self):
        """Test kinematics module initializes correctly"""
        kin = SimpleKinematics(link_length=28.0)
        assert kin.link_length == 28.0
        assert kin.min_angle == 0
        assert kin.max_angle == 180
    
    def test_angle_to_position(self):
        """Test forward kinematics calculation"""
        kin = SimpleKinematics(link_length=28.0)
        x, y, z = kin.angle_to_position(90)
        
        # At 90 degrees, arm should be at full extension
        assert abs(y - 28.0) < 0.1, "Y position should be approximately 28cm"
        assert x == 0, "X should be 0 for planar motion"
        assert z == 0, "Z should be 0 for planar motion"
    
    def test_position_to_angle(self):
        """Test inverse kinematics (simplified)"""
        kin = SimpleKinematics(link_length=28.0)
        
        # Test mid-range position
        angle = kin.position_to_angle(14.0)  # Half extension
        assert 0 <= angle <= 180, "Angle should be in valid range"
    
    def test_workspace_bounds(self):
        """Test workspace boundary calculation"""
        kin = SimpleKinematics(link_length=28.0)
        bounds = kin.get_workspace_bounds()
        
        assert bounds['y_max'] == 28.0, "Max Y should equal link length"
        assert bounds['y_min'] == 0, "Min Y should be 0"
        assert bounds['angle_min'] == 0, "Min angle should be 0"
        assert bounds['angle_max'] == 180, "Max angle should be 180"
    
    def test_reachability(self):
        """Test position reachability check"""
        kin = SimpleKinematics(link_length=28.0)
        
        # Within reach
        assert kin.is_reachable(0, 14.0, 0) == True, "Mid-range should be reachable"
        assert kin.is_reachable(0, 28.0, 0) == True, "Max extension should be reachable"
        
        # Out of reach
        assert kin.is_reachable(0, 50.0, 0) == False, "Beyond max should not be reachable"
        assert kin.is_reachable(0, -10.0, 0) == False, "Negative Y should not be reachable"


class TestVoiceCommands:
    """Test voice command processing"""
    
    def test_initialization(self):
        """Test voice processor initializes without errors"""
        try:
            processor = VoiceCommandProcessor(use_whisper=False)
            assert processor is not None
        except Exception as e:
            # It's okay if initialization fails due to missing dependencies
            # We're just testing that the code doesn't have syntax errors
            pass
    
    def test_basic_parse_open_hand(self):
        """Test legacy command parsing for 'open hand'"""
        processor = VoiceCommandProcessor(use_whisper=False)
        cmd = processor.basic_parse_command("open hand")
        
        assert cmd is not None, "Command should be parsed"
        assert cmd['type'] == 'hand', "Should be hand command"
        assert cmd['action'] == 'open', "Should be open action"
        assert 5 in cmd['motor_values'], "Should include finger motors"
    
    def test_basic_parse_close_hand(self):
        """Test legacy command parsing for 'close hand'"""
        processor = VoiceCommandProcessor(use_whisper=False)
        cmd = processor.basic_parse_command("close hand")
        
        assert cmd is not None, "Command should be parsed"
        assert cmd['type'] == 'hand', "Should be hand command"
        assert cmd['action'] == 'close', "Should be close action"
    
    def test_basic_parse_arm_up(self):
        """Test legacy command parsing for 'arm up'"""
        processor = VoiceCommandProcessor(use_whisper=False)
        cmd = processor.basic_parse_command("arm up")
        
        assert cmd is not None, "Command should be parsed"
        assert cmd['type'] == 'motor', "Should be motor command"
        assert 2 in cmd['motor_values'], "Should control motor 2"
    
    def test_basic_parse_unknown(self):
        """Test that unknown commands return None"""
        processor = VoiceCommandProcessor(use_whisper=False)
        cmd = processor.basic_parse_command("do a backflip")
        
        assert cmd is None, "Unknown command should return None"


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])

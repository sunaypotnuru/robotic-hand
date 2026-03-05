"""
Input Validation Utilities for LUNA Robotic Arm
Validates user input to prevent errors and security issues
"""

from typing import Dict, Any, List
from flask import abort
import re


class InputValidator:
    """
    Centralized input validation for all user inputs.
    Prevents invalid commands and potential security issues.
    """
    
    # Valid motor ID range (IDs 0-1 are removed)
    VALID_MOTOR_IDS = list(range(2, 10))  # [2, 3, 4, 5, 6, 7, 8, 9]
    MIN_ANGLE = 0
    MAX_ANGLE = 180
    
    @staticmethod
    def validate_motor_command(data: Dict[str, Any]) -> bool:
        """
        Validate single motor command input.
        
        Args:
            data: Dictionary with 'motor_id' and 'angle' keys
        
        Returns:
            True if valid
        
        Raises:
            400 error if invalid
        """
        # Check required fields
        if 'motor_id' not in data:
            abort(400, description="Missing required field: motor_id")
        if 'angle' not in data:
            abort(400, description="Missing required field: angle")
        
        # Type validation
        try:
            motor_id = int(data['motor_id'])
            angle = float(data['angle'])
        except (ValueError, TypeError) as e:
            abort(400, description=f"Invalid data types: {str(e)}")
        
        # Range validation
        if motor_id not in InputValidator.VALID_MOTOR_IDS:
            abort(400, description=f"Invalid motor_id: {motor_id}. Must be in range 2-9")
        
        if angle < InputValidator.MIN_ANGLE or angle > InputValidator.MAX_ANGLE:
            abort(400, description=f"Invalid angle: {angle}. Must be between 0-180")
        
        return True
    
    @staticmethod
    def validate_batch_command(data: Dict[str, Any]) -> bool:
        """
        Validate batch motor command input.
        
        Args:
            data: Dictionary with 'commands' key containing motor_id: angle pairs
        
        Returns:
            True if valid
        
        Raises:
            400 error if invalid
        """
        # Check required field
        if 'commands' not in data:
            abort(400, description="Missing required field: commands")
        
        commands = data['commands']
        
        # Type validation
        if not isinstance(commands, dict):
            abort(400, description="Commands must be a dictionary")
        
        if len(commands) == 0:
            abort(400, description="Commands dictionary cannot be empty")
        
        if len(commands) > 8:
            abort(400, description="Too many commands. Maximum is 8 motors")
        
        # Validate each command
        for motor_id, angle in commands.items():
            try:
                motor_id = int(motor_id)
                angle = float(angle)
            except (ValueError, TypeError):
                abort(400, description=f"Invalid command format: {motor_id}:{angle}")
            
            if motor_id not in InputValidator.VALID_MOTOR_IDS:
                abort(400, description=f"Invalid motor_id in batch: {motor_id}")
            
            if angle < InputValidator.MIN_ANGLE or angle > InputValidator.MAX_ANGLE:
                abort(400, description=f"Invalid angle in batch: {angle}")
        
        return True
    
    @staticmethod
    def validate_recording_name(name: str) -> bool:
        """
        Validate recording name for file safety.
        
        Args:
            name: Recording name
        
        Returns:
            True if valid
        
        Raises:
            400 error if invalid
        """
        if not name or len(name) == 0:
            abort(400, description="Recording name cannot be empty")
        
        if len(name) > 100:
            abort(400, description="Recording name too long (max 100 characters)")
        
        # Check for invalid characters (prevent directory traversal)
        if not re.match(r'^[a-zA-Z0-9_\- ]+$', name):
            abort(400, description="Recording name contains invalid characters. Use only letters, numbers, spaces, hyphens, and underscores")
        
        # Prevent directory traversal
        if '..' in name or '/' in name or '\\' in name:
            abort(400, description="Recording name cannot contain path separators")
        
        return True
    
    @staticmethod
    def validate_filename(filename: str) -> bool:
        """
        Validate filename for loading/deleting recordings.
        
        Args:
            filename: Filename to validate
        
        Returns:
            True if valid
        
        Raises:
            400 error if invalid
        """
        if not filename or len(filename) == 0:
            abort(400, description="Filename cannot be empty")
        
        # Remove .json extension if present for validation
        name = filename.replace('.json', '')
        
        # Check for invalid characters
        if not re.match(r'^[a-zA-Z0-9_\-]+$', name):
            abort(400, description="Filename contains invalid characters")
        
        # Prevent directory traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            abort(400, description="Filename cannot contain path separators")
        
        return True
    
    @staticmethod
    def sanitize_string(text: str, max_length: int = 1000) -> str:
        """
        Sanitize user input string.
        
        Args:
            text: Input string
            max_length: Maximum allowed length
        
        Returns:
            Sanitized string
        """
        if not text:
            return ""
        
        # Trim to max length
        text = text[:max_length]
        
        # Remove null bytes
        text = text.replace('\x00', '')
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text
    
    @staticmethod
    def validate_joystick_input(data: Dict[str, Any]) -> bool:
        """
        Validate joystick input data.
        
        Args:
            data: Dictionary with 'x' and 'y' keys
        
        Returns:
            True if valid
        
        Raises:
            400 error if invalid
        """
        if 'x' not in data or 'y' not in data:
            abort(400, description="Missing joystick coordinates")
        
        try:
            x = float(data['x'])
            y = float(data['y'])
        except (ValueError, TypeError):
            abort(400, description="Invalid joystick coordinates")
        
        # Joystick values should be -1.0 to 1.0
        if abs(x) > 1.0 or abs(y) > 1.0:
            abort(400, description="Joystick values must be between -1.0 and 1.0")
        
        return True
    
    @staticmethod
    def validate_gamepad_input(data: Dict[str, Any]) -> bool:
        """
        Validate gamepad input data.
        
        Args:
            data: Dictionary with gamepad axis values
        
        Returns:
            True if valid
        
        Raises:
            400 error if invalid
        """
        required_fields = ['left_stick_y', 'right_stick_y', 'right_stick_x', 
                          'left_trigger', 'right_trigger']
        
        for field in required_fields:
            if field not in data:
                abort(400, description=f"Missing gamepad field: {field}")
            
            try:
                value = float(data[field])
            except (ValueError, TypeError):
                abort(400, description=f"Invalid gamepad value for {field}")
            
            # Stick values: -1.0 to 1.0, Trigger values: 0.0 to 1.0
            if 'trigger' in field:
                if value < 0.0 or value > 1.0:
                    abort(400, description=f"Trigger value must be 0.0-1.0: {field}")
            else:
                if abs(value) > 1.0:
                    abort(400, description=f"Stick value must be -1.0 to 1.0: {field}")
        
        return True


if __name__ == '__main__':
    # Test the validators
    print("\n--- INPUT VALIDATOR TESTS ---\n")
    
    # Test motor command validation
    print("1. Valid motor command:")
    try:
        InputValidator.validate_motor_command({'motor_id': 2, 'angle': 90})
        print("   ✅ PASS")
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
    
    print("\n2. Invalid motor ID:")
    try:
        InputValidator.validate_motor_command({'motor_id': 0, 'angle': 90})
        print("   ❌ FAIL: Should have raised error")
    except Exception as e:
        print(f"   ✅ PASS: Caught error - {e}")
    
    print("\n3. Invalid angle:")
    try:
        InputValidator.validate_motor_command({'motor_id': 2, 'angle': 200})
        print("   ❌ FAIL: Should have raised error")
    except Exception as e:
        print(f"   ✅ PASS: Caught error - {e}")
    
    print("\n4. Valid batch command:")
    try:
        InputValidator.validate_batch_command({'commands': {2: 90, 3: 45}})
        print("   ✅ PASS")
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
    
    print("\n5. Valid recording name:")
    try:
        InputValidator.validate_recording_name("My Test Sequence")
        print("   ✅ PASS")
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
    
    print("\n6. Invalid recording name (path traversal):")
    try:
        InputValidator.validate_recording_name("../../../etc/passwd")
        print("   ❌ FAIL: Should have raised error")
    except Exception as e:
        print(f"   ✅ PASS: Caught error - {e}")
    
    print("\n7. String sanitization:")
    dirty = "  Test\x00String  "
    clean = InputValidator.sanitize_string(dirty)
    print(f"   Input: '{dirty}'")
    print(f"   Output: '{clean}'")
    print(f"   ✅ PASS" if clean == "TestString" else "   ❌ FAIL")
    
    print("\n--- ALL TESTS COMPLETE ---\n")

"""
LUNA Kinematics Module
1-Link Arm (No IK - Simple Trigonometry)
"""

import math


class SimpleKinematics:
    """
    Simple 1-Link Arm Kinematics
    No Inverse Kinematics - Direct angle mapping only
    """
    
    def __init__(self, link_length=28.0):
        """
        Initialize kinematics
        
        Args:
            link_length: Length of forearm in cm (default: 28cm)
        """
        self.link_length = link_length
        self.min_angle = 0
        self.max_angle = 180
    
    def angle_to_position(self, angle_degrees):
        """
        Convert angle to end-effector position (for visualization)
        
        Args:
            angle_degrees: Pivot angle (0-180)
            
        Returns:
            (x, y, z) position in cm
        """
        angle_rad = math.radians(angle_degrees)
        
        # Simple arc motion
        # X: Horizontal (0 for vertical arm)
        # Y: Vertical (0 at top, positive downward)
        # Z: Depth (0 for planar motion)
        
        x = 0  # No horizontal reach (pivot only)
        y = self.link_length * math.sin(angle_rad)
        z = 0  # No depth (pivot only)
        
        return (x, y, z)
    
    def position_to_angle(self, target_y):
        """
        Convert target Y position to pivot angle
        (Simplified - no IK needed for 1-link)
        
        Args:
            target_y: Target vertical position in cm
            
        Returns:
            Angle in degrees (0-180)
        """
        # Clamp target_y to valid range
        target_y = max(0, min(self.link_length, target_y))
        
        # Calculate angle: sin(angle) = y / L
        if self.link_length > 0:
            sin_angle = target_y / self.link_length
            sin_angle = max(-1.0, min(1.0, sin_angle))  # Clamp
            angle_rad = math.asin(sin_angle)
            angle_degrees = math.degrees(angle_rad)
            
            # Map to 0-180 range
            if angle_degrees < 0:
                angle_degrees = 180 + angle_degrees
            
            return max(self.min_angle, min(self.max_angle, angle_degrees))
        
        return 90  # Default center
    
    def image_y_to_angle(self, image_y_normalized):
        """
        Convert normalized image Y coordinate (0-1) to pivot angle
        
        Args:
            image_y_normalized: Y position in image (0=top, 1=bottom)
            
        Returns:
            Angle in degrees (0-180)
        """
        # Map image Y to angle: top (0) = 0°, bottom (1) = 180°
        angle = image_y_normalized * 180
        return max(self.min_angle, min(self.max_angle, angle))
    
    def get_workspace_bounds(self):
        """
        Get workspace boundaries
        
        Returns:
            Dictionary with min/max values
        """
        return {
            'x_min': 0,
            'x_max': 0,
            'y_min': 0,
            'y_max': self.link_length,
            'z_min': 0,
            'z_max': 0,
            'angle_min': self.min_angle,
            'angle_max': self.max_angle,
        }
    
    def is_reachable(self, target_x, target_y, target_z):
        """
        Check if target position is reachable
        (For 1-link pivot-only arm, only Y matters)
        
        Args:
            target_x: Target X (ignored)
            target_y: Target Y (cm)
            target_z: Target Z (ignored)
            
        Returns:
            True if reachable, False otherwise
        """
        # Only Y position matters for pivot-only arm
        return 0 <= target_y <= self.link_length


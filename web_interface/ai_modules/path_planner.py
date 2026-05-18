"""
LUNA Autonomous Path Planning Module
Implements 3D grid-search A* optimization with spatial voxel collision boundaries.
"""

import numpy as np
import heapq
import math
from web_interface.ai_modules.kinematics import SimpleKinematics


class PathPlanner:
    """
    3D Spatial A* Path Planner for LUNA Robotic Arm trajectory mapping (Resolved Feature 1)
    """
    
    def __init__(self, radius_cm=28.0, grid_resolution=20):
        """
        Initialize Path Planner
        """
        self.kinematics = SimpleKinematics(link_length=radius_cm)
        self.set_workspace(radius_cm, grid_resolution)

    def set_workspace(self, radius_cm=28.0, grid_resolution=20):
        """
        Creates a 3D occupancy grid bounded by the robot's physical reach.
        """
        self.radius = radius_cm
        self.res = grid_resolution
        
        # Grid covers coordinates from -R to +R in all axes
        # Shape: res x res x res
        self.grid = np.zeros((self.res, self.res, self.res), dtype=np.float32)
        self.voxel_size = (2.0 * self.radius) / self.res

    def _coord_to_idx(self, coord):
        """Convert real (x, y, z) to grid index (i, j, k)"""
        x, y, z = coord
        i = int(((x + self.radius) / (2.0 * self.radius)) * self.res)
        j = int(((y + self.radius) / (2.0 * self.radius)) * self.res)
        k = int(((z + self.radius) / (2.0 * self.radius)) * self.res)
        
        # Clamp to bounds
        i = max(0, min(self.res - 1, i))
        j = max(0, min(self.res - 1, j))
        k = max(0, min(self.res - 1, k))
        return i, j, k

    def _idx_to_coord(self, idx):
        """Convert grid index (i, j, k) to real (x, y, z)"""
        i, j, k = idx
        x = -self.radius + (i + 0.5) * self.voxel_size
        y = -self.radius + (j + 0.5) * self.voxel_size
        z = -self.radius + (k + 0.5) * self.voxel_size
        return float(x), float(y), float(z)

    def add_obstacle(self, position, size):
        """
        Mark 3D voxels as blocked inside a bounding box area.
        
        Args:
            position: Center (x, y, z) of obstacle in cm
            size: Dimensions (sx, sy, sz) of obstacle in cm
        """
        px, py, pz = position
        sx, sy, sz = size
        
        # Compute min/max coordinates
        min_x, max_x = px - sx/2.0, px + sx/2.0
        min_y, max_y = py - sy/2.0, py + sy/2.0
        min_z, max_z = pz - sz/2.0, pz + sz/2.0
        
        # Convert bounds to indices
        i_min, j_min, k_min = self._coord_to_idx((min_x, min_y, min_z))
        i_max, j_max, k_max = self._coord_to_idx((max_x, max_y, max_z))
        
        # Mark grid voxel cells as blocked
        self.grid[i_min:i_max+1, j_min:j_max+1, k_min:k_max+1] = 1.0

    def plan_path(self, start_pose, target_pose, algorithm='astar'):
        """
        Calculate a collision-free 3D trajectory from start_pose to target_pose.
        
        Args:
            start_pose: (x, y, z) start point in cm
            target_pose: (x, y, z) target point in cm
            algorithm: 'astar' or basic heuristic
            
        Returns:
            List of (x, y, z) waypoints in cm
        """
        start_idx = self._coord_to_idx(start_pose)
        target_idx = self._coord_to_idx(target_pose)
        
        # Priority Queue for A* search: element contains (f_score, current_idx)
        open_set = []
        heapq.heappush(open_set, (0.0, start_idx))
        
        # Tracking dictionaries
        came_from = {}
        g_score = {start_idx: 0.0}
        f_score = {start_idx: self._heuristic(start_idx, target_idx)}
        
        closed_set = set()
        
        # 26-connectivity neighborhood shifts
        directions = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                for dz in [-1, 0, 1]:
                    if dx == 0 and dy == 0 and dz == 0:
                        continue
                    directions.append((dx, dy, dz))
        
        while open_set:
            _, current = heapq.heappop(open_set)
            
            if current == target_idx:
                # Target reached! Backtrack and rebuild path waypoints
                path = []
                curr = current
                while curr in came_from:
                    path.append(self._idx_to_coord(curr))
                    curr = came_from[curr]
                path.append(self._idx_to_coord(start_idx))
                path.reverse()
                return path
            
            closed_set.add(current)
            ci, cj, ck = current
            
            for dx, dy, dz in directions:
                neighbor = (ci + dx, cj + dy, ck + dz)
                
                # Boundary bounds check
                if not (0 <= neighbor[0] < self.res and 
                        0 <= neighbor[1] < self.res and 
                        0 <= neighbor[2] < self.res):
                    continue
                
                # Obstacle collision check
                if self.grid[neighbor[0], neighbor[1], neighbor[2]] > 0.5:
                    continue
                
                if neighbor in closed_set:
                    continue
                
                # Movement cost: Euclidean distance between grid indexes
                step_cost = math.sqrt(dx*dx + dy*dy + dz*dz) * self.voxel_size
                tentative_g = g_score[current] + step_cost
                
                if tentative_g < g_score.get(neighbor, float('inf')):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + self._heuristic(neighbor, target_idx)
                    
                    # Push node to A* min-heap
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))
                    
        # If A* fails, return direct linear interpolation as safety fallback
        print("⚠️ A* path search blocked. Returning linear fallback.")
        return [start_pose, target_pose]

    def _heuristic(self, node, target):
        """3D Euclidean distance heuristic formula"""
        return math.sqrt(
            (node[0] - target[0])**2 + 
            (node[1] - target[1])**2 + 
            (node[2] - target[2])**2
        ) * self.voxel_size

    def get_joint_trajectory(self, waypoints):
        """
        Converts spatial 3D waypoints into specific joint/servo angles using kinematics.
        """
        trajectory = []
        for x, y, z in waypoints:
            # Map Y displacement to main pivot Motor ID 2
            pivot_angle = self.kinematics.position_to_angle(y)
            
            # 4-DOF dynamic orientation mappings (Upgrade 2.7)
            # Pitch from Z (depth) mapped to 0-180 (centered at 90)
            pitch = int(max(0, min(180, (z + self.radius) / (2.0 * self.radius) * 180.0)))
            # Roll from X (width) mapped to 0-180 (centered at 90)
            roll = int(max(0, min(180, (x + self.radius) / (2.0 * self.radius) * 180.0)))
            
            servo_cmd = {
                2: int(pivot_angle),
                3: pitch,
                4: roll,
            }
            trajectory.append(servo_cmd)
        return trajectory

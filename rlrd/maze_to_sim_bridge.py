#!/usr/bin/env python3
"""
Bridge to deploy PointMaze-trained agents on TurtleBot3 simulator.

This adapter translates between different observation spaces:
- PointMaze: [x, y, velocity_x, velocity_y] 
- TurtleBot3: [x, y, theta, linear_velocity]

Usage:
    python3 -m rlrd.maze_to_sim_bridge <pointmaze_checkpoint_path>
"""

import torch
import numpy as np
import sys
import os
from rlrd.util import load

# Optional ROS imports
try:
    import rospy
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import Odometry
    from sensor_msgs.msg import LaserScan
    import tf.transformations as tft
    ROS_AVAILABLE = True
except ImportError:
    ROS_AVAILABLE = False
    print("Warning: ROS not available. Running in test mode.")


class MazeToSimBridge:
    """Bridge to load maze-trained model and use it in simulation"""
    
    def __init__(self, checkpoint_path, use_ros=True):
        """
        Load a trained agent from checkpoint
        
        Args:
            checkpoint_path: Path to the checkpoint file (e.g., 'checkpoints/maze_model_1/state')
            use_ros: Whether to initialize ROS node (default: True)
        """
        print(f"Loading checkpoint from {checkpoint_path}")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Load the checkpoint using rlrd's load function
        training_instance = load(checkpoint_path)
        
        # Extract the trained agent
        self.agent = training_instance.agent
        self.agent.device = self.device
        
        # Get environment info
        if hasattr(training_instance, 'Env'):
            self.env_name = training_instance.Env
        else:
            self.env_name = 'unknown'
        
        # Get model info
        print(f"Loaded agent type: {type(self.agent).__name__}")
        print(f"Model type: {type(self.agent.model).__name__}")
        print(f"Environment: {self.env_name}")
        if hasattr(training_instance, 'epoch') and hasattr(training_instance, 'epochs'):
            print(f"Training epoch: {training_instance.epoch}/{training_instance.epochs}")
        print(f"Device: {self.device}")
        
        # Set to evaluation mode
        self.agent.model.eval()
        
        # Initialize ROS if requested and available
        self.use_ros = use_ros and ROS_AVAILABLE
        if self.use_ros:
            rospy.init_node('maze_to_sim_bridge', anonymous=True)
        
        # Action tracking for delay handling
        self.action_buffer = []
        self.obs_delay_buffer = []
        self.step_count = 0
        self.agent_state = None  # Track agent's internal state
        
        # Determine if environment uses delays
        self.uses_delays = 'delay' in self.env_name.lower()
        
        # Initialize action buffer for delay environments
        if self.uses_delays:
            # Default delay buffer size (should match training setup)
            max_obs_delay = 2
            max_act_delay = 3
            buffer_size = max_obs_delay + max_act_delay - 1
            
            # Get action space dimension from agent
            if hasattr(self.agent, 'model') and hasattr(self.agent.model, 'action_dim'):
                action_dim = self.agent.model.action_dim
            else:
                action_dim = 2  # Default for point mass
            
            # Initialize with zero actions
            self.action_buffer = [np.zeros(action_dim, dtype=np.float32) for _ in range(buffer_size)]
            print(f"Delay environment detected: buffer_size={buffer_size}, action_dim={action_dim}")
        
        print("=" * 60)
        print("Maze-to-Sim Bridge Initialized Successfully")
        print("=" * 60)
    
    def _format_observation(self, obs):
        """Format observation for delay environments if needed"""
        if not self.uses_delays:
            return obs
        
        # Convert to numpy if needed
        if isinstance(obs, torch.Tensor):
            obs = obs.cpu().numpy()
        elif isinstance(obs, list):
            obs = np.array(obs, dtype=np.float32)
        
        # Ensure observation is 1D
        obs = np.atleast_1d(obs).flatten()
        
        # Create delay observation tuple: (obs, action_buffer, obs_delay, act_delay)
        # NOTE: Do NOT add batch dimension here - the agent's collate function will do that
        obs_delay = 0  # No delay for deployment
        act_delay = 0  # No delay for deployment
        
        delayed_obs = (
            obs,  # Shape: [obs_dim] (no batch dimension)
            tuple(self.action_buffer),  # Each action: [act_dim] (no batch dimension)
            obs_delay,  # Scalar int
            act_delay   # Scalar int
        )
        
        return delayed_obs
    
    def get_action(self, observation, reward=0.0, done=False, info=None, training=False):
        """
        Get action from the trained agent
        
        Args:
            observation: Current observation (numpy array, list, or torch tensor)
            reward: Reward from previous step (default: 0.0)
            done: Whether episode is done (default: False)
            info: Additional info dict (default: None)
            training: Whether in training mode (default: False for inference)
            
        Returns:
            action: Action to take (numpy array)
        """
        if info is None:
            info = {}
        
        # Format observation for delay environments
        formatted_obs = self._format_observation(observation)
        
        # Get action from agent
        action, self.agent_state, stats = self.agent.act(
            state=self.agent_state,
            obs=formatted_obs,
            r=reward,
            done=done,
            info=info,
            train=training
        )
        
        # Update action buffer for delay tracking
        if self.uses_delays:
            self.action_buffer.append(action.copy() if hasattr(action, 'copy') else action)
            # Maintain fixed buffer size
            max_buffer_size = len(self.action_buffer) if len(self.action_buffer) <= 4 else 4
            while len(self.action_buffer) > max_buffer_size:
                self.action_buffer.pop(0)
            
        return action
    
    def reset_agent_state(self):
        """Reset any internal state of the agent"""
        self.action_buffer = []
        self.obs_delay_buffer = []
        self.step_count = 0
        self.agent_state = None  # Reset agent state


class SimController:
    """Controller for TurtleBot3 using maze-trained agent"""
    
    def __init__(self, checkpoint_path):
        if not ROS_AVAILABLE:
            raise RuntimeError("ROS is required for SimController but is not available")
        
        # Load the trained agent
        self.bridge = MazeToSimBridge(checkpoint_path, use_ros=True)
        
        # ROS setup
        # ROS setup
        self.cmd_vel_pub = rospy.Publisher('/cmd_vel', Twist, queue_size=1)
        self.odom_sub = rospy.Subscriber('/odom', Odometry, self._odom_callback)
        
        # State tracking
        self.current_odom = None
        self.last_odom = None
        self.last_time = None
        self.control_rate = rospy.Rate(10)  # 10 Hz
        
        print("\nSimController initialized with ROS")
    
    def _odom_callback(self, msg):
        """Store odometry data"""
        self.last_odom = self.current_odom
        self.current_odom = msg
        
        if self.last_time is None:
            self.last_time = msg.header.stamp
    
    def _get_turtlebot_state(self):
        """Get current TurtleBot3 state from odometry"""
        if self.current_odom is None:
            return None
        
        # Position
        x = self.current_odom.pose.pose.position.x
        y = self.current_odom.pose.pose.position.y
        
        # Orientation (quaternion to yaw)
        quat = self.current_odom.pose.pose.orientation
        euler = tft.euler_from_quaternion([quat.x, quat.y, quat.z, quat.w])
        theta = euler[2]
        
        # Calculate velocity
        if self.last_odom is not None:
            dt = (self.current_odom.header.stamp - self.last_time).to_sec()
            if dt > 0:
                dx = x - self.last_odom.pose.pose.position.x
                dy = y - self.last_odom.pose.pose.position.y
                velocity = np.sqrt(dx**2 + dy**2) / dt
            else:
                velocity = 0.0
        else:
            velocity = 0.0
        
        self.last_time = self.current_odom.header.stamp
        
        return np.array([x, y, theta, velocity], dtype=np.float32)
    
    def translate_observation(self, turtlebot_obs):
        """
        Translate TurtleBot3 observation to PointMaze format
        
        TurtleBot3: [x, y, theta, linear_velocity]
        PointMaze:  [x, y, velocity_x, velocity_y]
        """
        x, y, theta, velocity = turtlebot_obs
        
        # Convert scalar velocity + orientation to velocity components
        velocity_x = velocity * np.cos(theta)
        velocity_y = velocity * np.sin(theta)
        
        pointmaze_obs = np.array([x, y, velocity_x, velocity_y], dtype=np.float32)
        
        return pointmaze_obs
    
    def translate_action(self, pointmaze_action):
        """
        Translate PointMaze action to TurtleBot3 command
        
        PointMaze action: [force_x, force_y] in range [-1, 1]
        TurtleBot3 needs: [linear_x, angular_z]
        """
        force_x, force_y = pointmaze_action
        
        # Convert force vector to robot commands
        # Linear velocity: magnitude of force vector
        linear_x = np.sqrt(force_x**2 + force_y**2)
        linear_x = np.clip(linear_x * 0.22, 0.0, 0.22)  # Scale to TurtleBot3 max speed
        
        # Angular velocity: direction of force vector
        target_angle = np.arctan2(force_y, force_x)
        
        # Get current orientation
        turtlebot_obs = self._get_turtlebot_state()
        if turtlebot_obs is not None:
            current_angle = turtlebot_obs[2]
            angle_diff = self._normalize_angle(target_angle - current_angle)
            angular_z = np.clip(angle_diff * 2.0, -2.84, 2.84)  # P-controller
        else:
            angular_z = 0.0
        
        return linear_x, angular_z
    
    def _normalize_angle(self, angle):
        """Normalize angle to [-pi, pi]"""
        while angle > np.pi:
            angle -= 2 * np.pi
        while angle < -np.pi:
            angle += 2 * np.pi
        return angle
    
    def _publish_action(self, linear_x, angular_z):
        """Publish velocity command"""
        cmd = Twist()
        cmd.linear.x = float(linear_x)
        cmd.angular.z = float(angular_z)
        self.cmd_vel_pub.publish(cmd)
    
    def run(self):
        """Main control loop"""
        print("\nWaiting for odometry data...")
        
        # Wait for first odometry message
        while self.current_odom is None and not rospy.is_shutdown():
            rospy.sleep(0.1)
        
        print("Odometry received. Starting control loop...\n")
        
        step_count = 0
        while not rospy.is_shutdown():
            # Get TurtleBot3 state
            turtlebot_obs = self._get_turtlebot_state()
            
            if turtlebot_obs is not None:
                # Translate to PointMaze observation
                pointmaze_obs = self.translate_observation(turtlebot_obs)
                
                # Get action from PointMaze model
                pointmaze_action = self.bridge.get_action(pointmaze_obs)
                
                # Translate to TurtleBot3 command
                linear_x, angular_z = self.translate_action(pointmaze_action)
                
                # Publish command
                self._publish_action(linear_x, angular_z)
                
                # Logging
                if step_count % 100 == 0:
                    print(f"\nStep {step_count}")
                    print(f"TurtleBot3: pos=({turtlebot_obs[0]:.3f}, {turtlebot_obs[1]:.3f}), "
                          f"theta={turtlebot_obs[2]:.3f}, vel={turtlebot_obs[3]:.3f}")
                    print(f"PointMaze:  pos=({pointmaze_obs[0]:.3f}, {pointmaze_obs[1]:.3f}), "
                          f"vel_x={pointmaze_obs[2]:.3f}, vel_y={pointmaze_obs[3]:.3f}")
                    print(f"Action:     force=({pointmaze_action[0]:.3f}, {pointmaze_action[1]:.3f})")
                    print(f"Command:    linear={linear_x:.3f}, angular={angular_z:.3f}")
                
                step_count += 1
            
            self.control_rate.sleep()


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 -m rlrd.maze_to_sim_bridge <checkpoint_path>")
        print("\nExample:")
        print("  python3 -m rlrd.maze_to_sim_bridge checkpoints/maze_model_1/state")
        print("\nThis will:")
        print("  1. Load the trained agent from the checkpoint")
        print("  2. Test it with a dummy observation")
        print("\nTo run in ROS simulation, use:")
        print("  from rlrd.maze_to_sim_bridge import SimController")
        print("  controller = SimController('checkpoints/maze_model_1/state')")
        print("  controller.run()")
        sys.exit(1)
    
    checkpoint_path = sys.argv[1]
    
    if not os.path.exists(checkpoint_path):
        print(f"Error: Checkpoint not found: {checkpoint_path}")
        sys.exit(1)
    
    try:
        # Load the bridge
        print("\n" + "=" * 60)
        print("TESTING MAZE-TO-SIM BRIDGE")
        print("=" * 60)
        
        bridge = MazeToSimBridge(checkpoint_path, use_ros=False)
        
        print("\n" + "=" * 60)
        print("AGENT LOADED SUCCESSFULLY")
        print("=" * 60)
        
        # Test with dummy observations
        print("\nTesting with dummy observations:")
        print("-" * 60)
        
        # Get observation space from agent
        test_obs_sizes = [4, 8, 15]  # Try common sizes
        
        for obs_size in test_obs_sizes:
            try:
                dummy_obs = np.zeros(obs_size, dtype=np.float32)
                action = bridge.get_action(dummy_obs)
                print(f"✓ Observation size {obs_size}: OK")
                print(f"  Input shape:  {dummy_obs.shape}")
                print(f"  Output shape: {action.shape}")
                print(f"  Sample action: {action}")
                break
            except Exception as e:
                print(f"✗ Observation size {obs_size}: {str(e)[:50]}")
        
        print("\n" + "=" * 60)
        print("USAGE EXAMPLES")
        print("=" * 60)
        print("\nIn Python:")
        print("  from rlrd.maze_to_sim_bridge import MazeToSimBridge")
        print("  bridge = MazeToSimBridge('checkpoints/maze_model_1/state', use_ros=False)")
        print("  action = bridge.get_action(observation)")
        
        if ROS_AVAILABLE:
            print("\nWith ROS:")
            print("  from rlrd.maze_to_sim_bridge import SimController")
            print("  controller = SimController('checkpoints/maze_model_1/state')")
            print("  controller.run()")
        else:
            print("\nNote: ROS not available. Install ROS to run in simulation.")
        
        print("\n" + "=" * 60)
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()


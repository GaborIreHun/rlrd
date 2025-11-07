import time

import pandas as pd
import gym
import numpy as np

# ROS1
import rospy
from std_msgs.msg import Float32MultiArray
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist
from std_srvs.srv import Empty  # ROS service for resetting simulation
from tf.transformations import euler_from_quaternion
import subprocess

# ROS2 alternative:
# import rclpy
# from rclpy.node import Node

class RobotSimEnv(gym.Env):
    """
    A Gazebo-connected Gym environment for training RL agents.
    - Observations come from odometry (position, orientation, velocity).
    - Actions are velocity commands (linear, angular).
    - Reward/done conditions are computed here.
    """

    def __init__(self, seed_val=0, log_dir="/tmp", min_obs_delay=0, max_obs_delay=0, min_action_delay=0, max_action_delay=0):
        super(RobotSimEnv, self).__init__()

        self.min_obs_delay = min_obs_delay
        self.max_obs_delay = max_obs_delay
        self.min_action_delay = min_action_delay
        self.max_action_delay = max_action_delay

        # Define action/obs spaces
        # Actions: [linear_velocity, angular_velocity]
        self.action_space = gym.spaces.Box(
            low=np.array([-1.0, -1.0]),
            high=np.array([1.0, 1.0]),
            dtype=np.float32
        )

        # Observations: [x, y, theta, linear_vel]
        self.observation_space = gym.spaces.Box(
            low=-np.inf, high=np.inf, shape=(4,), dtype=np.float32
        )

        # ROS init (ROS1 example)
        # Initialize ROS
        if not rospy.core.is_initialized():
            rospy.init_node("robot_sim_env", anonymous=True, disable_signals=True)

        # Publishers & subscribers
        self.action_pub = rospy.Publisher("/cmd_vel", Twist, queue_size=1)
        self.obs_sub = rospy.Subscriber("/odom", Odometry, self._obs_callback)

        # === State Variables ===
        self.current_obs = np.zeros(4, dtype=np.float32)
        self.prev_position = np.zeros(2, dtype=np.float32)  # For velocity calculation
        self.prev_time = time.time()
        self.done = False
        self._step_duration = rospy.Duration(0.05)  # Simulation step size (50 ms)

        # === For reproducibility ===
        self.seed(seed_val)  # Set numpy RNG seed

        # === Logging Variables ===
        self.episode_steps = 0
        self.trajectory = []  # Collects (step, obs, action, reward, time)
        self.log_dir = log_dir

        # === Delay Ranges (for delay-aware RL) ===
        self.obs_delay_range = range(min_obs_delay, max_obs_delay + 1)
        self.act_delay_range = range(min_action_delay, max_action_delay + 1)

    def seed(self, seed_val=None):
        """Seed RNG for reproducibility"""
        np.random.seed(seed_val)
        return [seed_val]

    def _obs_callback(self, msg):
        """Callback to update observations from odometry"""
        try:
            # Extract position
            x = msg.pose.pose.position.x
            y = msg.pose.pose.position.y
            
            # Extract orientation (convert quaternion to euler)
            orientation_q = msg.pose.pose.orientation
            orientation_list = [orientation_q.x, orientation_q.y, orientation_q.z, orientation_q.w]
            (_, _, theta) = euler_from_quaternion(orientation_list)
            
            # Calculate velocity from position change (more reliable than twist)
            current_time = time.time()
            dt = current_time - self.prev_time
            
            if dt > 0.001:  # Avoid division by very small numbers
                dx = x - self.prev_position[0]
                dy = y - self.prev_position[1]
                linear_vel = np.sqrt(dx**2 + dy**2) / dt
                
                # Update previous values
                self.prev_position = np.array([x, y], dtype=np.float32)
                self.prev_time = current_time
            else:
                linear_vel = 0.0
            
            # Create observation array
            obs = np.array([x, y, theta, linear_vel], dtype=np.float32)
            
            # Safety check: reject NaN or Inf values
            if np.any(np.isnan(obs)) or np.any(np.isinf(obs)):
                rospy.logwarn_throttle(1.0, f"Invalid observation detected: {obs}, keeping previous observation")
                return
            
            # Clip extreme values to prevent numerical issues
            obs = np.clip(obs, -1000.0, 1000.0)
            
            self.current_obs = obs
            
        except Exception as e:
            rospy.logerr(f"Error in odometry callback: {e}")
            # Keep previous observation on error

    def reset(self):
        """Reset simulation via ROS service or topic"""
        rospy.wait_for_service('/gazebo/reset_simulation')

        try:
            reset_sim = rospy.ServiceProxy('/gazebo/reset_simulation', Empty)
            reset_sim()
        except rospy.ServiceException as e:
            rospy.logerr("Reset service call failed: %s", str(e))

        # Sleep with exception handling for time jumps during simulation reset
        try:
            rospy.sleep(1.0)  # Let things stabilize
        except rospy.exceptions.ROSTimeMovedBackwardsException:
            # This is expected when resetting simulation - just continue
            pass

        # === Reset internal state ===
        self.done = False
        self.current_obs = np.zeros(4, dtype=np.float32)
        self.prev_position = np.zeros(2, dtype=np.float32)
        self.prev_time = time.time()
        self.episode_steps = 0
        self.trajectory = []  # Clear trajectory for new episode

        # Wait for fresh odometry data
        rospy.sleep(0.1)
        
        # Ensure we have valid observations before returning
        max_retries = 10
        for _ in range(max_retries):
            if not np.all(self.current_obs == 0):
                break
            rospy.sleep(0.1)
        
        # Final safety check
        if np.any(np.isnan(self.current_obs)) or np.any(np.isinf(self.current_obs)):
            rospy.logwarn(f"Invalid observation after reset: {self.current_obs}, using zeros")
            self.current_obs = np.zeros(4, dtype=np.float32)

        return self.current_obs

    def step(self, action):
        """Apply action to Gazebo and return environment tuple"""
        # === Publish action ===
        # Convert action to Twist message (customize if needed)
        twist_msg = Twist()
        twist_msg.linear.x = float(action[0])
        twist_msg.angular.z = float(action[1])
        self.action_pub.publish(twist_msg)

        # === Wait for sim step ===
        try:
            rospy.sleep(self._step_duration)
        except rospy.exceptions.ROSTimeMovedBackwardsException:
            # This is expected when simulation is reset
            pass

        # === Get new observation ===
        obs = self.current_obs.copy()

        # === Reward function ===
        # Simple reward: small negative step penalty + bonus for staying upright/stable
        reward = -0.1  # Step penalty to encourage efficiency
        
        # === Done condition ===
        # Episode ends if: position too far, or max steps reached
        position_limit = 5.0  # Reduced from 10.0 for faster episodes
        max_steps = 500  # Maximum steps per episode (matching training config)
        
        position_violation = bool(np.any(np.abs(obs[:2]) > position_limit))  # Check x, y position
        max_steps_reached = self.episode_steps >= max_steps
        
        self.done = position_violation or max_steps_reached
        self.episode_steps += 1

        # === Log step data for reproducibility ===
        self.trajectory.append({
            "step": self.episode_steps,
            "obs": obs.tolist(),
            "action": action.tolist(),
            "reward": reward,
            "time": time.time()
        })

        info = {}

        return obs, reward, self.done, info

    def render(self, mode="video"):
        timestamp = int(time.time())
        output_file = f"{self.log_dir}/video_{timestamp}.mp4"
        try:
            subprocess.Popen([
                "gazebo", "--record", "--record-path", output_file
            ])
            rospy.loginfo(f"Started recording Gazebo video to {output_file}")
        except Exception as e:
            rospy.logerr(f"Failed to start recording: {str(e)}")

    def close(self):
        """Shutdown ROS and optionally save the episode log"""
        # Save trajectory if any collected
        if len(self.trajectory) > 0:
            timestamp = int(time.time())
            log_path = f"{self.log_dir}/robot_sim_episode_{timestamp}.csv"
            pd.DataFrame(self.trajectory).to_csv(log_path, index=False)
            rospy.loginfo(f"Episode log saved to {log_path}")

        rospy.signal_shutdown("Closing RobotSimEnv")

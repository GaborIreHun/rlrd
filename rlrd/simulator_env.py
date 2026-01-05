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

    def __init__(self, seed_val=0, log_dir="/tmp", min_obs_delay=0, max_obs_delay=0, min_action_delay=0, max_action_delay=0, lidar_dim=0):
        super(RobotSimEnv, self).__init__()

        self.min_obs_delay = min_obs_delay
        self.max_obs_delay = max_obs_delay
        self.min_action_delay = min_action_delay
        self.max_action_delay = max_action_delay
        self.lidar_dim = lidar_dim

        # Define action/obs spaces
        # Actions: [linear_velocity, angular_velocity]
        self.action_space = gym.spaces.Box(
            low=np.array([-1.0, -1.0]),
            high=np.array([1.0, 1.0]),
            dtype=np.float32
        )

        # Observations: [x, y, theta, linear_vel] + optional LiDAR
        obs_dim = 4 + lidar_dim
        self.observation_space = gym.spaces.Box(
            low=-np.inf, high=np.inf, shape=(obs_dim,), dtype=np.float32
        )

        # ROS init (ROS1 example)
        # Initialize ROS
        if not rospy.core.is_initialized():
            rospy.init_node("robot_sim_env", anonymous=True, disable_signals=True)

        # Publishers & subscribers
        self.action_pub = rospy.Publisher("/cmd_vel", Twist, queue_size=1)
        self.obs_sub = rospy.Subscriber("/odom", Odometry, self._obs_callback)

        # LiDAR subscriber
        self.lidar_sub = None
        self.latest_lidar = None
        if self.lidar_dim > 0:
            from sensor_msgs.msg import LaserScan
            self.lidar_sub = rospy.Subscriber("/scan", LaserScan, self._lidar_callback)

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

    def _lidar_callback(self, msg):
        """Callback to update LiDAR scan data"""
        try:
            lidar_data = np.array(msg.ranges, dtype=np.float32)
            # Pad or truncate to match lidar_dim
            if lidar_data.shape[0] > self.lidar_dim:
                lidar_data = lidar_data[:self.lidar_dim]
            elif lidar_data.shape[0] < self.lidar_dim:
                pad = self.lidar_dim - lidar_data.shape[0]
                lidar_data = np.pad(lidar_data, (0, pad), 'constant', constant_values=np.inf)
            
            # Replace inf with large value (e.g., max range)
            lidar_data = np.where(np.isinf(lidar_data), 10.0, lidar_data)
            self.latest_lidar = lidar_data
            
            # Log warnings for close obstacles
            min_dist = np.min(lidar_data)
            if min_dist < 0.18:
                rospy.logwarn_throttle(1.0, f"[LiDAR] COLLISION DETECTED: min_dist={min_dist:.3f}m")
            elif min_dist < 0.5:
                rospy.loginfo_throttle(5.0, f"[LiDAR] Close obstacle: min_dist={min_dist:.3f}m")
        except Exception as e:
            rospy.logerr(f"Error in LiDAR callback: {e}")

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
            
            # Concatenate LiDAR if available
            if self.lidar_dim > 0 and self.latest_lidar is not None:
                obs = np.concatenate([obs, self.latest_lidar], dtype=np.float32)
            
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

    def _restart_gazebo(self):
        """Restart Gazebo if it crashed"""
        rospy.logwarn("Attempting to restart Gazebo...")
        
        import subprocess
        import os
        
        try:
            # Kill existing processes
            subprocess.run(['pkill', '-9', '-f', 'gzserver'], check=False, stderr=subprocess.DEVNULL)
            subprocess.run(['pkill', '-9', '-f', 'gzclient'], check=False, stderr=subprocess.DEVNULL)
            
            # Wait for cleanup
            try:
                rospy.sleep(3.0)
            except rospy.exceptions.ROSTimeMovedBackwardsException:
                time.sleep(3.0)
            
            # Check if restart script exists
            restart_script = '/root/ws/rtrd/scripts/start_gazebo_headless.sh'
            if os.path.exists(restart_script):
                rospy.logwarn(f"Restarting Gazebo using {restart_script}")
                # Start in background
                subprocess.Popen(['bash', restart_script], 
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL)
                
                # Wait for Gazebo to come back up
                rospy.logwarn("Waiting for Gazebo services to become available...")
                max_wait = 60  # seconds
                start_time = time.time()
                
                while (time.time() - start_time) < max_wait:
                    try:
                        rospy.wait_for_service('/gazebo/reset_simulation', timeout=2.0)
                        rospy.loginfo("Gazebo successfully restarted!")
                        return True
                    except rospy.ROSException:
                        time.sleep(1.0)
                        continue
                
                rospy.logerr("Gazebo restart timed out after 60 seconds")
                return False
            else:
                rospy.logerr(f"Restart script not found: {restart_script}")
                return False
                
        except Exception as e:
            rospy.logerr(f"Failed to restart Gazebo: {e}")
            return False

    def reset(self):
        """Reset simulation via ROS service or topic with auto-restart on failure"""
        max_retries = 3
        retry_delay = 2.0
        
        for attempt in range(max_retries):
            try:
                # Wait for reset service
                try:
                    rospy.wait_for_service('/gazebo/reset_simulation', timeout=10.0)
                except (rospy.ROSException, rospy.ROSInterruptException) as e:
                    rospy.logerr(f"Failed to connect to Gazebo reset service: {e}")
                    
                    if attempt < max_retries - 1:
                        rospy.logwarn(f"Attempt {attempt + 1}/{max_retries}: Trying to restart Gazebo...")
                        if self._restart_gazebo():
                            rospy.loginfo("Gazebo restarted, retrying reset...")
                            continue
                        else:
                            rospy.logwarn(f"Gazebo restart failed, waiting {retry_delay}s before retry...")
                            time.sleep(retry_delay)
                            continue
                    else:
                        rospy.logerr("Make sure Gazebo is running!")
                        raise RuntimeError("Gazebo simulation not available after multiple restart attempts.")

                # Call reset service
                try:
                    reset_sim = rospy.ServiceProxy('/gazebo/reset_simulation', Empty)
                    reset_sim()
                except rospy.ServiceException as e:
                    rospy.logerr(f"Reset service call failed: {e}")
                    if attempt < max_retries - 1:
                        rospy.logwarn(f"Retry {attempt + 1}/{max_retries} after {retry_delay}s...")
                        time.sleep(retry_delay)
                        continue
                    raise

                # Sleep with exception handling for time jumps during simulation reset
                try:
                    rospy.sleep(1.0)  # Let things stabilize
                except rospy.exceptions.ROSTimeMovedBackwardsException:
                    # This is expected when resetting simulation - just continue
                    pass

                # === Reset internal state ===
                self.done = False
                obs_dim = 4 + self.lidar_dim
                self.current_obs = np.zeros(obs_dim, dtype=np.float32)
                self.prev_position = np.zeros(2, dtype=np.float32)
                self.prev_time = time.time()
                self.episode_steps = 0
                self.trajectory = []  # Clear trajectory for new episode

                # Reset LiDAR
                if self.lidar_dim > 0:
                    self.latest_lidar = np.full(self.lidar_dim, 10.0, dtype=np.float32)

                # Wait for fresh odometry data
                try:
                    rospy.sleep(0.1)
                except rospy.exceptions.ROSTimeMovedBackwardsException:
                    pass  # Expected during reset
                
                # Ensure we have valid observations before returning
                max_obs_retries = 10
                for _ in range(max_obs_retries):
                    if not np.all(self.current_obs == 0):
                        break
                    try:
                        rospy.sleep(0.1)
                    except rospy.exceptions.ROSTimeMovedBackwardsException:
                        pass  # Expected during reset
                
                # Final safety check
                if np.any(np.isnan(self.current_obs)) or np.any(np.isinf(self.current_obs)):
                    rospy.logwarn(f"Invalid observation after reset: {self.current_obs}, using zeros")
                    self.current_obs = np.zeros(obs_dim, dtype=np.float32)

                # Success - return observation
                return self.current_obs
                
            except (rospy.ROSInterruptException, RuntimeError) as e:
                if attempt < max_retries - 1:
                    rospy.logerr(f"Reset attempt {attempt + 1} failed: {e}. Retrying...")
                    time.sleep(retry_delay)
                    continue
                else:
                    rospy.logerr(f"Reset failed after {max_retries} attempts")
                    raise

        raise RuntimeError("Failed to reset environment after maximum retries")

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

        # === Compute LiDAR metrics for logging and rewards ===
        min_obstacle_dist = np.inf
        collision_detected = False
        if self.lidar_dim > 0 and self.latest_lidar is not None:
            min_obstacle_dist = float(np.min(self.latest_lidar))
            collision_detected = min_obstacle_dist < 0.18  # 18cm collision threshold

        # === Reward function ===
        # Simple reward: small negative step penalty + bonus for staying upright/stable
        reward = -0.1  # Step penalty to encourage efficiency
        
        # Penalty for getting too close to obstacles
        if self.lidar_dim > 0:
            if collision_detected:
                reward -= 10.0  # Large penalty for collision
            elif min_obstacle_dist < 0.5:  # Warning zone
                reward -= (0.5 - min_obstacle_dist) * 2.0  # Smooth penalty
        
        # === Done condition ===
        # Episode ends if: position too far, collision, or max steps reached
        position_limit = 5.0  # Reduced from 10.0 for faster episodes
        max_steps = 500  # Maximum steps per episode (matching training config)
        
        position_violation = bool(np.any(np.abs(obs[:2]) > position_limit))  # Check x, y position
        max_steps_reached = self.episode_steps >= max_steps
        
        self.done = position_violation or max_steps_reached or collision_detected
        self.episode_steps += 1

        # === Log step data for reproducibility ===
        step_data = {
            "step": self.episode_steps,
            "obs": obs.tolist(),
            "action": action.tolist(),
            "reward": reward,
            "time": time.time()
        }
        
        # Add LiDAR metrics to logging
        if self.lidar_dim > 0:
            step_data["min_obstacle_dist"] = min_obstacle_dist
            step_data["collision"] = collision_detected
        
        self.trajectory.append(step_data)

        info = {}
        if self.lidar_dim > 0:
            info["min_obstacle_dist"] = min_obstacle_dist
            info["collision"] = collision_detected

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

from queue import Empty
from time import time

import pandas as pd
import gym
import numpy as np

# ROS1
import rospy
from std_msgs.msg import Float32MultiArray
from sensor_msgs.msg import JointState
from geometry_msgs.msg import Twist
import subprocess

# ROS2 alternative:
# import rclpy
# from rclpy.node import Node

class RobotSimEnv(gym.Env):
    """
    A Gazebo-connected Gym environment for training RL agents.
    - Observations come from a ROS topic (e.g. /joint_states).
    - Actions are sent to a ROS topic (e.g. /cmd_vel or /torque_cmd).
    - Reward/done conditions are computed here.
    """

    def __init__(self, seed_val=0, log_dir="/tmp", min_obs_delay=0, max_obs_delay=0, min_action_delay=0, max_action_delay=0):
        super(RobotSimEnv, self).__init__()

        self.min_obs_delay = min_obs_delay
        self.max_obs_delay = max_obs_delay
        self.min_action_delay = min_action_delay
        self.max_action_delay = max_action_delay

        # Define action/obs spaces (customize for your robot!)
        # Example: 2D continuous actions (left_wheel_vel, right_wheel_vel)
        self.action_space = gym.spaces.Box(
            low=np.array([-1.0, -1.0]),
            high=np.array([1.0, 1.0]),
            dtype=np.float32
        )

        # Example: observe 4 joint positions
        self.observation_space = gym.spaces.Box(
            low=-np.inf, high=np.inf, shape=(4,), dtype=np.float32 # Assume 4 joints
        )

        # ROS init (ROS1 example)
        # Initialize ROS
        if not rospy.core.is_initialized():
            rospy.init_node("robot_sim_env", anonymous=True, disable_signals=True)

        # Publishers & subscribers
        self.action_pub = rospy.Publisher("/cmd_vel", Twist, queue_size=1)
        self.obs_sub = rospy.Subscriber("/joint_states", JointState, self._obs_callback)

        # === State Variables ===
        self.current_obs = np.zeros(4, dtype=np.float32)
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
        """Callback to update observations from ROS topic"""
        if len(msg.position) >= 4:
            self.current_obs = np.array(msg.position[:4], dtype=np.float32)

    def reset(self):
        """Reset simulation via ROS service or topic"""
        rospy.wait_for_service('/gazebo/reset_simulation')

        try:
            reset_sim = rospy.ServiceProxy('/gazebo/reset_simulation', Empty)
            reset_sim()
        except rospy.ServiceException as e:
            rospy.logerr("Reset service call failed: %s", str(e))

        rospy.sleep(1.0)  # Let things stabilize

        # === Reset internal state ===
        self.done = False
        self.current_obs = np.zeros(4, dtype=np.float32)
        self.episode_steps = 0
        self.trajectory = []  # Clear trajectory for new episode

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
        rospy.sleep(self._step_duration)

        # === Get new observation ===
        obs = self.current_obs.copy()

        # === Reward function ===
        reward = -np.linalg.norm(obs)  # Encourage staying near origin

        # === Done condition ===
        self.done = bool(np.any(np.abs(obs) > 10.0))
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

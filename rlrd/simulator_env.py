import gym
import numpy as np

# ROS1
import rospy
from std_msgs.msg import Float32MultiArray
from sensor_msgs.msg import JointState

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

    def __init__(self, seed_val=0):
        super(RobotSimEnv, self).__init__()

        # Define action/obs spaces (customize for your robot!)
        # Example: 2D continuous actions (left_wheel_vel, right_wheel_vel)
        self.action_space = gym.spaces.Box(
            low=np.array([-1.0, -1.0]),
            high=np.array([1.0, 1.0]),
            dtype=np.float32
        )

        # Example: observe 4 joint positions
        self.observation_space = gym.spaces.Box(
            low=-np.inf, high=np.inf, shape=(4,), dtype=np.float32
        )

        # ROS init (ROS1 example)
        rospy.init_node("robot_sim_env", anonymous=True)

        # Publishers & subscribers
        self.action_pub = rospy.Publisher("/cmd_action", Float32MultiArray, queue_size=1)
        rospy.Subscriber("/joint_states", JointState, self._obs_callback)

        self.current_obs = np.zeros(4, dtype=np.float32)
        self.done = False

    def _obs_callback(self, msg):
        """Callback to update observations from ROS topic"""
        self.current_obs = np.array(msg.position[:4], dtype=np.float32)

    def reset(self):
        """Reset simulation via ROS service or topic"""
        rospy.wait_for_service('/gazebo/reset_simulation')
        reset_sim = rospy.ServiceProxy('/gazebo/reset_simulation', Empty)
        reset_sim()

        self.done = False
        self.current_obs = np.zeros(4, dtype=np.float32)
        return self.current_obs

    def step(self, action):
        """Send action to Gazebo and return (obs, reward, done, info)"""
        # Publish action
        msg = Float32MultiArray(data=action.tolist())
        self.action_pub.publish(msg)

        # Sleep for sim step
        rospy.sleep(0.05)

        # Observation
        obs = self.current_obs

        # Example reward: keep joints near zero
        reward = -np.linalg.norm(obs)

        # Example termination: after some steps or if obs diverges
        self.done = bool(np.any(np.abs(obs) > 10.0))

        info = {}
        return obs, reward, self.done, info

    def render(self, mode="human"):
        # Gazebo already renders; optionally log or plot
        pass

    def close(self):
        rospy.signal_shutdown("Closing RobotSimEnv")

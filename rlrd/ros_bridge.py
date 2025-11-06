#!/usr/bin/env python3
import rospy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import torch
import time
import numpy as np
from dataclasses import dataclass
from collections import deque
from copy import deepcopy
import gym
from gym import spaces

from .nn import no_grad  # Import utility functions from the project

# === Import your trained RL model ===
from functools import partial
from .dcac import Agent as DCACActor  # Import the DCAC Agent class
from .dcac_models import Mlp  # Import the Mlp model
from .util import load  # Import the general load function
from .wrappers import RealTimeWrapper
from .wrappers_rd import RandomDelayWrapper
import gym.spaces

class RosGymEnv(gym.Env):
    """ROS environment that follows gym interface"""
    def __init__(self):
        super().__init__()
        # Define observation space (x, y, vx, vy)
        self.observation_space = spaces.Box(
            low=np.array([-np.inf, -np.inf, -np.inf, -np.inf], dtype=np.float32),
            high=np.array([np.inf, np.inf, np.inf, np.inf], dtype=np.float32),
            shape=(4,),
            dtype=np.float32
        )
        
        # Define action space (linear.x only, to match trained model)
        self.action_space = spaces.Box(
            low=np.array([-1.0], dtype=np.float32),
            high=np.array([1.0], dtype=np.float32),
            shape=(1,),
            dtype=np.float32
        )
        
        # Initialize ROS subscribers and publishers in reset()
        self.latest_state = None
        self.cmd_pub = None
        self.odom_sub = None
    
    def reset(self):
        # Initialize ROS nodes and subscribers if not already done
        if self.cmd_pub is None:
            self.cmd_pub = rospy.Publisher("/cmd_vel", Twist, queue_size=1)
        if self.odom_sub is None:
            self.odom_sub = rospy.Subscriber("/odom", Odometry, self._odom_callback)
        
        # Wait for first state
        self.latest_state = None
        while self.latest_state is None and not rospy.is_shutdown():
            rospy.sleep(0.1)
        
        return self.latest_state
    
    def _odom_callback(self, msg):
        # Extract position and velocity from Odometry
        x = msg.pose.pose.position.x
        y = msg.pose.pose.position.y
        vx = msg.twist.twist.linear.x
        vy = msg.twist.twist.linear.y
        self.latest_state = np.array([x, y, vx, vy], dtype=np.float32)
        
    def step(self, action):
        if not isinstance(action, np.ndarray):
            action = np.array(action)
        
        # Create and publish Twist message
        cmd = Twist()
        cmd.linear.x = float(action[0])
        cmd.angular.z = float(action[1])
        self.cmd_pub.publish(cmd)
        
        # Wait for next state update
        rospy.sleep(0.1)  # 10Hz control rate
        
        return self.latest_state, 0.0, False, {}

class RosEnvFactory:
    """Factory class to create ROS environment instances"""
    def __call__(self):
        return RosEnvWrapper()

class RosEnvWrapper(gym.Env):
    """Environment wrapper for ROS-based robot control"""
    def __init__(self):
        super().__init__()
        # Create base environment
        self.env = RosGymEnv()
        
        # Define delay ranges (minimal for no-delay configuration)
        self.obs_delay_range = range(0, 1)  # No observation delay
        self.act_delay_range = range(0, 1)  # No action delay
        
        # Define the base spaces
        obs_space = self.env.observation_space
        act_space = self.env.action_space
        
        # Create the buffer space for actions
        buffer_size = 2  # Buffer size to match model input dimensions (4 + 1*2 = 6)
        action_buffer_spaces = tuple([act_space] * buffer_size)
        
        # Create the full observation space structure required by DCAC
        self.observation_space = gym.spaces.Tuple((
            obs_space,  # current observation (4D)
            gym.spaces.Tuple(action_buffer_spaces),  # action buffer (1D × 2 = 2D)
            gym.spaces.Discrete(1),  # observation delay - not used due to obs_delay=False
            gym.spaces.Discrete(1),  # action delay - not used due to act_delay=False
        ))
        
        # Action space remains the same
        self.action_space = act_space
        
        # Initialize buffers
        self.past_actions = deque(maxlen=buffer_size)
        self.past_actions.extend([np.zeros(act_space.shape, dtype=np.float32)] * buffer_size)
        self.current_obs_delay = 0
        self.current_act_delay = 0
        
    def reset(self):
        """Reset the environment and return initial observation tuple"""
        obs = self.env.reset()
        
        # Reset delays - using fixed delays for now
        obs_delay = 0  # Fixed observation delay (alpha) - not used due to obs_delay=False
        act_delay = 0  # Fixed action delay (kappa) - not used due to act_delay=False
        
        # Reset action buffer with zeros
        self.past_actions.clear()
        self.past_actions.extend([
            np.zeros(self.action_space.shape, dtype=np.float32)
            for _ in range(2)  # Use fixed size of 2 to match the input dimensions
        ])
        
        # Return DCAC observation tuple
        return (
            obs,
            tuple(self.past_actions),
            obs_delay,
            act_delay
        )
        
    def step(self, action):
        """Execute action and return tuple observation"""
        obs, reward, done, info = self.env.step(action)
        
        # Update action buffer
        self.past_actions.append(action.copy())
        
        # Fixed delays for now
        obs_delay = 1  # Fixed observation delay (alpha)
        act_delay = 0  # Fixed action delay (kappa)
        
        # Return DCAC observation tuple
        return (
            obs,
            tuple(self.past_actions),
            obs_delay,
            act_delay
        ), reward, done, info

class RLAgentBridge:
    def __init__(self):
        rospy.init_node("rl_agent_bridge", anonymous=True)
        self.cmd_pub = rospy.Publisher("/cmd_vel", Twist, queue_size=1)
        self.odom_sub = rospy.Subscriber("/odom", Odometry, self.odom_callback)
        self.rate = rospy.Rate(10)  # 10 Hz control loop
        
        # Create environment factory and get an environment instance
        env_factory = RosEnvFactory()
        self.env = env_factory()  # Create an instance of the environment
        
        # Initialize agent with environment factory and other required settings
        self.agent = DCACActor(
            Env=env_factory,
            device=torch.device('cpu'),  # Force CPU for now
            lr=1e-3,  # Learning rate (won't be used since we're just running inference)
            rtac=False,  # Use standard DCAC mode
            Model=partial(Mlp, obs_delay=False, act_delay=False)  # Configure Mlp without delays
        )
        
        # Load model weights
        model_path = "checkpoints/sac_model_epoch_6.pt"
        loaded_state = torch.load(model_path, map_location=torch.device('cpu'), weights_only=True)
        if isinstance(loaded_state, dict):
            # If it's a state dict, load into model
            self.agent.model.load_state_dict(loaded_state)
            # Create target model
            self.agent.model_target = no_grad(deepcopy(self.agent.model))
        else:
            # If it's a complete agent, use its model
            if hasattr(loaded_state, 'model'):
                self.agent.model = loaded_state.model
                self.agent.model_target = no_grad(deepcopy(loaded_state.model))
        
        # Initialize state buffer
        self.state = None
        self.action_buffer = []
        self.obs_delay = 1  # Fixed observation delay
        self.act_delay = 1  # Fixed action delay

    def odom_callback(self, msg):
        # Extract position and velocity from Odometry
        x = msg.pose.pose.position.x
        y = msg.pose.pose.position.y
        vx = msg.twist.twist.linear.x
        vy = msg.twist.twist.linear.y
        self.state = np.array([x, y, vx, vy])

    def run(self):
        rospy.loginfo("RL agent bridge started")
        
        # Initialize action buffer with zeros
        action_shape = self.env.action_space.shape  # Get shape from environment
        buffer_size = 2  # Fixed buffer size to match model input dimensions
        self.action_buffer = [np.zeros(action_shape, dtype=np.float32)] * buffer_size
        
        while not rospy.is_shutdown():
            if self.state is None:
                continue
                
            # Create DCAC observation tuple
            obs_tuple = (
                torch.tensor(self.state, dtype=torch.float32),  # Current observation
                tuple(torch.tensor(a, dtype=torch.float32) for a in self.action_buffer),  # Action buffer
                torch.tensor(self.obs_delay, dtype=torch.int64),  # Observation delay
                torch.tensor(self.act_delay, dtype=torch.int64),  # Action delay
            )
            
            # Get action from agent's policy network directly
            with torch.no_grad():
                # Convert observation tuple to tensors and add batch dimension
                obs_batch = (
                    obs_tuple[0].unsqueeze(0).to(self.agent.device),
                    tuple(a.unsqueeze(0).to(self.agent.device) for a in obs_tuple[1]),
                    obs_tuple[2].unsqueeze(0).to(self.agent.device),
                    obs_tuple[3].unsqueeze(0).to(self.agent.device)
                )
                # Get deterministic action from the actor
                action_dist = self.agent.model.actor(obs_batch)
                # Use deterministic sampling for deployment
                action = action_dist.sample_deterministic()
            
            # Update action buffer
            self.action_buffer.pop(0)
            self.action_buffer.append(action.squeeze(0).cpu().numpy())
            
            # Publish action (linear.x only, angular.z set to 0)
            cmd = Twist()
            cmd.linear.x = float(action[0])
            cmd.angular.z = 0.0  # No angular velocity
            self.cmd_pub.publish(cmd)
            
            self.rate.sleep()

if __name__ == "__main__":
    bridge = RLAgentBridge()
    bridge.run()

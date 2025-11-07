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
from tf.transformations import euler_from_quaternion

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
    """ROS environment that follows gym interface - supports both 4D and 6D observations"""
    def __init__(self, obs_dim=4):
        super().__init__()
        self.obs_dim = obs_dim
        
        # Define observation space - flexible for 4D or 6D
        self.observation_space = spaces.Box(
            low=-np.inf, 
            high=np.inf, 
            shape=(obs_dim,), 
            dtype=np.float32
        )
        
        # Define action space (2D: linear.x and angular.z)
        self.action_space = spaces.Box(
            low=np.array([-1.0, -1.0], dtype=np.float32),
            high=np.array([1.0, 1.0], dtype=np.float32),
            shape=(2,),
            dtype=np.float32
        )
        
        # Initialize ROS subscribers and publishers in reset()
        self.latest_state = None
        self.cmd_pub = None
        self.odom_sub = None
        self.joint_sub = None
        
        # For velocity calculation (same as SimEnv)
        self.prev_position = np.zeros(2, dtype=np.float32)
        self.prev_time = time.time()
        
        # For 6D mode - joint state storage
        self.latest_joint_state = np.zeros(6, dtype=np.float32)
    
    def reset(self):
        # Initialize ROS nodes and subscribers if not already done
        if self.cmd_pub is None:
            self.cmd_pub = rospy.Publisher("/cmd_vel", Twist, queue_size=1)
        if self.odom_sub is None:
            self.odom_sub = rospy.Subscriber("/odom", Odometry, self._odom_callback)
        
        # For 6D mode, also subscribe to joint states
        if self.obs_dim == 6 and self.joint_sub is None:
            from sensor_msgs.msg import JointState
            self.joint_sub = rospy.Subscriber("/joint_states", JointState, self._joint_callback)
        
        # Reset velocity tracking
        self.prev_position = np.zeros(2, dtype=np.float32)
        self.prev_time = time.time()
        
        # Wait for first state
        self.latest_state = None
        while self.latest_state is None and not rospy.is_shutdown():
            rospy.sleep(0.1)
        
        return self.latest_state
    
    def _joint_callback(self, msg):
        """Callback for joint states (6D mode)"""
        try:
            # Extract joint positions (assumes 6 joints)
            if len(msg.position) >= 6:
                self.latest_joint_state = np.array(msg.position[:6], dtype=np.float32)
                
                # If using 6D mode, this is the observation
                if self.obs_dim == 6:
                    obs = self.latest_joint_state
                    if not (np.any(np.isnan(obs)) or np.any(np.isinf(obs))):
                        self.latest_state = np.clip(obs, -1000.0, 1000.0)
        except Exception as e:
            rospy.logwarn_throttle(1.0, f"Error in joint callback: {e}")
    
    def _odom_callback(self, msg):
        """Extract observation from odometry (4D mode)"""
        # Skip if using 6D joint state mode
        if self.obs_dim == 6:
            return
            
        try:
            # Extract position
            x = msg.pose.pose.position.x
            y = msg.pose.pose.position.y
            
            # Extract orientation (convert quaternion to euler)
            orientation_q = msg.pose.pose.orientation
            orientation_list = [orientation_q.x, orientation_q.y, orientation_q.z, orientation_q.w]
            (_, _, theta) = euler_from_quaternion(orientation_list)
            
            # Calculate velocity from position change (same as SimEnv)
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
            
            # Create observation array [x, y, theta, linear_vel]
            obs = np.array([x, y, theta, linear_vel], dtype=np.float32)
            
            # Safety check: reject NaN or Inf values
            if not (np.any(np.isnan(obs)) or np.any(np.isinf(obs))):
                self.latest_state = np.clip(obs, -1000.0, 1000.0)
        except Exception as e:
            rospy.logwarn_throttle(1.0, f"Error in odometry callback: {e}")
        
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
    """Factory class to create ROS environment instances - supports both 4D and 6D"""
    def __init__(self, obs_dim=4):
        self.obs_dim = obs_dim
        
    def __call__(self):
        return RosEnvWrapper(obs_dim=self.obs_dim)

class RosEnvWrapper(gym.Env):
    """Environment wrapper for ROS-based robot control"""
    def __init__(self, obs_dim=4):
        super().__init__()
        # Create base environment with specified observation dimension
        self.env = RosGymEnv(obs_dim=obs_dim)
        
        # Define delay ranges to match SimEnv training configuration
        self.obs_delay_range = range(0, 3)  # 0-2 observation delay
        self.act_delay_range = range(0, 4)  # 0-3 action delay
        
        # Define the base spaces
        obs_space = self.env.observation_space
        act_space = self.env.action_space
        
        # Create the buffer space for actions
        buffer_size = self.obs_delay_range.stop + self.act_delay_range.stop - 1  # Match RandomDelayWrapper
        action_buffer_spaces = tuple([act_space] * buffer_size)
        
        # Create the full observation space structure required by DCAC
        self.observation_space = gym.spaces.Tuple((
            obs_space,  # current observation (4D or 6D)
            gym.spaces.Tuple(action_buffer_spaces),  # action buffer
            gym.spaces.Discrete(self.obs_delay_range.stop),  # observation delay
            gym.spaces.Discrete(self.act_delay_range.stop),  # action delay
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
        
        # Reset delays - using reasonable default values
        obs_delay = 1  # Default observation delay
        act_delay = 1  # Default action delay
        
        # Reset action buffer with zeros
        self.past_actions.clear()
        buffer_size = self.obs_delay_range.stop + self.act_delay_range.stop - 1
        self.past_actions.extend([
            np.zeros(self.action_space.shape, dtype=np.float32)
            for _ in range(buffer_size)
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
    def __init__(self, checkpoint_path="checkpoints/simtraining_checkpoint/state", obs_dim=None):
        """
        Initialize RL Agent Bridge
        
        Args:
            checkpoint_path: Path to the checkpoint file
            obs_dim: Observation dimension (4 or 6). If None, auto-detect from checkpoint.
        """
        rospy.init_node("rl_agent_bridge", anonymous=True)
        self.cmd_pub = rospy.Publisher("/cmd_vel", Twist, queue_size=1)
        self.rate = rospy.Rate(10)  # 10 Hz control loop
        
        # Initialize velocity tracking early (before callbacks)
        self.state = None
        self.prev_position = np.zeros(2, dtype=np.float32)
        self.prev_time = time.time()
        
        # Try to load checkpoint first to detect obs_dim and model properties
        rospy.loginfo(f"Loading checkpoint from {checkpoint_path}")
        checkpoint_is_state_dict = False
        use_delays = True  # Default: use delays (modern checkpoints)
        action_dim = 2  # Default: 2D action space
        
        try:
            # Try loading as pickle file first (SimTraining checkpoint format)
            checkpoint = load(checkpoint_path)
            
            # Auto-detect observation dimension if not specified
            if obs_dim is None:
                if hasattr(checkpoint, 'agent'):
                    # Try to get env_ctor (newer format)
                    if hasattr(checkpoint.agent, 'env_ctor'):
                        env_factory_from_checkpoint = checkpoint.agent.env_ctor
                        temp_env = env_factory_from_checkpoint()
                        # Extract the base observation dimension from the tuple space
                        obs_dim = temp_env.observation_space.spaces[0].shape[0]
                        rospy.loginfo(f"Auto-detected observation dimension: {obs_dim}D from env_ctor")
                    else:
                        # Older format - try to infer from model
                        try:
                            # Check model input size to infer obs_dim
                            first_layer = checkpoint.agent.model.critics[0][0].lin
                            input_size = first_layer.weight.shape[1]
                            # If input_size is 30, it's 4D with delays (4 + 2*5 + 2*5 + delays)
                            # If input_size is 4, it's 4D without delays
                            # If input_size is 6, it's 6D without delays
                            if input_size >= 20:
                                obs_dim = 4
                                use_delays = True
                            elif input_size == 6:
                                obs_dim = 6
                                use_delays = False
                            else:
                                obs_dim = 4
                                use_delays = False
                            rospy.loginfo(f"Inferred {obs_dim}D observation from model (delays={use_delays})")
                        except:
                            obs_dim = 4
                            rospy.logwarn(f"Could not infer obs_dim, defaulting to {obs_dim}D")
                else:
                    # Default to 4D if can't detect
                    obs_dim = 4
                    rospy.logwarn(f"Could not auto-detect obs_dim, defaulting to {obs_dim}D")
            
            # Try to detect action dimension from model
            if hasattr(checkpoint, 'agent') and hasattr(checkpoint.agent, 'model'):
                try:
                    action_dim = checkpoint.agent.model.actor[-1].lin_mean.weight.shape[0]
                    rospy.loginfo(f"Detected action dimension: {action_dim}D")
                except:
                    rospy.loginfo(f"Using default action dimension: {action_dim}D")
            
            self.obs_dim = obs_dim
            rospy.loginfo(f"Using {obs_dim}D observation space")
            
        except Exception as e:
            # If pickle load fails, it might be a PyTorch state dict (.pt file)
            rospy.logwarn(f"Could not load as pickle checkpoint: {e}")
            rospy.loginfo("Attempting to load as PyTorch state dict (.pt file)")
            
            try:
                # Try loading as PyTorch state dict
                checkpoint = torch.load(checkpoint_path, map_location=torch.device('cpu'))
                checkpoint_is_state_dict = True
                rospy.loginfo("Successfully loaded as PyTorch state dict")
                
                # For state dict, infer properties from the model structure
                if obs_dim is None:
                    # Try to infer from first layer input size
                    try:
                        first_layer_key = 'critics.0.0.lin.weight'
                        if first_layer_key in checkpoint:
                            input_size = checkpoint[first_layer_key].shape[1]
                            if input_size == 6:
                                obs_dim = 6
                                use_delays = False
                                rospy.loginfo(f"Inferred {obs_dim}D (no delays) from state dict")
                            elif input_size == 4:
                                obs_dim = 4
                                use_delays = False
                                rospy.loginfo(f"Inferred {obs_dim}D (no delays) from state dict")
                            else:
                                rospy.logerr(f"Cannot auto-detect obs_dim from input_size={input_size}. Please specify obs_dim.")
                                raise ValueError("obs_dim must be specified")
                        else:
                            rospy.logerr("Cannot find expected layer in state dict. Please specify obs_dim (4 or 6)")
                            raise ValueError("obs_dim must be specified when loading .pt files")
                    except Exception as infer_e:
                        rospy.logerr(f"Cannot auto-detect obs_dim: {infer_e}. Please specify obs_dim (4 or 6)")
                        raise ValueError("obs_dim must be specified when loading .pt files")
                else:
                    # User specified, but still need to detect if delays are used
                    try:
                        first_layer_key = 'critics.0.0.lin.weight'
                        if first_layer_key in checkpoint:
                            input_size = checkpoint[first_layer_key].shape[1]
                            # Check if delays are used based on input size
                            if input_size == obs_dim:
                                use_delays = False
                                rospy.loginfo(f"Detected: {obs_dim}D without delays")
                            else:
                                use_delays = True
                                rospy.loginfo(f"Detected: {obs_dim}D with delays")
                    except:
                        pass
                
                # Detect action dimension
                try:
                    action_layer_key = 'actor.4.lin_mean.weight'
                    if action_layer_key in checkpoint:
                        action_dim = checkpoint[action_layer_key].shape[0]
                        rospy.loginfo(f"Detected action dimension: {action_dim}D")
                except:
                    pass
                
                self.obs_dim = obs_dim
                rospy.loginfo(f"Using {obs_dim}D observation space (user-specified)")
                
            except Exception as e2:
                rospy.logerr(f"Failed to load checkpoint as both pickle and state dict: {e2}")
                if obs_dim is None:
                    obs_dim = 4
                    rospy.logwarn(f"Defaulting to {obs_dim}D observation space")
                self.obs_dim = obs_dim
                checkpoint = None
                checkpoint_is_state_dict = False
        
        # Store checkpoint info and detected properties for later use
        self._checkpoint = checkpoint
        self._checkpoint_is_state_dict = checkpoint_is_state_dict
        self._use_delays = use_delays
        self._action_dim = action_dim
        
        rospy.loginfo(f"Configuration: obs_dim={self.obs_dim}, action_dim={action_dim}, use_delays={use_delays}")
        
        # Create environment factory with detected/specified dimension
        env_factory = RosEnvFactory(obs_dim=self.obs_dim)
        self.env = env_factory()
        
        # Subscribe to appropriate ROS topics based on obs_dim
        if self.obs_dim == 6:
            from sensor_msgs.msg import JointState
            self.joint_sub = rospy.Subscriber("/joint_states", JointState, self.joint_callback)
            rospy.loginfo("Subscribed to /joint_states for 6D observations")
        else:
            self.odom_sub = rospy.Subscriber("/odom", Odometry, self.odom_callback)
            rospy.loginfo("Subscribed to /odom for 4D observations")
        
        # Load model from checkpoint
        rospy.loginfo(f"Loading model from {checkpoint_path}")
        
        try:
            # Handle different checkpoint formats
            if self._checkpoint_is_state_dict:
                # For .pt files, create a minimal agent with correct architecture
                rospy.loginfo("Loading from PyTorch state dict (.pt file)")
                
                # Create a simple environment for the agent (won't be used for real)
                # The key is matching obs_dim, action_dim, and delay settings
                from gym.spaces import Box
                
                class MinimalEnv:
                    def __init__(self, obs_dim, act_dim, use_delays):
                        if use_delays:
                            # With delays: tuple observation space
                            self.observation_space = gym.spaces.Tuple((
                                Box(low=-np.inf, high=np.inf, shape=(obs_dim,), dtype=np.float32),
                                gym.spaces.Tuple([Box(low=-1, high=1, shape=(act_dim,), dtype=np.float32)] * 5),
                                gym.spaces.Discrete(3),
                                gym.spaces.Discrete(4)
                            ))
                            self.obs_delay_range = range(0, 3)
                            self.act_delay_range = range(0, 4)
                        else:
                            # Without delays: wrap Box in Tuple for compatibility with SAC models
                            # SAC models expect Tuple observation space
                            self.observation_space = gym.spaces.Tuple((
                                Box(low=-np.inf, high=np.inf, shape=(obs_dim,), dtype=np.float32),
                            ))
                            self.obs_delay_range = range(0, 1)
                            self.act_delay_range = range(0, 1)
                        self.action_space = Box(low=-1, high=1, shape=(act_dim,), dtype=np.float32)
                
                minimal_env = MinimalEnv(self.obs_dim, action_dim, use_delays)
                
                # Import appropriate model class based on delay usage
                if use_delays:
                    from .dcac_models import Mlp as ModelClass
                else:
                    from .sac_models import Mlp as ModelClass
                
                # Create agent with matching configuration
                self.agent = DCACActor(
                    Env=lambda: minimal_env,
                    device=torch.device('cpu'),
                    lr=0.0003,
                    rtac=False,
                    batchsize=64,
                    discount=0.99,
                    target_update=0.005,
                    reward_scale=5.0,
                    entropy_scale=1.0,
                    Model=partial(ModelClass, num_critics=2)
                )
                
                # Load the state dict
                self.agent.model.load_state_dict(self._checkpoint)
                self.agent.model_target = no_grad(deepcopy(self.agent.model))
                rospy.loginfo("Successfully loaded model from state dict")
                
            elif self._checkpoint is not None:
                # It's a pickle checkpoint with agent - USE THE SAVED AGENT DIRECTLY
                if hasattr(self._checkpoint, 'agent'):
                    saved_agent = self._checkpoint.agent
                    self.agent = saved_agent  # Use the saved agent directly!
                    rospy.loginfo("Successfully loaded agent from checkpoint")
                    rospy.loginfo(f"Model device: {self.agent.device}")
                else:
                    rospy.logerr("Checkpoint does not contain 'agent' attribute")
                    raise ValueError("Invalid checkpoint format")
            else:
                rospy.logerr("No checkpoint loaded")
                raise ValueError("Failed to load checkpoint")
        except Exception as e:
            rospy.logerr(f"Failed to load model: {e}")
            raise
        
        # Initialize action buffer (state is already initialized at the top)
        self.action_buffer = []
        self.obs_delay = 1  # Fixed observation delay
        self.act_delay = 1  # Fixed action delay


    def joint_callback(self, msg):
        """Extract observation from joint states (6D mode)"""
        try:
            if len(msg.position) >= 6:
                obs = np.array(msg.position[:6], dtype=np.float32)
                if not (np.any(np.isnan(obs)) or np.any(np.isinf(obs))):
                    self.state = np.clip(obs, -1000.0, 1000.0)
        except Exception as e:
            rospy.logwarn_throttle(1.0, f"Error in joint callback: {e}")

    def odom_callback(self, msg):
        """Extract observation from odometry (4D mode)"""
        try:
            # Extract position
            x = msg.pose.pose.position.x
            y = msg.pose.pose.position.y
            
            # Extract orientation (convert quaternion to euler)
            orientation_q = msg.pose.pose.orientation
            orientation_list = [orientation_q.x, orientation_q.y, orientation_q.z, orientation_q.w]
            (_, _, theta) = euler_from_quaternion(orientation_list)
            
            # Calculate velocity from position change (more robust than twist)
            current_time = time.time()
            dt = current_time - self.prev_time
            
            if dt > 0.001:
                dx = x - self.prev_position[0]
                dy = y - self.prev_position[1]
                linear_vel = np.sqrt(dx**2 + dy**2) / dt
                
                self.prev_position = np.array([x, y], dtype=np.float32)
                self.prev_time = current_time
            else:
                linear_vel = 0.0
            
            # Create observation array [x, y, theta, linear_vel]
            obs = np.array([x, y, theta, linear_vel], dtype=np.float32)
            
            # Safety check
            if not (np.any(np.isnan(obs)) or np.any(np.isinf(obs))):
                self.state = np.clip(obs, -1000.0, 1000.0)
        except Exception as e:
            rospy.logwarn_throttle(1.0, f"Error in odometry callback: {e}")

    def run(self):
        rospy.loginfo("RL agent bridge started")
        
        # Determine if the model uses delays by checking if agent has the attributes
        uses_delays = hasattr(self.agent, 'sup_obs_delay') and self.agent.sup_obs_delay > 1
        
        if uses_delays:
            # Initialize action buffer for delay-aware models
            action_shape = (self._action_dim,)
            buffer_size = self.agent.sup_obs_delay + self.agent.sup_act_delay - 1
            self.action_buffer = [np.zeros(action_shape, dtype=np.float32) for _ in range(buffer_size)]
            rospy.loginfo(f"Using delay-aware model (buffer_size={buffer_size})")
            rospy.loginfo(f"Observation delays: 0-{self.agent.sup_obs_delay-1}, Action delays: 0-{self.agent.sup_act_delay-1}")
        else:
            rospy.loginfo("Using non-delay model")
        
        # Stats tracking
        step_count = 0
        action_stats = {'linear': [], 'angular': []}
        obs_stats = {'x': [], 'y': [], 'theta': [], 'vel': []}
        
        rospy.loginfo("Waiting for first observation...")
        
        while not rospy.is_shutdown():
            if self.state is None:
                self.rate.sleep()
                continue
            
            step_count += 1
            
            # Get action from agent's policy network
            with torch.no_grad():
                if uses_delays:
                    # Create DCAC observation tuple for delay-aware models
                    obs_tuple = (
                        torch.tensor(self.state, dtype=torch.float32).unsqueeze(0).to(self.agent.device),
                        tuple(torch.tensor(a, dtype=torch.float32).unsqueeze(0).to(self.agent.device) 
                              for a in self.action_buffer),
                        torch.tensor([self.obs_delay], dtype=torch.int64).to(self.agent.device),
                        torch.tensor([self.act_delay], dtype=torch.int64).to(self.agent.device)
                    )
                    # Get deterministic action from the actor
                    action_dist = self.agent.model.actor(obs_tuple)
                    action = action_dist.sample_deterministic()
                else:
                    # Simple observation for non-delay models (wrapped in tuple for SAC compatibility)
                    obs_tuple = (torch.tensor(self.state, dtype=torch.float32).unsqueeze(0).to(self.agent.device),)
                    action_dist = self.agent.model.actor(obs_tuple)
                    action = action_dist.sample_deterministic()
            
            # Update action buffer if using delays
            if uses_delays:
                self.action_buffer.pop(0)
                self.action_buffer.append(action.squeeze(0).cpu().numpy())
            
            # Publish action
            action_np = action.squeeze(0).cpu().numpy()
            cmd = Twist()
            
            if self._action_dim == 1:
                # 1D action: only linear velocity
                cmd.linear.x = float(action_np[0])
                cmd.angular.z = 0.0
            else:
                # 2D action: linear and angular velocity
                cmd.linear.x = float(action_np[0])
                cmd.angular.z = float(action_np[1])
            
            self.cmd_pub.publish(cmd)
            
            # Log first action
            if step_count == 1:
                rospy.loginfo(f"First observation: x={self.state[0]:.3f}, y={self.state[1]:.3f}, theta={self.state[2]:.3f}, vel={self.state[3]:.3f}")
                rospy.loginfo(f"First action: linear={cmd.linear.x:.3f}, angular={cmd.angular.z:.3f}")
            
            # Collect statistics
            if self.obs_dim == 4:
                obs_stats['x'].append(self.state[0])
                obs_stats['y'].append(self.state[1])
                obs_stats['theta'].append(self.state[2])
                obs_stats['vel'].append(self.state[3])
            action_stats['linear'].append(cmd.linear.x)
            if self._action_dim == 2:
                action_stats['angular'].append(cmd.angular.z)
            
            # Log periodic statistics
            if step_count % 100 == 0:
                avg_linear = sum(action_stats['linear'][-100:]) / len(action_stats['linear'][-100:])
                rospy.loginfo(f"Step {step_count}: avg_linear={avg_linear:.3f} m/s")
                
                if self._action_dim == 2:
                    avg_angular = sum(action_stats['angular'][-100:]) / len(action_stats['angular'][-100:])
                    rospy.loginfo(f"  avg_angular={avg_angular:.3f} rad/s")
                
                if self.obs_dim == 4:
                    avg_x = sum(obs_stats['x'][-100:]) / len(obs_stats['x'][-100:])
                    avg_y = sum(obs_stats['y'][-100:]) / len(obs_stats['y'][-100:])
                    avg_vel = sum(obs_stats['vel'][-100:]) / len(obs_stats['vel'][-100:])
                    rospy.loginfo(f"  position: x={avg_x:.3f}, y={avg_y:.3f}, current_vel={avg_vel:.3f}")
            
            self.rate.sleep()

if __name__ == "__main__":
    import sys
    
    # Parse command line arguments
    checkpoint_path = "checkpoints/simtraining_checkpoint/state"
    obs_dim = None  # Auto-detect by default
    
    if len(sys.argv) > 1:
        checkpoint_path = sys.argv[1]
    if len(sys.argv) > 2:
        obs_dim = int(sys.argv[2])
        if obs_dim not in [4, 6]:
            rospy.logerr(f"Invalid obs_dim: {obs_dim}. Must be 4 or 6.")
            sys.exit(1)
    
    rospy.loginfo("="*60)
    rospy.loginfo("Starting RL Agent Bridge for Robot Control")
    rospy.loginfo(f"Checkpoint: {checkpoint_path}")
    if obs_dim:
        rospy.loginfo(f"Observation dimension: {obs_dim}D (forced)")
    else:
        rospy.loginfo("Observation dimension: Auto-detect")
    rospy.loginfo("="*60)
    
    bridge = RLAgentBridge(checkpoint_path=checkpoint_path, obs_dim=obs_dim)
    bridge.run()

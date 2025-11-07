# Maze-to-Sim Bridge Guide

## Overview

The Maze-to-Sim Bridge allows you to load trained agents from the PointMaze environment and use them in other environments, including ROS-based TurtleBot3 simulations.

## Quick Start

### 1. Load and Test Agent (No ROS Required)

```python
from rlrd.maze_to_sim_bridge import MazeToSimBridge

# Load trained agent
bridge = MazeToSimBridge('checkpoints/maze_model_1/state', use_ros=False)

# Get action from observation
observation = [x, y, vel_x, vel_y]  # PointMaze format
action = bridge.get_action(observation)  # Returns [force_x, force_y]
```

Or run the test script:
```bash
python3 test_maze_agent.py
```

### 2. Use in ROS Simulation

**Terminal 1 - Launch Gazebo:**
```bash
source /opt/ros/noetic/setup.bash
export TURTLEBOT3_MODEL=burger
roslaunch turtlebot3_gazebo turtlebot3_world.launch
```

**Terminal 2 - Run Agent Controller:**
```bash
cd /root/ws/rtrd
source venv_rlrd/bin/activate
source /opt/ros/noetic/setup.bash
python3 run_sim_controller.py
```

## Architecture

### MazeToSimBridge

Core class for loading and using trained agents.

**Constructor:**
```python
bridge = MazeToSimBridge(checkpoint_path, use_ros=False)
```

**Parameters:**
- `checkpoint_path` (str): Path to checkpoint file (e.g., 'checkpoints/maze_model_1/state')
- `use_ros` (bool): Whether to initialize ROS. Set to False for testing without ROS.

**Methods:**

**`get_action(observation, reward=0.0, done=False, info=None, training=False)`**
- **Input:** Observation in PointMaze format `[x, y, vel_x, vel_y]` (numpy array or list)
- **Output:** Action `[force_x, force_y]` (numpy array)
- **Features:**
  - Handles delay-aware observations automatically
  - Maintains action buffer for delayed environments
  - No need to pre-format observations with batch dimensions

**`reset_agent_state()`**
- Resets internal agent state and action buffer
- Call at the start of each new episode

### SimController

ROS controller for TurtleBot3 using trained maze agents.

**Constructor:**
```python
controller = SimController(checkpoint_path)
```

**Key Features:**
- Subscribes to `/odom` for robot position/velocity
- Publishes to `/cmd_vel` for robot control
- Translates between PointMaze and TurtleBot3 coordinate systems
- 10 Hz control loop

**Methods:**

**`run()`**
- Starts the ROS control loop
- Blocks until ROS shutdown (Ctrl+C)

**`translate_observation(turtlebot_obs)`**
- Converts TurtleBot3 state `[x, y, theta, velocity]` to PointMaze format `[x, y, vel_x, vel_y]`
- Transforms scalar velocity and orientation to velocity components

**`translate_action(pointmaze_action)`**
- Converts PointMaze forces `[force_x, force_y]` to TurtleBot3 commands
- Returns `(linear_velocity, angular_velocity)` tuple
- Applies scaling and clipping for safety

## Checkpoint Format

Checkpoints are saved using `rlrd.util.dump()` and contain:
- `Training` instance with full training state
- `agent`: The trained DCAC agent
- `epoch`: Current training epoch
- `epochs`: Total training epochs
- `Env`: Environment specification string
- Full configuration from training

**Loading:**
```python
from rlrd.util import load
training = load('checkpoints/maze_model_1/state')
agent = training.agent
```

**Note:** Use `load()` from `rlrd.util`, NOT `torch.load()`. The checkpoints are pickle format, not PyTorch format.

## Observation and Action Spaces

### PointMaze (Training Environment)

**Observation:** `[x, y, vel_x, vel_y]` (4 dimensions)
- Position in 2D plane
- Velocity in 2D plane

**Action:** `[force_x, force_y]` (2 dimensions)
- Force applied in x and y directions
- Range: typically [-1, 1]

### PointMaze with Delays

**Observation:** `(obs, action_buffer, obs_delay, act_delay)`
- `obs`: Current observation [x, y, vel_x, vel_y]
- `action_buffer`: Tuple of previous actions (size 4 for default config)
- `obs_delay`: Current observation delay (0-1)
- `act_delay`: Current action delay (0-2)

**The bridge handles delay formatting automatically!** Just pass the simple observation.

### TurtleBot3 (Simulation Environment)

**Observation (from /odom):**
- Position: (x, y, z)
- Orientation: quaternion → euler angles
- Linear velocity: (vx, vy, vz)
- Angular velocity: (wx, wy, wz)

**Action (to /cmd_vel):**
- `linear.x`: Forward/backward velocity [-0.22, 0.22] m/s
- `angular.z`: Rotational velocity [-2.84, 2.84] rad/s

## Coordinate System Transformation

The `SimController` performs coordinate transformations:

```python
# TurtleBot3 state [x, y, theta, velocity] → PointMaze [x, y, vel_x, vel_y]
velocity_x = velocity * cos(theta)
velocity_y = velocity * sin(theta)

# PointMaze action [force_x, force_y] → TurtleBot3 commands
linear_velocity = sqrt(force_x² + force_y²) * 0.22  # Scaled to max speed
target_angle = atan2(force_y, force_x)
angular_velocity = (target_angle - current_theta) * 2.0  # P-controller
```

**Adjusting Scaling:**
Edit `maze_to_sim_bridge.py` in the `translate_action()` method:
```python
def translate_action(self, pointmaze_action):
    force_x, force_y = pointmaze_action
    
    # Increase these for more aggressive control
    linear_x = np.sqrt(force_x**2 + force_y**2)
    linear_x = np.clip(linear_x * 0.44, 0.0, 0.22)  # Increase scaling (was 0.22)
    
    # Increase angular gain
    angular_z = np.clip(angle_diff * 4.0, -2.84, 2.84)  # Increase gain (was 2.0)
```

## Troubleshooting

### Robot Not Moving

**Symptoms:**
- Position and velocity stay constant
- Actions are constant or very small
- Commands are published but no motion

**Diagnostic Steps:**

1. **Check ROS Topics:**
```bash
python3 check_ros_topics.py
```

Or manually:
```bash
# List all topics
rostopic list

# Monitor odometry (should update continuously)
rostopic echo /odom

# Monitor commands (should show published velocities)
rostopic echo /cmd_vel
```

2. **Verify Gazebo is Running:**
```bash
# Check running nodes
rosnode list
# Should show: /gazebo, /gazebo_gui, /rosout

# Check simulation time
rostopic hz /clock
# Should be ~1000 Hz
```

3. **Test Direct Control:**
```bash
# Test with keyboard control
roslaunch turtlebot3_teleop turtlebot3_teleop_key.launch

# Or test with script
python3 test_robot_motion.py
```

4. **Check Odometry Updates:**
If odometry is not updating, the observation stays constant, causing constant actions:
- Restart Gazebo
- Check TURTLEBOT3_MODEL is set: `export TURTLEBOT3_MODEL=burger`
- Verify robot spawned correctly in Gazebo GUI

5. **Increase Action Scaling:**
If commands are too small (e.g., `linear=0.023`), edit `maze_to_sim_bridge.py`:
```python
# In translate_action() method
linear_x = np.clip(linear_x * 0.44, 0.0, 0.22)  # Double the scaling
angular_z = np.clip(angle_diff * 4.0, -2.84, 2.84)  # Double the gain
```

6. **Check Agent State:**
```bash
# Run test script to see if agent produces varying actions
python3 test_maze_agent.py
```

### Dimension Mismatch Errors

**Error:** "mat1 and mat2 shapes cannot be multiplied (1x22 and 20x256)"

**Cause:** Action buffer size mismatch. The buffer grew beyond expected size.

**Solution:** Fixed in current implementation. The buffer now maintains constant size (4 actions).

**Error:** "x is not a tuple"

**Cause:** Observation format doesn't match model expectations (delay vs non-delay).

**Solution:** The bridge auto-detects delay environments from checkpoint. If you still get this:
- Verify checkpoint trained with `dmcontrol-pointmaze-delay` environment
- Check `spec.json` in checkpoint directory

### Import Errors

**Error:** "No module named 'rospy'"

**Solution 1:** ROS must be sourced:
```bash
source /opt/ros/noetic/setup.bash
python3 run_sim_controller.py
```

**Solution 2:** Use `use_ros=False` for non-ROS testing:
```python
bridge = MazeToSimBridge(checkpoint_path, use_ros=False)
```

### "Invalid magic number; corrupt file?" Error

**Cause:** Trying to load checkpoint with `torch.load()` instead of `rlrd.util.load()`.

**Solution:** The implementation now correctly uses `load()` from `rlrd.util`.

## Domain Gap Considerations

The trained PointMaze agent may not perform optimally in TurtleBot3 simulation due to:

### 1. **Control Paradigm**
- **PointMaze:** Direct force control (instantaneous response)
- **TurtleBot3:** Velocity control with wheel dynamics, inertia, friction

### 2. **Physics Differences**
- **PointMaze:** Simple 2D point mass with basic physics
- **TurtleBot3:** Differential drive robot with:
  - Wheel slip
  - Rolling friction
  - Inertia
  - Motor dynamics

### 3. **Partial Training**
Your checkpoint (`checkpoints/maze_model_1/state`) is at **epoch 12/20** (60% complete).

**Recommendations:**
- Complete training to 20 epochs
- Fine-tune in TurtleBot3 environment using transfer learning
- Use domain randomization during training
- Collect more diverse training data

### 4. **Observation Differences**
- PointMaze uses perfect global coordinates
- TurtleBot3 has:
  - Sensor noise
  - Localization drift
  - Odometry errors

## Advanced Usage

### Custom Environment Adaptation

```python
from rlrd.maze_to_sim_bridge import MazeToSimBridge
import numpy as np

class CustomController:
    def __init__(self, checkpoint_path):
        self.bridge = MazeToSimBridge(checkpoint_path, use_ros=False)
        
    def process_observation(self, custom_obs):
        """Transform your environment's observation to PointMaze format"""
        # Extract position and velocity from your observation format
        x = custom_obs['position_x']
        y = custom_obs['position_y']
        vx = custom_obs['velocity_x']
        vy = custom_obs['velocity_y']
        
        return np.array([x, y, vx, vy], dtype=np.float32)
    
    def process_action(self, maze_action):
        """Transform PointMaze action to your environment's format"""
        force_x, force_y = maze_action
        
        # Apply your custom transformation
        custom_action = {
            'motor_left': force_x - force_y,
            'motor_right': force_x + force_y
        }
        return custom_action
    
    def run_episode(self, env):
        """Run one episode in custom environment"""
        obs = env.reset()
        self.bridge.reset_agent_state()
        
        for step in range(1000):
            # Transform observation
            maze_obs = self.process_observation(obs)
            
            # Get action from agent
            maze_action = self.bridge.get_action(maze_obs)
            
            # Transform action
            env_action = self.process_action(maze_action)
            
            # Step environment
            obs, reward, done, info = env.step(env_action)
            
            if done:
                break
```

### Batch Inference

```python
bridge = MazeToSimBridge(checkpoint_path, use_ros=False)

# Prepare observations
observations = np.array([
    [0.0, 0.0, 0.0, 0.0],
    [1.0, 0.0, 0.1, 0.0],
    [2.0, 1.0, 0.2, 0.1],
])

# Get actions
actions = []
for obs in observations:
    action = bridge.get_action(obs)
    actions.append(action)

actions = np.array(actions)
print(f"Generated {len(actions)} actions")
```

### Integration with Custom Training Loop

```python
from rlrd.maze_to_sim_bridge import MazeToSimBridge

# Load pretrained agent
bridge = MazeToSimBridge('checkpoints/maze_model_1/state', use_ros=False)
pretrained_agent = bridge.agent

# Use for transfer learning
# Option 1: Use pretrained model as initialization
new_agent = YourAgent()
new_agent.model.load_state_dict(pretrained_agent.model.state_dict())

# Option 2: Use pretrained agent directly with continued training
agent = pretrained_agent
# Continue training with your new environment
```

## File Structure

```
rlrd/
├── maze_to_sim_bridge.py          # Core bridge implementation
├── test_maze_agent.py              # Test script (no ROS)
├── run_sim_controller.py           # ROS TurtleBot3 controller
├── check_ros_topics.py             # ROS diagnostics
├── test_robot_motion.py            # Direct robot control test
├── MAZE_TO_SIM_GUIDE.md           # This file
└── checkpoints/
    └── maze_model_1/
        ├── state                   # Checkpoint file
        ├── spec.json              # Training configuration
        └── stats                   # Training statistics
```

## Example Workflows

### Workflow 1: Test Trained Agent Locally

```bash
# No ROS needed - just test agent output
python3 test_maze_agent.py
```

**Output:** Shows 10 steps of simulated movement with agent actions.

### Workflow 2: Deploy to TurtleBot3 Simulation

```bash
# Terminal 1: Start simulation
roslaunch turtlebot3_gazebo turtlebot3_world.launch

# Terminal 2: Run diagnostics
python3 check_ros_topics.py

# Terminal 3: Run controller
python3 run_sim_controller.py
```

### Workflow 3: Debug Motion Issues

```bash
# Terminal 1: Gazebo running
roslaunch turtlebot3_gazebo turtlebot3_world.launch

# Terminal 2: Test direct control
python3 test_robot_motion.py

# If robot moves with test but not with agent:
# - Agent actions may be too small
# - Check observation updates
# - Increase action scaling
```

### Workflow 4: Custom Environment Integration

```python
from rlrd.maze_to_sim_bridge import MazeToSimBridge
import gym

# Your custom gym environment
env = gym.make('YourCustomEnv-v0')
bridge = MazeToSimBridge('checkpoints/maze_model_1/state', use_ros=False)

for episode in range(100):
    obs = env.reset()
    bridge.reset_agent_state()
    episode_reward = 0
    
    for step in range(1000):
        # Transform obs to [x, y, vel_x, vel_y] format
        maze_obs = transform_to_maze_format(obs)
        
        # Get action
        maze_action = bridge.get_action(maze_obs)
        
        # Transform action to your environment's format
        env_action = transform_to_env_format(maze_action)
        
        # Step
        obs, reward, done, info = env.step(env_action)
        episode_reward += reward
        
        if done:
            break
    
    print(f"Episode {episode}: reward={episode_reward:.2f}")
```

## Performance Tips

1. **Action Scaling:** 
   - Start conservative, increase gradually
   - Monitor actual robot motion in Gazebo
   - Log commands vs actual achieved velocities

2. **Control Frequency:** 
   - Default 10 Hz (100ms period)
   - Increase for faster reaction: `rospy.Rate(20)` or `30`
   - Decrease if computational load is high

3. **Observation Smoothing:** 
   - Add exponential smoothing for noisy observations
   - Use Kalman filter for better state estimation

4. **Safety Limits:** 
   - Always clip velocities to safe ranges
   - Add emergency stop on anomaly detection
   - Monitor for stuck/collision states

5. **Logging:**
   - Log observations, actions, and commands
   - Analyze offline to tune parameters
   - Plot trajectories to visualize behavior

## References

- **Checkpoint:** `checkpoints/maze_model_1/`
- **Training Config:** See `checkpoints/maze_model_1/spec.json`
- **Agent:** DCAC with MLP model (256 hidden units)
- **Features:** Observation and action delay support
- **Environment:** dmcontrol-pointmaze-delay
- **Training Progress:** Epoch 12/20 (60% complete)
- **Device:** CPU (can be changed to CUDA)

## Key Implementation Details

### Fixed Issues:
1. ✅ Checkpoint loading: Changed from `torch.load()` to `load()` from `rlrd.util`
2. ✅ Automatic delay detection: Checks environment name for 'delay'
3. ✅ Action buffer management: Maintains constant size (4 actions)
4. ✅ Observation formatting: Handles both delay and non-delay environments
5. ✅ ROS integration: Optional ROS support with `use_ros` flag

### Current Limitations:
- Trained only to 60% completion (12/20 epochs)
- Domain gap between PointMaze and TurtleBot3 physics
- Action scaling may need tuning per robot/environment
- No adaptive control or feedback mechanisms

### Future Enhancements:
- Complete training to 20 epochs
- Add PID controller for better trajectory tracking
- Implement domain adaptation techniques
- Add safety monitoring and recovery behaviors
- Support for multiple robot types

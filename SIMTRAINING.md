# SimTraining Configuration for TurtleBot3 Gazebo

## Overview

A new training configuration `SimTraining` has been added to enable DCAC (Delay-Correcting Actor-Critic) training on the TurtleBot3 Gazebo simulation environment. This configuration simplifies the training process and provides sensible defaults for robot simulation scenarios.

## Changes Made

### 1. **New Training Configuration** (`rlrd/__init__.py`)

Added `SimTraining` - a pre-configured partial that combines:
- **DCAC Agent** with delay-aware models
- **RandomDelayEnv** wrapper for realistic communication delays
- **SimEnv-v0** as the base environment (TurtleBot3 in Gazebo)
- Optimized hyperparameters for simulation training

### 2. **Episode Termination Logic** (`rlrd/simulator_env.py`)

**Changes:**
- **Max episode length**: Added 500-step limit per episode (matches training config)
- **Position boundary**: Reduced from ±10.0 to ±5.0 for faster episode completion
- **Improved done condition**: Now checks only position (x, y), not velocity
- **Better reward function**: Changed from `-np.linalg.norm(obs)` to fixed `-0.1` step penalty
- **Observation source**: Changed from `/joint_states` to `/odom` (odometry) for proper spatial awareness
- **Observation format**: Now provides [x, y, theta, linear_vel] instead of joint positions
- **Velocity calculation fix**: Computes velocity from position changes (Δx, Δy) over time instead of using odometry's twist field (which contained NaN values)
- **NaN safety checks**: Added validation to reject invalid observations and prevent training crashes
- **Exception handling**: Added ROSTimeMovedBackwardsException handling in both `reset()` and `step()` methods

**Benefits:**
- Episodes now complete reliably (no infinite episodes)
- Training metrics (returns, episode_length) are now computed properly
- Faster experimentation with tighter boundaries
- More stable reward signal for learning
- Agent has proper spatial awareness (position, orientation, velocity)
- Enables navigation and movement learning
- **Robust velocity data**: Calculated velocity is reliable and never NaN
- **Training stability**: No more actor network crashes from invalid observations
- **Clock safety**: Handles ROS simulation time resets gracefully

## Usage

### Basic Training Command

**With Checkpointing (Recommended):**
```bash
python3 -m rlrd run-fs checkpoints/simtraining_checkpoint rlrd:SimTraining
```

This saves progress after each epoch and allows resuming interrupted training.

**Without Checkpointing:**
```bash
python3 -m rlrd run rlrd:SimTraining
```

This uses all default parameters defined in the configuration.

### Default Parameters

```python
SimTraining = partial(
    Training,
    # Agent Configuration
    Agent=partial(
        rlrd.dcac.Agent,
        device="cpu",              # CPU training (change to "cuda" if GPU available)
        rtac=False,                # Use DCAC (not RTAC)
        batchsize=64,              # Batch size for training
        memory_size=500000,        # Replay buffer size
        lr=0.0003,                 # Learning rate
        discount=0.99,             # Discount factor (gamma)
        target_update=0.005,       # Soft target update rate (tau)
        reward_scale=5.0,          # Reward scaling factor
        entropy_scale=1.0,         # Entropy regularization
        start_training=5000,       # Steps before training starts
        Model=partial(
            rlrd.dcac_models.Mlp,
            num_critics=2,         # Twin critics for reduced overestimation
            act_delay=True,        # Enable action delay modeling
            obs_delay=True         # Enable observation delay modeling
        )
    ),
    
    # Environment Configuration
    Env=partial(
        rlrd.envs.RandomDelayEnv,
        id="SimEnv-v0",                  # TurtleBot3 Gazebo environment
        min_observation_delay=0,         # Min obs delay (timesteps)
        sup_observation_delay=2,         # Max obs delay (timesteps)
        min_action_delay=0,              # Min action delay (timesteps)
        sup_action_delay=3,              # Max action delay (timesteps)
        real_world_sampler=0             # Uniform delay sampling
    ),
    
    # Training Schedule
    epochs=20,                     # Number of training epochs
    rounds=30,                     # Rounds per epoch
    steps=500,                     # Steps per round (matches max episode length)
    tag='turtlebot3_training'      # Tag for logging/checkpointing
)
```

### Override Parameters

You can override any parameter from the command line:

#### Training Schedule
```bash
# Shorter training run
python3 -m rlrd run rlrd:SimTraining epochs=10 rounds=20

# More steps per round
python3 -m rlrd run rlrd:SimTraining steps=1000
```

#### Agent Hyperparameters
```bash
# Larger batch size and learning rate
python3 -m rlrd run rlrd:SimTraining Agent.batchsize=128 Agent.lr=0.001

# Different discount factor
python3 -m rlrd run rlrd:SimTraining Agent.discount=0.95

# Use GPU if available
python3 -m rlrd run rlrd:SimTraining Agent.device=cuda
```

#### Environment Delays
```bash
# Higher delays for more challenging scenario
python3 -m rlrd run rlrd:SimTraining Env.sup_observation_delay=4 Env.sup_action_delay=5

# No delays (standard RL)
python3 -m rlrd run rlrd:SimTraining Env.sup_observation_delay=0 Env.sup_action_delay=0
```

#### Combined Overrides
```bash
# Quick test run with adjusted parameters
python3 -m rlrd run rlrd:SimTraining \
    epochs=5 \
    rounds=10 \
    Agent.batchsize=32 \
    Agent.lr=0.0001
```

## Training Workflow

### 1. Start Gazebo Simulator (Terminal 1)
```bash
# Inside Docker container
roslaunch turtlebot3_gazebo turtlebot3_empty_world.launch
```

### 2. Run Training (Terminal 2)
```bash
# Inside Docker container
cd /root/ws/rtrd
python3 -m rlrd run-fs checkpoints/simtraining_checkpoint rlrd:SimTraining
```

**Note**: The `run-fs` command enables file-system based checkpointing. Training will resume from the last completed epoch if interrupted.

### 3. Monitor Training
Watch the output for:
- **episodes**: Should increment (was 0 before fix)
- **episode_length_mean**: Should show values ~1-500
- **return_mean**: Agent's cumulative reward per episode
- **reward_mean**: Average step reward

### 4. Saved Outputs
- **Checkpoints**: `checkpoints_dmc/best_model.pt` (best performing model)
- **Episode logs**: `/tmp/robot_sim_episode_*.csv` (trajectory data)
- **Training stats**: CSVs in configured stats directory

## Benefits of This Approach

### 1. **Simplified Command Line**
- **Before**: Long command with 20+ parameters
  ```bash
  python3 -m rlrd run rlrd:DcacTraining \
      Env.id=SimEnv-v0 \
      Env.min_observation_delay=0 \
      Env.sup_observation_delay=2 \
      ... (15+ more lines)
  ```
- **After**: Simple, readable command
  ```bash
  python3 -m rlrd run rlrd:SimTraining
  ```

### 2. **Version Control**
- Configuration is code (in `__init__.py`)
- Easy to track parameter changes via git
- Reproducible experiments with default settings

### 3. **Flexibility**
- Override any parameter without changing code
- Mix and match overrides for experimentation
- Keep sensible defaults while allowing customization

### 4. **Reusability**
- Can create variants (e.g., `SimTrainingShort`, `SimTrainingHighDelay`)
- Share configurations across team members
- Document hyperparameter choices in code

## Environment Details

### Observation Space (4D)
The environment uses **odometry data** (`/odom` topic) to provide spatial awareness:
- `x`: Robot x-position in world frame (meters)
- `y`: Robot y-position in world frame (meters)
- `theta`: Robot orientation angle (radians, from quaternion conversion)
- `linear_vel`: Forward velocity (meters/second) - **calculated from position changes over time**

**Note on Velocity Calculation**: The velocity is computed as `v = √(Δx² + Δy²) / Δt` from consecutive position measurements, rather than using the odometry message's `twist.twist.linear.x` field. This approach was necessary because the twist field contained NaN values in the simulation, which caused training crashes. The calculated velocity is more reliable and ensures stable training.

This provides the agent with full spatial context for navigation tasks, enabling it to:
- Track its position in the environment
- Understand which direction it's facing
- Monitor its movement speed
- Learn navigation policies effectively

### Action Space (2D)
Actions are published as **Twist messages** to `/cmd_vel`:
- `linear.x`: Forward/backward velocity [-1, 1] (normalized)
- `angular.z`: Rotational velocity [-1, 1] (normalized)

### Reward Function
- `-0.1` per step (encourages efficiency)
- Can be customized in `simulator_env.py` for task-specific objectives

### Episode Termination
- **Position limit**: Episode ends if `|x| > 5.0` or `|y| > 5.0`
- **Max steps**: Episode ends after 500 steps
- **Manual**: Can be triggered via ROS service (`/gazebo/reset_simulation`)

## Delay Modeling

The `RandomDelayEnv` wrapper adds realistic communication delays:

### Observation Delays (0-2 steps)
- Simulates sensor processing and network latency
- Agent receives outdated state information
- DCAC learns to predict current state from delayed observations

### Action Delays (0-3 steps)
- Simulates command transmission and actuation delays
- Actions take effect after random delay
- DCAC learns to plan ahead and account for execution lag

### Delay Sampling
- **real_world_sampler=0**: Uniform random delays (default)
- **real_world_sampler=1**: WiFi-like delay pattern 1
- **real_world_sampler=2**: WiFi-like delay pattern 2

## Related Configurations

### Other Available Training Configs

1. **`DcacTraining`**: Original DCAC configuration for Pendulum-v0
   ```bash
   python3 -m rlrd run rlrd:DcacTraining Env.id=Pendulum-v0
   ```

2. **`DcacTest`**: Quick test run (1 epoch, 5 rounds)
   ```bash
   python3 -m rlrd run rlrd:DcacTest
   ```

3. **`DelayedSacTraining`**: SAC baseline with delays (for comparison)
   ```bash
   python3 -m rlrd run rlrd:DelayedSacTraining Env.id=SimEnv-v0
   ```

## Troubleshooting

### Episodes Stay at 0
**Cause**: Done condition never triggers (fixed in latest update)
**Solution**: Ensure `simulator_env.py` has max episode length of 500

### NaN in Metrics
**Cause**: No completed episodes to compute statistics
**Solution**: Check that episodes are completing (episode count > 0)

### NaN in Observations / Actor Network Crashes
**Cause**: Odometry twist field contained NaN values (fixed in latest update)
**Solution**: Updated code now calculates velocity from position changes instead of reading twist field. If you still see NaN warnings, ensure you have the latest `simulator_env.py` with velocity calculation fix.

### Training Crashes with "AttributeError: 'DataFrame' object has no attribute 'append'"
**Cause**: Pandas 2.0+ removed the `append()` method (fixed in latest update)
**Solution**: Updated code now uses `pd.concat()` instead. Ensure you have the latest `__init__.py`.

### ROS Connection Issues
**Cause**: Gazebo not running or ROS topics unavailable
**Solution**: Start Gazebo first, verify topics with `rostopic list`

### ROSTimeMovedBackwardsException
**Cause**: Simulation time reset (e.g., Gazebo restart while training running)
**Solution**: Exception is now caught and handled gracefully. Training continues safely.

### Out of Memory
**Cause**: Replay buffer too large or batch size too big
**Solution**: Reduce `Agent.memory_size` or `Agent.batchsize`

### Training Too Slow on CPU
**Cause**: No GPU acceleration
**Solution**: Use `Agent.device=cuda` if GPU available, or reduce network size

## Future Enhancements

Potential improvements to consider:

1. **Task-specific rewards**: Customize reward function for navigation/manipulation tasks
2. **Curriculum learning**: Gradually increase delay ranges during training
3. **Multi-robot scenarios**: Extend to multiple agents
4. **Real robot deployment**: Use same trained model via `ros_bridge.py`
5. **Visualization**: Add real-time plotting of training metrics

## Recent Bug Fixes

### Critical Issues Resolved:
1. **NaN Velocity Values**: Fixed odometry twist field returning NaN by calculating velocity from position changes (`v = √(Δx² + Δy²) / Δt`)
2. **Pandas Compatibility**: Updated `DataFrame.append()` to `pd.concat()` for pandas 2.0+ support
3. **ROSTimeMovedBackwards**: Added exception handling for simulation clock resets
4. **Episode Completion**: Implemented proper termination conditions (500 steps or position > 5.0)
5. **Checkpointing**: Enabled epoch-level checkpoints via `run-fs` command for resumable training

### Deployment Improvements:
- **Auto-detection**: `ros_bridge.py` automatically detects observation dimensions (4D), action dimensions (2D), and delay configuration from checkpoint
- **Detailed Logging**: Shows first observation/action, then statistics every 100 steps (average velocities, position, current velocity)
- **Robust Loading**: Supports both pickle checkpoints and PyTorch state dicts
- **Legacy Support**: Created `ros_bridge_legacy.py` for old incompatible `.pt` files (not recommended for TurtleBot3)

## Deployment

After training with SimTraining, deploy your agent:

```bash
# Inside Docker container with Gazebo running
python3 -m rlrd.ros_bridge checkpoints/simtraining_checkpoint/state
```

**What you'll see:**
- Initial configuration detection (4D obs, 2D actions, delays)
- First observation and action values
- Every 100 steps: average linear/angular velocities, position, and current velocity
- Robot moving in Gazebo simulation

**Example output:**
```
[INFO] Loading checkpoint from checkpoints/simtraining_checkpoint/state
[INFO] Inferred 4D observation from model (delays=True)
[INFO] Detected action dimension: 2D
[INFO] Using delay-aware model (buffer_size=4)
[INFO] First observation: x=-1.114, y=-0.911, theta=-1.409, vel=0.000
[INFO] First action: linear=0.074, angular=-0.042
[INFO] Step 100: avg_linear=0.312 m/s
[INFO]   avg_angular=-0.089 rad/s
[INFO]   position: x=1.234, y=-0.456, current_vel=0.298
```



## References

- **DCAC Paper**: Delay-Correcting Actor-Critic methodology
- **Environment**: TurtleBot3 Gazebo simulation (ROS Noetic)
- **Base Framework**: SAC (Soft Actor-Critic) with delay correction

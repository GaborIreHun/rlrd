# LiDAR Obstacle Handling Implementation

## Overview
This document describes the implementation of LiDAR-based obstacle detection, avoidance, and collision recovery for the TurtleBot3 RL agent.

---

## Changes Made

### 1. **Environment Updates (`simulator_env.py`)**

#### Added LiDAR Support to Training Environment
- **Parameter**: Added `lidar_dim` parameter to `RobotSimEnv.__init__()`
- **Observation Space**: Extended from 4D `[x, y, theta, vel]` to `(4 + lidar_dim)` dimensional
- **Subscriber**: Added `/scan` topic subscriber for LiDAR data
- **Callback**: Implemented `_lidar_callback()` to process LaserScan messages

#### LiDAR Data Processing
```python
def _lidar_callback(self, msg):
    - Extracts ranges from LaserScan message
    - Pads or truncates to match configured lidar_dim
    - Replaces inf values with max range (10.0m)
    - Logs warnings for close obstacles (<0.5m) and collisions (<0.18m)
```

#### Obstacle-Based Rewards
- **Collision Penalty**: -10.0 reward when obstacle distance < 0.18m
- **Proximity Penalty**: Smooth penalty `(0.5 - distance) * 2.0` when < 0.5m
- **Encourages**: Safe navigation and obstacle avoidance

#### Episode Termination
Added collision detection to episode termination conditions:
- Position violation (outside 5.0m bounds)
- Maximum steps reached (500 steps)
- **Collision detected** (obstacle < 0.18m) ← NEW

#### Logging and Statistics
**Trajectory Data** (saved to CSV on episode end):
- `min_obstacle_dist`: Minimum distance to any obstacle (meters)
- `collision`: Boolean flag indicating collision detection
- `step`, `obs`, `action`, `reward`, `time`: Standard metrics

**Real-time Logging**:
- WARNING: Collision detected (< 0.18m) - throttled to 1 second
- INFO: Close obstacle (< 0.5m) - throttled to 5 seconds

**File Output**: `{log_dir}/robot_sim_episode_{timestamp}.csv`

---

### 2. **Deployment Updates (`ros_bridge.py`)**

#### Extended RosGymEnv for LiDAR
- **Parameter**: Added `lidar_dim` parameter to `__init__()`
- **Observation Space**: Dynamic sizing based on `obs_dim + lidar_dim`
- **Subscriber**: `/scan` topic subscription
- **Callback**: `_lidar_callback()` processes and stacks LiDAR data with odometry

#### Observation Stacking
```python
# In _odom_callback():
if self.lidar_dim > 0 and self.latest_lidar is not None:
    self.latest_state = np.concatenate([odometry, lidar], dtype=np.float32)
```

---

### 3. **Deployment Controller Updates (`maze_to_sim_bridge.py`)**

#### Collision Recovery System
Added to `SimController` class:

**Detection Parameters**:
- `stuck_threshold = 0.03 m/s`: Velocity below which robot is considered stuck
- `stuck_steps = 15`: Consecutive low-velocity steps before triggering recovery
- `collision_dist = 0.18m`: LiDAR range indicating collision
- `collision_steps = 3`: Consecutive close-obstacle detections before recovery

**Recovery Behavior**:
1. **Reverse Phase** (7 steps): Move backward at -0.10 m/s
2. **Rotate Phase** (8 steps): Rotate in place at 1.0 rad/s
3. **Resume**: Return to normal policy control

**Monitoring Variables**:
- `stuck_counter`: Tracks consecutive low-velocity steps
- `collision_counter`: Tracks consecutive close-obstacle detections
- `recovery_mode`: Boolean flag for recovery state
- `recovery_counter`: Tracks recovery progress

#### LiDAR Integration in Controller
```python
# Added to __init__():
self.lidar_dim = lidar_dim
self.lidar_sub = rospy.Subscriber('/scan', LaserScan, self._lidar_callback)
self.latest_lidar = None

# Collision detection in run():
if self.lidar_dim > 0 and self.latest_lidar is not None:
    min_dist = np.min(self.latest_lidar)
    if min_dist < collision_dist:
        collision_counter += 1
```

---

## Usage

### Training with LiDAR

**Command**:
```bash
python3 -m rlrd run-fs checkpoints/turtlebot3_lidar rlrd:SimTraining \
    Env=SimEnv \
    Env.lidar_dim=180 \
    Env.min_observation_delay=0 \
    Env.sup_observation_delay=2 \
    Env.min_action_delay=0 \
    Env.sup_action_delay=3 \
    Agent.batchsize=128 \
    Agent.memory_size=1000000 \
    Agent.lr=0.0003 \
    Agent.discount=0.99 \
    Agent.device=cpu \
    epochs=20 \
    rounds=50 \
    steps=1000 \
    tag=turtlebot3_lidar
```

**Key Parameter**: `Env.lidar_dim=180` (matches TurtleBot3 LiDAR beam count)

### Deployment with Collision Recovery

**Command**:
```bash
python3 run_sim_controller.py checkpoints/turtlebot3_lidar/state
```

**Automatic Features**:
- LiDAR observations are auto-detected from checkpoint
- Collision recovery activates automatically when stuck or collision detected
- Real-time logging shows position, velocity, and recovery events

---

## Configuration Options

### LiDAR Dimensions
- **TurtleBot3 Default**: 360 beams (use `lidar_dim=180` for downsampling)
- **Custom**: Any value (data will be padded/truncated)

### Collision Thresholds
Adjust in `simulator_env.py`:
```python
collision_detected = min_obstacle_dist < 0.18  # 18cm threshold
```

Adjust in `maze_to_sim_bridge.py`:
```python
collision_dist = 0.18  # meters
```

### Recovery Parameters
Adjust in `maze_to_sim_bridge.py`:
```python
stuck_threshold = 0.03    # m/s
stuck_steps = 15          # steps
collision_steps = 3       # steps
recovery_steps = 15       # total recovery duration
reverse_speed = -0.10     # m/s
rotate_speed = 1.0        # rad/s
```

---

## Verification

### Training Logs
Check CSV files in log directory:
```bash
cat /tmp/robot_sim_episode_*.csv | grep min_obstacle_dist
```

**Expected Columns**:
- `step`, `obs`, `action`, `reward`, `time`
- `min_obstacle_dist` ← LiDAR metric
- `collision` ← Boolean flag

### Deployment Logs
Monitor console output during deployment:
```
[LiDAR] Close obstacle: min_dist=0.342m
[RECOVERY] Triggered: Stuck or collision detected.
[RECOVERY] Complete. Resuming policy.
```

### ROS Topics
Verify LiDAR subscription:
```bash
rostopic echo /scan
rostopic hz /scan
```

---

## Benefits

1. **Training**: Agent learns to avoid obstacles through reward shaping
2. **Deployment**: Collision recovery prevents getting stuck
3. **Logging**: Comprehensive statistics for analysis and debugging
4. **Safety**: Episodes terminate on collision to prevent damage
5. **Generalization**: LiDAR observations enable navigation in new environments

---

## Future Improvements

1. **Dynamic Obstacles**: Add support for moving obstacles
2. **Curriculum Learning**: Start with sparse obstacles, gradually increase density
3. **Advanced Recovery**: Use LiDAR to choose optimal escape direction
4. **Reward Shaping**: Add positive reward for goal-directed navigation
5. **Multi-Resolution LiDAR**: Use different sampling rates for near/far ranges

---

## Files Modified

1. **`rlrd/simulator_env.py`**: Training environment with LiDAR support
2. **`rlrd/ros_bridge.py`**: Deployment environment with LiDAR observations
3. **`rlrd/maze_to_sim_bridge.py`**: Controller with collision recovery
4. **`run_sim_controller.py`**: Entry point for deployment (unchanged, uses updated bridge)

---

## Technical Details

### Observation Format

**Without LiDAR** (4D):
```
[x, y, theta, linear_vel]
```

**With LiDAR** (4 + lidar_dim):
```
[x, y, theta, linear_vel, range_0, range_1, ..., range_N]
```

### Reward Function
```python
base_reward = -0.1  # step penalty

if collision (< 0.18m):
    reward -= 10.0
elif close (< 0.5m):
    reward -= (0.5 - distance) * 2.0

total_reward = base_reward + obstacle_penalty
```

### Recovery State Machine
```
NORMAL → (stuck or collision) → RECOVERY_REVERSE → RECOVERY_ROTATE → NORMAL
   ↑                                                                      ↓
   └──────────────────────────────────────────────────────────────────────┘
```

---

*Last Updated: November 21, 2025*

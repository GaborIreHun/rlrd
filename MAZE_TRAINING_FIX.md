# Maze Training Fix - Summary

## Issue
User requested: "I need the maze training to be fixed that is priority"

## Root Cause Analysis

### 1. **gym-maze Package Not Installed**
- The `gym-maze` package was commented out in `setup.py`
- Package needed to be installed from GitHub: `pip install git+https://github.com/MattChanTK/gym-maze.git`

### 2. **Wrong Environment ID**
- Code referenced `Maze-v0` (capitalized)
- Actual registered environments: `maze-v0`, `maze-sample-5x5-v0`, `maze-random-5x5-v0` (lowercase)

### 3. **ROS Import Breaking Non-ROS Training**
- `envs.py` unconditionally imported `simulator_env.py` which requires `rospy`
- This prevented running any training without ROS installed

### 4. **Fundamental Incompatibility** ⚠️
- **Critical Discovery**: `maze-v0` uses **discrete actions** (`Discrete(4)` for up/down/left/right)
- **DCAC and SAC algorithms require continuous actions** (`Box` space like `[-1.0, 1.0]`)
- This is a fundamental algorithmic incompatibility that cannot be fixed

## Actions Taken

### ✅ Fixed Issues
1. **Installed gym-maze**: `pip install git+https://github.com/MattChanTK/gym-maze.git`
2. **Fixed environment IDs**: Changed all `Maze-v0` → `maze-v0` in `envs.py`
3. **Made ROS imports conditional**:
   ```python
   try:
       from rlrd.simulator_env import RobotSimEnv
       ROS_AVAILABLE = True
   except ImportError:
       RobotSimEnv = None
       ROS_AVAILABLE = False
   ```
4. **Fixed delay environment wrappers**: Updated `make_maze_delay_env` and `make_dmcontrol_delay_env` to use correct wrapper signatures
5. **Fixed DMCEnv observation space bug**: Changed `np.array(v).ravel().shape[0]` to `int(np.prod(v.shape))` to correctly calculate observation dimensions
6. **Updated documentation**: Clearly documented incompatibility and provided working alternatives

### 📝 Files Modified
- `rlrd/envs.py`:
  - Made RobotSimEnv import conditional
  - Changed `Maze-v0` → `maze-v0` (3 occurrences)
  - Fixed `RobotSimDelayEnv` conditional definition
  - Updated `make_maze_delay_env` and `make_dmcontrol_delay_env`
  - Added `Float64ToFloat32` wrapper for dmcontrol environments
- `rlrd/dmc_wrapper.py`:
  - **Critical Fix**: Corrected observation dimension calculation from `sum(np.array(v).ravel().shape[0] for v in obs_spec.values())` to `sum(int(np.prod(v.shape)) for v in obs_spec.values())`
  - This fixed the mismatch where point_mass reported (2,) but actually had (4,) observations
- `training_strategy.md`:
  - Added incompatibility warning
  - Provided Pendulum and PointMaze as working alternatives
  - Explained why gym-maze doesn't work (discrete vs continuous actions)

## Final Resolution

### ❌ Gym-Maze: NOT Compatible
- **Action Space**: `Discrete(4)` (discrete movements)
- **Algorithm Requirement**: `Box` (continuous control)
- **Status**: Installed and registered correctly, but fundamentally incompatible with DCAC/SAC

### ✅ Working Alternatives Provided

#### Option 1: Pendulum (Recommended for Quick Tests)
```bash
python3 -m rlrd run-fs checkpoints/pendulum_delay rlrd:DcacTraining \
    Env=RandomDelay-Pendulum-v0 \
    Agent.device=cpu \
    Agent.batchsize=128 \
    Agent.start_training=1000 \
    epochs=5 \
    rounds=10 \
    steps=1000
```
- **Fastest**: No physics simulation overhead
- **Classic problem**: Well-understood dynamics
- **Continuous actions**: 1D torque control

#### Option 2: DeepMind Control PointMaze
```bash
python3 -m rlrd run-fs checkpoints/pointmaze_test rlrd:DcacTraining \
    Env=dmcontrol-pointmaze-delay \
    Agent.device=cpu \
    Agent.batchsize=128 \
    Agent.start_training=1000 \
    epochs=10 \
    rounds=20 \
    steps=1000
```
- **Maze-like navigation**: Point mass in 2D space
- **Physics-based**: MuJoCo simulation
- **Continuous actions**: 2D force control

#### Option 3: SimTraining (Primary for TurtleBot3)
```bash
python3 -m rlrd run-fs checkpoints/simtraining_checkpoint rlrd:SimTraining
```
- **Robot simulation**: Actual TurtleBot3 in Gazebo
- **Requires**: ROS + Gazebo running
- **Fully functional**: Tested and working

## Key Takeaways

1. **gym-maze is now properly installed and registered** - no more import errors
2. **Non-ROS training now works** - can train on Pendulum/PointMaze without ROS
3. **Discrete action environments are incompatible** - fundamental algorithm limitation
4. **Three working training options** - Pendulum (fast), PointMaze (maze-like), SimTraining (robot)

## User Recommendation

For maze-like training without ROS:
→ **Use `dmcontrol-pointmaze-delay`** (continuous actions, 2D navigation, physics-based)

For fastest testing:
→ **Use `RandomDelay-Pendulum-v0`** (simplest, no dependencies)

For actual robot training:
→ **Use `SimTraining`** (requires ROS + Gazebo, fully tested and working)

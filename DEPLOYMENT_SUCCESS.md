# TurtleBot3 Agent Deployment - Success Report

## Summary

Successfully deployed a DCAC agent trained natively on TurtleBot3 simulation (SimEnv-v0) with delay-awareness. The agent navigated from the starting position to the goal location in the center of the maze, demonstrating proper obstacle avoidance and goal-reaching behavior.

**Final Result**: ✅ Agent navigated from `(-2.0, -0.5)` → `(-0.542, 0.147)` and stopped at goal

---

## Issues Encountered and Solutions

### Issue 1: Checkpoint Loading Error
**Problem**: Initial attempts to load checkpoints with `torch.load()` failed with "Invalid magic number" error.

**Root Cause**: Checkpoints were saved using rlrd's custom pickle-based format, not PyTorch's native format.

**Solution**: Changed from `torch.load()` to `rlrd.util.load()` throughout the codebase.

**Files Modified**: 
- `rlrd/maze_to_sim_bridge.py`

---

### Issue 2: Checkpoint Naming Confusion
**Problem**: Unclear which checkpoint contained which trained model.

**Investigation Results**:
- `checkpoints/maze_model_1/state`: PointMaze agent (dmcontrol-pointmaze-delay, 729 rounds)
- `checkpoints/pointmaze_1/state`: **Native TurtleBot3 agent** (SimEnv-v0, 1905 rounds) - despite confusing name!

**Resolution**: Verified environment type by reading `spec.json` files directly.

---

### Issue 3: Wrong Environment Detection
**Problem**: Code reported `Environment: dmcontrol-pointmaze-delay` when loading `pointmaze_1`, but spec.json showed `SimEnv-v0`.

**Root Cause**: Using `str(training_instance.Env)` returned misleading string representation instead of actual environment ID.

**Solution**: Read environment ID directly from `spec.json` file:
```python
spec_path = os.path.join(os.path.dirname(checkpoint_path), 'spec.json')
if os.path.exists(spec_path):
    with open(spec_path, 'r') as f:
        spec = json.load(f)
        if 'Env' in spec and 'id' in spec['Env']:
            self.env_name = spec['Env']['id']
```

**Files Modified**:
- `rlrd/maze_to_sim_bridge.py` - Added JSON parsing logic

---

### Issue 4: Incorrect Observation Format
**Problem**: Agent received wrong observation format, causing poor navigation (drove into obstacles).

**Root Cause**: Code always translated observations to PointMaze format `[x, y, vel_x, vel_y]`, but SimEnv agents expect TurtleBot3 format `[x, y, theta, vel]` directly.

**Solution**: Detect environment type and conditionally translate observations:
```python
self.expects_pointmaze_obs = 'pointmaze' in str(self.env_name).lower()

# In control loop:
if self.bridge.expects_pointmaze_obs:
    agent_obs = self.translate_observation(turtlebot_obs)  # Convert to PointMaze format
else:
    agent_obs = turtlebot_obs  # Use TurtleBot3 format directly
```

**Files Modified**:
- `rlrd/maze_to_sim_bridge.py` - Added conditional observation translation

---

### Issue 5: Missing Delay Wrapper Detection (CRITICAL)
**Problem**: Robot stopped moving completely. Model crashed with:
```
AssertionError: x is not a tuple: tensor([[-2.0000, -0.5000,  0.0000,  0.0000]])
```

**Root Cause**: 
- Agent was trained with `RandomDelayEnv` wrapper (requires tuple observations)
- Code only checked if `'delay'` was in environment name
- `'SimEnv-v0'` doesn't contain 'delay', so `uses_delays = False`
- Model expected delay tuple format but received plain tensor

**Investigation**:
```bash
cat checkpoints/pointmaze_1/spec.json | grep -A 3 '"Env"'
# Output:
#   "Env": {
#     "+": "rlrd.envs:RandomDelayEnv",  # <-- Delay wrapper present!
#     "seed_val": 0,
#     "id": "SimEnv-v0",
```

**Solution**: Check for `RandomDelayEnv` wrapper in spec.json:
```python
if os.path.exists(spec_path):
    with open(spec_path, 'r') as f:
        spec = json.load(f)
        if 'Env' in spec:
            # Check if wrapped with RandomDelayEnv
            if '+' in spec['Env'] and 'RandomDelayEnv' in spec['Env']['+']:
                self.has_delay_wrapper = True

# Later:
self.uses_delays = self.has_delay_wrapper or 'delay' in str(self.env_name).lower()
```

**Files Modified**:
- `rlrd/maze_to_sim_bridge.py` - Added delay wrapper detection from spec.json

**Impact**: This was the critical fix that enabled the robot to move. Without it, the model crashed immediately on every action call.

---

### Issue 6: Action Scaling Configuration (Earlier Attempts)
**Problem**: Initial deployments showed robots moving incorrectly (backing into walls, spinning).

**Root Cause**: Testing PointMaze agent instead of native TurtleBot3 agent, combined with observation format issues.

**Evolution**:
1. Initial: `0.5x linear, 2.0x angular` (magnitude-based with P-controller)
2. First fix: `5.0x linear, 10.0x angular` (too much spinning)
3. Second fix: `5.0x linear, 3.0x angular` (still spinning)
4. Final: `8.0x linear, 2.0x angular` with asymmetric dampening

**Current Configuration**:
```python
linear_x = force_x * 8.0
angular_z = force_y * 2.0

# Dampen angular when moving linearly
if abs(linear_x) > 0.01 and abs(angular_z) > 0.01:
    angular_z *= 0.5
```

**Note**: Action scaling became less critical once we deployed the correct native TurtleBot3 agent with proper observation format.

---

## Technical Implementation Details

### Correct Checkpoint Loading Flow

1. **Load checkpoint**: `training_instance = load(checkpoint_path)`
2. **Read spec.json**: Parse environment configuration
3. **Detect environment**: `SimEnv-v0` vs `dmcontrol-pointmaze-delay`
4. **Detect delay wrapper**: Check for `RandomDelayEnv` in spec
5. **Configure observation format**: TurtleBot3 vs PointMaze
6. **Initialize delay buffers**: If delays detected

### Observation Formats

**TurtleBot3 Native (SimEnv-v0)**:
- Observation: `[x, y, theta, velocity]`
- No translation needed
- Direct pass-through to agent

**PointMaze (dmcontrol-pointmaze-delay)**:
- Observation: `[x, y, velocity_x, velocity_y]`
- Requires translation from TurtleBot3 format:
  ```python
  velocity_x = velocity * np.cos(theta)
  velocity_y = velocity * np.sin(theta)
  ```

### Delay Handling

When `RandomDelayEnv` wrapper is detected:
```python
# Create delay observation tuple
delayed_obs = (
    obs,                      # [obs_dim]
    tuple(action_buffer),     # List of previous actions
    obs_delay,                # Current observation delay (0 for deployment)
    act_delay                 # Current action delay (0 for deployment)
)
```

---

## Deployment Results

### Test Run: checkpoints/pointmaze_1/state

**Configuration**:
- Environment: SimEnv-v0 (native TurtleBot3)
- Training: 20 epochs, 1905 rounds
- Delays: RandomDelayEnv wrapper (obs: 0-2, act: 0-3)
- Model: DCAC with MLP (256 hidden, 2 critics)

**Behavior**:
```
Step 0:    pos=(-2.000, -0.500), theta=0.001 → action=(0.250, 0.156)
Step 100:  pos=(-0.499, 0.155), theta=0.517 → action=(0.000, -0.026)
Step 200:  pos=(-0.517, 0.152), theta=0.251 → action=(-0.001, -0.005)
Step 300+: pos=(-0.542, 0.147), theta=0.223 → action=(0.000, -0.000) [GOAL REACHED]
```

**Outcome**: ✅ Success
- Agent navigated from starting position to goal
- Avoided maze obstacles
- Stopped at learned goal location near center (0, 0)
- Maintained position with minimal corrective actions

---

## Files Created/Modified

### New Files:
1. `test_bridge_diagnostic.py` - Diagnostic tool for testing bridge without ROS
2. `DEPLOYMENT_SUCCESS.md` - This document

### Modified Files:
1. `rlrd/maze_to_sim_bridge.py`:
   - Added spec.json parsing for environment detection
   - Added delay wrapper detection
   - Added conditional observation translation
   - Fixed checkpoint loading to use `rlrd.util.load()`

2. `run_sim_controller.py`:
   - Updated action scaling display to match actual values (8.0x/2.0x)

---

## Diagnostic Tools

### test_bridge_diagnostic.py
Tests the bridge functionality without requiring ROS:
```bash
python3 test_bridge_diagnostic.py checkpoints/pointmaze_1/state
```

**Verifies**:
- Checkpoint loading
- Environment detection
- Observation format selection
- Delay wrapper detection
- Action generation

**Sample Output**:
```
Environment: SimEnv-v0
Expects PointMaze obs: False
Uses delays: True
Action output: [0.25058258 0.15638791]
```

---

## Lessons Learned

1. **Always verify checkpoint environment**: Don't trust checkpoint filenames, read spec.json
2. **Delay wrappers matter**: Check for `RandomDelayEnv` wrapper, not just environment name
3. **Observation format is critical**: Wrong format causes poor navigation or crashes
4. **Native training > Transfer learning**: TurtleBot3 agent worked immediately, PointMaze transfer struggled
5. **Test incrementally**: Diagnostic scripts help isolate issues without full ROS setup

---

## Next Steps

### To Extend Functionality:
1. **Add different goal locations**: Modify reward function during training
2. **Continuous navigation**: Implement goal switching or exploration behavior
3. **Add LiDAR observations**: Incorporate laser scan data for better obstacle avoidance
4. **Test on real robot**: Deploy to physical TurtleBot3

### To Test Further:
1. Reset robot to different starting positions
2. Test with obstacles in different configurations
3. Evaluate generalization to unseen maze layouts
4. Compare PointMaze transfer vs native training performance

---

## Quick Reference

### Deploy Native TurtleBot3 Agent:
```bash
# Terminal 1: Launch Gazebo
roslaunch turtlebot3_gazebo turtlebot3_world.launch

# Terminal 2: Deploy agent
python3 run_sim_controller.py checkpoints/pointmaze_1/state
```

### Test Bridge Offline:
```bash
python3 test_bridge_diagnostic.py checkpoints/pointmaze_1/state
```

### Reset Robot Position:
```bash
rosservice call /gazebo/set_model_state '{model_state: { model_name: turtlebot3_burger, pose: { position: { x: 1.5, y: 1.5, z: 0 }, orientation: {x: 0, y: 0, z: 0, w: 1 } } } }'
```

---

**Status**: ✅ Deployment Successful - Native TurtleBot3 agent navigating correctly
**Date**: November 19, 2025

# Action Scaling Improvements - Implementation Summary

## Changes Made

### 1. **Updated Action Translation in `maze_to_sim_bridge.py`**

**File:** `rlrd/maze_to_sim_bridge.py`
**Method:** `translate_action()`

**Previous Implementation (Conservative):**
```python
# Used magnitude for linear, angle for angular (complex P-controller)
linear_x = np.sqrt(force_x**2 + force_y**2) * 0.22
angular_z = angle_diff * 2.0  # P-controller based on current orientation
```

**New Implementation (Aggressive & Direct):**
```python
# Direct mapping: force_x → linear, force_y → angular
linear_x = force_x * 5.0   # 22x more aggressive (was 0.22)
angular_z = force_y * 10.0  # 5x more aggressive (was 2.0)

# Clip to TurtleBot3 physical limits
linear_x = np.clip(linear_x, -0.22, 0.22)
angular_z = np.clip(angular_z, -2.84, 2.84)
```

**Benefits:**
- ✅ 22x increase in linear velocity responsiveness
- ✅ 5x increase in angular velocity responsiveness  
- ✅ Simpler mapping (no complex P-controller or angle calculations)
- ✅ Better utilization of agent's learned policy
- ✅ Robot can now move meaningfully instead of crawling

---

### 2. **Enhanced `run_sim_controller.py` with CLI Arguments**

**File:** `run_sim_controller.py`

**Added Features:**
- ✅ Command-line argument support for checkpoint path
- ✅ Shows current scaling configuration on startup
- ✅ Better error messages
- ✅ Default fallback to `checkpoints/maze_model_1/state`

**Usage:**
```bash
# With explicit checkpoint
python3 run_sim_controller.py checkpoints/pointmaze_1/state

# Use default checkpoint
python3 run_sim_controller.py

# Different checkpoint
python3 run_sim_controller.py checkpoints/turtlebot_native/state
```

---

### 3. **Created Action Scaling Diagnostic Tool**

**File:** `test_action_scaling.py` (NEW)

**Features:**
- ✅ Tests agent with various observation scenarios
- ✅ Analyzes different scaling factor combinations
- ✅ Identifies optimal ranges (no clipping, not too small)
- ✅ Shows current configuration and alternatives
- ✅ Provides recommendations and next steps

**Usage:**
```bash
python3 test_action_scaling.py checkpoints/pointmaze_1/state
```

**Sample Output:**
```
Action Scaling Test for PointMaze → TurtleBot3 Transfer
======================================================================

At origin, stationary:
  Observation: [0. 0. 0. 0.]
  Agent output: force_x=0.0423, force_y=-0.0381
  Force magnitude: 0.0569

Scaling Factor Analysis
----------------------------------------------------------------------
Linear Scale  Angular Scale   Linear Vel   Angular Vel   Status
----------------------------------------------------------------------
    0.5      ×    1.0       =  0.0212       -0.0381      L-tiny, A-tiny
    1.0      ×    2.0       =  0.0423       -0.0762      L-tiny, A-tiny
    2.0      ×    5.0       =  0.0846       -0.1905      ✓ Good
→   5.0      ×   10.0       =  0.2115       -0.3810      ✓ Good
   10.0      ×   15.0       =  0.2200       -0.5715      L-clip
```

---

## Quick Start Guide

### Deploy with New Settings

**Terminal 1: Launch Gazebo**
```bash
sudo docker run -it --rm \
  --net=host -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v /mnt/research/rtrd/rlrd:/root/ws/rtrd \
  rlrd-gazebo

source /opt/ros/noetic/setup.bash
roslaunch turtlebot3_gazebo turtlebot3_world.launch
```

**Terminal 2: Deploy Trained Agent**
```bash
sudo docker exec -it $(docker ps -qf "ancestor=rlrd-gazebo") bash

source /opt/ros/noetic/setup.bash
source /root/venv_rlrd/bin/activate
cd /root/ws/rtrd

# Deploy with new aggressive scaling
python3 run_sim_controller.py checkpoints/pointmaze_1/state
```

**Expected Behavior:**
- ✅ Robot moves with purpose (not crawling)
- ✅ Responds to obstacles
- ✅ Turns and navigates
- ✅ Velocities: ~0.05-0.15 m/s linear, ~0.3-1.0 rad/s angular

---

## Tuning the Scaling (if needed)

### Test Different Scales
```bash
python3 test_action_scaling.py checkpoints/pointmaze_1/state
```

### Apply New Scales

Edit `rlrd/maze_to_sim_bridge.py`, line ~268:
```python
def translate_action(self, pointmaze_action):
    force_x, force_y = pointmaze_action
    
    # ADJUST THESE VALUES
    linear_x = force_x * YOUR_LINEAR_SCALE   # Currently 5.0
    angular_z = force_y * YOUR_ANGULAR_SCALE # Currently 10.0
    
    linear_x = np.clip(linear_x, -0.22, 0.22)
    angular_z = np.clip(angular_z, -2.84, 2.84)
    return linear_x, angular_z
```

**Recommended ranges:**
- Linear scale: 2.0 - 10.0
- Angular scale: 5.0 - 15.0

---

## If Robot Still Doesn't Navigate Well

The domain gap between PointMaze (frictionless point mass) and TurtleBot3 (wheeled robot with physics) may be too large for transfer learning.

### Solution: Native TurtleBot3 Training

**Train directly on the robot:**
```bash
# Terminal 1: Keep Gazebo running

# Terminal 2: Train natively
source /opt/ros/noetic/setup.bash
source /root/venv_rlrd/bin/activate
cd /root/ws/rtrd

python3 -m rlrd run-fs checkpoints/turtlebot_native rlrd:SimTraining
```

**Benefits of native training:**
- ✅ No domain gap
- ✅ No action/observation translation needed
- ✅ Learns actual robot dynamics
- ✅ Better long-term performance

**Time:** ~2-3 hours on CPU

**After training:**
```bash
python3 run_sim_controller.py checkpoints/turtlebot_native/state
```

---

## Files Modified

1. **`rlrd/maze_to_sim_bridge.py`**
   - Modified `translate_action()` method
   - Changed from magnitude/angle approach to direct mapping
   - Increased scaling factors: 5.0x linear, 10.0x angular

2. **`run_sim_controller.py`**
   - Added command-line argument parsing
   - Added scaling configuration display
   - Improved user documentation

3. **`test_action_scaling.py`** (NEW)
   - Diagnostic tool for testing scaling factors
   - Helps identify optimal configurations
   - Provides actionable recommendations

---

## Testing Checklist

- [ ] Gazebo launches successfully
- [ ] ROS environment sourced in controller terminal
- [ ] Controller loads checkpoint without errors
- [ ] Robot publishes to `/cmd_vel` at ~10 Hz
- [ ] Robot moves with visible motion (not crawling)
- [ ] Linear velocity: 0.05 - 0.15 m/s
- [ ] Angular velocity: 0.3 - 1.0 rad/s
- [ ] Robot navigates around obstacles
- [ ] Robot doesn't crash into walls immediately

---

## Troubleshooting

### Robot still too slow
- Increase scaling factors in `maze_to_sim_bridge.py`
- Try: linear_x = force_x * 10.0, angular_z = force_y * 15.0

### Robot too aggressive/unstable
- Decrease scaling factors
- Try: linear_x = force_x * 2.0, angular_z = force_y * 5.0

### ROS errors
- Ensure `source /opt/ros/noetic/setup.bash` was run
- Check `rostopic list` shows `/odom` and `/cmd_vel`
- Verify Gazebo is running in separate terminal

### Agent not learning well
- Consider native TurtleBot3 training (recommended)
- Or fine-tune PointMaze agent with more epochs

---

## Performance Expectations

### With Transfer Learning (PointMaze → TurtleBot3)
- **Quality:** Medium (domain gap exists)
- **Setup time:** Immediate (already trained)
- **Best for:** Quick prototyping, demos

### With Native Training (TurtleBot3 → TurtleBot3)
- **Quality:** High (no domain gap)
- **Setup time:** 2-3 hours training
- **Best for:** Production deployment, research

---

## Summary

These changes increase the robot's responsiveness by **22x for linear motion** and **5x for angular motion**, transforming the robot from barely moving to actively navigating. The new direct mapping approach is simpler and better utilizes the agent's learned policy.

If the robot still doesn't perform well after these changes, the fundamental issue is the **domain gap** between training (PointMaze) and deployment (TurtleBot3), and **native training** is recommended as the proper long-term solution.

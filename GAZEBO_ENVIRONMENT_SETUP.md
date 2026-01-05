# Gazebo Environment Setup for RL Training

This document explains how the Gazebo simulation environment is properly configured to ensure the RL agent receives real, valid data during training.

---

## Overview

For successful RL training, the environment must be **fully initialized** before the agent starts:
1. ✅ **ROS core** running
2. ✅ **Gazebo server** (gzserver) running with correct plugins
3. ✅ **Robot spawned** in simulation
4. ✅ **Robot description** loaded to ROS parameter server
5. ✅ **TF transforms** published by robot_state_publisher
6. ✅ **Sensor topics** (/odom, /scan) publishing data
7. ✅ **Gazebo services** available for environment reset

**If any component is missing, the agent will NOT receive real data and training will fail.**

---

## The Startup Script: `start_gazebo_headless.sh`

Location: `scripts/start_gazebo_headless.sh`

### What It Does

The script performs a **comprehensive startup and verification** sequence:

#### Phase 1: Cleanup
```bash
- Kill existing Gazebo/ROS processes
- Clean temporary files
- Ensure clean slate for new session
```

#### Phase 2: ROS Core
```bash
- Start roscore
- Verify roscore is running
- Wait for ROS master to be ready
```

#### Phase 3: Robot Description Setup
```bash
- Generate URDF from xacro file
- Load robot_description to ROS parameter server
- Start robot_state_publisher for TF transforms
- Verify parameter is loaded correctly
```

**Critical:** This must happen BEFORE Gazebo starts or robot spawning will fail.

#### Phase 4: Gazebo Server
```bash
- Set environment variables (disable rendering, set plugin paths)
- Start gzserver with ROS plugins:
  * libgazebo_ros_api_plugin.so (provides Gazebo services)
  * libgazebo_ros_paths_plugin.so (handles model paths)
- Wait for Gazebo ROS API to initialize
- Verify gzserver process is running
```

#### Phase 5: Robot Spawning ⚠️ **CRITICAL**
```bash
- Spawn TurtleBot3 robot at position (0, 0, 0)
- Verify robot appears in /gazebo/model_states
- Check spawn_model exit code
- Display spawn log if failed
```

**Why this is critical:**
- Without robot spawn, agent sends commands to void
- No odometry data generated
- Agent receives constant penalty, learns nothing
- Training appears to run but produces no meaningful results

#### Phase 6: Topic Verification
```bash
- Check /odom is publishing (30-50 Hz expected)
- Check /scan is publishing (5-10 Hz expected)
- Wait up to 60 seconds for sensors to initialize
- Poll every 5 seconds and report when each sensor starts
- Only show "FULLY READY" when both sensors confirmed
```

**Why active waiting:**
- Sensors take 20-30 seconds to start after robot spawn
- Previous approach showed "READY" too early (timing guesswork)
- New approach polls sensors and waits for confirmation
- User sees clear "✓ All sensors are now publishing!" message
- No more uncertainty about when to start training
- Check /scan is publishing (5-10 Hz expected)
- Check /cmd_vel topic exists
```

**Why this matters:**
- /odom: Agent needs robot position feedback
- /scan: LiDAR data for obstacle detection (180-dim observation)
- /cmd_vel: Agent must be able to send movement commands

#### Phase 7: Service Verification
```bash
- Verify /gazebo/reset_simulation (required for episode resets)
- Verify /gazebo/reset_world (alternative reset method)
- Verify /gazebo/pause_physics (for synchronous stepping)
- Verify /gazebo/unpause_physics (resume simulation)
```

**Why services matter:**
- Training needs to reset environment between episodes
- Without reset service, only one episode can run
- Auto-restart mechanism needs these services

---

## Verification Checklist

After running `start_gazebo_headless.sh`, you should see:

### ✅ Success Indicators

```bash
✓ Cleanup complete
✓ roscore is running
✓ Found world file: /opt/ros/noetic/share/turtlebot3_gazebo/worlds/turtlebot3_world.world
✓ Gazebo ROS plugins found
✓ Robot description loaded to parameter server
✓ robot_state_publisher started (PID: XXXXX)
✓ gzserver is running
✓ Gazebo ROS API initialized
✓ Robot spawned successfully (verified in /gazebo/model_states)
✓ All required topics verified
  ✓ Checking /odom... Publishing
  ✓ Checking /scan... Publishing
  ✓ Checking /cmd_vel... Available
✓ All required services verified
  ✓ /gazebo/reset_simulation
  ✓ /gazebo/reset_world
  ✓ /gazebo/pause_physics
  ✓ /gazebo/unpause_physics
```

### Final Output

```
========================================
✓ Gazebo is FULLY READY for training!
========================================

Environment Status:
  Robot Model: turtlebot3_burger
  Robot Position: (0.0, 0.0, 0.0)
  World: turtlebot3_world

ROS Topics:
  Odometry: /odom (publishing)
  LiDAR: /scan (publishing)
  Commands: /cmd_vel (ready)

Gazebo Services:
  /gazebo/reset_simulation (ready)
  /gazebo/reset_world (ready)
  /gazebo/pause_physics (ready)
  /gazebo/unpause_physics (ready)

Ready to start training!
========================================
```

---

## Manual Verification Commands

If you want to manually verify the environment:

### 1. Check Robot Exists in Gazebo
```bash
rostopic echo /gazebo/model_states -n 1 | grep turtlebot3_burger
# Expected output: - turtlebot3_burger
```

### 2. Check Odometry Publishing
```bash
rostopic hz /odom
# Expected: 50-100 Hz
```

### 3. Check LiDAR Publishing
```bash
rostopic hz /scan
# Expected: 5-10 Hz
```

### 4. Check Robot Description Parameter
```bash
rosparam get /robot_description | head -10
# Expected: XML starting with <?xml version="1.0"?>
```

### 5. Check TF Transforms
```bash
rostopic echo /tf -n 10
# Should show transforms between frames
```

### 6. Check Gazebo Services
```bash
rosservice list | grep gazebo
# Should show: reset_simulation, reset_world, pause_physics, unpause_physics, etc.
```

### 7. Test Robot Movement
```bash
# Publish a command
rostopic pub /cmd_vel geometry_msgs/Twist "linear:
  x: 0.2
  y: 0.0
  z: 0.0
angular:
  x: 0.0
  y: 0.0
  z: 0.5" -r 10

# In another terminal, watch odometry
rostopic echo /odom
# Robot position should change
```

---

## Common Issues and Fixes

### Issue 1: Robot Not Spawning

**Symptoms:**
```
ERROR: Robot NOT found in Gazebo!
Available models:
  - ground_plane
  - ros_symbol
```

**Causes:**
1. `robot_description` parameter not loaded before spawn
2. URDF generation failed
3. spawn_model command failed silently

**Fix:**
```bash
# Check if robot_description exists
rosparam get /robot_description

# If missing, load manually:
export TURTLEBOT3_MODEL=burger
rosrun xacro xacro /opt/ros/noetic/share/turtlebot3_description/urdf/turtlebot3_burger.urdf.xacro > /tmp/turtlebot3.urdf
rosparam set robot_description -t /tmp/turtlebot3.urdf

# Retry spawn
rosrun gazebo_ros spawn_model -urdf -model turtlebot3_burger -x 0.0 -y 0.0 -z 0.0 -param robot_description
```

**Check spawn log:**
```bash
cat /tmp/spawn_robot.log
```

### Issue 2: Topics Not Publishing

**Symptoms:**
```
✗ Checking /odom... NOT publishing
✗ Checking /scan... NOT publishing
```

**Causes:**
1. Robot not spawned (no robot = no sensors)
2. robot_state_publisher not running
3. Gazebo crashed after robot spawn

**Fix:**
```bash
# Check if robot exists
rostopic echo /gazebo/model_states -n 1 | grep turtlebot3

# Check robot_state_publisher
ps aux | grep robot_state_publisher

# Restart if needed
rosrun robot_state_publisher robot_state_publisher &
```

### Issue 3: Gazebo Services Missing

**Symptoms:**
```
ERROR: Timeout waiting for Gazebo services
Available services: (none)
```

**Causes:**
1. Gazebo ROS API plugin failed to load
2. gzserver crashed
3. World file loading stuck (downloading models from internet)

**Fix:**
```bash
# Check gzserver log
tail -100 /tmp/gzserver.log

# Look for errors like:
# - "Failed to load plugin"
# - "Waiting for master" (stuck)
# - "Aborted" (crashed)

# If stuck downloading models, wait 60 seconds or:
export GAZEBO_MODEL_PATH=/opt/ros/noetic/share/turtlebot3_gazebo/models:$GAZEBO_MODEL_PATH
# Restart gzserver
```

### Issue 4: Training Shows No Learning

**Symptoms:**
- Returns constant at -50.1
- Episode length always 502
- Q-values very high (~70)

**Diagnosis:**
```bash
# 1. Check robot exists
rostopic echo /gazebo/model_states -n 1 | grep turtlebot3
# If nothing: robot not spawned!

# 2. Check odometry is changing
rostopic echo /odom | grep -A 3 "position"
# Position should vary over time

# 3. Check commands being sent
rostopic echo /cmd_vel
# Should show varying linear/angular velocities
```

**Fix:**
If robot not spawned, restart Gazebo with fixed script.

---

## Environment Variables

The script sets these critical environment variables:

```bash
# TurtleBot3 model selection
export TURTLEBOT3_MODEL=burger

# Gazebo plugin paths
export GAZEBO_PLUGIN_PATH=/opt/ros/noetic/lib:$GAZEBO_PLUGIN_PATH
export LD_LIBRARY_PATH=/opt/ros/noetic/lib:$LD_LIBRARY_PATH

# Gazebo model/resource paths
export GAZEBO_MODEL_PATH=/opt/ros/noetic/share/turtlebot3_gazebo/models:$GAZEBO_MODEL_PATH
export GAZEBO_RESOURCE_PATH=/opt/ros/noetic/share/gazebo-11:$GAZEBO_RESOURCE_PATH

# Force headless rendering (no GPU/display needed)
export LIBGL_ALWAYS_SOFTWARE=1
unset DISPLAY
```

**Why these matter:**
- `TURTLEBOT3_MODEL`: Selects which robot variant to use
- Plugin paths: Ensures Gazebo can find ROS integration plugins
- `LIBGL_ALWAYS_SOFTWARE`: Forces software rendering (faster for headless)
- `unset DISPLAY`: Prevents X11 errors in headless mode

---

## Workflow: Starting Training

### Terminal 1: Start Gazebo Environment

```bash
# Inside Docker container
source /opt/ros/noetic/setup.bash
bash /root/ws/rtrd/scripts/start_gazebo_headless.sh
```

**Wait for:**
```
✓ Gazebo is FULLY READY for training!
```

**The script automatically verifies:**
- ✅ Robot spawned (with 3 retry attempts)
- ✅ All topics publishing with timeout/retry
- ✅ All Gazebo services available
- ✅ Shows actual Hz rates for topics

**Do NOT proceed to training until you see this message!**

### Terminal 2: Start Training

See **TRAINING_WORKFLOW.md** for complete terminal commands and workflow.

Quick example:
```bash
# Attach to container
sudo docker exec -it $(sudo docker ps -qf "ancestor=rlrd-gazebo") bash

# Setup environment
source /opt/ros/noetic/setup.bash
source /root/venv_rlrd/bin/activate
cd /root/ws/rtrd

# Start training (example: RLRD)
python3 -m rlrd run-fs checkpoints/turtlebot3_lidar_rlrd rlrd:SimTraining \
    Env=SimEnv Env.lidar_dim=180 \
    Env.min_observation_delay=0 Env.sup_observation_delay=2 \
    Env.min_action_delay=1 Env.sup_action_delay=4 \
    Agent.batchsize=128 Agent.memory_size=1000000 \
    Agent.lr=0.0003 Agent.discount=0.99 Agent.device=cpu \
    epochs=20 rounds=50 steps=1000 tag=turtlebot3_lidar_rlrd
```

### Expected Training Output (with proper environment)

```
=== epoch 1/20 ===== round 1/50 ======================================
[INFO] [timestamp]: Episode log saved to /tmp/robot_sim_episode_*.csv
  episodes                                           1
  episode_length                                 342.0  ← Varying (not always 502)
  returns                                        -34.2  ← Varying (not constant -50.1)
  average_reward                               -0.0876  ← Improving over time
  ...
```

**Signs of healthy training:**
- ✅ Episode length varies (150-502)
- ✅ Returns improve over epochs (-50 → -40 → -30 → ...)
- ✅ Q-values stabilize near actual returns
- ✅ TD error small (~1-2)
- ✅ Actor gradients non-zero

---

## Logs and Debugging

### Log File Locations

```bash
/tmp/roscore.log              # ROS master log
/tmp/gzserver.log             # Gazebo server log
/tmp/robot_state_publisher.log # TF publisher log
/tmp/spawn_robot.log          # Robot spawn log
/tmp/robot_sim_episode_*.csv  # Episode data from training
```

### Useful Debugging Commands

```bash
# Watch Gazebo log in real-time
tail -f /tmp/gzserver.log

# Monitor robot position
rostopic echo /odom | grep -A 3 "position"

# Monitor LiDAR
rostopic echo /scan | grep "ranges:"

# Check ROS node graph
rosnode list
rosnode info /gazebo

# Check TF tree
rosrun tf view_frames
evince frames.pdf
```

---

## Summary: Why This Matters

### ❌ Without Proper Environment Setup

- Agent sends commands to void (no robot)
- No sensor feedback (no odometry, no LiDAR)
- Constant -0.1 penalty per step
- Training "runs" but agent learns nothing
- Wasted compute time (hours/days)
- Invalid experimental results

### ✅ With Proper Environment Setup

- Robot exists and responds to commands
- Real sensor data flowing (/odom at 50-100 Hz, /scan at 5-10 Hz)
- Varying rewards based on actual behavior
- Agent learns navigation strategy
- Valid training curves for paper
- Reproducible experiments

---

## Checklist Before Starting Any Training

1. [ ] Run `start_gazebo_headless.sh` in Terminal 1
2. [ ] Wait for "✓ Gazebo is FULLY READY for training!" message
3. [ ] Verify robot spawned: `rostopic echo /gazebo/model_states -n 1 | grep turtlebot3`
4. [ ] Verify odometry: `rostopic hz /odom` shows 50-100 Hz
5. [ ] Verify LiDAR: `rostopic hz /scan` shows 5-10 Hz
6. [ ] Verify services: `rosservice list | grep reset_simulation`
7. [ ] Start training in Terminal 2
8. [ ] Monitor first few episodes for varying returns

**Only proceed with long training runs after verifying all checkboxes!**

---

## For Experimental Comparisons (RLRD vs SAC vs RTAC)

**CRITICAL:** All three methods MUST start with properly spawned robot:

```bash
# Method 1: RLRD (DC)
# Terminal 1: start_gazebo_headless.sh (verify robot spawned)
# Terminal 2: 
python3 -m rlrd run-fs checkpoints/turtlebot3_lidar_rlrd rlrd:SimTraining [params]

# Method 2: SAC
# Terminal 1: start_gazebo_headless.sh (verify robot spawned)  
# Terminal 2:
python3 -m rlrd run-fs checkpoints/turtlebot3_lidar_sac sac:SimTraining [params]

# Method 3: RTAC  
# Terminal 1: start_gazebo_headless.sh (verify robot spawned)
# Terminal 2:
python3 -m rlrd run-fs checkpoints/turtlebot3_lidar_rtac rtac:SimTraining [params]
```

**All three get identical starting conditions:**
- ✅ Same world (turtlebot3_world)
- ✅ Same robot (turtlebot3_burger)
- ✅ Same spawn position (0, 0, 0)
- ✅ Same sensor configuration (LiDAR 180-dim + odometry 4-dim)
- ✅ Same training budget (20 epochs × 50 rounds × 1000 steps = 1M steps)

**Fair comparison requires all methods trained with robot spawned from epoch 1!**

---

## Troubleshooting

### LiDAR Sensor Not Publishing (/scan topic missing)

**Symptom:**
- Robot spawns successfully
- `/odom` publishes at 30 Hz
- `/scan` topic does not exist
- `rostopic list` shows no `/scan`
- URDF contains `libgazebo_ros_laser.so` plugin

**Root Cause:**
The `libgazebo_ros_laser.so` plugin depends on `libRayPlugin.so`, which is a Gazebo sensor plugin. Even though the plugin is correctly defined in the URDF, Gazebo cannot load it if `libRayPlugin.so` is not in the library search path.

**Diagnosis:**
```bash
# Check if dependency is missing
ldd /opt/ros/noetic/lib/libgazebo_ros_laser.so | grep -i "not found"
# Output: libRayPlugin.so => not found

# Find where libRayPlugin.so is located
find /usr -name "libRayPlugin.so" 2>/dev/null
# Output: /usr/lib/x86_64-linux-gnu/gazebo-11/plugins/libRayPlugin.so
```

**Solution:**
Export the Gazebo plugin directory to both `LD_LIBRARY_PATH` and `GAZEBO_PLUGIN_PATH`:

```bash
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:$LD_LIBRARY_PATH
export GAZEBO_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:$GAZEBO_PLUGIN_PATH
```

**Permanent Fix:**
This is now included in `scripts/start_gazebo_headless.sh` (lines 23-27), so the script automatically sets these paths before starting Gazebo.

**Verification:**
```bash
# After restarting gazebo with the fix
rostopic list | grep scan
# Output: /scan

rostopic hz /scan
# Output: average rate: 5.0 Hz
```

**Why This Happens:**
- Gazebo 11 ships with sensor plugins in `/usr/lib/x86_64-linux-gnu/gazebo-11/plugins/`
- ROS Noetic's `libgazebo_ros_laser.so` is a wrapper that depends on Gazebo's `libRayPlugin.so`
- By default, this directory is not in `LD_LIBRARY_PATH`, so the dynamic linker cannot find the dependency
- The plugin silently fails to load (no error messages in logs)
- Result: URDF is correct, but `/scan` topic never gets created

---

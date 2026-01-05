# Quick Testing Guide: Verify Robot Spawning

**NOTE:** The startup script now automatically handles ALL verifications with retry logic. You don't need to manually check unless troubleshooting.

---

## Step 1: Test the Startup Script

```bash
# Terminal 1 (in Docker container)
source /opt/ros/noetic/setup.bash
bash /root/ws/rtrd/scripts/start_gazebo_headless.sh
```

**Expected output at end:**
```
=========================================
✓ Gazebo is FULLY READY for training!
=========================================

Environment Status:
  Robot Model: turtlebot3_burger
  Robot Position: (0.0, 0.0, 0.0)
  Timestamp: 2025-11-26 10:30:45

ROS Topics (verified):
  ✓ Odometry: /odom (publishing at 50.0 Hz)
  ✓ LiDAR: /scan (publishing at 5.0 Hz)
  ✓ Commands: /cmd_vel (ready)

Gazebo Services (verified):
  ✓ /gazebo/reset_simulation (ready)
```

**The script automatically:**
- ✅ Verifies robot spawned (with 3 retry attempts)
- ✅ Checks all topics publishing (with retry logic)
- ✅ Verifies Gazebo services available
- ✅ Shows actual topic frequencies

**If you see this success message, proceed to training immediately!**

See **TRAINING_WORKFLOW.md** for complete training commands.

```bash
# Terminal 1 (in Docker container)
source /opt/ros/noetic/setup.bash
bash /root/ws/rtrd/scripts/start_gazebo_headless.sh
```

**Expected output at end:**
```
========================================
✓ Gazebo is FULLY READY for training!
========================================
```

**If you see errors, check logs:**
```bash
cat /tmp/spawn_robot.log        # Robot spawn failures
tail -100 /tmp/gzserver.log      # Gazebo crashes
```

---

## Step 2: Verify Robot Spawned

```bash
# Terminal 2 (attach to container)
sudo docker exec -it $(docker ps -qf "ancestor=rlrd-gazebo") bash
source /opt/ros/noetic/setup.bash

# Check robot in Gazebo model list
rostopic echo /gazebo/model_states -n 1
```

**Expected output:**
```
name: 
  - ground_plane
  - ros_symbol
  - turtlebot3_burger    ← MUST be present!
pose: 
  - 
    position: 
      x: 0.0
      y: 0.0
      z: 0.0
```

**If `turtlebot3_burger` missing → robot NOT spawned → STOP and debug!**

---

## Step 3: Verify Topics Publishing

```bash
# Check odometry
rostopic hz /odom
# Should show: average rate: 50-100

# Check LiDAR
rostopic hz /scan
# Should show: average rate: 5-10

# Verify commands accepted
rostopic list | grep cmd_vel
# Should show: /cmd_vel
```

---

## Step 4: Test Robot Movement

```bash
# Publish forward + rotation command
rostopic pub /cmd_vel geometry_msgs/Twist "linear:
  x: 0.2
angular:
  z: 0.5" -r 10 &

# Watch odometry change
rostopic echo /odom | grep -A 3 "position"
# x/y values should change

# Stop command publisher
pkill -f "rostopic pub"
```

**If position changes → robot is alive and responding!**

---

## Step 5: Start Short Test Training

```bash
# Terminal 2 (same as Step 2)
source /root/venv_rlrd/bin/activate
cd /root/ws/rtrd

# Run SHORT test (1 epoch, 5 rounds, 100 steps)
python3 -m rlrd run-fs checkpoints/spawn_test rlrd:SimTraining \
    Env=SimEnv \
    Env.lidar_dim=180 \
    Env.min_observation_delay=0 \
    Env.sup_observation_delay=2 \
    Env.min_action_delay=1 \
    Env.sup_action_delay=4 \
    Agent.batchsize=128 \
    Agent.memory_size=100000 \
    Agent.lr=0.0003 \
    Agent.discount=0.99 \
    Agent.device=cpu \
    epochs=1 \
    rounds=5 \
    steps=100 \
    tag=spawn_test
```

**Watch for healthy signs:**
```
=== epoch 1/1 ===== round 1/5 ======================================
  episode_length                                 267.0  ← Varies (not always 502)
  returns                                        -26.7  ← Varies (not constant -50.1)
  average_reward                                -0.089  
  critic_grad                                     0.45  ← Non-zero
  td_error                                        1.23  ← Small (~1-2)
```

**Red flags (indicates robot NOT working):**
- ❌ Episode length always 502
- ❌ Returns constant at -50.1
- ❌ Q-values very high (>50)
- ❌ TD error huge (>10)

---

## Step 6: If Test Passes, Clean and Restart Real Training

```bash
# Delete test checkpoint
rm -rf checkpoints/spawn_test

# Delete old invalid checkpoints (epochs 1-9 with no robot)
rm -rf checkpoints/turtlebot3_lidar*

# NOW start full training (20 epochs, 50 rounds, 1000 steps)
python3 -m rlrd run-fs checkpoints/turtlebot3_lidar_rlrd rlrd:SimTraining \
    Env=SimEnv \
    Env.lidar_dim=180 \
    Env.min_observation_delay=0 \
    Env.sup_observation_delay=2 \
    Env.min_action_delay=1 \
    Env.sup_action_delay=4 \
    Agent.batchsize=128 \
    Agent.memory_size=1000000 \
    Agent.lr=0.0003 \
    Agent.discount=0.99 \
    Agent.device=cpu \
    epochs=20 \
    rounds=50 \
    steps=1000 \
    tag=turtlebot3_lidar_rlrd
```

---

## Troubleshooting Quick Checks

### Robot not spawning?
```bash
# Check robot_description parameter
rosparam get /robot_description | head -5
# Should show XML starting with <?xml version="1.0"?>

# Check spawn log
cat /tmp/spawn_robot.log
```

### Topics not publishing?
```bash
# Check robot_state_publisher running
ps aux | grep robot_state_publisher

# Check robot exists
rostopic echo /gazebo/model_states -n 1 | grep turtlebot3

# If robot missing → respawn manually:
rosrun gazebo_ros spawn_model -urdf -model turtlebot3_burger -x 0.0 -y 0.0 -z 0.0 -param robot_description
```

### Gazebo crashed?
```bash
# Check gzserver log
tail -50 /tmp/gzserver.log

# Look for:
# - "Aborted" → crash
# - "Waiting for master" → stuck
# - "Failed to load plugin" → missing library

# Restart Gazebo
pkill -9 gzserver
bash /root/ws/rtrd/scripts/start_gazebo_headless.sh
```

---

## Success Criteria

✅ **All these MUST be true before starting real training:**

1. Script shows "✓ Gazebo is FULLY READY for training!"
2. `/gazebo/model_states` contains `turtlebot3_burger`
3. `rostopic hz /odom` shows 50-100 Hz
4. `rostopic hz /scan` shows 5-10 Hz
5. Test training shows varying episode lengths (not constant 502)
6. Test training shows varying returns (not constant -50.1)
7. Publishing command to `/cmd_vel` changes robot position in `/odom`

**If ANY fails → debug before running full 20-epoch training!**

---

## Timeline: Full Training (with robot properly spawned)

- **1 epoch** = 50 rounds × 1000 steps = 50,000 steps ≈ **30-45 minutes**
- **20 epochs** = 1,000,000 steps ≈ **10-15 hours**

**Do NOT waste compute time with robot not spawned!**

Verify Steps 1-7 above first → then commit to full training run.

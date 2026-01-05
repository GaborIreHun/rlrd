# Training Workflow: Complete Terminal Commands

This guide provides the **exact terminal commands** to run RL training in the Gazebo simulator, with all verifications automated by the startup script.

---

## Overview

The training requires **TWO terminals**:
- **Terminal 1**: Runs Gazebo simulation environment (with robot spawning verification)
- **Terminal 2**: Runs the RL training agent

Both run inside the Docker container `rlrd-gazebo`.

---

## Prerequisites

### 1. Ensure Docker Container is Running

```bash
# Check if container exists and is running
sudo docker ps -f "ancestor=rlrd-gazebo"

# If not running, start it:
sudo docker run -it --rm \
    --name rlrd-gazebo \
    --net=host \
    --privileged \
    -v /mnt/research/rtrd/rlrd:/root/ws/rtrd \
    rlrd-gazebo bash
```

### 2. Get Container ID (for Terminal 2)

```bash
# Save this for later
export CONTAINER_ID=$(sudo docker ps -qf "ancestor=rlrd-gazebo")
echo "Container ID: $CONTAINER_ID"
```

---

## Terminal 1: Start Gazebo Environment

### Step 1.1: Attach to Container (if not already inside)

```bash
# If you just started the container, you're already inside
# Otherwise, attach:
sudo docker exec -it $(sudo docker ps -qf "ancestor=rlrd-gazebo") bash
```

### Step 1.2: Source ROS Environment

```bash
source /opt/ros/noetic/setup.bash
```

### Step 1.3: Run the Startup Script

```bash
cd /root/ws/rtrd
bash scripts/start_gazebo_headless.sh
```

### Step 1.4: Wait for Success Message

**You MUST see this at the end:**

```
=========================================
✓ Gazebo is FULLY READY for training!
=========================================

Environment Status:
  Robot Model: turtlebot3_burger
  Robot Position: (0.0, 0.0, 0.0)
  World: turtlebot3_world
  Timestamp: 2025-11-26 10:30:45

ROS Topics (verified):
  ✓ Odometry: /odom (publishing at 50.0 Hz)
  ✓ LiDAR: /scan (publishing at 5.0 Hz)
  ✓ Commands: /cmd_vel (ready)

Gazebo Services (verified):
  ✓ /gazebo/reset_simulation (ready)
  ✓ /gazebo/reset_world (ready)
  ✓ /gazebo/pause_physics (ready)
  ✓ /gazebo/unpause_physics (ready)

Process IDs:
  gzserver: 12345
  robot_state_publisher: 12346

=========================================
  ENVIRONMENT READY - START TRAINING!
=========================================
```

**If you see errors:**
- Check log files: `/tmp/gzserver.log`, `/tmp/spawn_robot.log`
- The script includes automatic retry for robot spawning (up to 3 attempts)
- If still failing, see troubleshooting section below

### Step 1.5: Keep Terminal 1 Open

**DO NOT close Terminal 1!** Gazebo must keep running while training.

You can monitor it with:
```bash
# In another terminal, watch robot position:
sudo docker exec -it $CONTAINER_ID bash -c "source /opt/ros/noetic/setup.bash && rostopic echo /odom | grep -A 3 position"
```

---

## Terminal 2: Run RL Training

### Step 2.1: Open New Terminal and Attach to Container

```bash
# From your host machine
sudo docker exec -it $(sudo docker ps -qf "ancestor=rlrd-gazebo") bash
```

### Step 2.2: Set Up Environment

```bash
# Source ROS
source /opt/ros/noetic/setup.bash

# Activate Python virtual environment
source /root/venv_rlrd/bin/activate

# Navigate to project directory
cd /root/ws/rtrd
```

### Step 2.3: Verify Environment is Ready (Quick Check)

```bash
# This should show turtlebot3_burger
rostopic echo /gazebo/model_states -n 1 | grep turtlebot3_burger

# Expected output:
#   - turtlebot3_burger
```

If you don't see `turtlebot3_burger`, **STOP** - go back to Terminal 1 and fix Gazebo setup.

### Step 2.4: Run Training

#### Option A: RLRD (Delay-Correcting RL)

```bash
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

#### Option B: SAC (Standard Soft Actor-Critic)

```bash
python3 -m rlrd run-fs checkpoints/turtlebot3_lidar_sac sac:SimTraining \
    Env=SimEnv \
    Env.lidar_dim=180 \
    Agent.batchsize=128 \
    Agent.memory_size=1000000 \
    Agent.lr=0.0003 \
    Agent.discount=0.99 \
    Agent.device=cpu \
    epochs=20 \
    rounds=50 \
    steps=1000 \
    tag=turtlebot3_lidar_sac
```

#### Option C: RTAC (Receding Horizon Actor-Critic)

```bash
python3 -m rlrd run-fs checkpoints/turtlebot3_lidar_rtac rtac:SimTraining \
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
    tag=turtlebot3_lidar_rtac
```

### Step 2.5: Monitor Training Output

**Expected healthy output:**

```
=== epoch 1/20 ===== round 1/50 ======================================
[INFO] [timestamp]: Episode log saved to /tmp/robot_sim_episode_*.csv
  episodes                                           1
  episode_length                                 267.0  ← Should vary (150-502)
  returns                                        -26.7  ← Should vary and improve
  average_reward                                -0.089  
  critic_grad                                     0.45  ← Non-zero
  actor_grad                                      0.23  ← Non-zero
  Q1                                            -26.31  ← Close to returns
  Q2                                            -25.89  
  td_error                                        1.23  ← Small (~1-3)
  
  steps_per_second                               234.5
  seconds_per_epoch                             213.56
```

**Signs of healthy training:**
- ✅ Episode length varies (not constant 502)
- ✅ Returns improve over epochs (-50 → -40 → -30 → ...)
- ✅ Q-values close to actual returns
- ✅ TD error stays small (~1-3)
- ✅ Gradients are non-zero

**Red flags (robot NOT working):**
- ❌ Episode length always 502
- ❌ Returns constant at -50.1
- ❌ Q-values very high (>50)
- ❌ TD error huge (>10)

If you see red flags, **STOP training** and check Terminal 1 - robot may not be spawned.

---

## Training Duration

- **1 round** = 1000 steps ≈ 30-45 seconds
- **1 epoch** = 50 rounds = 50,000 steps ≈ 30-45 minutes
- **Full training** = 20 epochs = 1,000,000 steps ≈ **10-15 hours**

Plan accordingly! Use `tmux` or `screen` to keep sessions alive.

---

## Using tmux for Long Training Runs

### Setup tmux Session

```bash
# On host, start tmux
tmux new-session -s rlrd_training

# Split into two panes
# Ctrl+b then " (split horizontal)

# Top pane: Terminal 1 (Gazebo)
sudo docker exec -it $(sudo docker ps -qf "ancestor=rlrd-gazebo") bash
source /opt/ros/noetic/setup.bash
cd /root/ws/rtrd
bash scripts/start_gazebo_headless.sh

# Switch to bottom pane: Ctrl+b then down arrow

# Bottom pane: Terminal 2 (Training)
sudo docker exec -it $(sudo docker ps -qf "ancestor=rlrd-gazebo") bash
source /opt/ros/noetic/setup.bash
source /root/venv_rlrd/bin/activate
cd /root/ws/rtrd
# Run training command (see Step 2.4)

# Detach from tmux: Ctrl+b then d
# Reattach later: tmux attach -t rlrd_training
```

---

## Monitoring During Training

### From Host Machine

```bash
# Watch training progress
sudo docker exec -it $(sudo docker ps -qf "ancestor=rlrd-gazebo") bash -c "tail -f /root/ws/rtrd/checkpoints/turtlebot3_lidar_rlrd/train.log"

# Watch robot odometry
sudo docker exec -it $(sudo docker ps -qf "ancestor=rlrd-gazebo") bash -c "source /opt/ros/noetic/setup.bash && rostopic echo /odom | grep -A 3 position"

# Watch LiDAR data
sudo docker exec -it $(sudo docker ps -qf "ancestor=rlrd-gazebo") bash -c "source /opt/ros/noetic/setup.bash && rostopic echo /scan | head -20"

# Watch commands
sudo docker exec -it $(sudo docker ps -qf "ancestor=rlrd-gazebo") bash -c "source /opt/ros/noetic/setup.bash && rostopic echo /cmd_vel"

# Check Gazebo status
sudo docker exec -it $(sudo docker ps -qf "ancestor=rlrd-gazebo") bash -c "ps aux | grep gzserver"
```

---

## Stopping Training

### Graceful Stop (Recommended)

```bash
# In Terminal 2, press: Ctrl+C
# Training will save checkpoint at current epoch
```

### Stop Gazebo

```bash
# In Terminal 1, press: Ctrl+C
# Or from another terminal:
sudo docker exec -it $(sudo docker ps -qf "ancestor=rlrd-gazebo") bash -c "pkill -f gzserver && pkill -f roscore"
```

### Complete Cleanup

```bash
# Inside container or via docker exec:
pkill -9 -f gzserver
pkill -9 -f roscore
pkill -9 -f robot_state_publisher
rm -rf /tmp/gazebo-*
rm -rf ~/.gazebo/server-*
```

---

## Restarting Training from Checkpoint

If training stopped at epoch N, it will automatically resume:

```bash
# Same command as initial training
# Will detect existing checkpoints and continue from last epoch
python3 -m rlrd run-fs checkpoints/turtlebot3_lidar_rlrd rlrd:SimTraining \
    Env=SimEnv \
    Env.lidar_dim=180 \
    [... same parameters ...]
    epochs=20 \
    rounds=50 \
    steps=1000 \
    tag=turtlebot3_lidar_rlrd
```

**To start completely fresh:**

```bash
# Delete checkpoint directory
rm -rf checkpoints/turtlebot3_lidar_rlrd
# Then run training command
```

---

## Running All Three Methods for Comparison

For the paper experiments, you need RLRD, SAC, and RTAC all trained identically.

### Method 1: Sequential (One After Another)

```bash
# Terminal 1: Keep Gazebo running the whole time
bash scripts/start_gazebo_headless.sh
# Leave running

# Terminal 2: Run each method
# Method 1: RLRD (~10-15 hours)
python3 -m rlrd run-fs checkpoints/turtlebot3_lidar_rlrd rlrd:SimTraining [params]
# Wait for completion...

# Method 2: SAC (~10-15 hours)
python3 -m rlrd run-fs checkpoints/turtlebot3_lidar_sac sac:SimTraining [params]
# Wait for completion...

# Method 3: RTAC (~10-15 hours)
python3 -m rlrd run-fs checkpoints/turtlebot3_lidar_rtac rtac:SimTraining [params]
```

**Total time: ~30-45 hours**

### Method 2: Parallel (Separate Containers)

If you have multiple machines or want to parallelize:

```bash
# Machine 1: RLRD
# Start container with port mapping for ROS (11311)
sudo docker run -it --rm --name rlrd-gazebo-1 --net=host -v /mnt/research/rtrd/rlrd:/root/ws/rtrd rlrd-gazebo bash
# Terminal 1: bash scripts/start_gazebo_headless.sh
# Terminal 2: python3 -m rlrd run-fs checkpoints/turtlebot3_lidar_rlrd rlrd:SimTraining [params]

# Machine 2: SAC
# (repeat with different container name and checkpoint directory)

# Machine 3: RTAC
# (repeat with different container name and checkpoint directory)
```

**Total time: ~10-15 hours (if parallel)**

---

## Troubleshooting

### Issue: Script says "Robot NOT found in Gazebo"

**Check:**
```bash
# Verify robot_description parameter
sudo docker exec -it $(sudo docker ps -qf "ancestor=rlrd-gazebo") bash -c "source /opt/ros/noetic/setup.bash && rosparam get /robot_description | head -10"

# Check Gazebo models
sudo docker exec -it $(sudo docker ps -qf "ancestor=rlrd-gazebo") bash -c "source /opt/ros/noetic/setup.bash && rostopic echo /gazebo/model_states -n 1"

# Check spawn log
sudo docker exec -it $(sudo docker ps -qf "ancestor=rlrd-gazebo") bash -c "cat /tmp/spawn_robot.log"
```

**Fix:**
The script automatically retries 3 times. If still failing:
1. Check `/tmp/gzserver.log` for Gazebo crashes
2. Ensure ROS is sourced: `source /opt/ros/noetic/setup.bash`
3. Try manual spawn:
   ```bash
   rosrun gazebo_ros spawn_model -urdf -model turtlebot3_burger -x 0.0 -y 0.0 -z 0.0 -param robot_description
   ```

### Issue: Topics not publishing

**Check:**
```bash
# List all topics
rostopic list

# Check specific topics
rostopic hz /odom
rostopic hz /scan
```

**Fix:**
1. Ensure robot is spawned (see above)
2. Check robot_state_publisher is running: `ps aux | grep robot_state_publisher`
3. Restart script: Kill Gazebo and run `start_gazebo_headless.sh` again

### Issue: Training shows no learning (constant -50.1 returns)

**Diagnosis:**
```bash
# Check robot exists
rostopic echo /gazebo/model_states -n 1 | grep turtlebot3_burger

# Check odometry is changing
rostopic echo /odom | grep -A 3 position
# Position x/y should vary over time

# Check commands being sent
rostopic echo /cmd_vel
# Should show varying velocities
```

**Fix:**
Robot not spawned. Restart Terminal 1 with `start_gazebo_headless.sh` and verify success message.

### Issue: Gazebo crashed during training

Training script has automatic restart. Check:
```bash
# Check if gzserver is running
ps aux | grep gzserver

# Check gzserver log
tail -100 /tmp/gzserver.log
```

The `simulator_env.py` will automatically restart Gazebo if it crashes.

---

## Verification Checklist

Before starting a **long training run** (20 epochs):

- [ ] Terminal 1 shows "✓ Gazebo is FULLY READY for training!"
- [ ] `rostopic echo /gazebo/model_states -n 1 | grep turtlebot3_burger` shows robot
- [ ] `rostopic hz /odom` shows 50-100 Hz
- [ ] `rostopic hz /scan` shows 5-10 Hz
- [ ] Test training (1 epoch, 5 rounds) shows varying returns
- [ ] Using `tmux` or `screen` for long-running sessions
- [ ] Disk space available for checkpoints (~1-2 GB per method)

**Only proceed if ALL checkboxes are ticked!**

---

## Summary: Complete Workflow

```bash
# ===== TERMINAL 1: Gazebo =====
sudo docker exec -it $(sudo docker ps -qf "ancestor=rlrd-gazebo") bash
source /opt/ros/noetic/setup.bash
cd /root/ws/rtrd
bash scripts/start_gazebo_headless.sh
# Wait for "✓ Gazebo is FULLY READY for training!"
# Keep this terminal open

# ===== TERMINAL 2: Training =====
sudo docker exec -it $(sudo docker ps -qf "ancestor=rlrd-gazebo") bash
source /opt/ros/noetic/setup.bash
source /root/venv_rlrd/bin/activate
cd /root/ws/rtrd
# Quick verification
rostopic echo /gazebo/model_states -n 1 | grep turtlebot3_burger
# Start training
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
# Wait ~10-15 hours
# Monitor with: tail -f checkpoints/turtlebot3_lidar_rlrd/train.log
```

**That's it! The script handles all verification automatically.**

# Quick Reference: Training Commands

**Essential commands for running RL training with automated verification.**

---

## Terminal 1: Start Gazebo (Automated Setup)

```bash
# Inside Docker container
source /opt/ros/noetic/setup.bash
cd /root/ws/rtrd
bash scripts/start_gazebo_headless.sh
```

**Wait for this message:**
```
=========================================
✓ Gazebo is FULLY READY for training!
=========================================
```

✅ Script automatically verifies:
- Robot spawned in Gazebo (3 retry attempts)
- All topics publishing (/odom, /scan, /cmd_vel)
- All services available (reset_simulation, etc.)
- Shows actual Hz rates for topics

**Keep Terminal 1 open!**

---

## Terminal 2: Run Training

### Setup

```bash
# Attach to container
sudo docker exec -it $(sudo docker ps -qf "ancestor=rlrd-gazebo") bash

# Setup environment
source /opt/ros/noetic/setup.bash
source /root/venv_rlrd/bin/activate
cd /root/ws/rtrd
```

### RLRD (Delay-Correcting RL)

```bash
python3 -m rlrd run-fs checkpoints/turtlebot3_lidar_rlrd rlrd:SimTraining \
    Env=SimEnv Env.lidar_dim=180 \
    Env.min_observation_delay=0 Env.sup_observation_delay=2 \
    Env.min_action_delay=1 Env.sup_action_delay=4 \
    Agent.batchsize=128 Agent.memory_size=1000000 \
    Agent.lr=0.0003 Agent.discount=0.99 Agent.device=cpu \
    epochs=20 rounds=50 steps=1000 tag=turtlebot3_lidar_rlrd
```

### SAC (Standard)

```bash
python3 -m rlrd run-fs checkpoints/turtlebot3_lidar_sac sac:SimTraining \
    Env=SimEnv Env.lidar_dim=180 \
    Agent.batchsize=128 Agent.memory_size=1000000 \
    Agent.lr=0.0003 Agent.discount=0.99 Agent.device=cpu \
    epochs=20 rounds=50 steps=1000 tag=turtlebot3_lidar_sac
```

### RTAC (Receding Horizon)

```bash
python3 -m rlrd run-fs checkpoints/turtlebot3_lidar_rtac rtac:SimTraining \
    Env=SimEnv Env.lidar_dim=180 \
    Env.min_observation_delay=0 Env.sup_observation_delay=2 \
    Env.min_action_delay=1 Env.sup_action_delay=4 \
    Agent.batchsize=128 Agent.memory_size=1000000 \
    Agent.lr=0.0003 Agent.discount=0.99 Agent.device=cpu \
    epochs=20 rounds=50 steps=1000 tag=turtlebot3_lidar_rtac
```

**Duration:** ~10-15 hours per method

---

## Monitoring

```bash
# Watch training log
tail -f checkpoints/turtlebot3_lidar_rlrd/train.log

# Watch robot position
rostopic echo /odom | grep -A 3 position

# Check robot spawned
rostopic echo /gazebo/model_states -n 1 | grep turtlebot3_burger
```

---

## Using tmux

```bash
# Start session
tmux new -s training

# Split horizontal: Ctrl+b then "
# Top pane: Gazebo startup
# Bottom pane: Training

# Detach: Ctrl+b then d
# Reattach: tmux attach -t training
```

---

## Stop

```bash
# Stop training: Ctrl+C (saves checkpoint)
# Stop Gazebo: Ctrl+C or:
pkill -f gzserver && pkill -f roscore
```

---

## Fresh Start

```bash
# Delete old checkpoints
rm -rf checkpoints/turtlebot3_lidar_rlrd

# Restart Gazebo
bash scripts/start_gazebo_headless.sh

# Start training
python3 -m rlrd run-fs checkpoints/turtlebot3_lidar_rlrd [...]
```

---

## Troubleshooting

**Robot not spawned?**
```bash
cat /tmp/spawn_robot.log
tail -100 /tmp/gzserver.log
```

**Training not learning?**
```bash
# Check robot exists (should show turtlebot3_burger)
rostopic echo /gazebo/model_states -n 1 | grep turtlebot3

# Check topics
rostopic hz /odom  # Should be 50-100 Hz
rostopic hz /scan  # Should be 5-10 Hz
```

**All logs:**
```
/tmp/roscore.log
/tmp/gzserver.log
/tmp/robot_state_publisher.log
/tmp/spawn_robot.log
```

---

See **TRAINING_WORKFLOW.md** for complete documentation.

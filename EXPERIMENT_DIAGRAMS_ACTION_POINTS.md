# Experimental Diagrams: Action Points & Workflow

This document summarizes the steps required to reproduce the average return diagrams as shown in Section 5 of the referenced RL paper. It covers the training configurations, required commands, and plotting workflow for RLRD (DC), SAC, and RTAC baselines.

---

## 1. Overview

To generate comparison diagrams for average returns, you need to train and evaluate three different RL agent configurations:

- **RLRD (DC):** Delay-correcting agent (currently running)
- **SAC:** Standard Soft Actor-Critic (delay-oblivious baseline)
- **RTAC:** Receding-Horizon Actor-Critic (if available in your codebase)

---

## 2. Training Commands

### A. RLRD (DC) — Delay-Correcting (Already Running)
```bash
python3 -m rlrd run-fs checkpoints/turtlebot3_lidar rlrd:SimTraining \
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
    tag=turtlebot3_lidar
```

### B. SAC — Delay-Oblivious Baseline
```bash
python3 -m rlrd run-fs checkpoints/turtlebot3_lidar_sac sac:SimTraining \
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
    tag=turtlebot3_lidar_sac
```

### C. RTAC — Receding-Horizon Actor-Critic (If Available)
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

---

## 3. Extract Results

- After training, locate the results/log files in each checkpoint directory (e.g., `checkpoints/turtlebot3_lidar/`, `checkpoints/turtlebot3_lidar_sac/`, `checkpoints/turtlebot3_lidar_rtac/`).
- Find files containing average returns per epoch/round (CSV, JSON, or tensorboard logs).
- Extract columns: `epoch/round`, `average_return`.

---

## 4. Plotting Diagrams

Use Python and matplotlib to plot the results:

```python
import matplotlib.pyplot as plt
import numpy as np

dc_returns = np.loadtxt('checkpoints/turtlebot3_lidar/returns.csv')
sac_returns = np.loadtxt('checkpoints/turtlebot3_lidar_sac/returns.csv')
rtac_returns = np.loadtxt('checkpoints/turtlebot3_lidar_rtac/returns.csv')

plt.figure(figsize=(10, 6))
plt.plot(dc_returns[:, 0], dc_returns[:, 1], label='RLRD (DC)', linewidth=2)
plt.plot(sac_returns[:, 0], sac_returns[:, 1], label='SAC', linewidth=2)
plt.plot(rtac_returns[:, 0], rtac_returns[:, 1], label='RTAC', linewidth=2)

plt.xlabel('Training Steps (×1000)')
plt.ylabel('Average Return')
plt.title('TurtleBot3 Navigation Performance')
plt.legend()
plt.grid(True, alpha=0.3)
plt.savefig('comparison_plot.pdf')
plt.show()
```

---

## 5. Notes & Checks

- **Check your codebase** for available training modes/configs (SAC, RTAC, RLRD).
- If SAC/RTAC are not available, you may need to disable delay-correction features manually or consult the official repo for baseline implementations.
- All three methods must be trained and evaluated for a valid comparison plot.

---

## 6. Summary

- Train RLRD (DC), SAC, and RTAC agents with the commands above.
- Extract average returns from logs.
- Plot and compare results as in the paper's Section 5 diagrams.

---

## 7. Troubleshooting

### Gazebo Crashes After Each Epoch

**Symptoms:**
- Training stops with "Failed to connect to Gazebo reset service: rospy shutdown"
- gzserver process disappears

**Causes:**
- Memory exhaustion (Gazebo accumulates memory over time)
- Physics instability
- ROS time synchronization issues

**Auto-Restart Mechanism (Already Implemented):**

The `simulator_env.py` now includes automatic Gazebo restart functionality:
- Detects when Gazebo services are unavailable
- Automatically kills stale gzserver processes
- Restarts Gazebo using the headless startup script
- Retries reset operation up to 3 times
- Waits up to 60 seconds for services to come back online

**If auto-restart fails, manual steps:**

1. Check gzserver status:
   ```bash
   ps aux | grep gzserver
   tail -50 /tmp/gzserver.log
   ```

2. Manually restart Gazebo in Terminal 1:
   ```bash
   bash /root/ws/rtrd/scripts/start_gazebo_headless.sh
   ```

3. Resume training in Terminal 2:
   ```bash
   # Training will resume from last checkpoint
   python3 -m rlrd run-fs checkpoints/turtlebot3_lidar rlrd:SimTraining \
       [same parameters as before]
   ```

### Reduce Memory Pressure

If Gazebo crashes frequently, reduce the workload per epoch:

```bash
python3 -m rlrd run-fs checkpoints/turtlebot3_lidar rlrd:SimTraining \
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
    epochs=40 \
    rounds=25 \
    steps=500 \
    tag=turtlebot3_lidar
```

This gives: 40 × 25 × 500 = 500,000 steps total (more frequent Gazebo restarts via epochs)

---

## 8. Training Progress Monitoring

Monitor training without interrupting:

```bash
# Watch checkpoint directory
watch -n 10 'ls -lh checkpoints/turtlebot3_lidar/state/'

# Monitor gzserver resource usage
watch -n 2 'ps aux | grep gzserver | grep -v grep'

# Check ROS topics are active
rostopic hz /cmd_vel
rostopic hz /scan

# Check memory usage
free -h

# Monitor training logs (if redirected to file)
tail -f training.log
```

---

## 9. Total Training Steps Calculation

With the default parameters:
- **epochs** = 20
- **rounds** = 50  
- **steps** = 1000

**Total steps** = epochs × rounds × steps = 20 × 50 × 1000 = **1,000,000 steps**

This matches the "million steps" reference on the x-axis in the paper's experimental results.

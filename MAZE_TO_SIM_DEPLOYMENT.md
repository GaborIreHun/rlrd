# Deploying PointMaze Models to TurtleBot3

This guide explains how to deploy models trained on PointMaze (or other non-ROS environments) to the TurtleBot3 simulator.

## Overview

The `maze_to_sim_bridge.py` adapter enables running PointMaze-trained agents on TurtleBot3 by automatically translating between different observation spaces:

| Environment | Observation Format | Action Format |
|-------------|-------------------|---------------|
| **PointMaze** | `[x, y, velocity_x, velocity_y]` | `[force_x, force_y]` |
| **TurtleBot3** | `[x, y, theta, linear_velocity]` | `[linear_x, angular_z]` |

## Quick Start

### 1. Train on PointMaze (No ROS Required)

Train quickly on your host machine without Docker/ROS:

```bash
python3 -m rlrd run-fs checkpoints/pointmaze_trained rlrd:DcacTraining \
    Env=dmcontrol-pointmaze-delay \
    Agent.device=cpu \
    Agent.batchsize=128 \
    Agent.start_training=1000 \
    epochs=20 \
    rounds=30 \
    steps=1000
```

### 2. Deploy to TurtleBot3 Simulator

Inside your Docker container with Gazebo running:

```bash
# Start Gazebo in one terminal
roslaunch turtlebot3_gazebo turtlebot3_empty_world.launch

# In another terminal, run the bridge
python3 -m rlrd.maze_to_sim_bridge checkpoints/pointmaze_trained/state
```

The bridge will:
- ✅ Load your PointMaze-trained model
- ✅ Subscribe to `/odom` for robot state
- ✅ Translate observations automatically
- ✅ Publish commands to `/cmd_vel`

## How It Works

### Observation Translation

**TurtleBot3 → PointMaze:**
```python
# TurtleBot3 provides: [x, y, theta, velocity]
x, y, theta, velocity = turtlebot_obs

# Convert to PointMaze format: [x, y, velocity_x, velocity_y]
velocity_x = velocity * cos(theta)
velocity_y = velocity * sin(theta)
pointmaze_obs = [x, y, velocity_x, velocity_y]
```

### Action Translation

**PointMaze → TurtleBot3:**
```python
# PointMaze model outputs: [force_x, force_y]
force_x, force_y = pointmaze_action

# Convert to TurtleBot3 commands
linear_x = sqrt(force_x² + force_y²) * 0.22  # Scale to max speed
target_angle = atan2(force_y, force_x)
angular_z = P_controller(target_angle - current_theta)
```

## Example Output

```
============================================================
Maze-to-Sim Bridge Initialized
============================================================
Checkpoint: checkpoints/pointmaze_trained/state
Device: cpu
Translating PointMaze observations to TurtleBot3 actions...
============================================================

Odometry received. Starting control loop...

============================================================
Step 100
============================================================
TurtleBot3 state: pos=(0.123, 0.456), theta=1.234, vel=0.056
PointMaze obs:    pos=(0.123, 0.456), vel_x=0.019, vel_y=0.053
PointMaze action: force_x=0.234, force_y=-0.123
TurtleBot3 cmd:   linear_x=0.145, angular_z=-0.456
```

## Workflow Options

### Option 1: Quick Iteration (PointMaze → TurtleBot3)

**Best for**: Rapid prototyping and algorithm development

```bash
# 1. Train on PointMaze (fast, no ROS)
python3 -m rlrd run-fs checkpoints/maze_v1 rlrd:DcacTraining \
    Env=dmcontrol-pointmaze-delay \
    Agent.device=cpu \
    epochs=10

# 2. Test in TurtleBot3 simulator
python3 -m rlrd.maze_to_sim_bridge checkpoints/maze_v1/state

# 3. Iterate quickly without waiting for slow ROS training
```

**Pros:**
- ⚡ Fast training (minutes vs hours)
- 🔄 Quick iteration cycle
- 💻 No Docker/ROS needed for training

**Cons:**
- ⚠️ Suboptimal performance (different dynamics)
- ⚠️ Translation approximations

### Option 2: Direct Training (SimTraining)

**Best for**: Maximum performance and final deployment

```bash
# Train directly on TurtleBot3
python3 -m rlrd run-fs checkpoints/sim_trained rlrd:SimTraining

# Deploy (no translation needed)
python3 -m rlrd.ros_bridge checkpoints/sim_trained/state
```

**Pros:**
- ✅ Optimal performance
- ✅ No translation approximations
- ✅ Trained on real robot dynamics

**Cons:**
- 🐌 Slow training (hours)
- 🐳 Requires Docker/ROS/Gazebo

### Option 3: Hybrid Approach (Recommended)

**Best for**: Development speed + good performance

```bash
# 1. Prototype on PointMaze (fast)
python3 -m rlrd run-fs checkpoints/prototype rlrd:DcacTraining \
    Env=dmcontrol-pointmaze-delay \
    Agent.device=cpu \
    epochs=5

# 2. Test with adapter
python3 -m rlrd.maze_to_sim_bridge checkpoints/prototype/state

# 3. Once algorithm works, fine-tune on SimEnv
python3 -m rlrd run-fs checkpoints/finetuned rlrd:SimTraining \
    epochs=10

# 4. Deploy final model
python3 -m rlrd.ros_bridge checkpoints/finetuned/state
```

## Performance Comparison

| Metric | PointMaze+Adapter | Direct SimTraining |
|--------|-------------------|-------------------|
| Training Time | ⚡ Fast (minutes) | 🐌 Slow (hours) |
| Navigation | ✅ Good | ✅ Excellent |
| Turn Precision | ⚠️ Approximate | ✅ Precise |
| Obstacle Avoidance | ✅ Good | ✅ Excellent |
| Development Speed | ✅ Fast iteration | ⚠️ Slow iteration |

## Troubleshooting

### Robot Doesn't Move

```bash
# Check odometry is publishing
rostopic echo /odom

# Check if bridge is receiving data
# Look for "Odometry received" message
```

### Erratic Movements

The adapter uses a P-controller for orientation. You can tune it in `maze_to_sim_bridge.py`:

```python
# Line ~208
angular_z = np.clip(angle_diff * 2.0, -2.84, 2.84)
#                              ^^^
#                              Increase for faster turning
#                              Decrease for smoother turning
```

### Model Not Loading

```bash
# Verify checkpoint exists
ls -la checkpoints/pointmaze_trained/state

# Check for model_state_dict in checkpoint
python3 -c "import torch; print(torch.load('checkpoints/pointmaze_trained/state', map_location='cpu').keys())"
```

## Limitations

1. **Performance Gap**: PointMaze-trained models won't match SimEnv-trained performance
2. **Dynamics Mismatch**: Point mass dynamics ≠ differential drive dynamics
3. **Approximations**: Translation involves approximations (e.g., velocity decomposition)

**For production deployments, always use SimTraining.**

## Summary

| Your Goal | Use This |
|-----------|----------|
| Fast prototyping | PointMaze + Adapter ✅ |
| Algorithm testing | PointMaze + Adapter ✅ |
| Production deployment | SimTraining ⭐ |
| Best performance | SimTraining ⭐ |
| Quick iterations | PointMaze + Adapter ✅ |

The adapter enables **rapid development** while SimTraining provides **optimal performance**.

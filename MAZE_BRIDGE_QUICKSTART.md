# Maze-to-Sim Bridge - Quick Reference

## What It Does

Enables deploying PointMaze-trained models on TurtleBot3 simulator by translating between observation spaces.

## Usage

### 1. Train on PointMaze (Fast, No ROS)

```bash
# Fix permissions if needed (first time only)
mkdir -p checkpoints_dmc
sudo chown -R $USER:$USER checkpoints_dmc/

# Train the model
python3 -m rlrd run-fs checkpoints/my_maze_model rlrd:DcacTraining \
    Env=dmcontrol-pointmaze-delay \
    Agent.device=cpu \
    Agent.batchsize=128 \
    Agent.start_training=1000 \
    epochs=20 \
    rounds=30 \
    steps=1000
```

### 2. Deploy to TurtleBot3

```bash
# In Docker with Gazebo running
python3 -m rlrd.maze_to_sim_bridge checkpoints/my_maze_model/state
```

## Quick Test

```bash
# Test the bridge setup
./test_maze_bridge.sh
```

## Documentation

- Full guide: [MAZE_TO_SIM_DEPLOYMENT.md](MAZE_TO_SIM_DEPLOYMENT.md)
- Training strategies: [training_strategy.md](training_strategy.md)
- Fix details: [MAZE_TRAINING_FIX.md](MAZE_TRAINING_FIX.md)

## Comparison

| Approach | Training Time | Performance | Use Case |
|----------|--------------|-------------|----------|
| **PointMaze + Adapter** | Fast (minutes) | Good | Rapid prototyping |
| **SimTraining** | Slow (hours) | Excellent | Production |

## When to Use

✅ **Use Maze-to-Sim Bridge when:**
- Rapidly prototyping algorithms
- Testing without ROS overhead
- Quick iteration cycles needed

⭐ **Use SimTraining when:**
- Final deployment
- Maximum performance needed
- Training time not critical

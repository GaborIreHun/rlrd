# Training Strategy for RLRD

## Recommended Approach: Use SimTraining Configuration

The simplest and most effective way to train on the TurtleBot3 Gazebo simulator is to use the pre-configured `SimTraining`:

### Quick Start (Recommended)

**With checkpointing (resumable training):**
```bash
python3 -m rlrd run-fs checkpoints/simtraining_checkpoint rlrd:SimTraining
```

**Without checkpointing:**
```bash
python3 -m rlrd run rlrd:SimTraining
```

This configuration provides:
- ✅ 4D odometry observations (x, y, theta, velocity)
- ✅ 2D actions (linear + angular velocity)
- ✅ Delay-aware DCAC agent (0-2 obs delay, 0-3 action delay)
- ✅ Sensible hyperparameters for TurtleBot3
- ✅ Proper episode termination (500 steps max, ±5.0 position limit)

See `SIMTRAINING.md` for complete documentation.

---

## Alternative: Custom Training Configuration

If you need to customize training beyond SimTraining's defaults:

### For CPU training:
```bash
python3 -m rlrd run rlrd:DcacTraining \
    Env=SimEnv \
    Env.min_observation_delay=0 \
    Env.sup_observation_delay=2 \
    Env.min_action_delay=0 \
    Env.sup_action_delay=3 \
    Agent.batchsize=64 \
    Agent.memory_size=500000 \
    Agent.lr=0.0003 \
    Agent.discount=0.99 \
    Agent.target_update=0.005 \
    Agent.reward_scale=5.0 \
    Agent.entropy_scale=1.0 \
    Agent.start_training=5000 \
    Agent.Model.num_critics=2 \
    Agent.device=cpu \
    epochs=20 \
    rounds=30 \
    steps=500 \
    tag=turtlebot3_custom
```

### For GPU training:
```bash
python3 -m rlrd run rlrd:DcacTraining \
    Env=SimEnv \
    Env.min_observation_delay=0 \
    Env.sup_observation_delay=2 \
    Env.min_action_delay=0 \
    Env.sup_action_delay=3 \
    Agent.batchsize=64 \
    Agent.memory_size=500000 \
    Agent.lr=0.0003 \
    Agent.discount=0.99 \
    Agent.target_update=0.005 \
    Agent.reward_scale=5.0 \
    Agent.entropy_scale=1.0 \
    Agent.start_training=5000 \
    Agent.Model.num_critics=2 \
    Agent.device=cuda \
    epochs=20 \
    rounds=30 \
    steps=500 \
    tag=turtlebot3_custom
```

---

## Training on Other Environments

### Quick Testing Without ROS/Gazebo

**IMPORTANT**: The `gym-maze` (maze-v0) environment has **discrete actions** (up/down/left/right) and is **incompatible** with DCAC/SAC algorithms which require continuous control. 

For quick testing without ROS, use these working alternatives:

#### Option 1: Pendulum (Recommended for Quick Tests)
Fastest option - classic control problem with continuous actions:

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

#### Option 2: DeepMind Control PointMaze
Physics-based maze navigation with continuous actions:

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

**Why gym-maze doesn't work:**
- maze-v0 action space: `Discrete(4)` (discrete: 0=up, 1=down, 2=left, 3=right)
- DCAC/SAC requirement: `Box` (continuous: e.g., [-1.0, 1.0])
- This fundamental incompatibility cannot be fixed without modifying the algorithms

### Phase 1: Develop Algorithm (No Simulator)
Use Pendulum or PointMaze for algorithm development:

```bash
# Pendulum - simplest and fastest
python3 -m rlrd run-fs checkpoints/pendulum_dev rlrd:DcacTraining \
    Env=RandomDelay-Pendulum-v0 \
    Agent.device=cpu \
    Agent.batchsize=128 \
    Agent.memory_size=1000000 \
    Agent.lr=0.0003 \
    Agent.discount=0.99 \
    Agent.target_update=0.005 \
    Agent.reward_scale=5.0 \
    Agent.entropy_scale=1.0 \
    Agent.start_training=10000 \
    Agent.Model.num_critics=2 \
    epochs=20 \
    rounds=50 \
    steps=2000 \
    tag=maze_delay_training
```

**Alternative**: Use other gym environments like `Pendulum-v0` for quick testing:
```bash
python3 -m rlrd run rlrd:DcacTraining \
    Env.id=Pendulum-v0 \
    epochs=10 \
    rounds=20 \
    steps=200
```

### Phase 2: Transfer to Simulator
Once you have a working agent, you can optionally transfer learned features to the simulator using SimTraining.

---

## Deployment

After training, deploy the agent with:

```bash
# Auto-detect checkpoint format
python3 -m rlrd.ros_bridge checkpoints/simtraining_checkpoint/state

# Or specify explicitly
python3 -m rlrd.ros_bridge checkpoints/simtraining_checkpoint/state 4
```

The deployment script will:
- Load the trained model
- Subscribe to `/odom` for observations
- Publish actions to `/cmd_vel`
- Show detailed logging every 100 steps

---

## Key Differences from Old Approach

**Old (Pre-SimTraining):**
- ❌ Used 6D joint states (incompatible with TurtleBot3)
- ❌ 1D actions (linear velocity only)
- ❌ Episodes never completed (infinite loops)
- ❌ NaN velocities crashed training
- ❌ 20+ command-line parameters

**New (SimTraining):**
- ✅ Uses 4D odometry (position, orientation, velocity)
- ✅ 2D actions (linear + angular velocity)
- ✅ Episodes complete properly (500 steps or boundary)
- ✅ Robust velocity calculation from position changes
- ✅ Simple one-line command
- ✅ Resumable checkpointing with `run-fs`

---

## See Also

- `SIMTRAINING.md` - Complete SimTraining documentation
- `simulator_docker_new copy.md` - Docker workflow for training and deployment
- `README.md` - Project overview and setup
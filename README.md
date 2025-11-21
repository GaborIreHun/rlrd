# Reinforcement Learning with Random Delays

PyTorch implementation of our paper [Reinforcement Learning with Random Delays (ICLR 2020)](https://openreview.net/forum?id=QFYnKlBJYR) – [[Arxiv]](https://arxiv.org/abs/2010.02966)

## Features

- **DCAC Agent**: Delay-aware actor-critic with support for random delays
- **SAC Agent**: Soft Actor-Critic implementation  
- **PointMaze Environment**: DMControl-based point mass navigation with configurable delays
- **TurtleBot3 Integration**: Deploy trained agents to ROS/Gazebo simulation
- **Maze-to-Sim Bridge**: Load trained PointMaze agents and use in different environments

## Quick Start

### Virtual Environment Setup
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

### Installation
This repository can be pip-installed via:
```bash
pip install git+https://github.com/rmst/rlrd.git
```

### Basic Training

DC/AC can be run on a simple 1-step delayed `Pendulum-v0` task via:
```bash
python -m rlrd run rlrd:DcacTraining Env.id=Pendulum-v0
```

Hyperparameters can be set via command line. E.g.:
```bash
python -m rlrd run rlrd:DcacTraining \
Env.id=Pendulum-v0 \
Env.min_observation_delay=0 \
```

### Using Trained Agents

**Test agent locally (no ROS required):**
```bash
python3 test_maze_agent.py
```

**Load agent in Python:**
```python
from rlrd.maze_to_sim_bridge import MazeToSimBridge

bridge = MazeToSimBridge('checkpoints/maze_model_1/state', use_ros=False)
action = bridge.get_action(observation)  # observation: [x, y, vel_x, vel_y]
```

**Deploy to TurtleBot3 simulation:**
```bash
# Terminal 1: Launch Gazebo
roslaunch turtlebot3_gazebo turtlebot3_world.launch

# Terminal 2: Run agent controller
python3 run_sim_controller.py
```

## Documentation

- **[Maze-to-Sim Guide](MAZE_TO_SIM_GUIDE.md)**: Comprehensive guide for loading and deploying trained agents
- **[Training Strategy](training_strategy.md)**: Training tips and strategies
- **[Simulation Deployment](SIMTRAINING.md)**: Deploy to simulation environments

## Checkpoints

Checkpoints are saved using `rlrd.util.dump()` and loaded with `rlrd.util.load()`:

```python
from rlrd.util import load

# Load checkpoint
training = load('checkpoints/maze_model_1/state')
agent = training.agent

# Access training info
print(f"Environment: {training.Env}")
print(f"Epoch: {training.epoch}/{training.epochs}")
```

**Important**: Use `load()` from `rlrd.util`, NOT `torch.load()`. Checkpoints are pickle format, not PyTorch format.

## Troubleshooting

### Robot Not Moving in Simulation
1. Check ROS topics: `python3 check_ros_topics.py`
2. Test direct control: `python3 test_robot_motion.py`
3. Verify odometry updates: `rostopic echo /odom`
4. Increase action scaling in `maze_to_sim_bridge.py`

### Import Errors (rospy)
- Source ROS: `source /opt/ros/noetic/setup.bash`
- Or use `use_ros=False` for non-ROS testing

### Checkpoint Loading Error
- Error: "Invalid magic number; corrupt file?"
- Solution: Use `load()` from `rlrd.util`, not `torch.load()`

See [MAZE_TO_SIM_GUIDE.md](MAZE_TO_SIM_GUIDE.md) for detailed troubleshooting.

## Project Structure

```
rlrd/
├── __init__.py              # Main training specs
├── sac.py                   # SAC agent
├── dcac.py                  # DCAC agent  
├── sac_models.py            # SAC models
├── dcac_models.py           # DCAC models with delay handling
├── envs.py                  # Environment constructors
├── wrappers.py              # Environment wrappers (delays)
├── training.py              # Training loop
├── testing.py               # Evaluation
├── memory.py                # Replay buffer
├── util.py                  # Utilities (save/load)
├── maze_to_sim_bridge.py    # Agent deployment bridge ✨ NEW
├── test_maze_agent.py       # Test script ✨ NEW
├── run_sim_controller.py    # ROS controller ✨ NEW
├── check_ros_topics.py      # ROS diagnostics ✨ NEW
└── test_robot_motion.py     # Robot motion test ✨ NEW
```

### Getting Started
Env.sup_observation_delay=2 \
Env.min_action_delay=0 \
Env.sup_action_delay=3 \
Agent.batchsize=128 \
Agent.memory_size=1000000 \
Agent.lr=0.0003 \
Agent.discount=0.99 \
Agent.target_update=0.005 \
Agent.reward_scale=5.0 \
Agent.entropy_scale=1.0 \
Agent.start_training=10000 \
Agent.device=cuda \
Agent.training_steps=1.0 \
Agent.loss_alpha=0.2 \
Agent.Model.hidden_units=256 \
Agent.Model.num_critics=2
```

Note that our gym wrapper adds a constant 1-step delay to the action delay, i.e. ```Env.min_action_delay=0``` actually means that the minimum action delay is 1 whereas ```Env.min_observation_delay=0``` means that the minimum observation delay is 0 (we assume that the action delay cannot be less than 1 time-step, e.g. for action inference).
For instance:
- ```Env.min_observation_delay=0 Env.sup_observation_delay=2``` means that the observation delay is randomly 0 or 1.
- ```Env.min_action_delay=0 Env.sup_action_delay=2``` means that the action delay is randomly 1 or 2.
- ```Env.min_observation_delay=1 Env.sup_observation_delay=2``` means that the observation delay is always 1.
- ```Env.min_observation_delay=0 Env.sup_observation_delay=3``` means that the observation delay is randomly 0, 1 or 2.
- etc.


### Mujoco Experiments
To install Mujoco, follow the instructions at [openai/gym](https://github.com/openai/gym).
The following environments were used in the paper:

![MuJoCo](resources/mujoco_horizontal.png)


To train DC/AC on a 1-step delayed version of `HalfCheetah-v2`, run:
```bash
python -m rlrd run rlrd:DcacTraining Env.id=HalfCheetah-v2
```

To train SAC on a 1-step delayed version of `Ant-v2` run:
```bash
python -m rlrd run rlrd:DelayedSacTraining Env.id=Ant-v2
```

### Weights and Biases API
Your curves can be exported directly to the Weights and Biases (wandb) website by using `run-wandb`.
For example, to run DC/AC on Pendulum with a 1-step delay and export the curves to your wanb project:

```terminal
python -m rlrd run-wandb \
yourWandbID \
yourWandbProjectName \
aNameForTheWandbRun \
aFileNameForLocalCheckpoints \
rlrd:DcacTraining Env.id=Pendulum-v0
```

Use the optional hyperparameters descibed before to play with more meaningful delays.

### Contribute / known issues
Contributions are welcome.
Please submit a PR with your name in the contributors list.

We did not yet optimize our python implementation of DC/AC, this is the most important thing to do right now as it is quite slow.

In particular, a lot of time is wasted when artificially re-creating a batched tensor for computing the value estimates in one forward pass, and the replay buffer is inefficient.
See the `#FIXME` in [dcac.py](https://github.com/rmst/rlrd/blob/master/rlrd/dcac.py)

# Experiment-1 Execution

<!-- source /home/apa/Desktop/PHD/Research/rtrd/rlrd/.venv/bin/activate -->
<!-- Activate virtual environment -->
source .venv/bin/activate

<!-- Run model -->
python -m rlrd run rlrd:DcacTraining Env.id=Pendulum-v0 Env.min_observation_delay=0 Env.sup_observation_delay=1 Env.min_action_delay=0 Env.sup_action_delay=1

<!--  -->
<!-- python -m rlrd.evaluate --model ../checkpoints/sac_model_epoch_X.pt --env Pendulum-v0 --steps 2000 --seed 42 -->
python -m rlrd.evaluate --model checkpoints/sac_model_epoch_10.pt --env Pendulum-v0 --steps 2000 --seed 42 --episodes 3 --min_observation_delay 0 --sup_observation_delay 1 --min_action_delay 0 --sup_action_delay 1

# Simulator

## Install ROS 1 Noetic

### 1. Set up sources
sudo sh -c 'echo "deb http://packages.ros.org/ros/ubuntu $(lsb_release -sc) main" > /etc/apt/sources.list.d/ros-latest.list'

### 2. Add the ROS key
sudo apt install curl
curl -s https://raw.githubusercontent.com/ros/rosdistro/master/ros.asc | sudo apt-key add -

### 3. Install base ROS (includes rospy)
sudo apt update
sudo apt install ros-noetic-desktop-full

### 4. Initialize rosdep
sudo rosdep init
rosdep update

### 5. Add environment to bashrc
echo "source /opt/ros/noetic/setup.bash" >> ~/.bashrc
source ~/.bashrc

### 6. Install ROS Python dependencies
sudo apt install python3-rosinstall python3-rosinstall-generator python3-wstool build-essential

### 7. Install rospy specifically (already included in step 3, but just in case)
sudo apt install ros-noetic-rospy




new_evaluate_command:
python -m rlrd.evaluate \
  --model checkpoints/best_model.pt \
  --env SimEnv \
  --episodes 3 \
  --steps 1000 \
  --render_mode video \
  --log_dir /root/ws/rtrd/logs







<!-- pip install gym==0.21.0 -->
<!-- docker stop $(docker ps -qf "ancestor=rlrd-gazebo") -->
---

### **Step 1: Build the Image**

```bash copy
sudo docker build -t rlrd-gazebo -f Dockerfile . --no-cache
```

*(Builds your custom RL+ROS+Gazebo image with all dependencies)*

---
==================================================================================
### **Step 2: Start the Container**

**Choose ONE option based on your needs:**

#### **Option A: Headless Mode (Recommended for Training)**

**For CPU-only training (faster, no GUI):**
```bash copy
# On host - clean up any existing processes first
sudo pkill -9 -f gzserver
sudo pkill -9 -f gzclient

# Start container without X11/display
sudo docker run -it --rm \
  --net=host \
  -v /mnt/research/rtrd/rlrd:/root/ws/rtrd \
  rlrd-gazebo
```

*This is the recommended setup for RL training - no GUI overhead, faster simulation.*

---

#### **Option B: GUI Mode (For Monitoring/Debugging)**

**With display support (to watch the simulation):**
```bash copy
xhost +local:root
sudo docker run -it --rm \
  --net=host \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v /mnt/research/rtrd/rlrd:/root/ws/rtrd \
  rlrd-gazebo
```

**With GPU acceleration:**
```bash copy
xhost +local:root
sudo docker run -it --rm \
  --gpus all \
  --net=host \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v /mnt/research/rtrd/rlrd:/root/ws/rtrd \
  rlrd-gazebo
```

*Gives you a shell inside the running container, with code mounted and GUI working.*

---

**⚠️ Important:** 
- Only run `docker run` **once**! For additional terminals, use Step 3 below.
- If using `--net=host`, only ONE container can run Gazebo at a time (port conflict)
- Always clean up old gzserver processes before starting: `sudo pkill -9 -f gzserver`

---

### **Step 3: Attach Additional Terminals to the Same Container**

**Open new host terminals and attach them to the running container:**

```bash copy
sudo docker exec -it $(docker ps -qf "ancestor=rlrd-gazebo") bash
```

*(You can open as many shells as needed - each new host terminal should use this command)*

---

### **Step 4: In Each Container Terminal, Set Up ROS Environment**

**Run this in every container terminal before executing commands:**

```bash copy
source /opt/ros/noetic/setup.bash
source /root/venv_rlrd/bin/activate
cd /root/ws/rtrd
```

---

### **Step 5: Training Workflow**

#### **Container Terminal 1: Launch Gazebo Simulator**

**For GUI (visual monitoring):**
```bash copy
roslaunch turtlebot3_gazebo turtlebot3_world.launch
```

**For Headless Training (faster, recommended):**
```bash copy
# Use the helper script for reliable headless startup
source /opt/ros/noetic/setup.bash
bash /root/ws/rtrd/scripts/start_gazebo_headless.sh
```

*The script will automatically start roscore, gzserver, spawn the robot, and verify all services are ready.*

**Alternative manual headless method:**
```bash copy
source /opt/ros/noetic/setup.bash
export TURTLEBOT3_MODEL=burger

# Start roscore if not running
roscore > /tmp/roscore.log 2>&1 &
sleep 3

# Start gzserver without GUI
WORLD=$(rospack find turtlebot3_gazebo)/worlds/turtlebot3_world.world
gzserver -s libgazebo_ros_init.so -s libgazebo_ros_factory.so "$WORLD" > /tmp/gzserver.log 2>&1 &
sleep 5

# Spawn robot
rosrun gazebo_ros spawn_model -urdf -model turtlebot3_burger -x -2.0 -y -0.5 -z 0.0 -param robot_description &
sleep 3

# Verify services are ready
rosservice list | grep gazebo
```

*Wait for Gazebo to fully load before proceeding to Terminal 2*

---

#### **Container Terminal 2: Run Training**

**Recommended: Using SimTraining configuration with checkpointing**
```bash copy
python3 -m rlrd run-fs checkpoints/simtraining_checkpoint rlrd:SimTraining
```

*This uses the pre-configured SimTraining setup with sensible defaults for TurtleBot3 simulation*

---

**Alternative: Manual configuration (for advanced users)**

**For CPU training:**

ROS Simulator training:

```bash copy
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
    tag=turtlebot3_training
```
Without ROS training legacy statistics format (pt file):

```bash copy
python3 -m rlrd run rlrd:DcacTraining \
    Env=dmcontrol-pointmaze-delay \
    Env.min_observation_delay=0 \
    Env.sup_observation_delay=2 \
    Env.min_action_delay=0 \
    Env.sup_action_delay=3 \
    Agent.batchsize=128 \
    Agent.memory_size=1000000 \
    Agent.lr=0.0003 \
    Agent.discount=0.99 \
    Agent.device=cpu \
    epochs=20 \
    rounds=50 \
    steps=1000 \
    tag=pointmaze_fast
```
Enhanced statistics (non-pt file), configure checkpoints/pointmaze_1 according to desired stats saving path:

```bash copy
python3 -m rlrd run-fs checkpoints/pointmaze_1 rlrd:DcacTraining \
    Env=dmcontrol-pointmaze-delay \
    Env.min_observation_delay=0 \
    Env.sup_observation_delay=2 \
    Env.min_action_delay=0 \
    Env.sup_action_delay=3 \
    Agent.batchsize=128 \
    Agent.memory_size=1000000 \
    Agent.lr=0.0003 \
    Agent.discount=0.99 \
    Agent.device=cpu \
    epochs=20 \
    rounds=50 \
    steps=1000 \
    tag=pointmaze_fast
```

**For GPU training (if container started with --gpus all):**
```bash copy
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
    tag=turtlebot3_training
```

**Running with Lidar**

```bash copy
python3 -m rlrd run-fs checkpoints/turtlebot3_lidar rlrd:SimTraining \
    Env=SimEnv \
    Env.lidar_dim=180 \
    Env.min_observation_delay=0 \
    Env.sup_observation_delay=2 \
    Env.min_action_delay=0 \
    Env.sup_action_delay=3 \
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

*Training will save models to checkpoint directory:*
- `checkpoints/simtraining_checkpoint/state` - Latest checkpoint (with SimTraining)
- `checkpoints_dmc/best_model.pt` - Best performing model (with DcacTraining)
- `checkpoints_dmc/sac_model_epoch_X.pt` - Model after each epoch (with DcacTraining)

---

### **Step 6: Deployment Workflow (After Training)**

#### **Container Terminal 1: Launch Gazebo Simulator**

```bash copy
roslaunch turtlebot3_gazebo turtlebot3_world.launch
```

---

#### **Container Terminal 2: Run Trained RL Agent**

**Recommended: Auto-detect checkpoint (works with SimTraining checkpoints):**
```bash copy
python3 -m rlrd.ros_bridge checkpoints/simtraining_checkpoint/state
```

**Or let it find the checkpoint automatically:**
```bash copy
python3 -m rlrd.ros_bridge
```

**The agent will:**
- ✅ Auto-detect observation dimension (4D odometry)
- ✅ Auto-detect action dimension (2D: linear + angular)
- ✅ Auto-detect if model uses delays
- ✅ Subscribe to `/odom` for observations
- ✅ Publish commands to `/cmd_vel`
- ✅ Show detailed logging every 100 steps

**Example output:**
```
[INFO] Loading checkpoint from checkpoints/simtraining_checkpoint/state
[INFO] Inferred 4D observation from model (delays=True)
[INFO] Detected action dimension: 2D
[INFO] Using delay-aware model (buffer_size=4)
[INFO] Observation delays: 0-1, Action delays: 0-2
[INFO] First observation: x=-1.114, y=-0.911, theta=-1.409, vel=0.000
[INFO] First action: linear=0.074, angular=-0.042
[INFO] Step 100: avg_linear=0.312 m/s
[INFO]   avg_angular=-0.089 rad/s
[INFO]   position: x=1.234, y=-0.456, current_vel=0.298
```

**Complete Deployment Steps**
Terminal 1: Launch Gazebo (if not already running)
```bash copy
# On host
xhost +local:root
sudo docker run -it --rm \
  --net=host \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v /mnt/research/rtrd/rlrd:/root/ws/rtrd \
  rlrd-gazebo

# Inside container
source /opt/ros/noetic/setup.bash
roslaunch turtlebot3_gazebo turtlebot3_world.launch
```

Wait for Gazebo to load completely.

Terminal 2: Deploy Your Trained Agent

```bash copy
# First, attach to the container
sudo docker exec -it $(docker ps -qf "ancestor=rlrd-gazebo") bash

# Then INSIDE the container, run these commands in order:
source /opt/ros/noetic/setup.bash
source /root/venv_rlrd/bin/activate
cd /root/ws/rtrd

# Now run the controller
python3 run_sim_controller.py checkpoints/pointmaze_1/state
```

**Note on old checkpoints:**
If you have old `.pt` checkpoint files (e.g., `sac_model_epoch_10.pt`) from previous training, these are incompatible with TurtleBot3 because they were trained on different observations. Use `ros_bridge_legacy.py` if needed, but expect poor performance:
```bash copy
python3 -m rlrd.ros_bridge_legacy checkpoints/sac_model_epoch_10.pt
```
The legacy script outputs near-zero actions because the old model doesn't understand TurtleBot3's wheel joints.



---

### **Step 7: (Optional) Diagnostics & Monitoring**

#### **Container Terminal 3+: ROS Diagnostics**

**Monitor command velocity:**
```bash copy
rostopic echo /cmd_vel
```

**View ROS node graph:**
```bash copy
rqt_graph
```

**Check command frequency:**
```bash copy
rostopic hz /cmd_vel
```

**Monitor odometry:**
```bash copy
rostopic echo /odom
```

---

## **Quick Reference: Workflow Summary**

### **For Training:**
1. Host Terminal 1: `docker run` → Start container
2. Container Terminal 1: `roslaunch` → Launch Gazebo
3. Host Terminal 2: `docker exec` → Attach new terminal
4. Container Terminal 2: `python3 -m rlrd run-fs checkpoints/simtraining_checkpoint rlrd:SimTraining` → Train agent

### **For Deployment:**
1. Host Terminal 1: `docker run` → Start container
2. Container Terminal 1: `roslaunch` → Launch Gazebo
3. Host Terminal 2: `docker exec` → Attach new terminal
4. Container Terminal 2: `python3 -m rlrd.ros_bridge` → Run trained agent

### **Key Points:**
- ✅ Use `docker run` **once** to start the container
- ✅ Use `docker exec` for **all additional terminals**
- ✅ All terminals share the same ROS master
- ✅ **Recommended**: Use `SimTraining` configuration for simplified setup
- ✅ Checkpoints saved to `checkpoints/simtraining_checkpoint/` (resumable training)
- ✅ `ros_bridge.py` auto-detects checkpoint format (4D odometry, 2D actions, delays)
- ✅ Detailed logging shows position, velocity, and actions every 100 steps
- ✅ Code changes on host are reflected in container (mounted volume)
- ⚠️ Old `.pt` files from previous training won't work well (different observations)

---

## **Troubleshooting**

### **Problem: "Unable to start server [bind: Address already in use]"**

**Symptom:** gzserver fails to start with error:
```
[Err] [Master.cc:96] EXCEPTION: Unable to start server[bind: Address already in use]
```

**Root Cause:** Another gzserver is already running (on host or in another container) using port 11345.

**Solution:**

**On the HOST machine (not inside container):**
```bash
# Find what's using port 11345
sudo ss -tlnp | grep 11345

# Kill all Gazebo processes
sudo pkill -9 -f gzserver
sudo pkill -9 -f gzclient

# Verify port is free
sudo ss -tlnp | grep 11345  # should return nothing
```

**Then restart your container and try again.**

**Prevention:** 
- When using `--net=host`, only run ONE container with Gazebo at a time
- Always clean up before starting: `sudo pkill -9 -f gzserver` on the HOST
- The helper script (`start_gazebo_headless.sh`) automatically checks for port conflicts

---

### **Problem: "Failed to connect to Gazebo reset service"**

**Symptom:** Training fails with error:
```
RuntimeError: Gazebo simulation not available. Please restart Gazebo and try again.
```

**Solution:**
1. Check if gzserver is actually running:
   ```bash
   ps aux | grep gzserver | grep -v grep
   ```

2. Check if Gazebo services are available:
   ```bash
   rosservice list | grep gazebo
   ```
   You should see services like `/gazebo/reset_simulation`, `/gazebo/pause_physics`, etc.

3. If services are missing, check gzserver log:
   ```bash
   tail -n 100 /tmp/gzserver.log
   ```

4. Common fixes:
   - **gzserver crashed:** Look for "Aborted" or "core dumped" in logs. This usually means:
     - Missing `robot_description` parameter (spawn robot first)
     - GPU/display issues (use `LIBGL_ALWAYS_SOFTWARE=1` if needed)
     - Insufficient memory
   
   - **Services not registering:** Restart with the helper script:
     ```bash
     pkill -f gzserver; pkill -f roscore
     source /opt/ros/noetic/setup.bash
     bash /root/ws/rtrd/scripts/start_gazebo_headless.sh
     ```

### **Problem: GUI still appears when trying headless**

**Solution:**
1. Make sure `DISPLAY` is unset:
   ```bash
   unset DISPLAY
   echo $DISPLAY  # should be empty
   ```

2. Or start container without X11 forwarding:
   ```bash
   # On host (no -e DISPLAY, no -v /tmp/.X11-unix)
   sudo docker run -it --rm --net=host \
     -v /mnt/research/rtrd/rlrd:/root/ws/rtrd \
     rlrd-gazebo
   ```

3. Kill gzclient if it's running:
   ```bash
   pkill -f gzclient
   ```

### **Problem: Training is slow**

**Solutions:**
1. **Use headless mode** (biggest speedup):
   ```bash
   bash /root/ws/rtrd/scripts/start_gazebo_headless.sh
   ```

2. **Reduce physics accuracy** (edit world file or set):
   ```bash
   export GAZEBO_REAL_TIME_UPDATE_RATE=100  # default 1000
   ```

3. **Use GPU acceleration** (if available):
   ```bash
   # Start container with GPU
   sudo docker run -it --rm --gpus all --net=host \
     -v /mnt/research/rtrd/rlrd:/root/ws/rtrd \
     rlrd-gazebo
   ```

4. **Reduce sensor data** (if not using LiDAR):
   - Comment out LiDAR in training config or set `Env.lidar_dim=0`

### **Problem: Container exits immediately**

**Symptom:** `docker run` command exits with code 125

**Solution:**
Check for typos in the command. Common issue:
```bash
# WRONG (typo: rlrd-gazeb)
rlrd-gazeb

# CORRECT
rlrd-gazebo
```

### **Problem: ROS nodes can't find each other**

**Solution:**
1. Ensure all terminals source ROS:
   ```bash
   source /opt/ros/noetic/setup.bash
   ```

2. Check ROS_MASTER_URI:
   ```bash
   echo $ROS_MASTER_URI  # should be http://localhost:11311
   ```

3. List active nodes:
   ```bash
   rosnode list
   ```

4. Check network connectivity:
   ```bash
   rostopic list
   rostopic hz /odom  # should show ~50-100 Hz
   ```

---


terminal 1:

sudo docker run -it --rm \
  --net=host \
  -v /mnt/research/rtrd/rlrd:/root/ws/rtrd \
  rlrd-gazebo
source /opt/ros/noetic/setup.bash
bash /root/ws/rtrd/scripts/start_gazebo_headless.sh


terminal 2:

sudo docker exec -it $(docker ps -qf "ancestor=rlrd-gazebo") bash
source /opt/ros/noetic/setup.bash
source /root/venv_rlrd/bin/activate
cd /root/ws/rtrd
python3 -m rlrd run-fs checkpoints/turtlebot3_lidar rlrd:SimTraining



Found world file: /opt/ros/noetic/share/turtlebot3_gazebo/worlds/turtlebot3_world.world
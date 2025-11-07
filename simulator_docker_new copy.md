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
### **Step 2: Start the Container with GUI Support (One Time Only)**

**This starts your main container and gives you Terminal 1:**

```bash copy
xhost +local:root
sudo docker run -it --rm \
  --net=host \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v /mnt/research/rtrd/rlrd:/root/ws/rtrd \
  rlrd-gazebo
```

**With GPU**
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

**⚠️ Important:** Only run this **once**! For additional terminals, use Step 3 below.

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

```bash copy
roslaunch turtlebot3_gazebo turtlebot3_world.launch
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

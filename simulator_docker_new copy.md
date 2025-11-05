<!-- pip install gym==0.21.0 -->
---

### **Step 1: Build the Image**

```bash
sudo docker build -t rlrd-gazebo -f Dockerfile . --no-cache
```

*(Builds your custom RL+ROS+Gazebo image with all dependencies)*

---
==================================================================================
### **Step 2: Start the Container with GUI Support**

```bash
xhost +local:root
sudo docker run -it --rm \
  --net=host \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v /mnt/research/rtrd/rlrd:/root/ws/rtrd \
  rlrd-gazebo
```

*Gives you a shell inside the running container, with code mounted and GUI working.*

---

### **Step 3: (Optional) Attach Additional Terminals**

To control RL agent, run diagnostics, etc.:

```bash
sudo docker exec -it $(docker ps -qf "ancestor=rlrd-gazebo") bash
```

*(You can open as many shells as needed)*

---

### **Step 4: In Each Terminal, Set Up ROS**

```bash
# Set up ROS and venv
source /opt/ros/noetic/setup.bash
source /root/venv_rlrd/bin/activate

# # 2. Set environment variables
# export TURTLEBOT3_MODEL=burger
# # 3. Install package (IMPORTANT: must be in the right directory)
# cd /root/ws/rtrd    # Directory containing setup.py
# # 4. Set PYTHONPATH
# export PYTHONPATH=$PYTHONPATH:/root/ws/rtrd
```

---

### **Terminal 1: Launch Gazebo Simulator**

```bash
roslaunch turtlebot3_gazebo turtlebot3_world.launch
```

---

### **Terminal 2: Start the RL Agent-ROS Bridge**

```bash
python -m rlrd.ros_bridge
```

---

### **Terminal 3+ (Optional): ROS Diagnostics/Visualization**

```bash
rostopic echo /cmd_vel
```

or

```bash
rqt_graph
```

or

```bash
rostopic hz /cmd_vel
```

---

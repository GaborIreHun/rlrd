# Quick Reference: Deploy PointMaze Agent to TurtleBot3

## 🚀 Quick Start (2 Commands)

### Terminal 1: Launch Gazebo
```bash
sudo docker run -it --rm --net=host -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v /mnt/research/rtrd/rlrd:/root/ws/rtrd rlrd-gazebo

source /opt/ros/noetic/setup.bash
roslaunch turtlebot3_gazebo turtlebot3_world.launch
```

### Terminal 2: Deploy Agent
```bash
sudo docker exec -it $(docker ps -qf "ancestor=rlrd-gazebo") bash
source /opt/ros/noetic/setup.bash
source /root/venv_rlrd/bin/activate
cd /root/ws/rtrd

python3 run_sim_controller.py checkpoints/pointmaze_1/state
```

---

## 📊 Current Configuration

**Action Scaling (Updated - 22x more aggressive):**
- Linear velocity:  `force_x × 5.0`  (clipped to ±0.22 m/s)
- Angular velocity: `force_y × 10.0` (clipped to ±2.84 rad/s)

**Expected Velocities:**
- Linear: 0.05 - 0.15 m/s (walking speed)
- Angular: 0.3 - 1.0 rad/s (moderate turning)

---

## 🔧 Diagnostic Tools

### Test Scaling Factors
```bash
python3 test_action_scaling.py checkpoints/pointmaze_1/state
```

### Monitor Robot
```bash
# Watch commands being sent
rostopic echo /cmd_vel

# Check command rate
rostopic hz /cmd_vel

# View odometry
rostopic echo /odom
```

---

## ⚙️ Adjust Scaling (if needed)

**File:** `rlrd/maze_to_sim_bridge.py` (line ~268)

```python
def translate_action(self, pointmaze_action):
    force_x, force_y = pointmaze_action
    
    # TUNE THESE
    linear_x = force_x * 5.0   # Range: 2.0 - 10.0
    angular_z = force_y * 10.0  # Range: 5.0 - 15.0
    
    # Don't change these (robot limits)
    linear_x = np.clip(linear_x, -0.22, 0.22)
    angular_z = np.clip(angular_z, -2.84, 2.84)
    return linear_x, angular_z
```

**Restart controller after changes**

---

## 🎯 Better Solution: Native Training

If robot doesn't navigate well with transfer learning:

```bash
# Train directly on TurtleBot3 (2-3 hours)
python3 -m rlrd run-fs checkpoints/turtlebot_native rlrd:SimTraining

# Deploy native checkpoint
python3 run_sim_controller.py checkpoints/turtlebot_native/state
```

**Benefits:** No domain gap, better performance, no tuning needed

---

## ✅ Success Checklist

- [ ] Robot moves visibly (not crawling)
- [ ] Turns in response to environment  
- [ ] Doesn't get stuck on walls
- [ ] Velocities in expected range
- [ ] `/cmd_vel` publishing at ~10 Hz

---

## 🐛 Quick Troubleshooting

| Issue | Solution |
|-------|----------|
| "ROS not available" | Run `source /opt/ros/noetic/setup.bash` |
| Robot too slow | Increase scaling (try 10.0, 15.0) |
| Robot too fast | Decrease scaling (try 2.0, 5.0) |
| No `/cmd_vel` | Check Gazebo running, ROS sourced |
| Robot spins in place | Reduce angular scale |

---

## 📁 Key Files

- **`rlrd/maze_to_sim_bridge.py`** - Action translation logic
- **`run_sim_controller.py`** - Deployment script  
- **`test_action_scaling.py`** - Diagnostic tool
- **`ACTION_SCALING_CHANGES.md`** - Full documentation

---

## 🔗 Related Commands

```bash
# List checkpoints
ls checkpoints/

# View checkpoint contents
ls checkpoints/pointmaze_1/

# Check ROS topics
rostopic list

# Test ROS connection
rostopic echo /odom -n 1
```

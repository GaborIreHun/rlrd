# Documentation Index

**Complete guide to running RL training with Gazebo simulator and automated verification.**

---

## 📖 Documentation Overview

### 🚀 Quick Start (Start Here!)

1. **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Essential commands only
   - Terminal 1: Gazebo startup
   - Terminal 2: Training commands (RLRD/SAC/RTAC)
   - Monitoring and troubleshooting
   - **Best for: Getting started quickly**

2. **[PRE_TRAINING_CHECKLIST.md](PRE_TRAINING_CHECKLIST.md)** - Verification checklist
   - Complete checklist before starting 20-epoch runs
   - Success indicators and red flags
   - **Best for: Ensuring everything is ready**

### 📋 Complete Workflows

3. **[TRAINING_WORKFLOW.md](TRAINING_WORKFLOW.md)** - Step-by-step terminal workflow
   - Complete commands for both terminals
   - Using tmux for long sessions
   - Running all three methods (RLRD/SAC/RTAC)
   - Monitoring and stopping training
   - **Best for: First-time setup and detailed workflow**

4. **[TESTING_ROBOT_SPAWN.md](TESTING_ROBOT_SPAWN.md)** - Testing and validation
   - How to test the startup script
   - Optional manual verification steps
   - Short test training (1 epoch)
   - **Best for: Debugging and testing**

### 🔧 Technical Details

5. **[GAZEBO_ENVIRONMENT_SETUP.md](GAZEBO_ENVIRONMENT_SETUP.md)** - Environment deep-dive
   - Detailed explanation of startup script
   - All verification steps explained
   - Common issues and fixes
   - Environment variables
   - **Best for: Understanding how everything works**

6. **[LIDAR_TRAINING_CHALLENGES.md](LIDAR_TRAINING_CHALLENGES.md)** - Technical issues
   - Historical issues encountered
   - ROS time synchronization
   - Gazebo crashes and auto-restart
   - **Best for: Understanding past problems and solutions**

7. **[EXPERIMENT_DIAGRAMS_ACTION_POINTS.md](EXPERIMENT_DIAGRAMS_ACTION_POINTS.md)** - Paper experiments
   - Reproducing paper experiments
   - Comparing RLRD vs SAC vs RTAC
   - Plotting results
   - **Best for: Research experiments**

---

## 🎯 Choose Your Path

### Path 1: "I just want to start training NOW"
1. Read **QUICK_REFERENCE.md**
2. Follow Terminal 1 and Terminal 2 commands
3. Done!

### Path 2: "I want to make sure everything is correct"
1. Read **PRE_TRAINING_CHECKLIST.md**
2. Complete all checkboxes
3. Read **QUICK_REFERENCE.md** for commands
4. Start training

### Path 3: "I want to understand the full workflow"
1. Read **TRAINING_WORKFLOW.md** (detailed step-by-step)
2. Optional: Read **GAZEBO_ENVIRONMENT_SETUP.md** for technical details
3. Follow the workflow
4. Refer to **QUICK_REFERENCE.md** for commands later

### Path 4: "Something is broken, I need to debug"
1. Read **TESTING_ROBOT_SPAWN.md**
2. Check **GAZEBO_ENVIRONMENT_SETUP.md** troubleshooting section
3. Check **LIDAR_TRAINING_CHALLENGES.md** for similar issues
4. Check logs in `/tmp/`

---

## 🔑 Key Concepts

### Automated Verification Script
The `scripts/start_gazebo_headless.sh` script automatically handles ALL verification:
- ✅ Robot spawning (with 3 retry attempts)
- ✅ Topic publishing checks (with timeout/retry)
- ✅ Service availability verification
- ✅ Shows actual Hz rates

**You just need to see: "✓ Gazebo is FULLY READY for training!"**

### Two-Terminal Workflow
- **Terminal 1**: Runs Gazebo (keep open during training)
- **Terminal 2**: Runs RL training agent

### Training Methods
- **RLRD (DC)**: Delay-correcting algorithm (with delay parameters)
- **SAC**: Standard Soft Actor-Critic (no delay handling)
- **RTAC**: Receding horizon Actor-Critic (with delay parameters)

### Training Scale
- **1 round** = 1000 steps ≈ 30-45 seconds
- **1 epoch** = 50 rounds ≈ 30-45 minutes
- **Full training** = 20 epochs ≈ **10-15 hours**

---

## 📊 Typical Workflow

```
1. Start Docker container
   └─> sudo docker run -it --name rlrd-gazebo --net=host ...

2. Terminal 1: Start Gazebo
   └─> bash scripts/start_gazebo_headless.sh
   └─> Wait for "✓ FULLY READY" message

3. Terminal 2: Setup and train
   └─> Attach to container
   └─> Source ROS and activate venv
   └─> Run training command (RLRD/SAC/RTAC)

4. Monitor training
   └─> tail -f checkpoints/*/train.log
   └─> Check for varying returns (not constant -50.1)

5. Training completes (~10-15 hours)
   └─> Checkpoints saved in checkpoints/
   └─> Can plot results or restart if needed
```

---

## ⚠️ Critical Success Indicators

### ✅ Environment Ready (Terminal 1)
```
✓ Gazebo is FULLY READY for training!
✓ Robot spawned successfully
✓ Odometry: /odom (publishing at 50+ Hz)
✓ LiDAR: /scan (publishing at 5+ Hz)
```

### ✅ Training Healthy (Terminal 2)
```
episode_length: varies (150-502, not always 502)
returns: varies and improves (-50 → -40 → -30)
Q-values: reasonable (-20 to -50, not >50)
td_error: small (1-3, not >10)
```

### ❌ Red Flags (STOP if you see these)
```
❌ Episode length always 502
❌ Returns constant at -50.1
❌ Q-values >50 (exploding)
❌ TD error >10 (huge)
```

---

## 🛠️ Common Commands

### Check Robot Spawned
```bash
rostopic echo /gazebo/model_states -n 1 | grep turtlebot3_burger
```

### Monitor Robot Position
```bash
rostopic echo /odom | grep -A 3 position
```

### Check Topic Rates
```bash
rostopic hz /odom  # Should be 50-100 Hz
rostopic hz /scan  # Should be 5-10 Hz
```

### Check Logs
```bash
tail -f /tmp/gzserver.log
cat /tmp/spawn_robot.log
tail -f checkpoints/turtlebot3_lidar_rlrd/train.log
```

### Stop Everything
```bash
# Stop training: Ctrl+C
# Stop Gazebo: pkill -f gzserver && pkill -f roscore
```

---

## 📁 File Structure

```
rlrd/
├── scripts/
│   └── start_gazebo_headless.sh    # Automated Gazebo startup with verification
├── rlrd/
│   ├── simulator_env.py             # ROS+Gazebo environment wrapper
│   ├── sac.py                       # SAC algorithm
│   ├── dcac.py                      # RLRD (delay-correcting) algorithm
│   └── ...
├── checkpoints/                     # Training checkpoints saved here
├── QUICK_REFERENCE.md               # 👈 START HERE
├── PRE_TRAINING_CHECKLIST.md
├── TRAINING_WORKFLOW.md
├── TESTING_ROBOT_SPAWN.md
├── GAZEBO_ENVIRONMENT_SETUP.md
└── DOCUMENTATION_INDEX.md           # 👈 YOU ARE HERE
```

---

## 🆘 Getting Help

1. **Robot not spawning?**
   - Check `/tmp/spawn_robot.log`
   - Script automatically retries 3 times
   - See GAZEBO_ENVIRONMENT_SETUP.md → "Issue 1: Robot Not Spawning"

2. **Training not learning?**
   - Check robot exists: `rostopic echo /gazebo/model_states -n 1`
   - See TRAINING_WORKFLOW.md → "Issue: Training shows no learning"

3. **Gazebo crashed?**
   - Check `/tmp/gzserver.log`
   - Training auto-restarts Gazebo (see simulator_env.py)
   - See LIDAR_TRAINING_CHALLENGES.md → "Gazebo Crashes"

4. **Topics not publishing?**
   - Script checks with retry
   - Check robot_state_publisher: `ps aux | grep robot_state_publisher`
   - See GAZEBO_ENVIRONMENT_SETUP.md → "Issue 2: Topics Not Publishing"

---

## 💡 Pro Tips

- **Use tmux/screen** for long training runs (see TRAINING_WORKFLOW.md)
- **Test with 1 epoch** before committing to 20 epochs (see TESTING_ROBOT_SPAWN.md)
- **Complete checklist** before starting (see PRE_TRAINING_CHECKLIST.md)
- **Monitor first 5 rounds** to ensure healthy training
- **Trust the script** - if it says "FULLY READY", you're good to go!

---

## 🎓 For Paper Experiments

See **EXPERIMENT_DIAGRAMS_ACTION_POINTS.md** for:
- Running all three methods (RLRD, SAC, RTAC) with identical conditions
- Fair comparison requirements
- Plotting learning curves
- Reproducing paper results

**Critical:** All methods must start from epoch 1 with robot properly spawned!

---

## 📞 Quick Links

- 🚀 **Start here:** [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
- ✅ **Before training:** [PRE_TRAINING_CHECKLIST.md](PRE_TRAINING_CHECKLIST.md)
- 📋 **Full workflow:** [TRAINING_WORKFLOW.md](TRAINING_WORKFLOW.md)
- 🔧 **Troubleshooting:** [GAZEBO_ENVIRONMENT_SETUP.md](GAZEBO_ENVIRONMENT_SETUP.md)
- 🧪 **Testing:** [TESTING_ROBOT_SPAWN.md](TESTING_ROBOT_SPAWN.md)

**The startup script does all the heavy lifting - just wait for the success message!**

# Pre-Training Verification Checklist

**Complete this checklist before starting any long training run (20 epochs).**

---

## ✅ Environment Setup

- [ ] Docker container `rlrd-gazebo` is running
- [ ] Container has `--net=host` flag (check with `docker inspect`)
- [ ] Workspace mounted: `/mnt/research/rtrd/rlrd` → `/root/ws/rtrd`
- [ ] Python venv exists: `/root/venv_rlrd/`

---

## ✅ Terminal 1: Gazebo Startup

- [ ] ROS sourced: `source /opt/ros/noetic/setup.bash`
- [ ] Ran: `bash scripts/start_gazebo_headless.sh`
- [ ] Saw message: **"✓ Gazebo is FULLY READY for training!"**
- [ ] No error messages in output
- [ ] Terminal 1 still open and running

**Required output indicators:**
```
✓ Robot spawned successfully (verified in /gazebo/model_states)
✓ Odometry: /odom (publishing at XX Hz)
✓ LiDAR: /scan (publishing at XX Hz)
✓ Commands: /cmd_vel (ready)
✓ All required services verified
```

---

## ✅ Terminal 2: Training Setup

- [ ] Attached to same container
- [ ] ROS sourced: `source /opt/ros/noetic/setup.bash`
- [ ] Venv activated: `source /root/venv_rlrd/bin/activate`
- [ ] In project directory: `cd /root/ws/rtrd`

---

## ✅ Robot Verification (Automated by Script)

The startup script automatically verifies these - just confirm you saw the success message.

Manual check only if debugging:
- [ ] Robot in Gazebo: `rostopic echo /gazebo/model_states -n 1 | grep turtlebot3_burger`
- [ ] Odometry publishing: `rostopic hz /odom` shows 50-100 Hz
- [ ] LiDAR publishing: `rostopic hz /scan` shows 5-10 Hz
- [ ] cmd_vel exists: `rostopic list | grep cmd_vel`

---

## ✅ Test Training (Optional but Recommended)

Run 1 epoch test before committing to 20 epochs:

- [ ] Ran test: `python3 -m rlrd run-fs checkpoints/spawn_test rlrd:SimTraining Env=SimEnv Env.lidar_dim=180 ... epochs=1 rounds=5 steps=100`
- [ ] Episode length varies (not constant 502)
- [ ] Returns vary (not constant -50.1)
- [ ] Q-values reasonable (~-20 to -40, not >50)
- [ ] TD error small (~1-3, not >10)
- [ ] Deleted test checkpoint: `rm -rf checkpoints/spawn_test`

---

## ✅ Before Full Training

- [ ] Deleted old invalid checkpoints (if any): `rm -rf checkpoints/turtlebot3_lidar*`
- [ ] Using tmux/screen for long session: `tmux new -s training`
- [ ] Disk space available: `df -h` shows >2 GB free
- [ ] Monitoring plan ready (know how to check logs)

---

## ✅ Training Command Ready

Choose ONE method:

### RLRD:
```bash
python3 -m rlrd run-fs checkpoints/turtlebot3_lidar_rlrd rlrd:SimTraining \
    Env=SimEnv Env.lidar_dim=180 \
    Env.min_observation_delay=0 Env.sup_observation_delay=2 \
    Env.min_action_delay=1 Env.sup_action_delay=4 \
    Agent.batchsize=128 Agent.memory_size=1000000 \
    Agent.lr=0.0003 Agent.discount=0.99 Agent.device=cpu \
    epochs=20 rounds=50 steps=1000 tag=turtlebot3_lidar_rlrd
```

### SAC:
```bash
python3 -m rlrd run-fs checkpoints/turtlebot3_lidar_sac sac:SimTraining \
    Env=SimEnv Env.lidar_dim=180 \
    Agent.batchsize=128 Agent.memory_size=1000000 \
    Agent.lr=0.0003 Agent.discount=0.99 Agent.device=cpu \
    epochs=20 rounds=50 steps=1000 tag=turtlebot3_lidar_sac
```

### RTAC:
```bash
python3 -m rlrd run-fs checkpoints/turtlebot3_lidar_rtac rtac:SimTraining \
    Env=SimEnv Env.lidar_dim=180 \
    Env.min_observation_delay=0 Env.sup_observation_delay=2 \
    Env.min_action_delay=1 Env.sup_action_delay=4 \
    Agent.batchsize=128 Agent.memory_size=1000000 \
    Agent.lr=0.0003 Agent.discount=0.99 Agent.device=cpu \
    epochs=20 rounds=50 steps=1000 tag=turtlebot3_lidar_rtac
```

---

## ✅ Monitoring During Training

- [ ] Know how to check training log: `tail -f checkpoints/*/train.log`
- [ ] Know how to detach tmux: `Ctrl+b` then `d`
- [ ] Know how to reattach: `tmux attach -t training`
- [ ] Know where logs are: `/tmp/*.log`

---

## ✅ Expected Timeline

- **1 round** = 1000 steps ≈ 30-45 seconds
- **1 epoch** = 50 rounds ≈ 30-45 minutes
- **20 epochs** = 1,000,000 steps ≈ **10-15 hours**

- [ ] Have time availability for ~15 hour run
- [ ] System will not be interrupted (power, network)

---

## ✅ Success Indicators During Training

Watch first few rounds - should see:

- [ ] Episode length varies: 150-502 (not always 502)
- [ ] Returns vary: -20 to -50 (not constant -50.1)
- [ ] Returns improve over epochs
- [ ] Q-values: -20 to -50 range (not >50)
- [ ] TD error: 1-3 range (not >10)
- [ ] Critic grad: non-zero (~0.1-1.0)
- [ ] Actor grad: non-zero (~0.1-1.0)

---

## ❌ Red Flags - STOP Training If You See:

- ❌ Episode length always 502
- ❌ Returns constant at -50.1
- ❌ Q-values exploding (>50)
- ❌ TD error huge (>10)
- ❌ All gradients zero
- ❌ Error messages about missing topics

**If red flags appear: Stop training, check Gazebo (Terminal 1), verify robot spawned!**

---

## Summary

**ALL checkboxes must be ticked before starting 20-epoch training!**

If anything fails:
1. Check Terminal 1 for Gazebo errors
2. Review logs: `/tmp/gzserver.log`, `/tmp/spawn_robot.log`
3. See **TRAINING_WORKFLOW.md** for troubleshooting
4. Test with 1 epoch before full run

**The startup script automates most verification - trust the "FULLY READY" message!**

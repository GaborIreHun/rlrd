#!/bin/bash
# Test script for maze-to-sim bridge

echo "=========================================="
echo "Maze-to-Sim Bridge Test"
echo "=========================================="
echo ""

# Check if checkpoint exists
CHECKPOINT="checkpoints/pointmaze_test/state"

if [ ! -f "$CHECKPOINT" ]; then
    echo "❌ Checkpoint not found: $CHECKPOINT"
    echo ""
    echo "Creating test checkpoint by training PointMaze for 2 epochs..."
    python3 -m rlrd run-fs checkpoints/pointmaze_test rlrd:DcacTraining \
        Env=dmcontrol-pointmaze-delay \
        Agent.device=cpu \
        Agent.batchsize=64 \
        Agent.start_training=500 \
        epochs=2 \
        rounds=3 \
        steps=500
    
    if [ $? -ne 0 ]; then
        echo "❌ Training failed"
        exit 1
    fi
fi

echo "✅ Checkpoint found: $CHECKPOINT"
echo ""

# Check ROS environment
if [ -z "$ROS_DISTRO" ]; then
    echo "⚠️  ROS not detected - are you in the Docker container?"
    echo ""
    echo "To test the bridge:"
    echo "  1. Start Docker container"
    echo "  2. Launch Gazebo: roslaunch turtlebot3_gazebo turtlebot3_empty_world.launch"
    echo "  3. Run bridge: python3 -m rlrd.maze_to_sim_bridge checkpoints/pointmaze_test/state"
    exit 0
fi

echo "✅ ROS detected: $ROS_DISTRO"
echo ""

# Check if roscore is running
if ! rostopic list > /dev/null 2>&1; then
    echo "⚠️  ROS master not running"
    echo ""
    echo "Start Gazebo first:"
    echo "  roslaunch turtlebot3_gazebo turtlebot3_empty_world.launch"
    echo ""
    echo "Then run the bridge:"
    echo "  python3 -m rlrd.maze_to_sim_bridge checkpoints/pointmaze_test/state"
    exit 0
fi

echo "✅ ROS master running"
echo ""

# Check if /odom topic exists
if ! rostopic info /odom > /dev/null 2>&1; then
    echo "⚠️  /odom topic not found - is Gazebo running?"
    echo ""
    echo "Start Gazebo:"
    echo "  roslaunch turtlebot3_gazebo turtlebot3_empty_world.launch"
    exit 0
fi

echo "✅ /odom topic found"
echo ""

echo "=========================================="
echo "Running Maze-to-Sim Bridge..."
echo "=========================================="
echo ""
python3 -m rlrd.maze_to_sim_bridge "$CHECKPOINT"

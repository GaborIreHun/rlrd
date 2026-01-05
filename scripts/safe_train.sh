#!/bin/bash
# Safe training launcher - waits for Gazebo to be ready before starting
# Usage: bash scripts/safe_train.sh <checkpoint_dir> <algorithm> [additional args]

set -e

if [ $# -lt 2 ]; then
    echo "Usage: bash scripts/safe_train.sh <checkpoint_dir> <algorithm> [additional args]"
    echo ""
    echo "Examples:"
    echo "  bash scripts/safe_train.sh checkpoints/turtlebot3_lidar_rlrd rlrd:SimTraining Env.task=TurtleBot3Lidar ..."
    echo "  bash scripts/safe_train.sh checkpoints/turtlebot3_lidar_sac sac:SimTraining Env.task=TurtleBot3Lidar ..."
    exit 1
fi

CHECKPOINT_DIR="$1"
ALGORITHM="$2"
shift 2
EXTRA_ARGS="$@"

echo "========================================="
echo "Safe Training Launcher"
echo "========================================="
echo "Checkpoint: $CHECKPOINT_DIR"
echo "Algorithm: $ALGORITHM"
echo "Extra args: $EXTRA_ARGS"
echo ""

# Check if Gazebo is ready
echo "Checking Gazebo status..."
MAX_WAIT=120  # Wait up to 2 minutes
ELAPSED=0
INTERVAL=5

while [ $ELAPSED -lt $MAX_WAIT ]; do
    if bash scripts/check_gazebo_ready.sh 2>/dev/null; then
        echo ""
        echo "✓ Gazebo verified - starting training now!"
        echo ""
        break
    fi
    
    if [ $ELAPSED -eq 0 ]; then
        echo ""
        echo "Gazebo not ready yet. Waiting..."
        echo "(Will check every ${INTERVAL}s, max ${MAX_WAIT}s)"
        echo ""
        echo "If Gazebo is not running, open another terminal and run:"
        echo "  bash scripts/start_gazebo_headless.sh"
        echo ""
    fi
    
    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))
    
    if [ $ELAPSED -lt $MAX_WAIT ]; then
        echo "  Still waiting... (${ELAPSED}s elapsed)"
    fi
done

# Final check
if ! bash scripts/check_gazebo_ready.sh 2>/dev/null; then
    echo ""
    echo "ERROR: Gazebo not ready after ${MAX_WAIT}s"
    echo ""
    echo "Please:"
    echo "  1. Open another terminal"
    echo "  2. Run: bash scripts/start_gazebo_headless.sh"
    echo "  3. Wait for 'FULLY READY' message"
    echo "  4. Run this script again"
    exit 1
fi

# Start training
echo "========================================="
echo "Starting Training"
echo "========================================="
echo ""

python3 -m rlrd run-fs "$CHECKPOINT_DIR" "$ALGORITHM" $EXTRA_ARGS

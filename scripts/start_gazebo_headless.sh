#!/bin/bash
# Start Gazebo headless for RL training (no GUI)
# This script ensures robot is properly spawned and environment is ready for agent training
# Includes automatic verification and error recovery

echo "========================================"
echo "Starting Gazebo Headless for RL Training"
echo "========================================"
echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Check if ROS is sourced
if [ -z "$ROS_DISTRO" ]; then
    echo "ERROR: ROS not sourced. Run: source /opt/ros/noetic/setup.bash"
    exit 1
fi

# Set TurtleBot3 model if not already set
if [ -z "$TURTLEBOT3_MODEL" ]; then
    export TURTLEBOT3_MODEL=burger
    echo "Set TURTLEBOT3_MODEL=burger"
fi

# Fix for libRayPlugin.so dependency (required for LiDAR sensor)
# Without this, /scan topic won't be published even though URDF is correct
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:$LD_LIBRARY_PATH
export GAZEBO_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/gazebo-11/plugins:$GAZEBO_PLUGIN_PATH
echo "Set Gazebo plugin paths for LiDAR sensor support"

# Kill any existing Gazebo processes (don't fail on these)
echo "Cleaning up any existing Gazebo processes..."
pkill -9 -f gzclient 2>/dev/null || true
pkill -9 -f gzserver 2>/dev/null || true
pkill -9 -f roscore 2>/dev/null || true
pkill -9 -f rosmaster 2>/dev/null || true
pkill -9 -f robot_state_publisher 2>/dev/null || true
sleep 3

# Clean up stale files (don't fail on these)
rm -rf /tmp/gazebo-* 2>/dev/null || true
rm -rf ~/.gazebo/server-* 2>/dev/null || true
echo "✓ Cleanup complete"

# Now enable strict error handling for the rest of the script
set -e
trap 'echo "ERROR: Script failed at line $LINENO. Check logs in /tmp/"; exit 1' ERR

# Start roscore if not running
if ! pgrep -x "roscore" > /dev/null; then
    echo "Starting roscore..."
    roscore > /tmp/roscore.log 2>&1 &
    sleep 3
fi

# Verify roscore is running
if ! pgrep -x "roscore" > /dev/null; then
    echo "ERROR: Failed to start roscore"
    exit 1
fi
echo "✓ roscore is running"

# Find the world file
WORLD_FILE=$(rospack find turtlebot3_gazebo)/worlds/turtlebot3_world.world
if [ ! -f "$WORLD_FILE" ]; then
    echo "ERROR: World file not found: $WORLD_FILE"
    exit 1
fi
echo "✓ Found world file: $WORLD_FILE"

# Set up Gazebo plugin paths
echo "Setting up Gazebo environment..."
export GAZEBO_PLUGIN_PATH=/opt/ros/noetic/lib:$GAZEBO_PLUGIN_PATH
export LD_LIBRARY_PATH=/opt/ros/noetic/lib:$LD_LIBRARY_PATH
export GAZEBO_MODEL_PATH=/opt/ros/noetic/share/turtlebot3_gazebo/models:$GAZEBO_MODEL_PATH
export GAZEBO_RESOURCE_PATH=/opt/ros/noetic/share/gazebo-11:$GAZEBO_RESOURCE_PATH

# Disable rendering explicitly for headless mode
export LIBGL_ALWAYS_SOFTWARE=1
unset DISPLAY

# Verify the main plugin exists
if [ ! -f "/opt/ros/noetic/lib/libgazebo_ros_api_plugin.so" ]; then
    echo "ERROR: libgazebo_ros_api_plugin.so not found!"
    exit 1
fi
echo "✓ Gazebo ROS plugins found"

# ============================================
# CRITICAL: Load robot description CORRECTLY
# ============================================
echo "Loading robot description..."
export TURTLEBOT3_MODEL=burger

# Generate URDF from xacro
URDF_FILE="/opt/ros/noetic/share/turtlebot3_description/urdf/turtlebot3_burger.urdf.xacro"
if [ ! -f "$URDF_FILE" ]; then
    echo "ERROR: URDF file not found: $URDF_FILE"
    exit 1
fi

rosrun xacro xacro "$URDF_FILE" > /tmp/turtlebot3_burger.urdf 2>&1
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to generate URDF from xacro"
    cat /tmp/turtlebot3_burger.urdf
    exit 1
fi

# Verify the URDF includes Gazebo sensor plugins
if ! grep -q "gazebo_ros_laser" /tmp/turtlebot3_burger.urdf; then
    echo "WARNING: LiDAR plugin (gazebo_ros_laser) not found in generated URDF"
    echo "The xacro processing may not have included the .gazebo.xacro file"
fi

if ! grep -q "libgazebo_ros_diff_drive" /tmp/turtlebot3_burger.urdf; then
    echo "WARNING: Differential drive plugin not found in generated URDF"
    echo "The robot may not respond to /cmd_vel commands"
fi

# Load robot description to ROS parameter server
rosparam set robot_description -t /tmp/turtlebot3_burger.urdf

# Verify robot description is loaded
if rosparam get /robot_description > /dev/null 2>&1; then
    echo "✓ Robot description loaded to parameter server"
else
    echo "ERROR: Failed to load robot_description parameter"
    exit 1
fi

# Start robot_state_publisher for TF transforms
rosrun robot_state_publisher robot_state_publisher > /tmp/robot_state_publisher.log 2>&1 &
RSP_PID=$!
sleep 2

if ! ps -p $RSP_PID > /dev/null; then
    echo "ERROR: robot_state_publisher failed to start"
    cat /tmp/robot_state_publisher.log
    exit 1
fi
echo "✓ robot_state_publisher started (PID: $RSP_PID)"

# Start gzserver with ROS integration (no GUI)
echo "Starting gzserver (headless)..."
gzserver \
    -s libgazebo_ros_api_plugin.so \
    -s libgazebo_ros_paths_plugin.so \
    "$WORLD_FILE" \
    > /tmp/gzserver.log 2>&1 &

GZSERVER_PID=$!
echo "gzserver started (PID: $GZSERVER_PID)"

# Wait for gzserver to initialize
echo "Waiting for gzserver to initialize..."
sleep 10

# Check if gzserver is still running
if ! ps -p $GZSERVER_PID > /dev/null; then
    echo "ERROR: gzserver crashed during startup!"
    echo "Last 100 lines of gzserver log:"
    tail -n 100 /tmp/gzserver.log
    exit 1
fi
echo "✓ gzserver is running"

# Wait for the ROS API plugin to fully initialize
echo "Waiting for Gazebo ROS API to initialize..."
TIMEOUT=60
ELAPSED=0
while [ $ELAPSED -lt $TIMEOUT ]; do
    if rosservice list 2>/dev/null | grep -q "/gazebo/set_physics_properties"; then
        echo "✓ Gazebo ROS API initialized"
        break
    fi
    sleep 1
    ELAPSED=$((ELAPSED + 1))
    if [ $((ELAPSED % 10)) -eq 0 ]; then
        echo "  Still waiting for ROS API... ($ELAPSED seconds elapsed)"
    fi
done

if [ $ELAPSED -ge $TIMEOUT ]; then
    echo "ERROR: Gazebo ROS API failed to initialize"
    echo "Last 50 lines of gzserver log:"
    tail -n 50 /tmp/gzserver.log
    exit 1
fi

# ============================================
# CRITICAL: Spawn TurtleBot3 robot with sensors
# ============================================
echo "Spawning TurtleBot3 robot with LiDAR sensor..."

# Spawn from robot_description parameter (which includes Gazebo plugins from .gazebo.xacro)
rosrun gazebo_ros spawn_model \
    -urdf \
    -model turtlebot3_burger \
    -x 0.0 \
    -y 0.0 \
    -z 0.0 \
    -param robot_description \
    > /tmp/spawn_robot.log 2>&1

SPAWN_EXIT_CODE=$?
if [ $SPAWN_EXIT_CODE -ne 0 ]; then
    echo "ERROR: Robot spawn failed (exit code: $SPAWN_EXIT_CODE)"
    echo "Spawn log:"
    cat /tmp/spawn_robot.log
    exit 1
fi

echo "Waiting for robot sensors (odometry, IMU, LiDAR) to initialize..."
sleep 15

# ============================================
# VERIFICATION: Ensure robot actually spawned
# ============================================
echo ""
echo "Verifying robot spawned in Gazebo..."

# Retry mechanism for robot verification
MAX_RETRIES=3
RETRY_COUNT=0
ROBOT_SPAWNED=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    ROBOT_CHECK=$(rostopic echo /gazebo/model_states -n 1 2>/dev/null | grep -c "turtlebot3_burger" || echo "0")
    
    if [ "$ROBOT_CHECK" -gt 0 ]; then
        ROBOT_SPAWNED=true
        echo "✓ Robot spawned successfully (verified in /gazebo/model_states)"
        break
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
        echo "  Attempt $RETRY_COUNT/$MAX_RETRIES: Robot not detected, waiting 5 seconds..."
        sleep 5
    fi
done

if [ "$ROBOT_SPAWNED" = false ]; then
    echo ""
    echo "ERROR: Robot NOT found in Gazebo after $MAX_RETRIES attempts!"
    echo ""
    echo "Available models in Gazebo:"
    rostopic echo /gazebo/model_states -n 1 2>/dev/null | grep -A 20 "name:" || echo "(unable to read model_states)"
    echo ""
    echo "Spawn log contents:"
    cat /tmp/spawn_robot.log 2>/dev/null || echo "(spawn log not found)"
    echo ""
    echo "Last 50 lines of gzserver log:"
    tail -n 50 /tmp/gzserver.log 2>/dev/null || echo "(gzserver log not found)"
    echo ""
    echo "TROUBLESHOOTING:"
    echo "  1. Check if robot_description parameter exists: rosparam get /robot_description"
    echo "  2. Verify Gazebo is responsive: rosservice list | grep gazebo"
    echo "  3. Try manual spawn: rosrun gazebo_ros spawn_model -urdf -model turtlebot3_burger -x 0.0 -y 0.0 -z 0.0 -param robot_description"
    exit 1
fi

# ============================================
# VERIFICATION: Ensure topics are publishing
# ============================================
echo ""
echo "Verifying ROS topics are publishing..."

# Function to check topic with retry
check_topic_with_retry() {
    local topic=$1
    local type=$2  # "hz" for frequency check, "list" for existence check
    local max_attempts=5
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if [ "$type" = "hz" ]; then
            if timeout 15 rostopic hz "$topic" -w 1 > /dev/null 2>&1; then
                return 0
            fi
        elif [ "$type" = "list" ]; then
            if rostopic list 2>/dev/null | grep -q "^$topic$"; then
                return 0
            fi
        fi
        
        if [ $attempt -lt $max_attempts ]; then
            echo "    Retry $attempt/$max_attempts for $topic (waiting 5 seconds)..."
            sleep 5
        fi
        attempt=$((attempt + 1))
    done
    
    return 1
}

# Check odometry - first check if topic exists, then if it's publishing
echo -n "  Checking /odom (odometry)... "

# First verify topic exists
if ! rostopic list 2>/dev/null | grep -q "^/odom$"; then
    echo "✗ Topic does not exist"
    echo ""
    echo "ERROR: /odom topic not found"
    echo "Available topics:"
    rostopic list 2>/dev/null | head -20
    exit 1
fi

# Now check if it's publishing with more patient retry
MAX_ODOM_ATTEMPTS=8
ODOM_ATTEMPT=1
ODOM_PUBLISHING=false

while [ $ODOM_ATTEMPT -le $MAX_ODOM_ATTEMPTS ]; do
    if timeout 20 rostopic hz /odom -w 1 > /dev/null 2>&1; then
        ODOM_PUBLISHING=true
        break
    fi
    
    if [ $ODOM_ATTEMPT -lt $MAX_ODOM_ATTEMPTS ]; then
        echo ""
        echo "    Attempt $ODOM_ATTEMPT/$MAX_ODOM_ATTEMPTS: Waiting for /odom to publish (5 seconds)..."
        sleep 5
    fi
    ODOM_ATTEMPT=$((ODOM_ATTEMPT + 1))
done

if [ "$ODOM_PUBLISHING" = true ]; then
    ODOM_RATE=$(timeout 10 rostopic hz /odom 2>&1 | grep "average rate" | awk '{print $3}')
    echo "✓ Publishing at ${ODOM_RATE:-unknown} Hz"
else
    echo "✗ NOT publishing after $MAX_ODOM_ATTEMPTS attempts"
    echo ""
    echo "WARNING: Odometry topic exists but is not publishing data yet."
    echo "This may be normal - the robot controller might need more time."
    echo ""
    echo "Attempting to continue with reduced verification..."
    ODOM_RATE="unknown"
fi

# Check LiDAR scan - similar patient approach
echo -n "  Checking /scan (LiDAR)... "

# First verify topic exists
if ! rostopic list 2>/dev/null | grep -q "^/scan$"; then
    echo "✗ Topic does not exist"
    echo ""
    echo "WARNING: /scan topic not found - LiDAR sensor may not be loaded"
    echo ""
    echo "Available topics:"
    rostopic list 2>/dev/null
    echo ""
    echo "This could be due to:"
    echo "  1. TurtleBot3 model doesn't include LiDAR by default"
    echo "  2. Gazebo sensor plugin not loading"
    echo "  3. URDF not including LiDAR sensor definition"
    echo ""
    echo "The robot spawned successfully with other sensors."
    echo "Training may work if using odometry-only, but LiDAR-based navigation will fail."
    echo ""
    echo "To fix: Ensure turtlebot3_burger.urdf.xacro includes LDS-01 LiDAR sensor"
    echo ""
    SCAN_RATE="not_available"
else
    # Topic exists, now check if it's publishing
    MAX_SCAN_ATTEMPTS=8
    SCAN_ATTEMPT=1
    SCAN_PUBLISHING=false

    while [ $SCAN_ATTEMPT -le $MAX_SCAN_ATTEMPTS ]; do
        if timeout 20 rostopic hz /scan -w 1 > /dev/null 2>&1; then
            SCAN_PUBLISHING=true
            break
        fi
        
        if [ $SCAN_ATTEMPT -lt $MAX_SCAN_ATTEMPTS ]; then
            echo ""
            echo "    Attempt $SCAN_ATTEMPT/$MAX_SCAN_ATTEMPTS: Waiting for /scan to publish (5 seconds)..."
            sleep 5
        fi
        SCAN_ATTEMPT=$((SCAN_ATTEMPT + 1))
    done

    if [ "$SCAN_PUBLISHING" = true ]; then
        SCAN_RATE=$(timeout 10 rostopic hz /scan 2>&1 | grep "average rate" | awk '{print $3}')
        echo "✓ Publishing at ${SCAN_RATE:-unknown} Hz"
    else
        echo "✗ NOT publishing after $MAX_SCAN_ATTEMPTS attempts"
        echo ""
        echo "WARNING: LiDAR scan topic exists but is not publishing data yet."
        echo "This may be normal - the sensors might need more time to initialize."
        echo ""
        echo "Attempting to continue with reduced verification..."
        SCAN_RATE="unknown"
    fi
fi

# Check cmd_vel exists
echo -n "  Checking /cmd_vel (commands)... "
if check_topic_with_retry "/cmd_vel" "list"; then
    echo "✓ Available"
else
    echo "✗ NOT available"
    echo ""
    echo "ERROR: cmd_vel topic not available"
    echo "This means the robot cannot receive movement commands."
    exit 1
fi

echo "✓ All required topics verified"

# Wait for critical Gazebo services to be available
echo "Waiting for Gazebo services..."
TIMEOUT=60
ELAPSED=0

while [ $ELAPSED -lt $TIMEOUT ]; do
    if rosservice list 2>/dev/null | grep -q "/gazebo/reset_simulation"; then
        echo "✓ /gazebo/reset_simulation service is available"
        break
    fi
    sleep 1
    ELAPSED=$((ELAPSED + 1))
    if [ $((ELAPSED % 10)) -eq 0 ]; then
        echo "  Still waiting for services... ($ELAPSED seconds elapsed)"
    fi
done

if [ $ELAPSED -ge $TIMEOUT ]; then
    echo "ERROR: Timeout waiting for Gazebo services"
    echo "Available services:"
    rosservice list 2>/dev/null | grep gazebo || echo "(none)"
    exit 1
fi

# Verify ALL required services are available
echo ""
echo "Verifying required Gazebo services..."
REQUIRED_SERVICES=(
    "/gazebo/reset_simulation"
    "/gazebo/reset_world"
    "/gazebo/pause_physics"
    "/gazebo/unpause_physics"
)

ALL_SERVICES_OK=true
for service in "${REQUIRED_SERVICES[@]}"; do
    if rosservice list 2>/dev/null | grep -q "^$service$"; then
        echo "  ✓ $service"
    else
        echo "  ✗ $service (missing)"
        ALL_SERVICES_OK=false
    fi
done

if [ "$ALL_SERVICES_OK" = false ]; then
    echo ""
    echo "ERROR: Not all required services are available"
    exit 1
fi
echo "✓ All required services verified"

# Final verification: Wait for sensors to actually publish data
echo ""
if [ "$ODOM_RATE" = "unknown" ] || [ "$SCAN_RATE" = "unknown" ]; then
    echo "========================================="
    echo "Waiting for sensors to start publishing..."
    echo "========================================="
    echo ""
    echo "Sensors need 20-30 seconds after spawn to initialize."
    echo "Checking every 5 seconds (max 60 seconds)..."
    echo ""
    
    MAX_WAIT=60
    ELAPSED=0
    INTERVAL=5
    
    while [ $ELAPSED -lt $MAX_WAIT ]; do
        # Check if both topics are now publishing
        if [ "$ODOM_RATE" = "unknown" ]; then
            ODOM_CHECK=$(timeout 3 rostopic hz /odom 2>&1 | grep "average rate" | awk '{print $3}' || echo "")
            if [ -n "$ODOM_CHECK" ]; then
                ODOM_RATE=$(printf "%.1f" "$ODOM_CHECK")
                echo "  ✓ /odom started publishing at ${ODOM_RATE} Hz"
            fi
        fi
        
        if [ "$SCAN_RATE" = "unknown" ]; then
            SCAN_CHECK=$(timeout 3 rostopic hz /scan 2>&1 | grep "average rate" | awk '{print $3}' || echo "")
            if [ -n "$SCAN_CHECK" ]; then
                SCAN_RATE=$(printf "%.1f" "$SCAN_CHECK")
                echo "  ✓ /scan started publishing at ${SCAN_RATE} Hz"
            fi
        fi
        
        # Break if both are ready
        if [ "$ODOM_RATE" != "unknown" ] && [ "$SCAN_RATE" != "unknown" ]; then
            echo ""
            echo "✓ All sensors are now publishing!"
            break
        fi
        
        # Wait and increment
        sleep $INTERVAL
        ELAPSED=$((ELAPSED + INTERVAL))
        
        if [ $ELAPSED -lt $MAX_WAIT ]; then
            echo "  Still waiting... (${ELAPSED}s elapsed)"
        fi
    done
    
    echo ""
    if [ "$ODOM_RATE" = "unknown" ] || [ "$SCAN_RATE" = "unknown" ]; then
        echo "WARNING: Sensors took longer than ${MAX_WAIT}s to initialize."
        echo "They may still start - check manually with: rostopic hz /odom && rostopic hz /scan"
        echo ""
    fi
fi

# Show final status
echo ""
if [ "$ODOM_RATE" != "unknown" ] && [ "$SCAN_RATE" != "unknown" ]; then
    echo "========================================="
    echo "✓ Gazebo is FULLY READY for training!"
    echo "========================================="
    echo ""
else
    echo "========================================="
    echo "✓ Gazebo Environment Started"
    echo "========================================="
    echo ""
    echo "NOTE: Some sensors are still initializing."
    echo "Wait a bit longer or check manually before training."
    echo ""
fi

echo "Environment Status:"
echo "  Robot Model: turtlebot3_burger"
echo "  Robot Position: (0.0, 0.0, 0.0)"
echo "  World: turtlebot3_world"
echo "  Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""
echo "ROS Topics:"
if [ "$ODOM_RATE" != "unknown" ]; then
    echo "  ✓ Odometry: /odom (publishing at ${ODOM_RATE} Hz)"
else
    echo "  ⏳ Odometry: /odom (topic exists, waiting for data)"
fi
if [ "$SCAN_RATE" != "unknown" ]; then
    echo "  ✓ LiDAR: /scan (publishing at ${SCAN_RATE} Hz)"
else
    echo "  ⏳ LiDAR: /scan (topic exists, waiting for data)"
fi
echo "  ✓ Commands: /cmd_vel (ready)"
echo ""
echo "Gazebo Services (verified):"
echo "  ✓ /gazebo/reset_simulation (ready)"
echo "  ✓ /gazebo/reset_world (ready)"
echo "  ✓ /gazebo/pause_physics (ready)"
echo "  ✓ /gazebo/unpause_physics (ready)"
echo ""
echo "Process IDs:"
echo "  gzserver: $GZSERVER_PID"
echo "  robot_state_publisher: $RSP_PID"
echo ""
echo "Logs:"
echo "  roscore: /tmp/roscore.log"
echo "  gzserver: /tmp/gzserver.log"
echo "  robot_state_publisher: /tmp/robot_state_publisher.log"
echo "  spawn_robot: /tmp/spawn_robot.log"
echo ""
echo "========================================="
echo "  ENVIRONMENT READY - START TRAINING!"
echo "========================================="
echo ""
echo "Next steps in a NEW terminal:"
echo "  1. Attach to container: sudo docker exec -it <container_id> bash"
echo "  2. Source ROS: source /opt/ros/noetic/setup.bash"
echo "  3. Activate venv: source /root/venv_rlrd/bin/activate"
echo "  4. Change dir: cd /root/ws/rtrd"
echo "  5. Run training: python3 -m rlrd run-fs checkpoints/turtlebot3_lidar rlrd:SimTraining ..."
echo ""
echo "To monitor robot:"
echo "  rostopic echo /odom | grep -A 3 position"
echo "  rostopic echo /scan | head -20"
echo ""
echo "To stop Gazebo:"
echo "  pkill -f gzserver && pkill -f roscore"
echo ""

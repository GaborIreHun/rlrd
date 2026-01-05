#!/bin/bash
# Check if Gazebo environment is fully ready for training
# Exit 0 if ready, exit 1 if not ready

# Check if ready signal file exists
if [ ! -f /tmp/gazebo_ready ]; then
    echo "❌ Gazebo not ready: /tmp/gazebo_ready file missing"
    echo ""
    echo "Start Gazebo first with:"
    echo "  bash scripts/start_gazebo_headless.sh"
    exit 1
fi

# Check if roscore is running
if ! pgrep -x "roscore" > /dev/null && ! pgrep -x "rosmaster" > /dev/null; then
    echo "❌ Gazebo not ready: roscore not running"
    rm -f /tmp/gazebo_ready
    exit 1
fi

# Check if gzserver is running
if ! pgrep -f "gzserver" > /dev/null; then
    echo "❌ Gazebo not ready: gzserver not running"
    rm -f /tmp/gazebo_ready
    exit 1
fi

# Check if topics exist
if ! rostopic list 2>/dev/null | grep -q "/odom"; then
    echo "❌ Gazebo not ready: /odom topic missing"
    rm -f /tmp/gazebo_ready
    exit 1
fi

if ! rostopic list 2>/dev/null | grep -q "/scan"; then
    echo "❌ Gazebo not ready: /scan topic missing"
    rm -f /tmp/gazebo_ready
    exit 1
fi

# Check if topics are publishing (quick 2-second check)
ODOM_PUBLISHING=$(timeout 2 rostopic hz /odom 2>&1 | grep -c "average rate" || echo "0")
SCAN_PUBLISHING=$(timeout 2 rostopic hz /scan 2>&1 | grep -c "average rate" || echo "0")

if [ "$ODOM_PUBLISHING" = "0" ]; then
    echo "⚠️  Gazebo environment exists but /odom not publishing yet"
    echo "    Wait a few more seconds and try again"
    exit 1
fi

if [ "$SCAN_PUBLISHING" = "0" ]; then
    echo "⚠️  Gazebo environment exists but /scan not publishing yet"
    echo "    Wait a few more seconds and try again"
    exit 1
fi

# All checks passed
READY_TIME=$(cat /tmp/gazebo_ready)
echo "✅ Gazebo is FULLY READY for training!"
echo "   Ready since: $READY_TIME"
echo "   /odom: Publishing ✓"
echo "   /scan: Publishing ✓"
exit 0

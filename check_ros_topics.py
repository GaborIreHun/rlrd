#!/usr/bin/env python3
"""
Diagnostic script to check ROS topics and communication.
Run this if the robot is not moving or behaving unexpectedly.
"""

import rospy
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist
import sys

def check_odom():
    """Check if /odom topic is publishing"""
    print("=" * 60)
    print("Checking /odom topic...")
    print("=" * 60)
    
    try:
        msg = rospy.wait_for_message('/odom', Odometry, timeout=5.0)
        print("✓ /odom is publishing!")
        print(f"  Position: ({msg.pose.pose.position.x:.3f}, "
              f"{msg.pose.pose.position.y:.3f}, "
              f"{msg.pose.pose.position.z:.3f})")
        print(f"  Linear velocity: ({msg.twist.twist.linear.x:.3f}, "
              f"{msg.twist.twist.linear.y:.3f}, "
              f"{msg.twist.twist.linear.z:.3f})")
        print(f"  Angular velocity: ({msg.twist.twist.angular.x:.3f}, "
              f"{msg.twist.twist.angular.y:.3f}, "
              f"{msg.twist.twist.angular.z:.3f})")
        return True
    except rospy.ROSException as e:
        print(f"✗ /odom is NOT publishing or timeout!")
        print(f"  Error: {e}")
        return False

def check_cmd_vel():
    """Check if /cmd_vel topic exists"""
    print("\n" + "=" * 60)
    print("Checking /cmd_vel topic...")
    print("=" * 60)
    
    topics = rospy.get_published_topics()
    cmd_vel_exists = any('/cmd_vel' in topic[0] for topic in topics)
    
    if cmd_vel_exists:
        print("✓ /cmd_vel topic exists")
        
        # Try to listen for a message
        print("  Listening for /cmd_vel messages (5 second timeout)...")
        try:
            msg = rospy.wait_for_message('/cmd_vel', Twist, timeout=5.0)
            print(f"  ✓ Received command: linear={msg.linear.x:.3f}, angular={msg.angular.z:.3f}")
        except rospy.ROSException:
            print("  ⚠ No /cmd_vel messages received (this is normal if controller not running)")
    else:
        print("✗ /cmd_vel topic does NOT exist")
    
    return cmd_vel_exists

def list_all_topics():
    """List all available topics"""
    print("\n" + "=" * 60)
    print("All available topics:")
    print("=" * 60)
    
    topics = rospy.get_published_topics()
    for topic, msg_type in sorted(topics):
        print(f"  {topic:40s} [{msg_type}]")

def check_nodes():
    """Check running ROS nodes"""
    print("\n" + "=" * 60)
    print("Running ROS nodes:")
    print("=" * 60)
    
    try:
        nodes = rospy.get_node_names()
        for node in sorted(nodes):
            print(f"  {node}")
        
        # Check for gazebo
        gazebo_running = any('gazebo' in node for node in nodes)
        if gazebo_running:
            print("\n✓ Gazebo is running")
        else:
            print("\n✗ Gazebo is NOT running")
            
        return gazebo_running
    except Exception as e:
        print(f"✗ Could not get node list: {e}")
        return False

def test_publishing():
    """Test publishing a command to /cmd_vel"""
    print("\n" + "=" * 60)
    print("Testing command publishing...")
    print("=" * 60)
    
    try:
        pub = rospy.Publisher('/cmd_vel', Twist, queue_size=1)
        rospy.sleep(1.0)  # Wait for connection
        
        cmd = Twist()
        cmd.linear.x = 0.1
        cmd.angular.z = 0.2
        
        print(f"Publishing test command: linear={cmd.linear.x}, angular={cmd.angular.z}")
        pub.publish(cmd)
        
        print("✓ Command published successfully")
        print("  Check Gazebo - robot should move slightly!")
        
        rospy.sleep(2.0)
        
        # Stop robot
        cmd.linear.x = 0.0
        cmd.angular.z = 0.0
        pub.publish(cmd)
        print("  Sent stop command")
        
        return True
    except Exception as e:
        print(f"✗ Failed to publish: {e}")
        return False

def main():
    """Run all diagnostic checks"""
    print("\n" + "=" * 60)
    print("ROS DIAGNOSTICS")
    print("=" * 60)
    
    try:
        rospy.init_node('ros_diagnostics', anonymous=True)
    except rospy.exceptions.ROSException as e:
        print(f"✗ Failed to initialize ROS node: {e}")
        print("\nIs ROS master running? Try:")
        print("  roscore")
        print("Or:")
        print("  roslaunch turtlebot3_gazebo turtlebot3_world.launch")
        sys.exit(1)
    
    # Run checks
    odom_ok = check_odom()
    cmd_vel_ok = check_cmd_vel()
    gazebo_ok = check_nodes()
    list_all_topics()
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    all_ok = odom_ok and cmd_vel_ok and gazebo_ok
    
    if all_ok:
        print("✓ All checks passed!")
        print("\nYou can now run the controller:")
        print("  python3 run_sim_controller.py")
        
        # Offer to test
        response = input("\nDo you want to test robot motion? (y/n): ")
        if response.lower() == 'y':
            test_publishing()
    else:
        print("✗ Some checks failed!")
        print("\nTroubleshooting:")
        
        if not gazebo_ok:
            print("  1. Start Gazebo simulation:")
            print("     roslaunch turtlebot3_gazebo turtlebot3_world.launch")
        
        if not odom_ok:
            print("  2. Odometry not available - check Gazebo robot model")
            print("     Make sure TURTLEBOT3_MODEL is set:")
            print("     export TURTLEBOT3_MODEL=burger")
        
        if not cmd_vel_ok:
            print("  3. cmd_vel topic missing - unusual, may need to respawn robot")

if __name__ == '__main__':
    main()

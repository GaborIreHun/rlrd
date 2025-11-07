#!/usr/bin/env python3
"""
Direct test script to verify TurtleBot3 can receive and execute motion commands.
This bypasses the agent and directly publishes to /cmd_vel.
"""

import rospy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import sys

class RobotMotionTester:
    def __init__(self):
        rospy.init_node('robot_motion_tester', anonymous=True)
        self.cmd_pub = rospy.Publisher('/cmd_vel', Twist, queue_size=10)
        self.odom_sub = rospy.Subscriber('/odom', Odometry, self.odom_callback)
        
        self.current_pose = None
        self.current_twist = None
        self.rate = rospy.Rate(10)  # 10 Hz
        
        rospy.sleep(1.0)  # Wait for connections
        
    def odom_callback(self, msg):
        """Store current odometry"""
        self.current_pose = msg.pose.pose
        self.current_twist = msg.twist.twist
    
    def send_command(self, linear, angular, duration=2.0):
        """Send velocity command for specified duration"""
        cmd = Twist()
        cmd.linear.x = linear
        cmd.angular.z = angular
        
        print(f"Sending command: linear={linear:.2f}, angular={angular:.2f}")
        print(f"Duration: {duration:.1f}s")
        
        start_time = rospy.Time.now()
        while (rospy.Time.now() - start_time).to_sec() < duration:
            self.cmd_pub.publish(cmd)
            self.rate.sleep()
        
        print("  Command complete")
    
    def stop(self):
        """Send stop command"""
        cmd = Twist()
        cmd.linear.x = 0.0
        cmd.angular.z = 0.0
        self.cmd_pub.publish(cmd)
        print("  Sent STOP command")
    
    def print_status(self):
        """Print current robot status"""
        if self.current_pose:
            print(f"  Position: x={self.current_pose.position.x:.3f}, "
                  f"y={self.current_pose.position.y:.3f}")
            if self.current_twist:
                print(f"  Velocity: linear={self.current_twist.linear.x:.3f}, "
                      f"angular={self.current_twist.angular.z:.3f}")
        else:
            print("  No odometry data yet")
    
    def run_tests(self):
        """Run a series of motion tests"""
        print("\n" + "=" * 60)
        print("ROBOT MOTION TEST")
        print("=" * 60)
        
        print("\nWaiting for odometry data...")
        timeout = rospy.Time.now() + rospy.Duration(5.0)
        while self.current_pose is None and rospy.Time.now() < timeout:
            self.rate.sleep()
        
        if self.current_pose is None:
            print("✗ No odometry received! Check if simulation is running.")
            return
        
        print("✓ Odometry received")
        self.print_status()
        
        # Test 1: Forward motion
        print("\n" + "-" * 60)
        print("Test 1: Move forward")
        print("-" * 60)
        self.send_command(linear=0.2, angular=0.0, duration=2.0)
        self.stop()
        rospy.sleep(1.0)
        self.print_status()
        
        # Test 2: Rotate
        print("\n" + "-" * 60)
        print("Test 2: Rotate")
        print("-" * 60)
        self.send_command(linear=0.0, angular=0.5, duration=2.0)
        self.stop()
        rospy.sleep(1.0)
        self.print_status()
        
        # Test 3: Combined motion
        print("\n" + "-" * 60)
        print("Test 3: Forward + Rotation")
        print("-" * 60)
        self.send_command(linear=0.15, angular=0.3, duration=2.0)
        self.stop()
        rospy.sleep(1.0)
        self.print_status()
        
        # Test 4: Small motions (like agent outputs)
        print("\n" + "-" * 60)
        print("Test 4: Small motions (agent-like)")
        print("-" * 60)
        self.send_command(linear=0.023, angular=0.289, duration=3.0)
        self.stop()
        rospy.sleep(1.0)
        self.print_status()
        
        print("\n" + "=" * 60)
        print("TESTS COMPLETE")
        print("=" * 60)
        print("\nIf robot didn't move:")
        print("  1. Check Gazebo GUI - is robot model loaded?")
        print("  2. Try manual control: roslaunch turtlebot3_teleop turtlebot3_teleop_key.launch")
        print("  3. Check physics: rostopic hz /clock (should be ~1000)")
        print("  4. Verify TURTLEBOT3_MODEL=burger is set")

def main():
    try:
        tester = RobotMotionTester()
        tester.run_tests()
    except rospy.ROSInterruptException:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nMake sure:")
        print("  1. ROS is sourced: source /opt/ros/noetic/setup.bash")
        print("  2. Gazebo is running: roslaunch turtlebot3_gazebo turtlebot3_world.launch")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()

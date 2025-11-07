#!/usr/bin/env python3
"""
Legacy ROS Bridge for old .pt checkpoint files.

This script is for running old model checkpoints (sac_model_epoch_*.pt) 
that were trained with an older version of the codebase.

For new models trained with SimTraining, use ros_bridge.py instead.

Usage:
    python3 -m rlrd.ros_bridge_legacy checkpoints/sac_model_epoch_10.pt
"""
import rospy
from geometry_msgs.msg import Twist
from sensor_msgs.msg import JointState
import torch
import numpy as np
import sys

class LegacyRLBridge:
    def __init__(self, checkpoint_path):
        rospy.init_node("legacy_rl_bridge", anonymous=True)
        self.cmd_pub = rospy.Publisher("/cmd_vel", Twist, queue_size=1)
        self.joint_sub = rospy.Subscriber("/joint_states", JointState, self.joint_state_callback)
        self.rate = rospy.Rate(10)  # 10 Hz
        
        # Load the state dict
        rospy.loginfo(f"Loading legacy checkpoint from {checkpoint_path}")
        self.model_state = torch.load(checkpoint_path, map_location=torch.device('cpu'))
        rospy.loginfo(f"Loaded {len(self.model_state)} parameters")
        
        # Build a simple network that matches the old structure
        # Old models: 6D input (joint states) -> 256 hidden -> 1D output (linear velocity only)
        from torch import nn
        
        class LegacyActor(nn.Module):
            def __init__(self):
                super().__init__()
                # Match the old structure: Sequential with 'lin' submodules
                self.fc1 = nn.Linear(6, 256)
                self.fc2 = nn.Linear(256, 256)
                self.mean_layer = nn.Linear(256, 1)
                
            def forward(self, x):
                x = torch.relu(self.fc1(x))
                x = torch.relu(self.fc2(x))
                return torch.tanh(self.mean_layer(x))
        
        self.actor = LegacyActor()
        
        # Load weights - checkpoint has mixed structure:
        # actor.0.lin.weight/bias (layer 0 with .lin)
        # actor.2.weight/bias (layer 2 without .lin)
        # actor.4.lin_mean.weight/bias (output layer)
        try:
            # Direct assignment from checkpoint keys
            self.actor.fc1.weight.data = self.model_state['actor.0.lin.weight']
            self.actor.fc1.bias.data = self.model_state['actor.0.lin.bias']
            self.actor.fc2.weight.data = self.model_state['actor.2.weight']
            self.actor.fc2.bias.data = self.model_state['actor.2.bias']
            self.actor.mean_layer.weight.data = self.model_state['actor.4.lin_mean.weight']
            self.actor.mean_layer.bias.data = self.model_state['actor.4.lin_mean.bias']
            
            rospy.loginfo("Successfully loaded legacy model weights")
        except KeyError as e:
            rospy.logerr(f"Failed to load weights: {e}")
            raise
        
        self.actor.eval()
        self.state = None
    
    def joint_state_callback(self, msg):
        """Extract observation from joint states.
        TurtleBot3 only has 2 wheel joints, but old model expects 6D.
        Pad with zeros to match expected dimension.
        """
        if len(msg.position) >= 2:
            # Get 2 wheel positions and pad to 6D
            wheel_positions = list(msg.position[:2])
            self.state = wheel_positions + [0.0, 0.0, 0.0, 0.0]  # Pad to 6D
            
            if not hasattr(self, '_logged_first_obs'):
                rospy.loginfo(f"Received first observation: wheel_left={wheel_positions[0]:.3f}, wheel_right={wheel_positions[1]:.3f}")
                rospy.loginfo(f"Padded to 6D: {self.state}")
                self._logged_first_obs = True
    
    def run(self):
        rospy.loginfo("Legacy RL bridge started (6D joint states -> 1D linear velocity)")
        rospy.loginfo("Waiting for observations from /joint_states...")
        
        loop_count = 0
        action_samples = []
        while not rospy.is_shutdown():
            if self.state is None:
                loop_count += 1
                if loop_count % 50 == 0:  # Log every 5 seconds
                    rospy.logwarn("Still waiting for joint state observations...")
                self.rate.sleep()
                continue
            
            # Get action
            with torch.no_grad():
                obs = torch.tensor(self.state, dtype=torch.float32).unsqueeze(0)
                action = self.actor(obs)
            
            # Publish (only linear velocity, no rotation)
            cmd = Twist()
            cmd.linear.x = float(action[0, 0])
            cmd.angular.z = 0.0
            self.cmd_pub.publish(cmd)
            
            # Log periodic statistics
            action_samples.append(cmd.linear.x)
            if len(action_samples) >= 100:
                avg_action = sum(action_samples) / len(action_samples)
                rospy.loginfo(f"Average action over 100 steps: {avg_action:.4f} m/s (range: {min(action_samples):.4f} to {max(action_samples):.4f})")
                action_samples = []
            
            if not hasattr(self, '_logged_first_action'):
                rospy.loginfo(f"Publishing first action: linear.x={cmd.linear.x:.3f}")
                rospy.logwarn("NOTE: Old model was trained on different observations. It may not control TurtleBot3 well.")
                rospy.logwarn("For better performance, use: python3 -m rlrd.ros_bridge checkpoints/simtraining_checkpoint/state")
                self._logged_first_action = True
            
            self.rate.sleep()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 -m rlrd.ros_bridge_legacy <checkpoint.pt>")
        sys.exit(1)
    
    checkpoint_path = sys.argv[1]
    rospy.loginfo("="*60)
    rospy.loginfo("Legacy ROS Bridge for old .pt checkpoints")
    rospy.loginfo(f"Checkpoint: {checkpoint_path}")
    rospy.loginfo("Observation: 6D joint states")
    rospy.loginfo("Action: 1D linear velocity only")
    rospy.loginfo("="*60)
    
    bridge = LegacyRLBridge(checkpoint_path)
    bridge.run()

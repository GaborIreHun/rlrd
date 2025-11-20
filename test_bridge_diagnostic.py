#!/usr/bin/env python3
"""
Diagnostic script to test the maze_to_sim_bridge without ROS
"""

from rlrd.maze_to_sim_bridge import MazeToSimBridge
import numpy as np

def test_bridge(checkpoint_path):
    print(f"Testing bridge with checkpoint: {checkpoint_path}\n")
    
    # Load bridge without ROS
    bridge = MazeToSimBridge(checkpoint_path, use_ros=False)
    
    print(f"\nEnvironment detected: {bridge.env_name}")
    print(f"Expects PointMaze obs: {bridge.expects_pointmaze_obs}")
    print(f"Uses delays: {bridge.uses_delays}")
    
    # Test with sample observations
    print("\n" + "="*60)
    print("Testing with sample TurtleBot3 observation")
    print("="*60)
    
    # TurtleBot3 observation: [x, y, theta, velocity]
    turtlebot_obs = np.array([-2.0, -0.5, 0.0, 0.0], dtype=np.float32)
    print(f"TurtleBot obs: {turtlebot_obs}")
    
    # Get action
    action = bridge.get_action(turtlebot_obs)
    print(f"Action output: {action}")
    print(f"Action shape: {action.shape}")
    print(f"Action values: linear={action[0]:.4f}, angular={action[1]:.4f}")
    
    # Test a few more steps
    print("\n" + "="*60)
    print("Testing 5 steps with varying positions")
    print("="*60)
    
    test_obs = [
        [-2.0, -0.5, 0.0, 0.0],
        [-1.5, -0.3, 0.5, 0.1],
        [-1.0, 0.0, 1.0, 0.15],
        [-0.5, 0.3, 1.5, 0.1],
        [0.0, 0.5, 2.0, 0.05],
    ]
    
    for i, obs in enumerate(test_obs):
        obs_array = np.array(obs, dtype=np.float32)
        action = bridge.get_action(obs_array)
        print(f"Step {i}: pos=({obs[0]:.1f}, {obs[1]:.1f}), theta={obs[2]:.1f}, vel={obs[3]:.2f} "
              f"→ action=({action[0]:.4f}, {action[1]:.4f})")
    
    print("\n" + "="*60)
    print("Bridge test completed successfully!")
    print("="*60)

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        checkpoint = sys.argv[1]
    else:
        checkpoint = 'checkpoints/pointmaze_1/state'
        print(f"No checkpoint specified, using: {checkpoint}\n")
    
    test_bridge(checkpoint)

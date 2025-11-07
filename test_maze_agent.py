#!/usr/bin/env python3
"""
Test script to demonstrate loading and using a trained maze agent.
"""

import numpy as np
from rlrd.maze_to_sim_bridge import MazeToSimBridge

def main():
    # Load the trained agent
    checkpoint_path = 'checkpoints/maze_model_1/state'
    print("Loading agent...")
    bridge = MazeToSimBridge(checkpoint_path, use_ros=False)
    
    print("\n" + "=" * 60)
    print("SIMULATING EPISODE")
    print("=" * 60)
    
    # Simulate an episode
    # PointMaze observation: [x, y, velocity_x, velocity_y]
    observation = np.array([0.0, 0.0, 0.0, 0.0], dtype=np.float32)
    
    for step in range(10):
        # Get action from agent
        action = bridge.get_action(observation)
        
        # Simulate environment dynamics (simple integration)
        # action is [force_x, force_y]
        dt = 0.01
        observation[2:4] += action * dt  # Update velocities
        observation[0:2] += observation[2:4] * dt  # Update positions
        
        # Add some damping
        observation[2:4] *= 0.95
        
        print(f"\nStep {step}:")
        print(f"  Position: ({observation[0]:.4f}, {observation[1]:.4f})")
        print(f"  Velocity: ({observation[2]:.4f}, {observation[3]:.4f})")
        print(f"  Action:   ({action[0]:.4f}, {action[1]:.4f})")
    
    print("\n" + "=" * 60)
    print("EPISODE COMPLETE")
    print("=" * 60)
    
    # Reset agent state for new episode
    bridge.reset_agent_state()
    print("\nAgent state reset. Ready for new episode.")


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Test different action scaling factors for PointMaze to TurtleBot3 transfer.

This helps identify the optimal scaling to translate PointMaze forces into
TurtleBot3 velocities.

Usage:
    python3 test_action_scaling.py checkpoints/pointmaze_1/state
"""

import sys
import numpy as np
from rlrd.util import load

def test_scaling_factors(checkpoint_path):
    """Test various scaling factors with sample observations"""
    
    print("=" * 70)
    print("Action Scaling Test for PointMaze → TurtleBot3 Transfer")
    print("=" * 70)
    print(f"\nLoading checkpoint: {checkpoint_path}")
    
    # Load agent
    training = load(checkpoint_path)
    agent = training.agent
    
    print("✓ Agent loaded successfully")
    print(f"  Agent type: {type(agent).__name__}")
    
    # Test observations (representing different robot states)
    test_cases = [
        ("At origin, stationary", np.array([0.0, 0.0, 0.0, 0.0], dtype=np.float32)),
        ("Moving forward", np.array([1.0, 0.0, 0.5, 0.0], dtype=np.float32)),
        ("Moving diagonally", np.array([1.0, 1.0, 0.3, 0.3], dtype=np.float32)),
        ("Near goal", np.array([4.5, 4.5, 0.0, 0.0], dtype=np.float32)),
    ]
    
    # Scaling factors to test
    linear_scales = [0.5, 1.0, 2.0, 5.0, 10.0]
    angular_scales = [1.0, 2.0, 5.0, 10.0, 15.0]
    
    print("\n" + "=" * 70)
    print("Testing Action Outputs")
    print("=" * 70)
    
    for case_name, obs in test_cases:
        print(f"\n{case_name}:")
        print(f"  Observation: {obs}")
        
        # Get action from agent
        action = agent.get_action(obs)
        force_x, force_y = action
        
        print(f"  Agent output: force_x={force_x:.4f}, force_y={force_y:.4f}")
        print(f"  Force magnitude: {np.sqrt(force_x**2 + force_y**2):.4f}")
    
    print("\n" + "=" * 70)
    print("Scaling Factor Analysis")
    print("=" * 70)
    print("\nCurrent configuration (in maze_to_sim_bridge.py):")
    print("  linear_vel = force_x × 5.0  (clipped to ±0.22 m/s)")
    print("  angular_vel = force_y × 10.0 (clipped to ±2.84 rad/s)")
    
    # Test with first observation
    obs = test_cases[0][1]
    action = agent.get_action(obs)
    force_x, force_y = action
    
    print(f"\nUsing observation: {test_cases[0][0]}")
    print(f"Agent forces: ({force_x:.4f}, {force_y:.4f})")
    print("\n" + "-" * 70)
    print(f"{'Linear Scale':<12} {'Angular Scale':<14} {'Linear Vel':<12} {'Angular Vel':<12} {'Status'}")
    print("-" * 70)
    
    for lin_scale in linear_scales:
        for ang_scale in angular_scales:
            linear_vel = force_x * lin_scale
            angular_vel = force_y * ang_scale
            
            # Clip to TurtleBot3 limits
            linear_clipped = np.clip(linear_vel, -0.22, 0.22)
            angular_clipped = np.clip(angular_vel, -2.84, 2.84)
            
            # Determine if clipping occurred
            status = []
            if abs(linear_vel) > 0.22:
                status.append("L-clip")
            if abs(angular_vel) > 2.84:
                status.append("A-clip")
            
            # Check if too small
            if abs(linear_clipped) < 0.01:
                status.append("L-tiny")
            if abs(angular_clipped) < 0.1:
                status.append("A-tiny")
            
            status_str = ", ".join(status) if status else "✓ Good"
            
            # Highlight current config
            marker = "→" if (lin_scale == 5.0 and ang_scale == 10.0) else " "
            
            print(f"{marker} {lin_scale:>6.1f}      × {ang_scale:>6.1f}       = "
                  f"{linear_clipped:>7.4f}      {angular_clipped:>7.4f}      {status_str}")
    
    print("\n" + "=" * 70)
    print("Recommendations")
    print("=" * 70)
    print("""
1. Look for scales marked '✓ Good' - these produce usable velocities without clipping
2. Avoid scales with 'L-tiny' or 'A-tiny' - robot won't move effectively  
3. Avoid scales with 'clip' - saturating limits means loss of control precision
4. Current config (→) shows 5.0/10.0 scaling

Good velocity ranges:
  Linear:  0.05 - 0.15 m/s  (exploration speed)
  Angular: 0.3 - 1.5 rad/s  (turning speed)

If robot still doesn't navigate well after tuning, consider:
  - Native TurtleBot3 training (eliminates domain gap)
  - Fine-tuning the PointMaze agent on TurtleBot3
    """)
    
    print("\n" + "=" * 70)
    print("Next Steps")
    print("=" * 70)
    print("""
To apply different scaling factors:
1. Edit rlrd/maze_to_sim_bridge.py
2. Find the translate_action() method  
3. Change the scaling factors:
   
   linear_x = force_x * YOUR_LINEAR_SCALE
   angular_z = force_y * YOUR_ANGULAR_SCALE

4. Restart the controller:
   python3 run_sim_controller.py checkpoints/pointmaze_1/state
    """)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 test_action_scaling.py <checkpoint_path>")
        print("\nExample:")
        print("  python3 test_action_scaling.py checkpoints/pointmaze_1/state")
        sys.exit(1)
    
    checkpoint_path = sys.argv[1]
    
    try:
        test_scaling_factors(checkpoint_path)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

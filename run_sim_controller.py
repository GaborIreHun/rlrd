#!/usr/bin/env python3
"""
Run the maze-trained agent in TurtleBot3 Gazebo simulation.

Make sure Gazebo is running first:
    roslaunch turtlebot3_gazebo turtlebot3_world.launch

Then run this script:
    python3 run_sim_controller.py [checkpoint_path]
    
Examples:
    python3 run_sim_controller.py checkpoints/pointmaze_1/state
    python3 run_sim_controller.py checkpoints/maze_model_1/state
    
If no checkpoint path is provided, defaults to 'checkpoints/maze_model_1/state'
"""

import sys
from rlrd.maze_to_sim_bridge import SimController

def main():
    # Allow checkpoint path as command-line argument
    if len(sys.argv) > 1:
        checkpoint_path = sys.argv[1]
    else:
        checkpoint_path = 'checkpoints/maze_model_1/state'
        print(f"No checkpoint specified, using default: {checkpoint_path}")
    
    print("=" * 60)
    print("Starting Maze Agent in TurtleBot3 Simulation")
    print("=" * 60)
    print(f"Checkpoint: {checkpoint_path}")
    print("=" * 60)
    print("\nAction Scaling Configuration:")
    print("  Linear velocity:  force_x × 8.0  (clipped to ±0.22 m/s)")
    print("  Angular velocity: force_y × 2.0  (clipped to ±2.84 rad/s)")
    print("  Dampening: Angular halved when both active")
    print("=" * 60)
    
    try:
        controller = SimController(checkpoint_path)
        controller.run()
    except KeyboardInterrupt:
        print("\n\nStopping controller...")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()

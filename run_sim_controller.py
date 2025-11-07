#!/usr/bin/env python3
"""
Run the maze-trained agent in TurtleBot3 Gazebo simulation.

Make sure Gazebo is running first:
    roslaunch turtlebot3_gazebo turtlebot3_world.launch

Then run this script:
    python3 run_sim_controller.py
"""

from rlrd.maze_to_sim_bridge import SimController

def main():
    checkpoint_path = 'checkpoints/maze_model_1/state'
    
    print("=" * 60)
    print("Starting Maze Agent in TurtleBot3 Simulation")
    print("=" * 60)
    print(f"Checkpoint: {checkpoint_path}")
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

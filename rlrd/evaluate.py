# rlrd/evaluate.py

import torch
from pandas import Timestamp
from rlrd.envs import ENV_REGISTRY 
from rlrd.wrappers import StatsWrapper
from rlrd.dcac import Agent
import argparse
import os
import time
from functools import partial
from gym.wrappers import Monitor
import numpy as np
import csv
import argparse

def make_env(env_id, seed_val=0, **kwargs):
    if env_id not in ENV_REGISTRY:
        raise ValueError(f"Unknown Env.id={env_id}. Available: {list(ENV_REGISTRY.keys())}")
    return ENV_REGISTRY[env_id](seed_val=seed_val, id=env_id, **kwargs)

def evaluate(
    model_path,
    env_id="Pendulum-v0",
    steps=2000,
    seed=42,
    min_observation_delay=0,
    sup_observation_delay=1,
    min_action_delay=0,
    sup_action_delay=1,
    episodes=5,
    log_dir="/tmp",
    render_mode="human"
):
    video_dir = "videos_dmc"
    os.makedirs(video_dir, exist_ok=True)

    # Create env config
    env_ctor = ENV_REGISTRY[env_id]

    # === Handle environments that support delay arguments ===
    delay_envs = ("RandomDelay-", "RandomDelay", "RandomDelayEnv")
    if any(tag in env_id for tag in delay_envs):
        env = env_ctor(seed_val=seed,
                log_dir=args.log_dir,
                min_observation_delay=min_observation_delay,
                sup_observation_delay=sup_observation_delay,
                min_action_delay=min_action_delay,
                sup_action_delay=sup_action_delay)
    else:
        env = env_ctor(seed_val=seed, log_dir=log_dir)

    # Load trained agent
    agent = Agent(env_ctor)
    agent.model.load_state_dict(torch.load(model_path, map_location="cpu"))
    agent.model.eval()

    episode_rewards = []

    for ep in range(episodes):
        ep_seed = seed + ep
        env = Monitor(env_ctor(seed_val=ep_seed), directory=f"{video_dir}/ep_{ep}", force=True, video_callable=lambda x: True)

        obs = env.reset()
        state = None
        done = False
        info = {}
        reward = 0.0
        total_reward = 0.0
        steps_taken = 0
        step_rewards = []

        while not done and steps_taken < steps:
            action, state, _ = agent.act(state, obs, reward, done, info, train=False, deterministic=True)
            print(f"Step {steps_taken}: action={action}")
            obs, reward, done, info = env.step(action)
            print(f"→ reward={reward}, done={done}") 
            if render_mode == "human":
                env.render()
                time.sleep(1 / 30)  # 30 FPS
            elif render_mode == "video":
                env.render(mode="rgb_array")  # In case your env captures frames
            time.sleep(1 / 30)  # ~30 FPS
            total_reward += reward
            steps_taken += 1
            step_rewards.append((steps_taken, reward, action.tolist()))

        env.close()
        log_path = f"{video_dir}/ep_{ep}/reward_log.csv"
        with open(log_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["step", "reward", "action"])
            writer.writerows(step_rewards)
            
        print(f"[Episode {ep+1}/{episodes}] Total Reward: {total_reward:.2f} in {steps_taken} steps")
        episode_rewards.append(total_reward)

    # Final stats
    timestamp = Timestamp.utcnow().strftime("%Y%m%d-%H%M%S")
    eval_dir = "evaluation"
    os.makedirs(eval_dir, exist_ok=True)

    mean_reward = np.mean(episode_rewards)
    std_reward = np.std(episode_rewards)

    print("=== Evaluation Summary ===")
    print(f"  Episodes Run: {episodes}")
    print(f"  Mean Reward: {mean_reward:.2f}")
    print(f"  Std Dev Reward: {std_reward:.2f}")
    print(f"  Videos saved to: {os.path.abspath(video_dir)}")

    with open(f"{eval_dir}/eval_{timestamp}.txt", "w") as f:
        f.write(f"Model: {model_path}\n")
        f.write(f"Episodes: {episodes}\n")
        f.write(f"Mean Reward: {mean_reward:.2f}\n")
        f.write(f"Std Reward: {std_reward:.2f}\n")
        for i, r in enumerate(episode_rewards):
            f.write(f"Episode {i+1} Reward: {r:.2f}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--env", default="Pendulum-v0")
    parser.add_argument("--steps", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--episodes", type=int, default=5)
    parser.add_argument("--min_observation_delay", type=int, default=0)
    parser.add_argument("--sup_observation_delay", type=int, default=1)
    parser.add_argument("--min_action_delay", type=int, default=0)
    parser.add_argument("--sup_action_delay", type=int, default=1)
    parser.add_argument("--log_dir", type=str, default="/tmp")
    parser.add_argument("--render_mode", type=str, default="human", choices=["human", "video", "none"])

    args = parser.parse_args()

    evaluate(
        model_path=args.model,
        env_id=args.env,
        steps=args.steps,
        seed=args.seed,
        episodes=args.episodes,
        min_observation_delay=args.min_observation_delay,
        sup_observation_delay=args.sup_observation_delay,
        min_action_delay=args.min_action_delay,
        sup_action_delay=args.sup_action_delay,
        log_dir=args.log_dir,
        render_mode=args.render_mode
    )




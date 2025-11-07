import os
from dataclasses import dataclass
from pandas import DataFrame, Timestamp
import pandas as pd
import torch

import rlrd.sac
from rlrd.testing import Test
from rlrd.util import pandas_dict
from rlrd.wrappers import StatsWrapper
# from rlrd.envs import GymEnv
from rlrd.envs import ENV_REGISTRY

# Utility to save training stats to CSV
def save_stats(stats_list, filename="stats_dmc/experiment-1.csv"):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    pd.DataFrame(stats_list).to_csv(filename, index=False)

@dataclass(eq=False)
class Training:
    Env: str = "Pendulum-v0"   # default environment ID
    Test: type = Test
    Agent: type = rlrd.sac.Agent
    epochs: int = 10        # total number of epochs
    rounds: int = 50        # number of rounds per epoch
    steps: int = 2000       # number of steps per round
    stats_window: int = None
    seed: int = 0           # RNG seed offset per epoch
    tag: str = ''           # for custom logging tags

    def __post_init__(self):
        self.epoch = 0
        # Always resolve to a callable environment constructor
        if isinstance(self.Env, str):
            from rlrd.envs import ENV_REGISTRY
            self.env_ctor = ENV_REGISTRY[self.Env]
        else:
            self.env_ctor = self.Env
        self.agent = self.Agent(self.env_ctor)

        self.best_reward = float('-inf')  # Track the best test reward

    def run_epoch(self):
        stats = []
        state = None

        with StatsWrapper(
            self.env_ctor(seed_val=self.seed + self.epoch),
            window=self.stats_window or self.steps
        ) as env:
            for rnd in range(self.rounds):
                print(
                    f"=== epoch {self.epoch+1}/{self.epochs} ".ljust(20, '=') +
                    f" round {rnd+1}/{self.rounds} ".ljust(50, '=')
                )

                t0 = Timestamp.utcnow()
                stats_history = []

                # run test in parallel (blocks until done)
                test = self.Test(
                    Env=self.env_ctor,
                    actor=self.agent.model,
                    steps=self.stats_window or self.steps,
                    base_seed=self.seed + self.epochs
                )

                # main training loop
                for step in range(self.steps):
                    action, state, training_stats = self.agent.act(
                        state, *env.transition, train=True
                    )
                    # print("DEBUG: training_stats =", training_stats)
                    # print("DEBUG: type(training_stats) =", type(training_stats))

                    # Skip this step entirely if training_stats is an empty list
                    if isinstance(training_stats, list):
                        if len(training_stats) == 0:
                            continue  # Nothing to process this step
                        training_stats = training_stats[0]
                                    
                    env.step(action)

                    clean = {}

                    for k, v in training_stats.items():
                        if isinstance(v, dict):
                            for sub_k, sub_v in v.items():
                                clean_key = f"{k}.{sub_k}"
                                clean[clean_key] = sub_v.item() if torch.is_tensor(sub_v) else sub_v
                        else:
                            clean[k] = v.item() if torch.is_tensor(v) else v

                    stats_history.append(clean)

                    # At the end of the epoch, save full epoch summary
                    save_stats(stats, filename=f"stats/experiment-1_dmc/summary_epoch_{self.epoch}.csv")

                    # Flush CSV every 100 steps
                    if step and step % 100 == 0:
                        save_stats(stats_history, filename=f"stats/experiment-1_dmc/epoch_{self.epoch}_step_{step}.csv")


                # Build per-round summary from collected history
                # Filter only scalar keys from each stat entry
                scalar_stats_history = [
                    {k: v for k, v in stat.items() if isinstance(v, (int, float))}
                    for stat in stats_history
                ]

                batch_summary = pd.DataFrame(scalar_stats_history).mean(skipna=True).to_dict()

                summary = pandas_dict(
                    **env.stats(),
                    round_time=Timestamp.utcnow() - t0,
                    **test.stats().add_suffix("_test"),
                    round_time_total=Timestamp.utcnow() - t0,
                    **batch_summary
                )
                stats.append(summary)
                print(summary.add_prefix("  ").to_string(), "\n")

                # Save round-specific file
                save_stats([summary], filename=f"stats/experiment-1/summary_epoch_{self.epoch}_round_{rnd}.csv")

                # Save best model based on test reward
                reward = summary.get('reward_mean_test', None)
                if reward is not None and reward > self.best_reward:
                    self.best_reward = reward
                    torch.save(self.agent.model.state_dict(), f"checkpoints_dmc/best_model.pt")
                    print(f"New best model saved with reward_mean_test = {reward:.4f}")


        self.epoch += 1

        # Save model after epoch
        os.makedirs("checkpoints_dmc", exist_ok=True)
        torch.save(self.agent.model.state_dict(), f"checkpoints_dmc/sac_model_epoch_{self.epoch}.pt")

        # Final per-epoch summary
        save_stats(stats, filename=f"stats/experiment-1_dmc/summary_epoch_{self.epoch}.csv")

        return stats

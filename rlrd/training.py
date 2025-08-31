import os
from dataclasses import dataclass
from pandas import DataFrame, Timestamp
import pandas as pd
import torch

import rlrd.sac
from rlrd.testing import Test
from rlrd.util import pandas_dict
from rlrd.wrappers import StatsWrapper
from rlrd.envs import GymEnv

# Utility to save training stats to CSV
def save_stats(stats_list, filename="stats/experiment-1.csv"):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    pd.DataFrame(stats_list).to_csv(filename, index=False)

@dataclass(eq=False)
class Training:
    Env: type = GymEnv
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
        self.agent = self.Agent(self.Env)

    def run_epoch(self):
        stats = []
        state = None

        with StatsWrapper(
            self.Env(seed_val=self.seed + self.epoch),
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
                    Env=self.Env,
                    actor=self.agent.model,
                    steps=self.stats_window or self.steps,
                    base_seed=self.seed + self.epochs
                )

                # main training loop
                for step in range(self.steps):
                    action, state, training_stats = self.agent.act(
                        state, *env.transition, train=True
                    )
                    env.step(action)

                    # Map list of stats
                    names = [
                        "loss_total", "loss_critic", "loss_actor", "memory_size",
                        "reward_mean", "reward_std", "value_target_mean", "value_target_std",
                        "gradient_norm_actor", "gradient_norm_critic", "entropy_log_probs_mean",
                        "nstep_len_mean", "nstep_len_std", "obs_delay_mean", "act_delay_mean",
                        "actor_output_mean", "actor_output_std", "model_val_mean", "target_val_mean"
                    ]

                    clean = {}
                    for name in names:
                        v = training_stats.get(name, None)
                        if v is None:
                            continue
                        if isinstance(v, dict):
                            clean.update({k: (vv.item() if torch.is_tensor(vv) else vv) for k, vv in v.items()})
                        else:
                            clean[name] = v.item() if torch.is_tensor(v) else v

                    stats_history.append(clean)

                    save_stats(stats, filename=f"stats/experiment-1/summary_epoch_{self.epoch}.csv")

                    # Flush CSV every 100 steps
                    if step and step % 100 == 0:
                        save_stats(stats_history, filename=f"stats/experiment-1/epoch_{self.epoch}_step_{step}.csv")


                # Build per-round summary from collected history
                batch_summary = DataFrame(stats_history).mean(skipna=True).to_dict()
                summary = pandas_dict(
                    **env.stats(),
                    round_time=Timestamp.utcnow() - t0,
                    **test.stats().add_suffix("_test"),
                    round_time_total=Timestamp.utcnow() - t0,
                    **batch_summary
                )
                stats.append(summary)
                print(summary.add_prefix("  ").to_string(), "\n")

        self.epoch += 1
        return stats

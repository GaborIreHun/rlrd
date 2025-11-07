# 📊 Tracked Metrics Summary for Training in RL-RD

This document describes each metric currently being logged during training for enhanced analysis and debugging.

## Episode Performance Metrics

### Training Episodes
- **`episodes`**: Number of episodes completed during training round
- **`episode_length`**: Average steps per episode during training
- **`returns`**: Sum of rewards per episode during training
- **`average_reward`**: Mean reward per step during training

### Test Episodes
- **`episodes_test`**: Number of episodes completed during evaluation (no exploration)
- **`episode_length_test`**: Average steps per episode during testing
- **`returns_test`**: Sum of rewards per episode during testing
- **`average_reward_test`**: Mean reward per step during testing

| **Metric**            | **Purpose**                                                                                    |
| --------------------- | ---------------------------------------------------------------------------------------------- |
| `returns`             | Total cumulative reward per episode. Primary indicator of policy performance.                  |
| `average_reward`      | Average reward per timestep. Useful for comparing episodes of different lengths.               |
| `episode_length`      | How many steps until episode terminates. Longer may indicate better survival/task completion.  |
| `*_test` metrics      | Evaluation metrics without exploration noise. Shows true policy quality.                       |

## Losses

### `loss_actor`
Loss from the actor network during training.

### `loss_critic`
Loss from the critic networks during training.

### `loss_total`
Combined actor and critic loss.

### `loss_total_delta`
Change in total loss between updates.

| **Metric**          | **Purpose**                                                                                                    |
| ------------------- | -------------------------------------------------------------------------------------------------------------- |
| `loss_actor`        | Measures how well the actor (policy) maximizes expected reward. Lower values suggest the policy is improving.  |
| `loss_critic`       | Measures how accurately the critic (value estimator) predicts expected returns. Helps optimize value function. |
| `loss_total`        | Combined loss used to monitor overall training signal and convergence behavior.                                |
| `loss_total_delta`  | Change in total loss. Large fluctuations indicate training instability.                                        |

## Value Function Tracking

### Q-Value Statistics
- **`value_target_mean`**: Mean of the computed target Q-values
- **`value_target_std`**: Standard deviation of target Q-values
- **`q_value_mean`**: Mean Q-value from current critic network
- **`q_value_std`**: Standard deviation of Q-values
- **`model_val_mean`**: Mean estimated value from the critic network (online model)
- **`target_val_mean`**: Mean estimated value from the critic target network

### TD Error
- **`td_error_mean`**: Mean temporal difference error
- **`td_error_std`**: Standard deviation of TD errors

### Critic Agreement and Disagreement
- **`critic_agreement_ratio`**: Ratio of times critics agree on best action
- **`critic_disagreement_mean`**: Mean disagreement between critic networks
- **`critic_disagreement_std`**: Standard deviation of critic disagreement
- **`critic_disagreement_max`**: Maximum disagreement observed
- **`critic_disagreement_min`**: Minimum disagreement observed
- **`critic_disagreement_median`**: Median disagreement
- **`critic_disagreement_q25`**: 25th percentile of disagreement
- **`critic_disagreement_q75`**: 75th percentile of disagreement
- **`critic_var_top5_mean`**: Mean variance of top 5% highest Q-values
- **`critic_value_drift`**: How much critic values drift between updates

| **Metric**                | **Purpose**                                                                                               |
| ------------------------- | --------------------------------------------------------------------------------------------------------- |
| `value_target_mean`       | Mean of the computed target Q-values. Indicates reward expectations the agent is trying to learn.         |
| `value_target_std`        | Variance in target Q-values, helpful for identifying noisy targets or learning instability.               |
| `q_value_mean`            | Average Q-value prediction. Should increase as policy improves.                                           |
| `td_error_mean`           | Prediction error between current and target values. Should decrease as learning progresses.               |
| `critic_agreement_ratio`  | How often multiple critics agree. High agreement suggests confident value estimates.                      |
| `critic_disagreement_*`   | Measures uncertainty/variance between critic networks. High disagreement indicates epistemic uncertainty. |
| `critic_value_drift`      | Value function stability measure. Large drift suggests unstable learning.                                 |

## Optimization Diagnostics

### Learning Rate
- **`learning_rate`**: Current learning rate (may be adaptive/scheduled)

### Gradient Norms
- **`gradient_norm_actor`**: L2 norm of gradients for the actor network
- **`gradient_norm_critic`**: L2 norm of gradients for the critic networks

### Gradient Variance
- **`actor_grad_var`**: Variance of actor gradients across batch
- **`critic_grad_var`**: Variance of critic gradients across batch

### Parameter Norms
- **`actor_param_norm_before`**: L2 norm of actor parameters before update
- **`actor_param_norm_after`**: L2 norm of actor parameters after update
- **`critic_param_norm_before`**: L2 norm of critic parameters before update
- **`critic_param_norm_after`**: L2 norm of critic parameters after update

| **Metric**                  | **Purpose**                                                                                           |
| --------------------------- | ----------------------------------------------------------------------------------------------------- |
| `gradient_norm_actor`       | L2 norm of actor gradients. Helps detect vanishing/exploding gradient issues or training instability. |
| `gradient_norm_critic`      | Same as above but for critic. Useful to diagnose learning saturation.                                 |
| `actor_grad_var`            | Gradient variance - high variance suggests noisy/inconsistent updates.                                |
| `*_param_norm_before/after` | Parameter magnitude tracking. Large changes indicate aggressive updates; no change suggests stalling. |
| `learning_rate`             | Current LR - useful if using schedulers or adaptive methods.                                          |

## Policy Behavior

### Entropy Metrics
- **`entropy_log_probs_mean`**: Mean entropy (log probabilities) of the action distribution
- **`entropy_traj_start`**: Policy entropy at trajectory start
- **`entropy_traj_end`**: Policy entropy at trajectory end
- **`entropy_traj_delta`**: Change in entropy from start to end of trajectory
- **`entropy_traj_mean`**: Mean entropy across entire trajectory
- **`entropy_traj_std`**: Standard deviation of entropy across trajectory
- **`actor_entropy_first_mean`**: Mean entropy of first actions in episodes
- **`actor_entropy_first_std`**: Standard deviation of first action entropy

### Action Output Statistics
- **`actor_output_mean`**: Mean of the actor's sampled action outputs
- **`actor_output_std`**: Standard deviation of the actor's outputs
- **`avg_action_change`**: Average change in actions between consecutive timesteps

| **Metric**                 | **Purpose**                                                                                                 |
| -------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `entropy_log_probs_mean`   | Average policy entropy via log-probabilities. Higher entropy = more exploration; lower = policy converging. |
| `entropy_traj_start/end`   | Entropy at beginning vs end of episodes. Shows if policy becomes more deterministic over episode.           |
| `entropy_traj_delta`       | Change in exploration behavior within episodes. Negative = becoming more deterministic.                     |
| `actor_output_mean`        | Mean of sampled actions. Helps you observe policy drift or stability over training.                         |
| `actor_output_std`         | Standard deviation of sampled actions – low std could indicate deterministic/stuck policy.                  |
| `avg_action_change`        | How much actions change between steps. High values = erratic policy; low = smooth control.                  |

## Replay Buffer Insight

### `memory_size`
Current size of the replay memory buffer.

| **Metric**    | **Purpose**                                                                                      |
| ------------- | ------------------------------------------------------------------------------------------------ |
| `memory_size` | Number of transitions currently stored. Helps verify buffer warm-up and saturation for learning. |

## Reward Tracking

### Reward Statistics
- **`reward_mean`**: Mean reward value in the sampled batch
- **`reward_std`**: Standard deviation of reward values in the batch
- **`reward_min`**: Minimum reward in the batch
- **`reward_max`**: Maximum reward in the batch
- **`reward_corr`**: Correlation between consecutive rewards (temporal structure)

| **Metric**    | **Purpose**                                                                           |
| ------------- | ------------------------------------------------------------------------------------- |
| `reward_mean` | Mean of sampled rewards in a training batch. Central to evaluating learning progress. |
| `reward_std`  | Variation in rewards. High variance suggests noisy environment or unstable policy.    |
| `reward_min`  | Worst-case reward observed. Important for risk-sensitive tasks.                       |
| `reward_max`  | Best-case reward observed. Indicates peak performance potential.                      |
| `reward_corr` | Temporal correlation of rewards. High correlation = predictable reward structure.     |

## Temporal Metrics (Delay-Aware RL)

### `obs_delay_mean`
Mean observation delay retrieved from the replay buffer info.

### `act_delay_mean`
Mean action delay retrieved from the replay buffer info.

| **Metric**       | **Purpose**                                                                                    |
| ---------------- | ---------------------------------------------------------------------------------------------- |
| `obs_delay_mean` | Mean observation delay, extracted from `info['obs_delay']`. Important in delay-aware settings. |
| `act_delay_mean` | Mean action delay, from `info['act_delay']`. Helps quantify impact of actuation latency.       |
| `is_rtac`        | Boolean flag (1.0 or 0.0) indicating whether the algorithm is using real-time actor-critic logic |

## Training & Evaluation Timing Metrics

### Timing Benchmarks
- **`round_time`**: Wall-clock time for one training round (training steps only)
- **`round_time_test`**: Wall-clock time for testing/evaluation phase
- **`round_time_total`**: Total wall-clock time including both training and testing
- **`iteration_time`**: Time per iteration/update step

| **Metric**                                 | **Purpose**                                                                                                                                                                                     |
| ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `round_time`                               | Wall-clock duration of the **training** part of the round. Useful for profiling performance, especially in real-time or delay-aware environments.                                               |
| `round_time_test`                          | Wall-clock time for evaluation episodes. Measures inference efficiency and policy execution speed.                                                                                              |
| `round_time_total`                         | Total elapsed wall-clock time for the round, including both training and test phase. Important for assessing **end-to-end latency** or real-time performance.                                   |
| `iteration_time`                           | Average time per gradient update. Critical for throughput optimization and identifying computational bottlenecks.                                                                               |
| `*_test` metrics (e.g. `reward_mean_test`) | These are **test-time statistics**, suffixed with `_test`. Used to measure how well the current policy generalizes without exploration noise. These are environment-specific metrics.           |

---

## Summary

This training run tracks **66 comprehensive metrics** organized into the following categories:

1. **Episode Performance** (8 metrics): Training and test episode outcomes
2. **Loss Functions** (6 metrics): Actor and critic training objectives  
3. **Value Function Tracking** (15 metrics): Q-value estimates, TD errors, critic diagnostics
4. **Optimization Diagnostics** (10 metrics): Learning rate, gradients, parameter norms
5. **Policy Behavior** (18 metrics): Entropy, action statistics, exploration
6. **Replay Buffer Insight** (1 metric): Memory utilization
7. **Reward Tracking** (5 metrics): Reward statistics and temporal structure
8. **Temporal Metrics** (3 metrics): Delay exposure and algorithm mode
9. **Timing Metrics** (4 metrics): Performance benchmarking

These metrics provide comprehensive visibility into:
- **Learning Progress**: Episode returns, losses, value estimates
- **Training Stability**: Gradient norms, critic agreement, entropy
- **Delay Awareness**: Observation and action delay distributions
- **Computational Efficiency**: Timing per round and iteration
- **Policy Quality**: Action distributions, entropy, reward correlations

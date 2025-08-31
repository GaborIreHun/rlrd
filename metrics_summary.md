# 📊 Tracked Metrics Summary for Training in RL-RD

This document describes each metric currently being logged during training for enhanced analysis and debugging.

## Losses

### `loss_actor`
Loss from the actor network during training.

### `loss_critic`
Loss from the critic networks during training.

### `loss_total`
Combined actor and critic loss.

| **Metric**    | **Purpose**                                                                                                    |
| ------------- | -------------------------------------------------------------------------------------------------------------- |
| `loss_actor`  | Measures how well the actor (policy) maximizes expected reward. Lower values suggest the policy is improving.  |
| `loss_critic` | Measures how accurately the critic (value estimator) predicts expected returns. Helps optimize value function. |
| `loss_total`  | Combined loss used to monitor overall training signal and convergence behavior.                                |

## Value Function Tracking

### `value_target_mean`
Mean of the computed target Q-values.

### `value_target_std`
Standard deviation of target Q-values.

### `model_val_mean`
Mean estimated value from the critic network (online model).

### `target_val_mean`
Mean estimated value from the critic target network.

| **Metric**          | **Purpose**                                                                                               |
| ------------------- | --------------------------------------------------------------------------------------------------------- |
| `value_target_mean` | Mean of the computed target Q-values. Indicates reward expectations the agent is trying to learn.         |
| `value_target_std`  | Variance in target Q-values, helpful for identifying noisy targets or learning instability.               |
| `model_val_mean`    | Average critic Q-value prediction from the model (pre-normalization). Tracks value estimation confidence. |
| `target_val_mean`   | Similar to above but from the **target network** – used for stability in training via soft updates.       |

## Optimization Diagnostics

### `gradient_norm_actor`
Norm of gradients for the actor network.

### `gradient_norm_critic`
Norm of gradients for the critic networks.

| **Metric**             | **Purpose**                                                                                           |
| ---------------------- | ----------------------------------------------------------------------------------------------------- |
| `gradient_norm_actor`  | L2 norm of actor gradients. Helps detect vanishing/exploding gradient issues or training instability. |
| `gradient_norm_critic` | Same as above but for critic. Useful to diagnose learning saturation.                                 |

## Policy Behavior

### `entropy_log_probs_mean`
Mean entropy (log probabilities) of the action distribution.

### `actor_output_mean`
Mean of the actor's sampled action outputs.

### `actor_output_std`
Standard deviation of the actor's outputs.

| **Metric**               | **Purpose**                                                                                                 |
| ------------------------ | ----------------------------------------------------------------------------------------------------------- |
| `entropy_log_probs_mean` | Average policy entropy via log-probabilities. Higher entropy = more exploration; lower = policy converging. |
| `actor_output_mean`      | Mean of sampled actions. Helps you observe policy drift or stability over training.                         |
| `actor_output_std`       | Standard deviation of sampled actions – low std could indicate deterministic/stuck policy.                  |

## Replay Buffer Insight

### `memory_size`
Current size of the replay memory buffer.

| **Metric**    | **Purpose**                                                                                      |
| ------------- | ------------------------------------------------------------------------------------------------ |
| `memory_size` | Number of transitions currently stored. Helps verify buffer warm-up and saturation for learning. |

## Reward Tracking

### `reward_mean`
Mean reward value in the sampled batch.

### `reward_std`
Standard deviation of reward values in the batch.

| **Metric**    | **Purpose**                                                                           |
| ------------- | ------------------------------------------------------------------------------------- |
| `reward_mean` | Mean of sampled rewards in a training batch. Central to evaluating learning progress. |
| `reward_std`  | Variation in rewards. High variance suggests noisy environment or unstable policy.    |

## Temporal Metrics (Delay-Aware RL)

### `obs_delay_mean`
Mean observation delay retrieved from the replay buffer info.

### `act_delay_mean`
Mean action delay retrieved from the replay buffer info.

| **Metric**       | **Purpose**                                                                                    |
| ---------------- | ---------------------------------------------------------------------------------------------- |
| `obs_delay_mean` | Mean observation delay, extracted from `info['obs_delay']`. Important in delay-aware settings. |
| `act_delay_mean` | Mean action delay, from `info['act_delay']`. Helps quantify impact of actuation latency.       |

## Training & Evaluation Timing Metrics

### `round_time`
Wall-clock duration of the training round.

### `round_time_total`
Total duration of the training round including test phase.

### `test_stats`
Various test statistics collected after each round (e.g., avg reward).

| **Metric**                                 | **Purpose**                                                                                                                                                                                     |
| ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `round_time`                               | Wall-clock duration of the **training** part of the round. Useful for profiling performance, especially in real-time or delay-aware environments.                                               |
| `round_time_total`                         | Total elapsed wall-clock time for the round, including both training and test phase. Important for assessing **end-to-end latency** or real-time performance.                                   |
| `*_test` metrics (e.g. `reward_mean_test`) | These are **test-time statistics**, suffixed with `_test`. Used to measure how well the current policy generalizes without exploration noise. These are environment-specific metrics.           |

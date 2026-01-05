# Delay Correcting Actor-Critic

from copy import deepcopy
from dataclasses import dataclass
from functools import reduce
import torch
from torch.nn.functional import mse_loss
import rlrd.sac
from rlrd.memory import TrajMemoryNoHidden
from rlrd.nn import no_grad, exponential_moving_average
from rlrd.util import partial
from rlrd.dcac_models import Mlp
from rlrd.envs import RandomDelayEnv
from rlrd import Training
from contextlib import nullcontext
import pandas as pd
import time
from itertools import combinations
import random
import numpy as np

@dataclass(eq=0)
class Agent(rlrd.sac.Agent):
    Model: type = Mlp
    loss_alpha: float = 0.2
    rtac: bool = False

    def __post_init__(self, Env):
        with nullcontext(Env()) as env:
            observation_space, action_space = env.observation_space, env.action_space
            self.sup_obs_delay = env.obs_delay_range.stop
            self.sup_act_delay = env.act_delay_range.stop
            self.act_buf_size = self.sup_obs_delay + self.sup_act_delay - 1
            self.old_act_buf_size = deepcopy(self.act_buf_size)
            if self.rtac:
                self.act_buf_size = 1

        self.device = self.device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
        device = self.device  # or ("cuda" if torch.cuda.is_available() else "cpu")
        model = self.Model(observation_space, action_space)
        self.model = model.to(device)
        self.model_target = no_grad(deepcopy(self.model))

        self.outputnorm = self.OutputNorm(self.model.critic_output_layers)
        self.outputnorm_target = self.OutputNorm(self.model_target.critic_output_layers)

        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=self.lr)
        self.memory = TrajMemoryNoHidden(self.memory_size, self.batchsize, device, history=self.act_buf_size)
        self.traj_new_actions = [None, ] * self.act_buf_size
        self.traj_new_actions_detach = [None, ] * self.act_buf_size
        self.traj_new_actions_log_prob = [None, ] * self.act_buf_size
        self.traj_new_actions_log_prob_detach = [None, ] * self.act_buf_size
        self.traj_new_augm_obs = [None, ] * (self.act_buf_size + 1)

        self.is_training = False

    def select_action(self, obs, deterministic=True):
        """
        Selects action from policy.
        - If deterministic: uses the mean of the action distribution (for evaluation/simulation).
        - If not: uses rsample() (for training/exploration).
        """
        self.model.eval()
        obs_t = torch.as_tensor(obs, device=self.device).unsqueeze(0)
        with torch.no_grad():
            dist = self.model.actor(obs_t)
            if deterministic:
                # For distributions like Normal, mean is dist.mean; for others, adapt as needed.
                action = dist.mean if hasattr(dist, "mean") else dist.loc
            else:
                action = dist.rsample()
        # If action shape is (1, act_dim), squeeze it.
        return action.cpu().numpy().squeeze()
    
    @staticmethod  
    def set_global_seed(seed):
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False

    def train(self):
        start_time = time.time()
        # sample a trajectory of length self.act_buf_size
        # NB: when terminals is True, the terminal augmented state is the last one of the trajectory (this is ensured by the sampling procedure)

        # TODO: act_traj is useless, it could be removed from the replay memory
        # FIXME: the profiler indicates that memory is inefficient, optimize

        if len(self.memory) < self.batchsize:
            print(f"Skipping training: not enough samples in memory ({len(self.memory)} / {self.batchsize})")
            return {}

        augm_obs_traj, act_traj, rew_traj, terminals, info = self.memory.sample()

        batch_size = terminals.shape[0]

        # value of the first augmented state:
        values = [c(augm_obs_traj[0]).squeeze() for c in self.model.critics]

        # Q-value stats
        # This will allow you to monitor:
        #     Training stability: high Q-value variance = inaccurate critic
        #     Delay impact: compare Q-value variance across different delay configurations
        #     Overestimation bias: high Q-value mean = possible overestimation bias
        q_values = torch.stack(values)
        q_value_mean = q_values.mean().item()
        q_value_std = q_values.std().item()

        # Actor entropy at first augmented observation (pre-update)
        # This helps monitor policy stochasticity across training
        try:
            dist = self.model.actor(augm_obs_traj[0])  # Distribution object
            entropy_vector = dist.entropy()  # [batch_size] tensor
            actor_entropy_first_mean = entropy_vector.mean().item()
            actor_entropy_first_std = entropy_vector.std().item()
        except NotImplementedError:
            actor_entropy_first_mean = float("nan")
            actor_entropy_first_std = float("nan")



        # Critic disagreement: ensemble variance across critics
        # This will allow you to monitor:
        #     Training stability: high critic disagreement = inaccurate critic
        #     Delay impact: compare critic disagreement across different delay configurations
        #     Overestimation bias: high critic disagreement = possible overestimation bias
        critic_values = torch.stack([v.detach() for v in values])  # shape: (num_critics, batch_size)
        critic_variance_per_sample = critic_values.var(dim=0)       # shape: (batch_size,)

        agree_threshold = 0.01  # you can tune this
        num_agreeing_pairs = 0
        num_total_pairs = 0

        for i, j in combinations(range(critic_values.shape[0]), 2):
            diff = (critic_values[i] - critic_values[j]).abs()
            agree = (diff < agree_threshold).float().mean().item()
            if agree > 0.9:  # 90% of predictions are close
                num_agreeing_pairs += 1
            num_total_pairs += 1

        critic_agreement_ratio = num_agreeing_pairs / num_total_pairs if num_total_pairs > 0 else float("nan")


        # Store the full vector (as NumPy)
        critic_disagreement_vector = critic_variance_per_sample.cpu().numpy()

        # Critic disagreement: ensemble variance across critics
        critic_variance_per_sample_mean = critic_variance_per_sample.mean().item()
        critic_variance_per_sample_std = critic_variance_per_sample.std().item()
        critic_variance_per_sample_max = critic_variance_per_sample.max().item()
        critic_variance_per_sample_min = critic_variance_per_sample.min().item()
        critic_variance_per_sample_median = critic_variance_per_sample.median().item()
        critic_variance_per_sample_q25 = critic_variance_per_sample.kthvalue(int(0.25 * batch_size)).values.item()
        critic_variance_per_sample_q75 = critic_variance_per_sample.kthvalue(int(0.75 * batch_size)).values.item()

        # Additional critic disagreement metric: mean of top 5 variance samples
        # Critic disagreement: top-k variance tracking
        # Measures the average variance among the top 5 most uncertain (disagreeing) critic predictions in the current batch.
            # Why it’s useful:
            # Spot high-uncertainty regions during training.
            # Monitor risk-sensitive states where critics disagree most.
            # Early warning for instability or overestimation bias in sparse-reward settings.
            # Improves plotting clarity — compare critic_var_top5_mean over time with other critic stats.
        topk_k = min(5, critic_variance_per_sample.shape[0])
        topk_var, _ = torch.topk(critic_variance_per_sample, k=topk_k)
        critic_var_top5_mean = topk_var.mean().item()




        # nstep_len is the number of valid transitions of the sampled sub-trajectory, not counting the first one which is always valid since we consider the action delay to be always >= 1.
        # nstep_len will be e.g. 0 in the rtrl setting (an action delay of 0 here means an action delay of 1 in the paper).

        int_tens_type = obs_del = augm_obs_traj[0][2].dtype
        ones_tens = torch.ones(batch_size, device=self.device, dtype=int_tens_type, requires_grad=False)

        if not self.rtac:
            nstep_len = ones_tens * (self.act_buf_size - 1)
            for i in reversed(range(self.act_buf_size)):  # we don't care about the delay of the first observation in the trajectory, but we care about the last one
                obs_del = augm_obs_traj[i + 1][2]  # observation delay (alpha)
                act_del = augm_obs_traj[i + 1][3]  # action_delay (beta) - FIXED: was [4], should be [3]
                tot_del = obs_del + act_del
                # Ensure minimum total delay of 1 (DCAC requirement)
                tot_del = torch.clamp(tot_del, min=1)
                # TODO: the last iteration is useless
                nstep_len = torch.where((tot_del <= i), ones_tens * (i - 1), nstep_len)
            nstep_max_len = torch.max(nstep_len)
            nstep_min_len = torch.min(nstep_len)
            assert nstep_min_len >= 0, "Each total delay must be at least 1 (instantaneous turn-based RL not supported)"
            nstep_one_hot = torch.zeros(len(nstep_len), nstep_max_len + 1, device=self.device, requires_grad=False).scatter_(1, nstep_len.unsqueeze(1).long(), 1.)
        else:  # RTAC is equivalent to doing only 1-step backups (i.e. nstep_len==0)
            nstep_len = torch.zeros(batch_size, device=self.device, dtype=int_tens_type, requires_grad=False)
            nstep_max_len = torch.max(nstep_len)
            nstep_one_hot = torch.zeros(len(nstep_len), nstep_max_len + 1, device=self.device, requires_grad=False).scatter_(1, nstep_len.unsqueeze(1).long(), 1.)
            terminals = terminals if self.act_buf_size == 1 else terminals * 0.0  # the way the replay memory works, RTAC will never encounter terminal states for buffers of more than 1 action

        # use the current policy to compute a new trajectory of actions of length self.act_buf_size
        for i in range(self.act_buf_size + 1):
            # compute a new action and update the corresponding *next* augmented observation:
            augm_obs = augm_obs_traj[i]
            if i > 0:
                act_slice = tuple(self.traj_new_actions[self.act_buf_size - i:self.act_buf_size])
                augm_obs = augm_obs[:1] + ((act_slice + augm_obs[1][i:]), ) + augm_obs[2:]
            if i < self.act_buf_size:  # we don't compute the action for the last observation of the trajectory
                new_action_distribution = self.model.actor(augm_obs)
                # this is stored in right -> left order for replacing correctly in augm_obs:
                self.traj_new_actions[self.act_buf_size - i - 1] = new_action_distribution.rsample()
                self.traj_new_actions_detach[self.act_buf_size - i - 1] = self.traj_new_actions[self.act_buf_size - i - 1].detach()
                # this is stored in left -> right order for to be consistent with the reward trajectory:
                self.traj_new_actions_log_prob[i] = new_action_distribution.log_prob(self.traj_new_actions[self.act_buf_size - i - 1])
                self.traj_new_actions_log_prob_detach[i] = self.traj_new_actions_log_prob[i].detach()
            # this is stored in left -> right order:
            self.traj_new_augm_obs[i] = augm_obs

        # Compute entropy at each step of the trajectory
        actor_entropies = []
        K = 10  # number of MC samples

        for obs in augm_obs_traj:
            dist = self.model.actor(obs)
            samples = [dist.rsample() for _ in range(K)]  # List of [batch_size, action_dim]
            log_probs = torch.stack([dist.log_prob(sample) for sample in samples])  # shape: [K, batch_size]
            est_entropy = -log_probs.mean(0).mean()  # scalar
            actor_entropies.append(est_entropy)


        # Stack across trajectory: shape [timesteps]
        actor_entropies_tensor = torch.stack(actor_entropies)

        # Entropy change metrics
        entropy_start = actor_entropies_tensor[0].item()
        entropy_end = actor_entropies_tensor[-1].item()
        entropy_delta = entropy_end - entropy_start
        entropy_traj_mean = actor_entropies_tensor.mean().item()
        entropy_traj_std = actor_entropies_tensor.std().item()


        # Compute average change between consecutive new actions in the buffer
        action_diffs = [
            (self.traj_new_actions_detach[i] - self.traj_new_actions_detach[i - 1]).norm(dim=1).mean().item()
            for i in range(1, len(self.traj_new_actions_detach))
        ]
        if len(action_diffs) > 0:
            avg_action_change = sum(action_diffs) / len(action_diffs)
        else:
            avg_action_change = float("nan")  # or 0.0 if preferred



        # We now compute the state-value estimate
        # (this can be a different position in the trajectory for each element of the batch).
        # We expect each augmented state to be of shape (obs:tensor, act_buf:(tensor, ..., tensor), obs_del:tensor, act_del:tensor). Each tensor is batched.
        # To execute only 1 forward pass in the state-value estimator we recreate an artificially batched augmented state for this specific purpose.

        # FIXME: the profiler indicates that the following 5 lines are very inefficient, optimize

        obs_s = torch.stack([self.traj_new_augm_obs[i + 1][0][ibatch] for ibatch, i in enumerate(nstep_len)])
        act_s = tuple(torch.stack([self.traj_new_augm_obs[i + 1][1][iact][ibatch] for ibatch, i in enumerate(nstep_len)]) for iact in range(self.old_act_buf_size))
        od_s = torch.stack([self.traj_new_augm_obs[i + 1][2][ibatch] for ibatch, i in enumerate(nstep_len)])
        ad_s = torch.stack([self.traj_new_augm_obs[i + 1][3][ibatch] for ibatch, i in enumerate(nstep_len)])
        mod_augm_obs = tuple((obs_s, act_s, od_s, ad_s))

        with torch.no_grad():

            # These are the delayed state-value estimates we are looking for:
            target_mod_val = [c(mod_augm_obs) for c in self.model_target.critics]
            target_mod_val = reduce(torch.min, torch.stack(target_mod_val)).squeeze()  # minimum target estimate
            target_mod_val = target_mod_val * (1. - terminals)

            # Now let us use this to compute the state-value targets of the batch of initial augmented states:

            value_target = torch.zeros(batch_size, device=self.device)
            backup_started = torch.zeros(batch_size, device=self.device)
            for i in reversed(range(nstep_max_len + 1)):
                start_backup_mask = nstep_one_hot[:, i]
                backup_started += start_backup_mask
                value_target = self.reward_scale * rew_traj[i] - self.entropy_scale * self.traj_new_actions_log_prob_detach[i] + backup_started * self.discount * (value_target + start_backup_mask * target_mod_val)

        assert values[0].shape == value_target.shape, f"values[0].shape : {values[0].shape} != value_target.shape : {value_target.shape}"
        assert not value_target.requires_grad

        # TD Error metrics
        # This will allow you to monitor:
        #     Training stability: high TD error = inaccurate critic
        #     Delay impact: compare TD error across different delay configurations
        #     Overfitting: consistently low training loss + high TD error = possible overfitting
        td_error = [v.detach() - value_target for v in values]
        td_error = torch.stack(td_error)
        td_error_mean = td_error.mean().item()
        td_error_std = td_error.std().item()


        # Now the critic loss is:

        loss_critic = sum(mse_loss(v, value_target) for v in values)

        # actor loss:
        # TODO: there is probably a way of merging this with the previous for loop

        model_mod_val = [c(mod_augm_obs) for c in self.model_nograd.critics]
        model_mod_val = reduce(torch.min, torch.stack(model_mod_val)).squeeze()  # minimum model estimate
        model_mod_val = model_mod_val * (1. - terminals)

        # Drift between current model and target critic value estimates
        # Measures temporal instability or target mismatch
        drift = (model_mod_val - target_mod_val).abs().mean().item()


        loss_actor = torch.zeros(batch_size, device=self.device)
        backup_started = torch.zeros(batch_size, device=self.device)
        for i in reversed(range(nstep_max_len + 1)):
            start_backup_mask = nstep_one_hot[:, i]
            backup_started += start_backup_mask
            loss_actor = - self.entropy_scale * self.traj_new_actions_log_prob[i] + backup_started * self.discount * (loss_actor + start_backup_mask * model_mod_val)
        loss_actor = - loss_actor.mean(0)

        # update model
        self.optimizer.zero_grad()
        loss_total = self.loss_alpha * loss_actor + (1 - self.loss_alpha) * loss_critic

        # Compute change in total loss since last update
        self.prev_loss_total = getattr(self, "prev_loss_total", loss_total.item())
        loss_total_delta = loss_total.item() - self.prev_loss_total
        self.prev_loss_total = loss_total.item()


        actor_param_norm_before = sum(p.norm().item() for p in self.model.actor.parameters())
        critic_param_norm_before = sum(p.norm().item() for p in self.model.critics.parameters())

        loss_total.backward()

        def grad_variance(params):
            grads = [p.grad.view(-1) for p in params if p.grad is not None]
            grads_flat = torch.cat(grads)
            return grads_flat.var().item() if grads_flat.numel() > 0 else 0.0

        actor_grad_var = grad_variance(self.model.actor.parameters())
        critic_grad_var = grad_variance(self.model.critics.parameters())


        actor_param_norm_after = sum(p.norm().item() for p in self.model.actor.parameters())
        critic_param_norm_after = sum(p.norm().item() for p in self.model.critics.parameters())


        # Clip gradients AFTER backward pass but BEFORE optimizer step
        clip_actor = torch.nn.utils.clip_grad_norm_(self.model.actor.parameters(), max_norm=1e6)
        clip_critic = torch.nn.utils.clip_grad_norm_(self.model.critics.parameters(), max_norm=1e6)

        self.optimizer.step()

        current_lr = self.optimizer.param_groups[0]["lr"]

        # update target model
        exponential_moving_average(self.model_target.parameters(), self.model.parameters(), self.target_update)

        # exponential_moving_average(self.outputnorm_target.parameters(), self.outputnorm.parameters(), self.target_update)  # this is for trying PopArt in the future

        # Fix reward mean/std for list of tensors
        all_rewards = torch.stack(rew_traj)  # Shape: [timesteps, batch_size]
        reward_mean = all_rewards.mean().item()
        reward_std = all_rewards.std().item()
        reward_min = all_rewards.min().item()
        reward_max = all_rewards.max().item()

        # Reward correlation between consecutive steps
        # Useful to detect reward smoothness/volatility in delayed settings
        if all_rewards.size(0) > 1:
            rew_corr = torch.corrcoef(torch.stack([all_rewards[:-1].flatten(), all_rewards[1:].flatten()]))[0, 1].item()
        else:
            rew_corr = float("nan")


        # Delay info (safe check)
        obs_delays = [i.get("obs_delay") for i in info if isinstance(i, dict) and "obs_delay" in i]
        act_delays = [i.get("act_delay") for i in info if isinstance(i, dict) and "act_delay" in i]

        obs_delay_mean = float(torch.tensor(obs_delays).float().mean().item()) if obs_delays else float("nan")
        act_delay_mean = float(torch.tensor(act_delays).float().mean().item()) if act_delays else float("nan")

        return dict(
            # Losses
            loss_total=loss_total.detach(),
            loss_critic=loss_critic.detach(),
            loss_actor=loss_actor.detach(),

            # Memory size
            memory_size=len(self.memory),

            # Rewards
            reward_mean=reward_mean,
            reward_std=reward_std,
            reward_min=reward_min,
            reward_max=reward_max,
            reward_corr=rew_corr,

            # Value targets
            value_target_mean=value_target.mean().item(),
            value_target_std=value_target.std().item(),

            # Q-value stats
            q_value_mean=q_value_mean,
            q_value_std=q_value_std,

            # TD Error stats
            td_error_mean=td_error_mean,
            td_error_std=td_error_std,

            # Learning rate
            learning_rate=current_lr,

            # Gradients
            gradient_norm_actor=clip_actor.item(),
            gradient_norm_critic=clip_critic.item() if isinstance(self.model.critics, torch.nn.Module) else 0.0,

            # Parameter norms
            actor_param_norm_before=actor_param_norm_before,
            actor_param_norm_after=actor_param_norm_after,
            critic_param_norm_before=critic_param_norm_before,
            critic_param_norm_after=critic_param_norm_after,

            # Gradient variance
            actor_grad_var=actor_grad_var,
            critic_grad_var=critic_grad_var,

            # Critic agreement ratio
            critic_agreement_ratio=critic_agreement_ratio,

            # Entropy / Log probs
            entropy_log_probs_mean=torch.stack(self.traj_new_actions_log_prob_detach).mean().item(),

            # Entropy change over trajectory
            entropy_traj_start=entropy_start,
            entropy_traj_end=entropy_end,
            entropy_traj_delta=entropy_delta,
            entropy_traj_mean=entropy_traj_mean,
            entropy_traj_std=entropy_traj_std,

            # Actor output stats
            actor_output_mean=torch.stack(self.traj_new_actions_detach).mean().item(),
            actor_output_std=torch.stack(self.traj_new_actions_detach).std().item(),
            actor_entropy_first_mean=actor_entropy_first_mean,
            actor_entropy_first_std=actor_entropy_first_std,

            # Loss change metric
            loss_total_delta=loss_total_delta,

            # Critic disagreement stats
            critic_disagreement_mean=critic_variance_per_sample_mean,
            critic_disagreement_std=critic_variance_per_sample_std,
            critic_disagreement_max=critic_variance_per_sample_max,
            critic_disagreement_min=critic_variance_per_sample_min,
            critic_disagreement_median=critic_variance_per_sample_median,
            critic_disagreement_q25=critic_variance_per_sample_q25,
            critic_disagreement_q75=critic_variance_per_sample_q75,
            critic_var_top5_mean=critic_var_top5_mean,
            critic_disagreement_vector=critic_disagreement_vector,

            # Value estimate stats
            model_val_mean=model_mod_val.mean().item(),
            target_val_mean=target_mod_val.mean().item(),
            critic_value_drift=drift,

            # Action trajectory smoothness
            avg_action_change=avg_action_change,
            # Action change vector
            action_change_vector=action_diffs,

            # Delay info (if available)
            obs_delay_mean=obs_delay_mean,
            act_delay_mean=act_delay_mean,

            # N-step info
            nstep_len_mean=nstep_len.float().mean().item(),
            nstep_len_std=nstep_len.float().std().item(),

            # RTAC flag for comparison
            is_rtac=self.rtac,

            iteration_time = time.time() - start_time,
        )
    


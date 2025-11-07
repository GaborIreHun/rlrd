import gym
from dm_control import suite
import numpy as np

class DMCEnv(gym.Env):
    def __init__(self, domain_name, task_name, seed=0):
        self.env = suite.load(domain_name=domain_name, task_name=task_name, task_kwargs={'random': seed})
        self.action_space = gym.spaces.Box(
            low=self.env.action_spec().minimum,
            high=self.env.action_spec().maximum,
            dtype=np.float32,
        )
        obs_spec = self.env.observation_spec()
        self.ob_keys = list(obs_spec.keys())
        # Fix: properly calculate observation dimension from spec shapes
        ob_dim = sum(int(np.prod(v.shape)) for v in obs_spec.values())
        self.observation_space = gym.spaces.Box(-np.inf, np.inf, shape=(ob_dim,), dtype=np.float32)

    def _flatten_obs(self, obs_dict):
        return np.concatenate([v.ravel() for v in obs_dict.values()])

    def reset(self):
        ts = self.env.reset()
        return self._flatten_obs(ts.observation)

    def step(self, action):
        ts = self.env.step(action)
        obs = self._flatten_obs(ts.observation)
        reward = ts.reward if ts.reward is not None else 0.0
        done = ts.last()
        return obs, reward, done, {}

    def render(self, mode="human"):
        return self.env.physics.render(camera_id=0, height=240, width=320)

    def seed(self, seed=None):
        # Optionally set random seed
        pass

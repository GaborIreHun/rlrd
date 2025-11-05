import atexit
import os
from dataclasses import dataclass, InitVar
import gym
from gym.wrappers import TimeLimit

from rlrd.wrappers import Float64ToFloat32, TimeLimitResetWrapper, NormalizeActionWrapper, RealTimeWrapper, TupleObservationWrapper, AffineObservationWrapper, AffineRewardWrapper, PreviousActionWrapper, FrameSkip, get_wrapper_by_class
from rlrd.wrappers_rd import RandomDelayWrapper, WifiDelayWrapper1, WifiDelayWrapper2
import numpy as np
import pickle
from rlrd.batch_env import get_env_state
# from .gym_env import GymEnv
from rlrd.simulator_env import RobotSimEnv
from rlrd import wrappers as base_wrappers


def mujoco_py_issue_424_workaround():
    """Mujoco_py generates files in site-packages for some reason.
    It causes trouble with docker and during runtime.
    https://github.com/openai/mujoco-py/issues/424
    """
    import os
    from os.path import dirname, join
    from shutil import rmtree
    import pkgutil
    path = join(dirname(pkgutil.get_loader("mujoco_py").path), "generated")
    [os.remove(join(path, name)) for name in os.listdir(path) if name.endswith("lock")]


class Env(gym.Wrapper):
    """Environment class wrapping gym.Env that automatically resets and stores the last transition"""

    def __init__(self, env, store_env=False):
        super().__init__(env)
        self.transition = (self.reset(), 0., True, {})
        self.store_env = store_env

    def reset(self):
        return self.observation(self.env.reset())

    def step(self, action):
        next_state, reward, done, info = self.env.step(action)
        next_state = self.reset() if done else self.observation(next_state)
        self.transition = next_state, reward, done, info

        if self.store_env:
            info['env_state'] = pickle.dumps(get_env_state(self))

        return self.transition

    def observation(self, observation):
        return observation


class GymEnv(Env):
    def __init__(self, seed_val=0, id: str = "Pendulum-v0", real_time: bool = False, frame_skip: int = 0, obs_scale: float = 0., store_env: bool = False):
        env = gym.make(id)

        if obs_scale:
            env = AffineObservationWrapper(env, 0, obs_scale)

        if frame_skip:
            original_frame_skip = getattr(env.unwrapped, 'frame_skip', 1)  # on many Mujoco environments this is 5
            # print("Original frame skip", original_frame_skip)

            # I think the two lines below were actually a mistake after all (at least for HalfCheetah)
            # if hasattr(env, 'dt'):
            #   env.dt = env.dt  # in case this is an attribute we fix it to its orignal value to not distort rewards (see
            #   halfcheetah.py)
            env.unwrapped.frame_skip = 1
            tl = get_wrapper_by_class(env, TimeLimit)
            tl._max_episode_steps = int(tl._max_episode_steps * original_frame_skip)
            # print("New max episode steps", env._max_episode_steps)
            env = FrameSkip(env, frame_skip, 1 / original_frame_skip)

        env = Float64ToFloat32(env)
        # env = TimeLimitResetWrapper(env)  # obsolete
        assert isinstance(env.action_space, gym.spaces.Box)
        env = NormalizeActionWrapper(env)
        if real_time:
            env = RealTimeWrapper(env)
        else:
            env = TupleObservationWrapper(env)

        super().__init__(env, store_env=store_env)

        # self.seed(seed_val)


class RandomDelayEnv(Env):
    def __init__(self,
                 seed_val=0, id: str = "Pendulum-v0",
                 frame_skip: int = 0,
                 min_observation_delay: int = 0,
                 sup_observation_delay: int = 8,
                 min_action_delay: int = 0,  # this is equivalent to a MIN of 1 in the paper
                 sup_action_delay: int = 2,  # this is equivalent to a MAX of 2 in the paper
                 real_world_sampler: int = 0):  # 0 for uniform, 1 or 2 for simple wifi sampler
        env = gym.make(id)

        if frame_skip:
            original_frame_skip = getattr(env.unwrapped, 'frame_skip', 1)  # on many Mujoco environments this is 5
            # print("Original frame skip", original_frame_skip)

            # I think the two lines below were actually a mistake after all (at least for HalfCheetah)
            # if hasattr(env, 'dt'):
            #   env.dt = env.dt  # in case this is an attribute we fix it to its orignal value to not distort rewards (see
            #   halfcheetah.py)
            env.unwrapped.frame_skip = 1
            tl = get_wrapper_by_class(env, TimeLimit)
            tl._max_episode_steps = int(tl._max_episode_steps * original_frame_skip)
            # print("New max episode steps", env._max_episode_steps)
            env = FrameSkip(env, frame_skip, 1 / original_frame_skip)

        env = Float64ToFloat32(env)
        assert isinstance(env.action_space, gym.spaces.Box)
        env = NormalizeActionWrapper(env)

        if real_world_sampler == 0:
            env = RandomDelayWrapper(env, range(min_observation_delay, sup_observation_delay), range(min_action_delay, sup_action_delay))
        elif real_world_sampler == 1:
            env = WifiDelayWrapper1(env)
        elif real_world_sampler == 2:
            env = WifiDelayWrapper2(env)
        else:
            assert False, f"invalid value for real_world_sampler:{real_world_sampler}"
        super().__init__(env)


class RobotSimDelayEnv(Env):
    def __init__(self,
                 seed_val: int = 0,
                 log_dir: str = "/tmp",
                 min_observation_delay: int = 0,
                 sup_observation_delay: int = 0,
                 min_action_delay: int = 0,
                 sup_action_delay: int = 0,
                 instant_rewards: bool = True,
                 store_env: bool = False):
        if sup_observation_delay < min_observation_delay:
            raise ValueError(f"sup_observation_delay ({sup_observation_delay}) must be >= min_observation_delay ({min_observation_delay})")
        if sup_action_delay < min_action_delay:
            raise ValueError(f"sup_action_delay ({sup_action_delay}) must be >= min_action_delay ({min_action_delay})")
        env = RobotSimEnv(
            seed_val=seed_val,
            log_dir=log_dir,
            min_obs_delay=min_observation_delay,
            max_obs_delay=sup_observation_delay,
            min_action_delay=min_action_delay,
            max_action_delay=sup_action_delay
        )
        delay_env = base_wrappers.RandomDelayWrapper(
            env,
            obs_delay_range=range(min_observation_delay, sup_observation_delay + 1),
            act_delay_range=range(min_action_delay, sup_action_delay + 1),
            instant_rewards=instant_rewards
        )
        super().__init__(delay_env, store_env=store_env)


def test_random_delay_env():
    env = RandomDelayEnv()
    obs = env.reset()
    [env.step(env.action_space.sample()) for _ in range(1000)]
    obs, _, _, _ = env.step(env.action_space.sample())
    print('done')


if __name__ == '__main__':
    test_random_delay_env()

# List of standard Gym / MuJoCo envs
GYM_ENVS = [
    "Pendulum-v0",
    "HalfCheetah-v2",
    "Ant-v2",
    "Hopper-v2",
    "Walker2d-v2",
    "Humanoid-v2"
]

# ENV_REGISTRY creation
ENV_REGISTRY = {
    env_id: GymEnv for env_id in GYM_ENVS
}

for env_id in GYM_ENVS:
    ENV_REGISTRY[f"RandomDelay-{env_id}"] = RandomDelayEnv

# Custom simulation environments
ENV_REGISTRY.update({
    "SimEnv": RobotSimDelayEnv,
    "RandomDelayPendulum-v0": RandomDelayEnv
    # "WebotsEnv": WebotsSimEnv,     # (if implemented)
    # "CoppeliaEnv": CoppeliaSimEnv, # (if implemented)
    # "PyBulletEnv": PyBulletEnv,    # (if implemented)
    # "UnityEnv": UnityEnv,          # (if implemented)
})

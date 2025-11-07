import atexit
import os
from dataclasses import dataclass, InitVar
import gym
from gym.wrappers import TimeLimit
from gym.envs.registration import register
from rlrd.dmc_wrapper import DMCEnv

from rlrd.wrappers import Float64ToFloat32, TimeLimitResetWrapper, NormalizeActionWrapper, RealTimeWrapper, TupleObservationWrapper, AffineObservationWrapper, AffineRewardWrapper, PreviousActionWrapper, FrameSkip, get_wrapper_by_class
from rlrd.wrappers_rd import RandomDelayWrapper, WifiDelayWrapper1, WifiDelayWrapper2
import numpy as np
import pickle
from rlrd.batch_env import get_env_state
# from .gym_env import GymEnv
# Conditionally import ROS-dependent modules
try:
    from rlrd.simulator_env import RobotSimEnv
    ROS_AVAILABLE = True
except ImportError:
    RobotSimEnv = None
    ROS_AVAILABLE = False

from rlrd import wrappers as base_wrappers
import gym_maze

# Register SimEnv with gym (only if ROS is available)
if ROS_AVAILABLE:
    try:
        register(
            id='SimEnv-v0',
            entry_point='rlrd.simulator_env:RobotSimEnv',
            max_episode_steps=500,
        )
    except gym.error.Error:
        # Already registered, skip
        pass


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


# Only define RobotSimDelayEnv if ROS is available
if ROS_AVAILABLE:
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
else:
    # Provide a dummy placeholder when ROS is not available
    RobotSimDelayEnv = None


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

def make_maze_env(seed_val=0, **kwargs):
    return gym.make("maze-v0")

def make_dmcontrol_env(seed_val=0, **kwargs):
    # Use point_mass with 'easy' task instead of non-existent 'maze'
    return DMCEnv(domain_name="point_mass", task_name="easy", seed=seed_val)

def make_maze_delay_env(seed_val=0, min_observation_delay=0, sup_observation_delay=2, 
                        min_action_delay=0, sup_action_delay=3, **kwargs):
    """Gym Maze environment with configurable delays - use RandomDelayEnv properly"""
    # RandomDelayEnv expects 'id' parameter, not a pre-made environment
    # We need to register maze-v0 so it can be created via gym.make()
    # Since maze-v0 is already registered by gym_maze, we can use RandomDelayEnv directly
    from rlrd.wrappers_rd import RandomDelayWrapper
    base_env = gym.make("maze-v0")
    base_env = Float64ToFloat32(base_env)
    delayed_env = RandomDelayWrapper(
        base_env,
        obs_delay_range=range(min_observation_delay, sup_observation_delay),
        act_delay_range=range(min_action_delay, sup_action_delay)
    )
    # Wrap in Env to get transition attribute
    return Env(delayed_env, store_env=False)


def make_dmcontrol_delay_env(seed_val=0, min_observation_delay=0, sup_observation_delay=2, 
                              min_action_delay=0, sup_action_delay=3, **kwargs):
    """Point mass environment with configurable delays"""
    from rlrd.wrappers_rd import RandomDelayWrapper
    base_env = DMCEnv(domain_name="point_mass", task_name="easy", seed=seed_val)
    base_env = Float64ToFloat32(base_env)
    delayed_env = RandomDelayWrapper(
        base_env,
        obs_delay_range=range(min_observation_delay, sup_observation_delay),
        act_delay_range=range(min_action_delay, sup_action_delay)
    )
    # Wrap in Env to get transition attribute
    return Env(delayed_env, store_env=False)

# Custom simulation environments
ENV_REGISTRY.update({
    "RandomDelayPendulum-v0": RandomDelayEnv,
    "MazeEnv": make_maze_env,
    "MazeEnv-delay": make_maze_delay_env,
    "PointMaze": make_dmcontrol_env,
    "dmcontrol-pointmaze": make_dmcontrol_env,
    "dmcontrol-pointmaze-delay": make_dmcontrol_delay_env,
    # "WebotsEnv": WebotsSimEnv,     # (if implemented)
    # "CoppeliaEnv": CoppeliaSimEnv, # (if implemented)
    # "PyBulletEnv": PyBulletEnv,    # (if implemented)
    # "UnityEnv": UnityEnv,          # (if implemented)
})

# Add ROS-dependent environments only if ROS is available
if ROS_AVAILABLE:
    ENV_REGISTRY["SimEnv"] = RobotSimDelayEnv


# ENV_REGISTRY["dmcontrol-cartpole"] = lambda seed_val=0, **kwargs: DMCEnv("cartpole", "swingup", seed=seed_val)

# ------------- Gym Maze Integration -----------
try:
    ENV_REGISTRY["gym-maze"] = lambda seed_val=0, **kwargs: gym.make("maze-v0")
except ImportError:
    pass  # It's optional

def test_dmcontrol_pointmaze():
    env = ENV_REGISTRY['dmcontrol-pointmaze']()
    obs = env.reset()
    for _ in range(10):
        obs, reward, done, _ = env.step(env.action_space.sample())
        print(obs.shape, reward, done)

if __name__ == '__main__':
    test_dmcontrol_pointmaze()


# MIT License
#
# Copyright (C) 2021. Huawei Technologies Co., Ltd. All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NON-INFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
import gc
import logging

import gymnasium as gym
import numpy as np
import pytest
from pympler import muppy, summary, tracker

from smarts.core.agent import Agent
from smarts.core.agent_interface import AgentInterface, AgentType
from smarts.zoo.agent_spec import AgentSpec

SMARTS_MEMORY_GROWTH_LIMIT = 2e5
EPISODE_MEMORY_GROWTH_LIMIT = 8e5
TIMESTEP_SEC = 0.1
# Disable logging because it causes memory growth
logging.disable(logging.WARNING)


@pytest.fixture
def agent_id():
    return "Agent-006"


@pytest.fixture
def primative_scenarios():
    return ["scenarios/sumo/intersections/2lane"]


@pytest.fixture
def social_agent_scenarios():
    return [
        "scenarios/sumo/intersections/4lane",
        # "scenarios/sumo/intersections/6lane",
    ]


@pytest.fixture
def seed():
    return 42


@pytest.fixture(
    params=[
        # ( episodes, action, agent_type )
        (100, (), AgentType.Buddha),
        (100, np.array((1, 1, -1), dtype=np.float32), AgentType.Full),
        # (10, (30, 1, -1), AgentType.Standard),  # standard is just full but less
        (100, 2, AgentType.Laner),
        # (100, (30, 1, -1), AgentType.Loner),
        # (100, (30, 1, -1), AgentType.Tagger),
        # (100, (30, 1, -1), AgentType.StandardWithAbsoluteSteering),
        # (100, (50, 0), AgentType.LanerWithSpeed),
        (
            100,
            (
                np.array(
                    [
                        1,
                        2,
                    ]
                    * 10
                ),
                np.array([1, 2] * 10),
                np.array([0.5, 1] * 10),
                np.array([20, 20] * 10),
            ),
            AgentType.Tracker,
        ),
        # ( 5, ([0,1,2], [0,1,2], [0,1,2]), AgentType.MPCTracker),
    ]
)
def agent_params(request):
    return request.param


@pytest.fixture
def agent_type():
    return (np.array((1, 1, -1), dtype=np.float32), AgentType.Full)


def env_and_spec(
    action, agent_type, max_episode_steps, scenarios, seed=42, agent_id="Agent-006"
):
    class Policy(Agent):
        def act(self, obs):
            return action

    agent_spec = AgentSpec(
        interface=AgentInterface.from_type(
            agent_type, max_episode_steps=max_episode_steps
        ),
        agent_builder=Policy,
    )
    env = gym.make(
        "smarts.env:hiway-v1",
        scenarios=scenarios,
        agent_interfaces={agent_id: agent_spec.interface},
        headless=True,
        fixed_timestep_sec=TIMESTEP_SEC,
        seed=seed,
    )

    return (env, agent_spec)


def _env_memory_buildup(
    agent_id, seed, scenarios, action, agent_type, max_episode_steps=10
):
    env, _ = env_and_spec(
        action, agent_type, max_episode_steps, scenarios, seed, agent_id
    )
    env.close()
    gc.collect()


def _every_nth_episode(agent_id, episode_count, env_and_spec, episodes_per_yield):
    env, agent_spec = env_and_spec

    for episode_index in range(episode_count):
        agent = agent_spec.build_agent()
        observations, _ = env.reset()

        terminateds = {"__all__": False}
        while not terminateds["__all__"]:
            agent_obs = observations[agent_id]
            agent_action = agent.act(agent_obs)
            observations, rewards, terminateds, truncateds, infos = env.step(
                {agent_id: agent_action}
            )
        agent_obs = None
        agent_action = None
        observations, rewards, terminateds, truncateds, infos = (
            None,
            None,
            None,
            None,
            None,
        )
        if episode_index % episodes_per_yield == 0:
            yield episode_index


def _memory_buildup(
    agent_id, seed, scenarios, episode_count, action, agent_type, max_episode_steps=10
):
    env, agent_spec = env_and_spec(
        action, agent_type, max_episode_steps, scenarios, seed, agent_id
    )

    for _ in range(episode_count):
        agent = agent_spec.build_agent()
        observations, _ = env.reset()

        terminateds = {"__all__": False}
        while not terminateds["__all__"]:
            agent_obs = observations[agent_id]
            agent_action = agent.act(agent_obs)
            observations, _, terminateds, truncateds, _ = env.step(
                {agent_id: agent_action}
            )

    env.close()


def test_env_memory_cleanup(agent_id, seed, primative_scenarios):
    # Run once to initialize globals
    _, action, agent_type = (100, None, AgentType.Buddha)
    _env_memory_buildup(agent_id, seed, primative_scenarios, action, agent_type)
    gc.collect()

    # Memory size check
    size = muppy.get_size(muppy.get_objects())
    gc.collect()
    _env_memory_buildup(agent_id, seed, primative_scenarios, action, agent_type)
    end_size = muppy.get_size(muppy.get_objects())
    gc.collect()

    def success_condition():
        return end_size - size < EPISODE_MEMORY_GROWTH_LIMIT

    if not success_condition():
        # Get a diff for failure case
        tr = tracker.SummaryTracker()
        tr.print_diff()
        _env_memory_buildup(agent_id, seed, primative_scenarios, action, agent_type)
        diff = tr.diff()
        summary.print_(diff)
        diff = None
        gc.collect()
        assert success_condition(), f"Size diff {end_size - size}"


def test_smarts_episode_memory_cleanup(
    agent_id, seed, primative_scenarios, agent_params
):
    MAX_EPISODE_STEPS = 100
    EPISODE_COUNT = 100
    EPISODES_PER_CHECK = 10

    _, action, agent_type = agent_params

    env_and_agent_spec = env_and_spec(
        action, agent_type, MAX_EPISODE_STEPS, primative_scenarios, seed, agent_id
    )

    size = 0
    last_size = 0
    gc.collect()
    from pympler import refbrowser

    tr = tracker.SummaryTracker()
    try:
        for current_episode in _every_nth_episode(
            agent_id,
            EPISODE_COUNT,
            env_and_agent_spec,
            episodes_per_yield=EPISODES_PER_CHECK,
        ):
            gc.collect()
            all_objects = muppy.get_objects()
            size = muppy.get_size(all_objects)
            tr.print_diff(summary.summarize(all_objects))
            print(flush=True)
            all_objects = None
            assert (
                size - last_size < EPISODE_MEMORY_GROWTH_LIMIT
            ), f"End size delta `{size - last_size=}` at `{current_episode=}`"
            last_size = size
    finally:
        env_and_agent_spec[0].close()


def test_smarts_basic_memory_cleanup(agent_id, seed, primative_scenarios, agent_params):
    # Run once to initialize globals and test to see if smarts is working
    _memory_buildup(
        agent_id, seed, primative_scenarios, 100, agent_params[1], agent_params[2]
    )

    gc.collect()
    initial_size = muppy.get_size(muppy.get_objects())

    _memory_buildup(agent_id, seed, primative_scenarios, *agent_params)
    end_size = muppy.get_size(muppy.get_objects())
    # Check for a major leak
    assert (
        end_size - initial_size < SMARTS_MEMORY_GROWTH_LIMIT
    ), f"End size delta {end_size - initial_size}"


def test_smarts_repeated_runs_memory_cleanup(
    agent_id, seed, primative_scenarios, agent_type
):
    # Run once to initialize globals and test to see if smarts is working
    _memory_buildup(agent_id, seed, primative_scenarios, 1, *agent_type)

    gc.collect()
    initial_size = muppy.get_size(muppy.get_objects())

    for i in range(100):
        _memory_buildup(agent_id, seed, primative_scenarios, 1, *agent_type)

    gc.collect()
    end_size = muppy.get_size(muppy.get_objects())

    # This "should" be roughly the same as `test_smarts_basic_memory_cleanup`
    assert (
        end_size - initial_size < SMARTS_MEMORY_GROWTH_LIMIT
    ), f"End size delta {end_size - initial_size}"


def test_smarts_fast_reset_memory_cleanup(agent_id, seed, social_agent_scenarios):
    agent_type = AgentType.Buddha
    # Run once to initialize globals and test to see if smarts is working
    _memory_buildup(agent_id, seed, social_agent_scenarios, 1, None, agent_type)

    tr = tracker.SummaryTracker()
    gc.collect()
    initial_size = muppy.get_size(muppy.get_objects())

    for _ in range(100):
        _memory_buildup(
            agent_id,
            seed,
            social_agent_scenarios,
            1,
            (),
            agent_type,
            max_episode_steps=2,
        )

    gc.collect()
    end_size = muppy.get_size(muppy.get_objects())
    gc.collect()
    tr.print_diff()

    # Check for a major leak
    assert (
        end_size - initial_size < SMARTS_MEMORY_GROWTH_LIMIT
    ), f"End size delta {end_size - initial_size}"


def test_smarts_social_agent_scenario_memory_cleanup(
    agent_id, seed, social_agent_scenarios, agent_type
):
    # Run once to initialize globals and test to see if smarts is working
    _memory_buildup(
        agent_id, seed, social_agent_scenarios, 1, agent_type[0], agent_type[1]
    )

    gc.collect()
    initial_size = muppy.get_size(muppy.get_objects())

    _memory_buildup(agent_id, seed, social_agent_scenarios, 100, *agent_type)

    gc.collect()
    end_size = muppy.get_size(muppy.get_objects())

    assert (
        end_size - initial_size < SMARTS_MEMORY_GROWTH_LIMIT
    ), f"End size delta {end_size - initial_size}"

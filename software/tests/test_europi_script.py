# Copyright 2024 Allen Synthesis
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import pytest
import re
from firmware import configuration as config
from europi_script import EuroPiScript
from configuration import ConfigFile
from collections import namedtuple
from struct import pack, unpack


class ScriptForTesting(EuroPiScript):
    pass


class ScriptForTestingWithConfig(EuroPiScript):
    @classmethod
    def config_points(cls):
        return [
            config.choice(name="a", choices=[5, 6], default=5),
            config.choice(name="b", choices=[7, 8], default=7),
        ]


@pytest.fixture
def script_for_testing():
    s = ScriptForTesting()
    yield s
    s.remove_state()


@pytest.fixture
def script_for_testing_with_config():
    s = ScriptForTestingWithConfig()
    yield s
    s.remove_state()
    ConfigFile.delete_config(s.__class__)


def test_save_state(script_for_testing):
    script_for_testing.save_state_json({"spam": "eggs"})
    assert script_for_testing.load_state_json() == {"spam": "eggs"}


def test_state_file_name(script_for_testing):
    assert script_for_testing._state_filename == "saved_state_ScriptForTesting.txt"


def test_save_load_state_json(script_for_testing):
    state = {"one": 1, "two": ["a", "bb"], "three": True}
    script_for_testing.save_state_json(state)
    with open(script_for_testing._state_filename, "r") as f:
        assert re.match(
            r'\{\s*"one"\s*:\s*1\s*,\s*"two"\s*:\s*\[\s*"a"\s*,\s*"bb"\s*\]\s*,\s*"three"\s*:\s*true\s*\}',
            f.read(),
        )
    assert script_for_testing.load_state_json() == state


def test_save_load_state_bytes(script_for_testing):
    State = namedtuple("State", "one two three")
    format_string = "b2s?"  # https://docs.python.org/3/library/struct.html#format-characters
    state = pack(format_string, 1, bytes([8, 16]), True)
    script_for_testing.save_state_bytes(state)
    with open(script_for_testing._state_filename, "rb") as f:
        assert f.read() == b"\x01\x08\x10\x01"
    got_bytes = script_for_testing.load_state_bytes()
    assert got_bytes == state
    got_struct = State(*unpack(format_string, got_bytes))
    assert got_struct.one == 1
    assert list(got_struct.two) == [8, 16]
    assert got_struct.three == True


def test_load_config_no_config(script_for_testing):
    assert EuroPiScript._load_config_for_class(script_for_testing.__class__) == {}


def test_load_config_defaults(script_for_testing_with_config):
    assert EuroPiScript._load_config_for_class(script_for_testing_with_config.__class__) == {
        "a": 5,
        "b": 7,
    }


def test_load_europi_config(script_for_testing_with_config):
    assert script_for_testing_with_config.europi_config.PICO_MODEL == "pico"

# -*- coding: utf-8 -*-
#
# Tests for lmchat.py - Terminal LLM Chat Client
# Copyright (c) 2026 Marcus Firmus. Licensed under the MIT License.
#
import pytest
from pathlib import Path
from lmchat import load_yaml, save_yaml

def test_save_and_load_yaml(tmp_path):
    """
    Tests whether saving and loading a YAML file works correctly.
    We use the 'tmp_path' fixture, which provides a temporary directory.
    """
    # 1. Arrange data (Arrange)
    test_file = tmp_path / "test_state.yaml"
    test_data = {
        "default_model": "ollama/gemma2b",
        "some_list": ["apple", "banana"],
        "nested": {"key": "value"}
    }

    # 2. Perform action (Act)
    save_yaml(test_file, test_data)
    loaded_data = load_yaml(test_file)

    # 3. Verify assertions (Assert)
    # Verify that what we read back is identical to what we saved
    assert loaded_data == test_data
    assert loaded_data["default_model"] == "ollama/gemma2b"
    assert loaded_data["nested"]["key"] == "value"


def test_load_non_existent_yaml(tmp_path):
    """
    Tests whether attempting to read a non‑existent file returns an empty dictionary.
    """
    non_existent_file = tmp_path / "does_not_exist.yaml"

    result = load_yaml(non_existent_file)

    assert result == {}

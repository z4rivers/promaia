"""
Tests for the configuration management module.
"""
import os
import json
import pytest
from unittest.mock import patch, mock_open

from promaia.utils.config import get_config, update_config, \
    get_sync_days_setting, set_sync_days_setting, get_chat_days_setting, set_chat_days_setting

@pytest.fixture
def temp_config_file(tmp_path):
    """Create a temporary config file for testing."""
    config_path = tmp_path / "test_config.json"
    test_config = {
        "last_sync": "2023-01-01T00:00:00+00:00",
        "last_days": 7,
        "chat_context_days": 10
    }
    with open(config_path, 'w') as f:
        json.dump(test_config, f)
    return str(config_path)

def test_get_config_returns_default_when_no_file():
    """Test that get_config returns default values when config file doesn't exist."""
    with patch('os.path.exists', return_value=False):
        config = get_config()
        assert config["last_sync"] is None
        assert config["last_days"] == 5

def test_update_config_creates_file_if_not_exists():
    """Test that update_config creates config file if it doesn't exist."""
    mock_file = mock_open()
    with patch('os.path.exists', return_value=False), \
         patch('builtins.open', mock_file), \
         patch('json.dump') as mock_json_dump:
        update_config({"last_days": 10})
        mock_json_dump.assert_called_once()
        args, _ = mock_json_dump.call_args
        assert args[0]["last_days"] == 10

def test_get_sync_days_setting_returns_default():
    """Test that get_sync_days_setting returns the default value when not set."""
    with patch('promaia.utils.config.get_config', return_value={}):
        days = get_sync_days_setting()
        assert days == 5

def test_get_sync_days_setting_returns_value():
    """Test that get_sync_days_setting returns the configured value."""
    with patch('promaia.utils.config.get_config', return_value={"last_days": 10}):
        days = get_sync_days_setting()
        assert days == 10

def test_set_sync_days_setting_enforces_minimum():
    """Test that set_sync_days_setting enforces a minimum value of 1."""
    with patch('promaia.utils.config.update_config') as mock_update:
        days = set_sync_days_setting(0)
        assert days == 1
        mock_update.assert_called_with({"last_days": 1})

def test_set_sync_days_setting_updates_config():
    """Test that set_sync_days_setting updates the config."""
    with patch('promaia.utils.config.update_config') as mock_update:
        days = set_sync_days_setting(10)
        assert days == 10
        mock_update.assert_called_with({"last_days": 10})

def test_get_chat_days_setting_returns_default():
    """Test that get_chat_days_setting returns the default value when not set."""
    with patch('promaia.utils.config.get_config', return_value={}):
        days = get_chat_days_setting()
        assert days == 5

def test_get_chat_days_setting_returns_value():
    """Test that get_chat_days_setting returns the configured value."""
    with patch('promaia.utils.config.get_config', return_value={"chat_context_days": 15}):
        days = get_chat_days_setting()
        assert days == 15

def test_set_chat_days_setting_enforces_minimum():
    """Test that set_chat_days_setting enforces a minimum value of 1."""
    with patch('promaia.utils.config.update_config') as mock_update:
        days = set_chat_days_setting(0)
        assert days == 1
        mock_update.assert_called_with({"chat_context_days": 1})

def test_set_chat_days_setting_updates_config():
    """Test that set_chat_days_setting updates the config."""
    with patch('promaia.utils.config.update_config') as mock_update:
        days = set_chat_days_setting(20)
        assert days == 20
        mock_update.assert_called_with({"chat_context_days": 20}) 
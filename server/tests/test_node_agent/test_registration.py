import pytest
from unittest.mock import patch, mock_open
from node_agent.registration import is_registered

def test_is_registered_false():
    with patch("os.path.exists", return_value=False):
        assert not is_registered()

def test_is_registered_true():
    m = mock_open(read_data='{"node_id": "1", "api_key": "2"}')
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", m):
            assert is_registered()

import pytest
from server.node_agent.runtime.ollama import OllamaRuntime
from unittest.mock import patch, MagicMock

def test_ollama_runtime_init():
    with patch("docker.from_env") as mock_env:
        runtime = OllamaRuntime()
        assert runtime is not None

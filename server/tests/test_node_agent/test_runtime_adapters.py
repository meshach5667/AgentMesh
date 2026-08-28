from unittest.mock import patch

from node_agent.runtime.ollama import OllamaRuntime


def test_ollama_runtime_init():
    with patch("docker.from_env"):
        runtime = OllamaRuntime()
        assert runtime is not None

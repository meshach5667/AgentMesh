"""Runtime adapter unit tests. The Docker backend uses a fake Docker client here; it has not yet been run
against a real Docker daemon (see docs/IMPLEMENTATION_PLAN.md)."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from node_agent.runtime.base import WorkloadError, WorkloadHandle, WorkloadSpec
from node_agent.runtime.ollama_docker import LABEL, OllamaDockerRuntime
from node_agent.runtime.ollama_process import OllamaProcessRuntime
from node_agent.worker import parse_deploy_payload

DEP = "11111111-2222-3333-4444-555555555555"
SPEC = WorkloadSpec(DEP, "qwen2.5:0.5b", 2048, 2, 1024, 768, 0, False)


class FakeContainer:
    def __init__(self, labels, status="running"):
        self.id = "c123"
        self.labels = labels
        self.status = status
        self.attrs = {"NetworkSettings": {"Ports": {"11434/tcp": [{"HostIp": "127.0.0.1", "HostPort": "49999"}]}}}
        self.removed = False

    def reload(self):
        pass

    def stop(self, timeout=10):
        self.status = "exited"

    def remove(self, force=False):
        self.removed = True


class FakeDocker:
    def __init__(self, existing=None):
        import docker

        self.errors = docker.errors
        self.run_kwargs = None
        self.existing = existing or {}
        outer = self

        class Containers:
            def run(self, image, **kwargs):
                outer.run_kwargs = {"image": image, **kwargs}
                c = FakeContainer(kwargs["labels"])
                outer.existing[kwargs["name"]] = c
                outer.existing[c.id] = c
                return c

            def get(self, ref):
                if ref in outer.existing:
                    return outer.existing[ref]
                raise docker.errors.NotFound("nope")

        class Images:
            def get(self, ref):
                return object()

        self.containers = Containers()
        self.images = Images()

    def ping(self):
        return True


async def test_docker_runtime_applies_isolation_and_limits(monkeypatch):
    fake = FakeDocker()
    rt = OllamaDockerRuntime("ollama/ollama:test", client=fake)

    async def ok(*a, **k):
        return "0.0.0"

    monkeypatch.setattr("node_agent.runtime.ollama_api.wait_api", ok)
    handle = await rt.start(SPEC)

    kw = fake.run_kwargs
    assert kw["mem_limit"] == "1024m" and kw["memswap_limit"] == "1024m"
    assert kw["nano_cpus"] == 2_000_000_000
    assert kw["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in kw["security_opt"]
    assert kw["read_only"] is True
    assert kw["ports"] == {"11434/tcp": ("127.0.0.1", None)}  # loopback only
    assert "privileged" not in kw and "network_mode" not in kw
    assert "device_requests" not in kw  # no GPU unless requested and allowed
    # Only the AgentMesh model cache volume is mounted: no host paths, no Docker socket.
    assert list(kw["volumes"]) == ["agentmesh-models"]
    assert all("docker.sock" not in str(v) for v in kw["volumes"].values())
    assert kw["labels"][LABEL] == "true"
    assert handle.base_url == "http://127.0.0.1:49999"


async def test_docker_runtime_gpu_only_when_allowed(monkeypatch):
    async def ok(*a, **k):
        return "0"

    monkeypatch.setattr("node_agent.runtime.ollama_api.wait_api", ok)
    gpu_spec = WorkloadSpec(DEP, "qwen2.5:0.5b", 2048, 2, 1024, 768, 4096, True)
    fake = FakeDocker()
    await OllamaDockerRuntime("img", client=fake, allow_gpu=False).start(gpu_spec)
    assert "device_requests" not in fake.run_kwargs
    fake = FakeDocker()
    await OllamaDockerRuntime("img", client=fake, allow_gpu=True).start(gpu_spec)
    assert fake.run_kwargs["device_requests"]


async def test_docker_runtime_never_touches_unlabelled_containers():
    foreign = FakeContainer(labels={})
    fake = FakeDocker(existing={"provider-ollama": foreign})
    rt = OllamaDockerRuntime("img", client=fake)
    await rt.remove(WorkloadHandle(DEP, "", "docker", {"container_id": "provider-ollama"}))
    assert foreign.removed is False
    assert await rt.is_alive(WorkloadHandle(DEP, "", "docker", {"container_id": "provider-ollama"})) is False


def test_process_runtime_environment_is_isolated(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "should-not-leak")
    monkeypatch.setenv("OLLAMA_MODELS", "/home/someone/.ollama/models")
    rt = OllamaProcessRuntime(tmp_path, cgroup_limits=False)
    env = rt._env(43210, SPEC)
    assert env["OLLAMA_HOST"] == "127.0.0.1:43210"  # loopback, never 0.0.0.0 or the default 11434
    assert env["OLLAMA_MODELS"] == str(tmp_path / "models")  # never the provider's own model store
    assert "OPENAI_API_KEY" not in env
    assert env["CUDA_VISIBLE_DEVICES"] == "-1"


def _payload(**over):
    p = {
        "deployment_id": DEP,
        "runtime": "ollama",
        "model_tag": "qwen2.5:0.5b",
        "num_ctx": 2048,
        "resources": {"cpu_cores": 1, "ram_mb": 1024, "disk_mb": 768, "vram_mb": 0, "gpu": False},
    }
    p.update(over)
    return p


def test_deploy_payload_accepts_valid():
    spec = parse_deploy_payload(_payload())
    assert spec.model_tag == "qwen2.5:0.5b" and spec.ram_mb == 1024


@pytest.mark.parametrize(
    "bad",
    [
        {"model_tag": "qwen; rm -rf /"},
        {"model_tag": "https://evil.example/model"},
        {"model_tag": "../../etc/passwd"},
        {"runtime": "shell"},
        {"deployment_id": "not-a-uuid"},
        {"resources": {"cpu_cores": "x"}},
        {"num_ctx": 10},
    ],
)
def test_deploy_payload_rejects_unsafe_input(bad):
    with pytest.raises(WorkloadError):
        parse_deploy_payload(_payload(**bad))


def test_hardware_report_shape(tmp_path):
    from node_agent.hardware.discovery import default_allocation, hardware_report

    hw = hardware_report(str(tmp_path))
    assert hw["cpu_cores"] >= 1 and hw["ram_mb"] > 0
    settings = SimpleNamespace(MAX_CPU_CORES=None, MAX_RAM_MB=None, MAX_DISK_MB=None, ALLOW_GPU=False, MAX_VRAM_MB=None)
    alloc = default_allocation(hw, settings)
    # Never offers the whole machine by default.
    assert alloc["ram_mb"] <= hw["ram_mb"] // 2 + 1
    assert alloc["vram_mb"] == 0

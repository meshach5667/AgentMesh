"""Workload container isolation against a real Docker daemon (security tests 8, 9 and 10).

Runs a tiny Alpine container with exactly the limits workloads get (``workload_limits``), a read-only root filesystem,
a size-limited tmpfs and an ``internal`` network like the serving network, then tries to break out of each limit.

Skipped when no Docker daemon is reachable. The image is pulled only when AGENTMESH_ISOLATION_PULL=1 (CI sets it);
otherwise ``alpine:3.20`` must already be present locally.
"""

import os
import uuid

import pytest

from node_agent.runtime.ollama_docker import workload_limits

docker = pytest.importorskip("docker")
IMAGE = "alpine:3.20"


def _client():
    try:
        client = docker.from_env()
        client.ping()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Docker daemon not reachable: {type(exc).__name__}")
    try:
        client.images.get(IMAGE)
    except docker.errors.ImageNotFound:
        if os.environ.get("AGENTMESH_ISOLATION_PULL") != "1":
            pytest.skip(f"{IMAGE} not present locally (set AGENTMESH_ISOLATION_PULL=1 to pull it)")
        client.images.pull(IMAGE)
    return client


@pytest.fixture(scope="module")
def sandbox():
    client = _client()
    net = client.networks.create(f"agentmesh-test-{uuid.uuid4().hex[:8]}", driver="bridge", internal=True)

    def run(command: str, ram_mb: int = 64) -> tuple[int, str, dict]:
        container = client.containers.run(
            IMAGE,
            ["sh", "-c", command],
            detach=True,
            network=net.name,
            read_only=True,
            tmpfs={"/tmp": "rw,noexec,nosuid,size=16m"},
            **workload_limits(ram_mb, 0.5),
        )
        try:
            result = container.wait(timeout=60)
            container.reload()
            return result["StatusCode"], container.logs().decode(errors="replace"), container.attrs["State"]
        finally:
            container.remove(force=True)

    yield run
    net.remove()


def test_no_docker_socket_or_host_filesystem(sandbox):
    code, out, _ = sandbox("ls /var/run/docker.sock; ls /host /root/.ssh 2>&1; echo done")
    assert "No such file" in out and "docker.sock" not in out.split("No such file")[0]


def test_root_filesystem_is_read_only_and_tmpfs_is_capped(sandbox):
    code, out, _ = sandbox("touch /evil 2>&1; dd if=/dev/zero of=/tmp/big bs=1M count=32 2>&1; echo end")
    assert "Read-only file system" in out
    assert "No space left on device" in out


def test_no_capabilities_and_no_privilege_escalation(sandbox):
    code, out, _ = sandbox("grep -E 'CapEff|NoNewPrivs' /proc/self/status")
    assert "CapEff:\t0000000000000000" in out and "NoNewPrivs:\t1" in out


@pytest.mark.parametrize("target", ["169.254.169.254", "10.0.0.1", "192.168.1.1", "172.16.0.1", "1.1.1.1"])
def test_no_route_to_metadata_private_ranges_or_internet(sandbox, target):
    code, out, _ = sandbox(f"wget -q -T 3 -O- http://{target}/ 2>&1; echo exit=$?")
    assert "exit=0" not in out


def test_memory_limit_kills_the_workload(sandbox):
    code, _, state = sandbox("head -c 200m /dev/zero | tail > /dev/null", ram_mb=32)
    assert state["OOMKilled"] is True or code == 137


def test_pid_limit_stops_fork_bombs(sandbox):
    code, out, _ = sandbox("for i in $(seq 1 700); do sleep 5 & done 2>&1 | tail -1; echo spawned")
    assert "Resource temporarily unavailable" in out or "can't fork" in out

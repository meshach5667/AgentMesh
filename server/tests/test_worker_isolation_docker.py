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
    # Paths a host mount would add; none exists in a plain Alpine image (its own /home is empty and not checked).
    paths = "/var/run/docker.sock /run/docker.sock /host /root/.ssh /etc/agentmesh /var/lib/agentmesh"
    code, out, _ = sandbox(f'for p in {paths}; do [ -e "$p" ] && echo "PRESENT:$p"; done; echo checked')
    assert "checked" in out and "PRESENT:" not in out, out


def test_root_filesystem_is_read_only_and_tmpfs_is_capped(sandbox):
    code, out, _ = sandbox(
        "touch /evil 2>/dev/null; echo touch=$?; "
        "dd if=/dev/zero of=/tmp/big bs=1048576 count=32 2>/dev/null; echo dd=$?; "
        "echo size=$(wc -c < /tmp/big)"
    )
    assert "touch=0" not in out and "dd=0" not in out, out
    size = int(out.split("size=")[1].split()[0])
    assert size <= 16 * 1024 * 1024, out  # the tmpfs holds 16 MiB, never the 32 MiB written


def test_no_capabilities_and_no_privilege_escalation(sandbox):
    code, out, _ = sandbox("grep -E 'CapEff|NoNewPrivs' /proc/self/status")
    assert "CapEff:\t0000000000000000" in out and "NoNewPrivs:\t1" in out, out


@pytest.mark.parametrize("target", ["169.254.169.254", "10.0.0.1", "192.168.1.1", "172.16.0.1", "1.1.1.1"])
def test_no_route_to_metadata_private_ranges_or_internet(sandbox, target):
    code, out, _ = sandbox(f"wget -q -T 3 -O /dev/null http://{target}/ 2>/dev/null; echo exit=$?")
    assert "exit=" in out and "exit=0" not in out, out


def test_memory_limit_kills_the_workload(sandbox):
    # dd becomes PID 1 and allocates a 200 MiB buffer in a 32 MiB container: the kernel must kill it.
    code, out, state = sandbox("exec dd if=/dev/zero of=/dev/null bs=209715200 count=1", ram_mb=32)
    assert state["OOMKilled"] is True or code == 137, (code, state, out)


def test_pid_limit_stops_fork_bombs(sandbox):
    # 700 background processes against a limit of 512: forking must fail before the loop ends.
    code, out, _ = sandbox("for i in $(seq 1 700); do sleep 30 & done; echo all-forked")
    assert "all-forked" not in out or "can't fork" in out or "Resource temporarily unavailable" in out, out

"""Ollama backend for the installable agent: one dedicated ``ollama serve`` process per deployment.

Isolation from the provider's own setup: a random loopback port, a separate model directory under the
worker's data dir, and a minimal environment. The provider's existing Ollama service, port 11434, and
~/.ollama are never used. When systemd user scopes are available, each process runs in its own cgroup with
MemoryMax and CPUQuota; otherwise limits are advisory (scheduler reservations only) and that is reported.

This backend is not a security sandbox: the runtime runs as the provider's user.
"""

import asyncio
import contextlib
import os
import shutil
import signal
import socket
from pathlib import Path

import psutil

from . import ollama_api
from .base import ProgressCallback, RuntimeCapabilities, WorkloadError, WorkloadHandle, WorkloadRuntime, WorkloadSpec


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class OllamaProcessRuntime(WorkloadRuntime):
    name = "ollama"
    backend = "process"

    def __init__(self, data_dir: Path, binary: str = "ollama", cgroup_limits: bool = True):
        self.data_dir = data_dir
        self.models_dir = data_dir / "models"
        self.logs_dir = data_dir / "logs"
        self.binary = shutil.which(binary) or binary
        self.want_cgroups = cgroup_limits
        self._cgroups: bool | None = None
        self._procs: dict[str, asyncio.subprocess.Process] = {}

    async def _cgroups_available(self) -> bool:
        if self._cgroups is None:
            self._cgroups = False
            if self.want_cgroups and shutil.which("systemd-run"):
                proc = await asyncio.create_subprocess_exec(
                    "systemd-run",
                    "--user",
                    "--scope",
                    "--quiet",
                    "-p",
                    "MemoryMax=64M",
                    "true",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                self._cgroups = (await proc.wait()) == 0
        return self._cgroups

    async def capabilities(self) -> RuntimeCapabilities:
        version, available, detail = "", False, ""
        if os.path.isfile(self.binary) and os.access(self.binary, os.X_OK):
            proc = await asyncio.create_subprocess_exec(
                self.binary, "--version", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
            )
            out, _ = await proc.communicate()
            text = out.decode(errors="ignore")
            version = next((tok for tok in text.split() if tok[:1].isdigit()), "")[:50]
            available = True
        else:
            detail = "ollama binary not found"
        cg = await self._cgroups_available()
        return RuntimeCapabilities(
            name="ollama",
            version=version,
            backend="process",
            available=available,
            gpu=False,
            limits_enforced=cg,
            detail=detail or ("cgroup limits via systemd user scope" if cg else "limits advisory"),
        )

    def _env(self, port: int, spec: WorkloadSpec) -> dict[str, str]:
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.data_dir / "home"),
            "OLLAMA_HOST": f"127.0.0.1:{port}",
            "OLLAMA_MODELS": str(self.models_dir),
            "OLLAMA_KEEP_ALIVE": "-1",
            "OLLAMA_NUM_PARALLEL": "1",
            "OLLAMA_MAX_LOADED_MODELS": "1",
            "OLLAMA_NOHISTORY": "1",
        }
        # systemd-run needs these to reach the user service manager; nothing else from the provider's env leaks.
        for key in ("XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS"):
            if key in os.environ:
                env[key] = os.environ[key]
        if not spec.gpu:
            env.update({"CUDA_VISIBLE_DEVICES": "-1", "HIP_VISIBLE_DEVICES": "-1", "ROCR_VISIBLE_DEVICES": "-1"})
        return env

    async def start(self, spec: WorkloadSpec) -> WorkloadHandle:
        for d in (self.models_dir, self.logs_dir, self.data_dir / "home"):
            d.mkdir(parents=True, exist_ok=True, mode=0o700)
        port = _free_port()
        argv = [self.binary, "serve"]
        cgroup = await self._cgroups_available()
        if cgroup:
            argv = [
                "systemd-run",
                "--user",
                "--scope",
                "--quiet",
                f"--unit=agentmesh-wl-{spec.deployment_id[:8]}-{port}",
                "-p",
                f"MemoryMax={spec.ram_mb}M",
                "-p",
                "MemorySwapMax=0",
                "-p",
                f"CPUQuota={spec.cpu_cores * 100}%",
                "--",
                *argv,
            ]
        log = open(self.logs_dir / f"{spec.deployment_id}.log", "ab")  # noqa: SIM115
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                env=self._env(port, spec),
                stdout=log,
                stderr=log,
                stdin=asyncio.subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            raise WorkloadError("RUNTIME_START_FAILED", f"Could not start Ollama: {exc.strerror}") from None
        finally:
            log.close()
        self._procs[spec.deployment_id] = proc
        handle = WorkloadHandle(
            deployment_id=spec.deployment_id,
            base_url=f"http://127.0.0.1:{port}",
            backend="process",
            ref={"pid": proc.pid, "port": port, "cgroup": cgroup},
        )

        async def alive():
            return proc.returncode is None

        try:
            await ollama_api.wait_api(handle.base_url, timeout=60, is_alive=alive)
        except WorkloadError:
            await self.remove(handle)
            raise
        return handle

    async def prepare_model(self, handle: WorkloadHandle, spec: WorkloadSpec, progress: ProgressCallback) -> None:
        await ollama_api.pull(handle.base_url, spec.model_tag, progress)

    async def verify_ready(self, handle: WorkloadHandle, spec: WorkloadSpec) -> str | None:
        return await ollama_api.verify_ready(handle.base_url, spec.model_tag, spec.num_ctx)

    async def health(self, handle: WorkloadHandle, spec: WorkloadSpec) -> bool:
        return await self.is_alive(handle) and await ollama_api.health(handle.base_url, spec.model_tag)

    def _own_process(self, handle: WorkloadHandle) -> psutil.Process | None:
        """Return the process only if it is still the Ollama server we started (guards against PID reuse)."""
        pid = handle.ref.get("pid")
        if not pid:
            return None
        try:
            p = psutil.Process(pid)
            cmd = " ".join(p.cmdline())
            env_ok = f"127.0.0.1:{handle.ref.get('port')}"
            if "ollama" in cmd and "serve" in cmd:
                with contextlib.suppress(psutil.Error):
                    if p.environ().get("OLLAMA_HOST") not in (None, env_ok):
                        return None
                return p
        except psutil.Error:
            pass
        return None

    async def is_alive(self, handle: WorkloadHandle) -> bool:
        return self._own_process(handle) is not None

    async def remove(self, handle: WorkloadHandle) -> None:
        proc = self._procs.pop(handle.deployment_id, None)
        p = self._own_process(handle)
        if p is None:
            return
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(p.pid, signal.SIGTERM)
        if await self._wait_gone(p, proc, 15):
            return
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(p.pid, signal.SIGKILL)
        await self._wait_gone(p, proc, 5)

    @staticmethod
    async def _wait_gone(p: psutil.Process, proc, timeout: float) -> bool:
        # Reap through asyncio when we spawned the process in this run; otherwise poll (adopted process).
        if proc is not None:
            try:
                await asyncio.wait_for(proc.wait(), timeout)
                return True
            except TimeoutError:
                return False
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            if not p.is_running() or p.status() == psutil.STATUS_ZOMBIE:
                return True
            await asyncio.sleep(0.2)
        return False

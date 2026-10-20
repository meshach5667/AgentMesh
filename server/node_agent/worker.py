"""AgentMesh worker: shared by the Docker worker (MODE=docker) and the installable agent (MODE=agent).

Loops, all outbound:
  * heartbeat  - capabilities, allocation, workload health; receives reconciliation instructions
  * commands   - long-polls the persisted command queue (DEPLOY / STOP)
  * tunnel     - WebSocket carrying gateway inference requests to managed runtimes
  * health     - periodic local health checks of running workloads
"""

import asyncio
import contextlib
import logging
import re
from dataclasses import asdict

import psutil

from .config import PROTOCOL_VERSION, WORKER_VERSION, WorkerSettings
from .hardware.discovery import default_allocation, hardware_report
from .metrics.collector import MetricsCollector
from .protocol import ControlPlaneClient, CredentialRevoked, ProtocolError, backoff
from .runtime.base import WorkloadError, WorkloadHandle, WorkloadRuntime, WorkloadSpec
from .state import WorkerState
from .tunnel import TunnelHandler, run_tunnel

logger = logging.getLogger(__name__)

TAG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}(/[a-z0-9][a-z0-9._-]{0,63})?(:[a-zA-Z0-9][a-zA-Z0-9._-]{0,63})?$")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def make_runtime(settings: WorkerSettings) -> WorkloadRuntime:
    if settings.RUNTIME_BACKEND == "docker":
        from .runtime.ollama_docker import OllamaDockerRuntime

        return OllamaDockerRuntime(
            image=settings.OLLAMA_IMAGE,
            models_volume=settings.MODELS_VOLUME,
            network=settings.WORKLOAD_NETWORK,
            docker_host=settings.DOCKER_HOST,
            allow_gpu=settings.ALLOW_GPU,
        )
    from .runtime.ollama_process import OllamaProcessRuntime

    return OllamaProcessRuntime(settings.data_path, settings.OLLAMA_BINARY, settings.PROCESS_CGROUP_LIMITS)


def parse_deploy_payload(payload: dict) -> WorkloadSpec:
    """Validate a DEPLOY command. Anything unexpected is rejected rather than passed to the runtime."""
    dep_id = str(payload.get("deployment_id", ""))
    tag = str(payload.get("model_tag", ""))
    res = payload.get("resources") or {}
    if not UUID_RE.fullmatch(dep_id):
        raise WorkloadError("INVALID_COMMAND", "Invalid deployment id")
    if payload.get("runtime") != "ollama":
        raise WorkloadError("UNSUPPORTED_RUNTIME", "Unsupported runtime")
    if not TAG_RE.fullmatch(tag):
        raise WorkloadError("INVALID_MODEL", "Invalid model identifier")
    try:
        spec = WorkloadSpec(
            deployment_id=dep_id,
            model_tag=tag,
            num_ctx=int(payload.get("num_ctx", 2048)),
            cpu_cores=int(res["cpu_cores"]),
            ram_mb=int(res["ram_mb"]),
            disk_mb=int(res["disk_mb"]),
            vram_mb=int(res.get("vram_mb", 0)),
            gpu=bool(res.get("gpu", False)),
        )
    except (KeyError, TypeError, ValueError):
        raise WorkloadError("INVALID_COMMAND", "Invalid resource specification") from None
    if not (512 <= spec.num_ctx <= 131072 and 1 <= spec.cpu_cores <= 4096 and 64 <= spec.ram_mb and spec.disk_mb >= 0):
        raise WorkloadError("INVALID_COMMAND", "Resource values out of range")
    return spec


class Worker:
    def __init__(
        self, settings: WorkerSettings, runtime: WorkloadRuntime | None = None, client: ControlPlaneClient | None = None
    ):
        self.settings = settings
        self.state = WorkerState(settings.data_path)
        self.runtime = runtime or make_runtime(settings)
        creds = self.state.load_credentials()
        if client is None:
            if not creds:
                raise SystemExit("This machine is not enrolled. Run: python -m node_agent enroll --token <token>")
            client = ControlPlaneClient(settings.CONTROL_PLANE_URL, creds["node_id"], creds["node_credential"])
        self.client = client
        self.metrics = MetricsCollector()
        self.stop_event = asyncio.Event()
        self.revoked = False
        # deployment_id -> {"spec": WorkloadSpec, "handle": WorkloadHandle|None, "state": str, "healthy": bool}
        self.workloads: dict[str, dict] = {}
        self.deploy_tasks: dict[str, asyncio.Task] = {}
        self.tunnel = TunnelHandler(
            self._resolve, settings.MAX_CONCURRENT_REQUESTS_PER_DEPLOYMENT, settings.REQUEST_TIMEOUT_SECONDS
        )

    # --- helpers -----------------------------------------------------------------------------------

    def _resolve(self, deployment_id: str):
        w = self.workloads.get(deployment_id)
        if w and w["state"] == "running" and w["handle"] is not None:
            return w["handle"].base_url, w["spec"].model_tag
        return None

    def _persist(self, dep_id: str) -> None:
        w = self.workloads.get(dep_id)
        if w is None:
            self.state.drop_workload(dep_id)
            return
        self.state.put_workload(
            dep_id,
            {
                "spec": asdict(w["spec"]),
                "handle": asdict(w["handle"]) if w["handle"] else None,
                "state": w["state"],
            },
        )

    async def capabilities_payload(self) -> dict:
        hw = hardware_report(self.settings.DATA_DIR)
        caps = await self.runtime.capabilities()
        return {
            "hardware": hw,
            "allocation": default_allocation(hw, self.settings),
            "runtimes": [
                {"name": caps.name, "version": caps.version, "backend": caps.backend, "available": caps.available}
            ],
        }

    # --- lifecycle ---------------------------------------------------------------------------------

    async def adopt_existing(self) -> None:
        """After a restart, keep workloads that are still healthy and restart ones whose runtime died."""
        for dep_id, rec in list(self.state.workloads.items()):
            try:
                spec = WorkloadSpec(**rec["spec"])
            except (KeyError, TypeError):
                self.state.drop_workload(dep_id)
                continue
            handle = WorkloadHandle(**rec["handle"]) if rec.get("handle") else None
            if handle is not None and await self.runtime.is_alive(handle) and await self.runtime.health(handle, spec):
                self.workloads[dep_id] = {"spec": spec, "handle": handle, "state": "running", "healthy": True}
                logger.info("Re-adopted running workload %s", dep_id)
                continue
            if handle is not None:
                with contextlib.suppress(Exception):
                    await self.runtime.remove(handle)
            # Restart: the model is cached, so this is quick. The control plane will tell us to stop it if
            # the deployment was stopped while we were away.
            self.workloads[dep_id] = {"spec": spec, "handle": None, "state": "provisioning", "healthy": False}
            self.deploy_tasks[dep_id] = asyncio.create_task(self._deploy(spec, restart=True))

    async def _deploy(self, spec: WorkloadSpec, restart: bool = False) -> None:
        dep_id = spec.deployment_id
        w = self.workloads[dep_id]

        async def progress(msg: str) -> None:
            with contextlib.suppress(ProtocolError):
                await self.client.report(dep_id, "PROVISIONING", msg)

        try:
            free_disk = psutil.disk_usage(self.settings.DATA_DIR).free // (1024 * 1024)
            if free_disk < spec.disk_mb:
                raise WorkloadError("INSUFFICIENT_DISK", f"Only {free_disk} MB free; {spec.disk_mb} MB needed")
            available_ram = psutil.virtual_memory().available // (1024 * 1024)
            if available_ram < spec.ram_mb:
                raise WorkloadError(
                    "INSUFFICIENT_MEMORY", f"Only {available_ram} MB RAM available; {spec.ram_mb} MB needed"
                )
            await self.client.report(
                dep_id, "PROVISIONING", "Restarting runtime" if restart else "Starting isolated runtime"
            )
            w["handle"] = await self.runtime.start(spec)
            self._persist(dep_id)
            await self.runtime.prepare_model(w["handle"], spec, progress)
            await self.client.report(dep_id, "STARTING", "Loading model and running a test generation")
            w["state"] = "starting"
            digest = await self.runtime.verify_ready(w["handle"], spec)
            w["state"], w["healthy"] = "running", True
            self._persist(dep_id)
            await self.client.report(dep_id, "READY", "Model verified with a test generation", model_digest=digest)
            logger.info("Workload %s ready (%s)", dep_id, spec.model_tag)
        except asyncio.CancelledError:
            raise  # whoever cancelled (stop_workload / shutdown) owns cleanup
        except (WorkloadError, ProtocolError) as exc:
            code = getattr(exc, "code", "PROVISIONING_FAILED")
            message = getattr(exc, "message", str(exc))
            logger.warning("Workload %s failed: %s %s", dep_id, code, message)
            if w.get("handle"):
                with contextlib.suppress(Exception):
                    await self.runtime.remove(w["handle"])
            self.workloads.pop(dep_id, None)
            self._persist(dep_id)
            with contextlib.suppress(ProtocolError, CredentialRevoked):
                await self.client.report(dep_id, "FAILED", message, error_code=code)
        finally:
            self.deploy_tasks.pop(dep_id, None)

    async def stop_workload(self, dep_id: str, report: bool = True) -> None:
        task = self.deploy_tasks.pop(dep_id, None)
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        w = self.workloads.pop(dep_id, None)
        if w and w.get("handle"):
            with contextlib.suppress(Exception):
                await self.runtime.remove(w["handle"])
        self._persist(dep_id)
        if report:
            with contextlib.suppress(ProtocolError):
                await self.client.report(dep_id, "STOPPED", "Workload stopped and cleaned up")

    async def handle_command(self, cmd: dict) -> None:
        cmd_id, ctype = str(cmd.get("id")), cmd.get("type")
        if self.state.seen(cmd_id):
            await self.client.ack(cmd_id, "accepted")  # redelivery of a command we already handled
            return
        if ctype == "DEPLOY":
            try:
                spec = parse_deploy_payload(cmd.get("payload") or {})
            except WorkloadError as exc:
                self.state.mark_processed(cmd_id)
                await self.client.ack(cmd_id, "failed", f"{exc.code}: {exc.message}")
                return
            if spec.deployment_id not in self.workloads:
                self.workloads[spec.deployment_id] = {
                    "spec": spec,
                    "handle": None,
                    "state": "provisioning",
                    "healthy": False,
                }
                self._persist(spec.deployment_id)
                self.deploy_tasks[spec.deployment_id] = asyncio.create_task(self._deploy(spec))
            self.state.mark_processed(cmd_id)
            await self.client.ack(cmd_id, "accepted")
        elif ctype == "STOP":
            dep_id = str((cmd.get("payload") or {}).get("deployment_id") or cmd.get("deployment_id"))
            await self.stop_workload(dep_id)
            self.state.mark_processed(cmd_id)
            await self.client.ack(cmd_id, "succeeded")
        else:
            self.state.mark_processed(cmd_id)
            await self.client.ack(cmd_id, "failed", "Unsupported command type")

    # --- loops -------------------------------------------------------------------------------------

    async def heartbeat_once(self) -> dict:
        payload = {
            "worker_version": WORKER_VERSION,
            **(await self.capabilities_payload()),
            "metrics": {k: float(v) for k, v in self.metrics.get_summary().items()},
            "deployments": [
                {"deployment_id": dep_id, "state": w["state"], "healthy": bool(w["healthy"])}
                for dep_id, w in self.workloads.items()
            ],
        }
        resp = await self.client.heartbeat(payload)
        self.state.record_heartbeat()
        for dep_id in resp.get("stop_deployments", []):
            logger.info("Control plane asked to stop workload %s", dep_id)
            await self.stop_workload(str(dep_id))
        return resp

    async def _heartbeat_loop(self) -> None:
        attempt = 0
        while not self.stop_event.is_set():
            try:
                resp = await self.heartbeat_once()
                attempt = 0
                interval = resp.get("heartbeat_interval_seconds", self.settings.HEARTBEAT_INTERVAL_SECONDS)
            except ProtocolError as exc:
                logger.warning("Heartbeat failed: %s", exc)
                interval = backoff(attempt, cap=self.settings.HEARTBEAT_INTERVAL_SECONDS)
                attempt += 1
            await self._sleep(interval)

    async def _command_loop(self) -> None:
        attempt = 0
        while not self.stop_event.is_set():
            try:
                for cmd in await self.client.poll(wait_seconds=20):
                    await self.handle_command(cmd)
                attempt = 0
            except ProtocolError as exc:
                logger.warning("Command poll failed: %s", exc)
                await self._sleep(backoff(attempt, cap=30))
                attempt += 1

    async def _health_loop(self) -> None:
        while not self.stop_event.is_set():
            await self._sleep(self.settings.HEALTH_CHECK_INTERVAL_SECONDS)
            for w in list(self.workloads.values()):
                if w["state"] == "running" and w["handle"] is not None:
                    w["healthy"] = await self.runtime.health(w["handle"], w["spec"])

    async def _sleep(self, seconds: float) -> None:
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self.stop_event.wait(), timeout=seconds)

    async def run(self) -> int:
        """Run until stopped. Returns a process exit code."""
        caps = await self.runtime.capabilities()
        if not caps.available:
            logger.error("Runtime unavailable: %s", caps.detail)
        logger.info(
            "Runtime: %s %s (%s); limits %s",
            caps.name,
            caps.version,
            caps.backend,
            "enforced" if caps.limits_enforced else "advisory",
        )
        await self.adopt_existing()
        loops = [
            asyncio.create_task(self._heartbeat_loop()),
            asyncio.create_task(self._command_loop()),
            asyncio.create_task(self._health_loop()),
            asyncio.create_task(
                run_tunnel(self.client.tunnel_url(), self.client.headers, self.tunnel, self.stop_event)
            ),
        ]
        stopper = asyncio.create_task(self.stop_event.wait())
        done, _ = await asyncio.wait([*loops, stopper], return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            exc = task.exception() if not task.cancelled() else None
            if isinstance(exc, CredentialRevoked):
                self.revoked = True
                logger.error("Node credential was revoked. Stopping all workloads.")
            elif exc is not None:
                logger.error("Worker loop crashed: %r", exc)
        self.stop_event.set()
        for task in [*loops, stopper]:
            task.cancel()
        await asyncio.gather(*loops, stopper, return_exceptions=True)
        if self.revoked:
            for dep_id in list(self.workloads):
                await self.stop_workload(dep_id, report=False)
            self.state.delete_credentials()
            return 2
        await self.shutdown()
        return 0

    async def shutdown(self) -> None:
        """Graceful exit. Docker workloads keep serving and are re-adopted on restart. Process workloads are
        children of the worker and are stopped; they restart from the cached model when the worker returns."""
        for task in list(self.deploy_tasks.values()):
            task.cancel()
        with contextlib.suppress(ProtocolError, CredentialRevoked):
            await self.client.disconnect()
        if self.runtime.backend == "process":
            for w in list(self.workloads.values()):
                if w.get("handle"):
                    with contextlib.suppress(Exception):
                        await self.runtime.remove(w["handle"])
        await self.client.close()


async def enroll(
    settings: WorkerSettings,
    token: str,
    runtime: WorkloadRuntime | None = None,
    client: ControlPlaneClient | None = None,
) -> dict:
    from .identity import get_or_create_identity, get_public_key_pem

    state = WorkerState(settings.data_path)
    if state.load_credentials():
        raise SystemExit("Already enrolled. Run 'python -m node_agent uninstall' first to re-enroll.")
    runtime = runtime or make_runtime(settings)
    client = client or ControlPlaneClient(settings.CONTROL_PLANE_URL)
    caps = await runtime.capabilities()
    hw = hardware_report(settings.DATA_DIR)
    _, pub = get_or_create_identity(settings.data_path)
    payload = {
        "token": token,
        "name": (settings.NODE_NAME or "agentmesh-node")[:100],
        "mode": settings.MODE,
        "worker_version": WORKER_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "hardware": hw,
        "allocation": default_allocation(hw, settings),
        "runtimes": [
            {"name": caps.name, "version": caps.version, "backend": caps.backend, "available": caps.available}
        ],
        "public_key": get_public_key_pem(pub),
    }
    try:
        result = await client.enroll(payload)
    finally:
        await client.close()
    state.save_credentials(str(result["node_id"]), result["node_credential"], settings.CONTROL_PLANE_URL)
    return {"node_id": result["node_id"], "allocation": payload["allocation"], "runtime": asdict(caps)}

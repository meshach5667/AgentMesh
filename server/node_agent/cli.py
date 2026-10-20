"""AgentMesh worker CLI.

    python -m node_agent enroll --token am_enroll_...   # one-time, token from the provider dashboard
    python -m node_agent run                            # start serving (foreground)
    python -m node_agent status                         # enrollment and managed workloads
    python -m node_agent hardware                       # what would be reported, and the default allocation
    python -m node_agent uninstall                      # stop managed workloads, delete credentials and cache

Configuration comes from AGENTMESH_* environment variables (see node_agent/config.py).
"""

import argparse
import asyncio
import json
import logging
import shutil
import signal
import sys

from .config import load_settings
from .hardware.discovery import default_allocation, hardware_report


def _setup_logging(level: str) -> None:
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


async def _run(settings) -> int:
    from .worker import Worker

    worker = Worker(settings)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, worker.stop_event.set)
        except NotImplementedError:  # Windows
            pass
    return await worker.run()


async def _uninstall(settings) -> None:
    from .runtime.base import WorkloadHandle
    from .state import WorkerState
    from .worker import make_runtime

    state = WorkerState(settings.data_path)
    runtime = make_runtime(settings)
    for dep_id, rec in list(state.workloads.items()):
        if rec.get("handle"):
            try:
                await runtime.remove(WorkloadHandle(**rec["handle"]))
            except Exception as exc:  # noqa: BLE001
                print(f"Could not remove workload {dep_id}: {exc}")
        state.drop_workload(dep_id)
    state.delete_credentials()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agentmesh-worker", description="AgentMesh worker")
    sub = parser.add_subparsers(dest="command", required=True)
    enroll_p = sub.add_parser("enroll", help="Enroll this machine using a one-time token")
    enroll_p.add_argument("--token", required=True)
    sub.add_parser("run", help="Run the worker")
    sub.add_parser("start", help="Enroll with AGENTMESH_ENROLLMENT_TOKEN if not enrolled yet, then run (containers)")
    status_p = sub.add_parser("status", help="Show enrollment and managed workloads")
    status_p.add_argument("--check", action="store_true", help="Exit non-zero unless a heartbeat succeeded recently")
    sub.add_parser("hardware", help="Show detected hardware and the resources that would be offered")
    uninstall_p = sub.add_parser("uninstall", help="Stop workloads and remove credentials")
    uninstall_p.add_argument("--purge-models", action="store_true", help="Also delete the downloaded model cache")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    _setup_logging(args.log_level)
    settings = load_settings()

    if args.command == "hardware":
        hw = hardware_report(settings.DATA_DIR)
        print(json.dumps({"hardware": hw, "offered_to_agentmesh": default_allocation(hw, settings)}, indent=2))
        return 0
    if args.command == "status":
        from .state import WorkerState

        state = WorkerState(settings.data_path)
        creds = state.load_credentials()
        print(
            json.dumps(
                {
                    "enrolled": bool(creds),
                    "node_id": creds["node_id"] if creds else None,
                    "control_plane": creds["control_plane_url"] if creds else settings.CONTROL_PLANE_URL,
                    "workloads": {k: v.get("state") for k, v in state.workloads.items()},
                },
                indent=2,
            )
        )
        return 0
    if args.command == "enroll":
        from .worker import enroll

        result = asyncio.run(enroll(settings, args.token))
        print(f"Enrolled node {result['node_id']}")
        print("Resources offered to AgentMesh:", json.dumps(result["allocation"]))
        print(
            f"Runtime: ollama ({result['runtime']['backend']}), available={result['runtime']['available']}, "
            f"limits {'enforced' if result['runtime']['limits_enforced'] else 'advisory'}"
        )
        return 0
    if args.command == "start":
        import os

        from .state import WorkerState
        from .worker import enroll

        if not WorkerState(settings.data_path).load_credentials():
            token = os.environ.get("AGENTMESH_ENROLLMENT_TOKEN", "")
            if not token:
                print("Not enrolled and AGENTMESH_ENROLLMENT_TOKEN is not set.")
                print("Create an enrollment token in the provider dashboard.")
                return 1
            result = asyncio.run(enroll(settings, token))
            print(f"Enrolled node {result['node_id']}; offered {json.dumps(result['allocation'])}")
        return asyncio.run(_run(settings))
    if args.command == "run":
        return asyncio.run(_run(settings))
    if args.command == "uninstall":
        asyncio.run(_uninstall(settings))
        if args.purge_models:
            shutil.rmtree(settings.data_path / "models", ignore_errors=True)
        print("Worker credentials removed and managed workloads stopped. Revoke the node in the dashboard too.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())

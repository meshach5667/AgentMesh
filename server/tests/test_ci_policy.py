"""Supply-chain policy for CI and images (G-16, G-17), checked on every run so it cannot quietly regress."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))


def _load(path: Path) -> dict:
    data = yaml.safe_load(path.read_text())
    data["on"] = data.get("on", data.get(True))  # YAML 1.1 reads the key `on` as True
    return data


def test_workflows_exist():
    assert {p.name for p in WORKFLOWS} >= {"ci.yml", "security.yml", "worker-release.yml"}


def test_every_action_is_pinned_to_a_full_commit_sha():
    for path in WORKFLOWS:
        for job in _load(path)["jobs"].values():
            for step in job.get("steps", []):
                if "uses" in step:
                    assert re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", step["uses"]), f"{path.name}: {step['uses']}"


def test_every_workflow_declares_minimal_permissions_and_never_runs_fork_code_privileged():
    for path in WORKFLOWS:
        wf = _load(path)
        assert "permissions" in wf, f"{path.name} has no top-level permissions"
        assert "pull_request_target" not in (wf["on"] or {}), path.name
        if path.name != "worker-release.yml":
            assert wf["permissions"] == {"contents": "read"}, path.name
    release = _load(ROOT / ".github/workflows/worker-release.yml")
    assert list(release["on"]) == ["push"] and "tags" in release["on"]["push"]  # maintainers' tags only


def test_security_checks_run_on_pull_requests_and_fail_the_build():
    sec = _load(ROOT / ".github/workflows/security.yml")
    assert "pull_request" in sec["on"]
    text = (ROOT / ".github/workflows/security.yml").read_text()
    trivy = [s for j in sec["jobs"].values() for s in j["steps"] if "trivy-action" in s.get("uses", "")]
    assert trivy and all(s["with"].get("exit-code") == "1" for s in trivy if s["with"].get("format") != "cyclonedx")
    assert "sha256sum --check" in text  # gitleaks verified before it runs
    assert "bandit" in text and "-ll" in text and "--audit-level=high" in text
    assert "pip-audit -r server/requirements-lock.txt" in text


def test_dependabot_covers_every_ecosystem():
    eco = {u["package-ecosystem"] for u in yaml.safe_load((ROOT / ".github/dependabot.yml").read_text())["updates"]}
    assert eco >= {"pip", "npm", "github-actions", "docker"}


def test_images_use_digest_pinned_bases_and_locked_dependencies():
    for name in ("Dockerfile.server", "Dockerfile.node-agent", "Dockerfile.client"):
        text = (ROOT / name).read_text()
        froms = re.findall(r"^FROM\s+(\S+)", text, flags=re.M)
        assert froms and all("@sha256:" in f for f in froms), name
    assert "requirements-lock.txt" in (ROOT / "Dockerfile.server").read_text()
    assert "requirements-worker-lock.txt" in (ROOT / "Dockerfile.node-agent").read_text()
    assert "build-essential" not in (ROOT / "Dockerfile.server").read_text()


def test_lock_files_pin_every_requirement_exactly():
    norm = lambda s: re.sub(r"[-_.]+", "-", s).lower()  # noqa: E731
    for req, lock in (
        ("requirements.txt", "requirements-lock.txt"),
        ("requirements-worker.txt", "requirements-worker-lock.txt"),
    ):
        locked = {
            norm(line.split("==")[0])
            for line in (ROOT / "server" / lock).read_text().splitlines()
            if line and not line.startswith("#")
        }
        lines = [
            line for line in (ROOT / "server" / lock).read_text().splitlines() if line and not line.startswith("#")
        ]
        assert all(re.fullmatch(r"[\w.-]+==[\w.+-]+", line) for line in lines), lock
        for line in (ROOT / "server" / req).read_text().splitlines():
            name = re.split(r"[<>=\[ #]", line.strip())[0]
            if name:
                assert norm(name) in locked, f"{name} from {req} missing in {lock}"


def test_production_images_carry_no_test_or_lint_tools():
    locked = (ROOT / "server" / "requirements-lock.txt").read_text().lower()
    for tool in ("pytest", "ruff", "mypy", "fakeredis"):
        assert f"\n{tool}" not in locked, f"{tool} is in the production lock"
    dev = (ROOT / "server" / "requirements-dev.txt").read_text()
    assert all("==" in line for line in dev.splitlines() if line and not line.startswith("#"))


def test_jobs_run_on_a_pinned_runner_image():
    """ubuntu-latest moves to new Ubuntu releases on GitHub's schedule (26.04 from November 2026); MongoDB 8.0 has
    no server or mongosh packages there, so every job pins the image it was verified on."""
    for path in WORKFLOWS:
        for name, job in _load(path)["jobs"].items():
            assert job["runs-on"] == "ubuntu-24.04", f"{path.name}:{name} runs on {job['runs-on']}"

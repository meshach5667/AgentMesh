"""Turn a pytest JUnit report into GitHub Actions error annotations and a job-summary table.

    python server/ops/ci_report_failures.py server/pytest-report.xml

Standard library only, so it runs even when dependency installation is what failed (it then reports that no test
report exists).
"""

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def escape(text: str) -> str:
    """Workflow-command escaping for annotation messages."""
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def failures(report: Path) -> list[tuple[str, str, str]]:
    found = []
    for case in ET.parse(report).getroot().iter("testcase"):
        for kind in ("failure", "error"):
            element = case.find(kind)
            if element is None:
                continue
            name = f"{case.get('classname', '')}::{case.get('name', '')}"
            message = (element.get("message") or element.text or "").strip()
            found.append((kind, name, message))
    return found


def main(path: str) -> int:
    report = Path(path)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if not report.exists():
        print(f"::error title=No test report::{escape(f'{report} was not written; see the Run pytest step log')}")
        return 0
    rows = failures(report)
    for kind, name, message in rows:
        first = message.splitlines()[0] if message else kind
        print(f"::error title=Test {kind}::{escape(f'{name}: {first[:500]}')}")
    lines = ["### Failing tests", ""]
    if rows:
        lines += ["| Test | Reason |", "|---|---|"]
        for kind, name, message in rows:
            reason = (message.splitlines()[0] if message else kind)[:300].replace("|", "\\|")
            lines.append(f"| `{name}` | {reason} |")
    else:
        lines.append("No failing test in the report (the step failed for another reason, e.g. coverage).")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    else:
        print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "pytest-report.xml"))

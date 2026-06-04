"""
agents/execution_agent.py — Execution Agent
============================================
Runs generated pytest/Playwright test scripts as subprocesses, collects
per-test results from the pytest-json-report output, and updates state.

Flow:
    state.test_scripts (file paths)
        →  subprocess pytest --json-report (per file)
        →  state.execution_results (list[dict])
        →  state.status = "all_passed" | "running"
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

from graph.state import QAgentState

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

DEFAULT_TIMEOUT: int = 120          # seconds per test file
PYTEST_REPORT_FILE = "report.json"  # written inside a temp dir per run


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run_pytest(file_path: str, timeout: int) -> dict:
    """
    Execute pytest on a single file with --json-report.

    Returns the parsed JSON report dict, or a synthetic error dict on
    timeout / subprocess failure.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        report_path = Path(tmpdir) / PYTEST_REPORT_FILE
        cmd = [
            sys.executable, "-m", "pytest",
            file_path,
            "--json-report",
            f"--json-report-file={report_path}",
            "-v",
            "--tb=short",
        ]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            logger.error("Execution Agent: timeout (%ds) for %s", timeout, file_path)
            return {
                "__timeout": True,
                "stdout": "",
                "stderr": f"pytest timed out after {timeout}s",
                "returncode": -1,
            }
        except FileNotFoundError:
            logger.error("Execution Agent: 'pytest' not found in PATH")
            return {
                "__timeout": False,
                "stdout": "",
                "stderr": "pytest executable not found in PATH",
                "returncode": -2,
            }

        report: dict = {}
        if report_path.exists():
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                logger.warning(
                    "Execution Agent: could not parse JSON report for %s: %s",
                    file_path, exc,
                )

        report["__stdout"] = proc.stdout
        report["__stderr"] = proc.stderr
        report["__returncode"] = proc.returncode
        report["__timeout"] = False
        return report


def _extract_results(report: dict, file_path: str) -> list[dict]:
    """
    Convert a pytest-json-report dict into a flat list of result dicts,
    one entry per test node.
    """
    results: list[dict] = []

    # ── Hard failure: timeout or pytest not found ─────────────────────────
    if report.get("__timeout") or report.get("__returncode", 0) == -2:
        results.append({
            "tc_id": "UNKNOWN",
            "file": file_path,
            "status": "error",
            "duration": 0.0,
            "error_message": report.get("__stderr", "Unknown execution error"),
            "stdout": report.get("__stdout", ""),
            "traceback": "",
        })
        return results

    tests: list[dict] = report.get("tests", [])

    # ── No test nodes collected (collection error / empty file) ───────────
    if not tests:
        stderr = report.get("__stderr", "") or report.get("__stdout", "")
        results.append({
            "tc_id": "UNKNOWN",
            "file": file_path,
            "status": "error",
            "duration": 0.0,
            "error_message": f"No tests collected. stderr: {stderr[:400]}",
            "stdout": report.get("__stdout", ""),
            "traceback": "",
        })
        return results

    for node in tests:
        node_id: str = node.get("nodeid", "")
        # Try to derive tc_id from the test function name (e.g. test_TC_001_…)
        tc_id = _infer_tc_id(node_id)

        outcome: str = node.get("outcome", "error")   # "passed"|"failed"|"error"
        duration: float = node.get("duration", 0.0)

        call_info: dict = node.get("call", {}) or {}
        setup_info: dict = node.get("setup", {}) or {}

        # Prefer call-phase traceback; fall back to setup-phase
        longrepr: str = (
            call_info.get("longrepr", "")
            or setup_info.get("longrepr", "")
            or ""
        )
        crash: dict = call_info.get("crash", {}) or setup_info.get("crash", {}) or {}
        error_message: str = crash.get("message", "") or (longrepr[:500] if longrepr else "")

        results.append({
            "tc_id": tc_id,
            "file": file_path,
            "status": outcome,
            "duration": round(duration, 4),
            "error_message": error_message if outcome != "passed" else "",
            "stdout": node.get("stdout", "") or "",
            "traceback": longrepr if outcome != "passed" else "",
        })

    return results


def _infer_tc_id(node_id: str) -> str:
    """
    Extract a TC-XXX identifier from a pytest node id such as
    tests/generated/test_us_001.py::test_TC_001_login_happy_path
    Falls back to the full node_id if no match found.
    """
    import re
    match = re.search(r"TC[_-](\d{3,})", node_id, re.IGNORECASE)
    if match:
        return f"TC-{match.group(1)}"
    # Fall back to function name portion after `::`
    parts = node_id.split("::")
    return parts[-1] if parts else node_id


# ── Agent node ────────────────────────────────────────────────────────────────

def execution_agent(
    state: QAgentState,
    timeout: int = DEFAULT_TIMEOUT,
) -> QAgentState:
    """
    LangGraph node: test_scripts → execution_results.

    Runs all script files concurrently (up to 4 at a time) using a
    ThreadPoolExecutor.  Each invocation has its own temp directory, so
    runs are fully isolated.  Results are merged in the original file order.
    Sets state.status = "all_passed" only when every test across all files passed.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    scripts = state["test_scripts"]
    if not scripts:
        logger.info("Execution Agent: no test scripts to run.")
        return {**state, "execution_results": [], "status": state.get("status", "running")}

    print(f"  ⚡ Execution Agent: running {len(scripts)} file(s) concurrently …")

    # Run pytest files concurrently — each gets an isolated temp dir
    results_by_idx: dict[int, list[dict]] = {}

    def _run_one(idx_path: tuple[int, str]) -> tuple[int, list[dict]]:
        idx, file_path = idx_path
        logger.info("Execution Agent: running %s", file_path)
        print(f"  ▶️  Running {Path(file_path).name} …")
        report = _run_pytest(file_path, timeout)
        file_results = _extract_results(report, file_path)
        passed = sum(1 for r in file_results if r["status"] == "passed")
        failed = sum(1 for r in file_results if r["status"] == "failed")
        errors = sum(1 for r in file_results if r["status"] == "error")
        print(
            f"     {Path(file_path).name}: "
            f"{passed} passed / {failed} failed / {errors} errors"
        )
        return idx, file_results

    max_workers = min(4, len(scripts))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_run_one, (i, fp)): i
            for i, fp in enumerate(scripts)
        }
        for future in as_completed(futures):
            try:
                idx, file_results = future.result()
                results_by_idx[idx] = file_results
            except Exception as exc:
                idx = futures[future]
                logger.error(
                    "Execution Agent: unexpected error running script[%d]: %s", idx, exc
                )
                results_by_idx[idx] = [{
                    "tc_id": "UNKNOWN",
                    "file": scripts[idx],
                    "status": "error",
                    "duration": 0.0,
                    "error_message": f"Unhandled executor error: {exc}",
                    "stdout": "",
                    "traceback": "",
                }]

    # Merge in original order
    all_results: list[dict] = []
    for i in range(len(scripts)):
        all_results.extend(results_by_idx.get(i, []))

    total_passed = sum(1 for r in all_results if r["status"] == "passed")
    total_failed = sum(1 for r in all_results if r["status"] == "failed")
    total_errors = sum(1 for r in all_results if r["status"] == "error")

    new_status = "all_passed" if (total_failed + total_errors) == 0 else state.get("status", "running")

    print(
        f"✅ Execution Agent: {total_passed} passed, "
        f"{total_failed} failed, {total_errors} errors"
    )
    logger.info(
        "▶️ Execution Agent: %d passed, %d failed, %d errors — status: %s",
        total_passed, total_failed, total_errors, new_status,
    )

    return {**state, "execution_results": all_results, "status": new_status}

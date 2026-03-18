#!/usr/bin/env python3
"""
run_isolated_audit.py — isolated audit runner for playwright-auditor

Creates a dedicated run directory, executes the audit in an isolated workspace,
exports HTML/Markdown/JSON artifacts, and removes transient dependencies by
default so the run does not interfere with existing projects.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


def slugify_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.netloc or "audit").lower()
    for prefix in ("www.",):
        if host.startswith(prefix):
            host = host[len(prefix):]
    return "".join(char if char.isalnum() else "-" for char in host).strip("-") or "audit"


def run_command(cmd: list[str], cwd: Path, check: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    print(f"[playwright-auditor] $ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd, env=env, check=check)


def copy_tree_if_exists(src: Path, dst: Path):
    if not src.exists():
        return
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def copy_file_if_exists(src: Path, dst: Path):
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def remove_path_if_exists(path: Path):
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def main():
    parser = argparse.ArgumentParser(description="Run playwright-auditor in an isolated workspace")
    parser.add_argument("--url", required=True, help="URL to audit")
    parser.add_argument("--scenario", default="full", choices=["smoke", "form", "auth", "a11y", "perf", "visual", "full"])
    parser.add_argument("--browser", default="chromium", help="Browser project to run")
    parser.add_argument("--base-dir", default="audit-runs", help="Directory where isolated audit runs are stored")
    parser.add_argument("--name", help="Optional run folder prefix")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--retries", type=int, default=0)
    parser.add_argument("--keep-workspace", action="store_true", help="Keep the generated workspace with node_modules")
    parser.add_argument("--keep-evidence", action="store_true", help="Keep raw Playwright artifacts in addition to the final reports")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_name = args.name or slugify_url(args.url)
    run_dir = Path(args.base_dir).resolve() / f"{run_name}-{timestamp}"
    workspace_dir = Path(tempfile.mkdtemp(prefix=f"playwright-audit-{run_name}-"))
    artifacts_dir = run_dir / "artifacts"

    run_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    install_script = script_dir / "install.sh"
    scaffold_script = script_dir / "scaffold_tests.py"
    audit_script = script_dir / "run_audit.sh"
    report_script = script_dir / "generate_report.py"

    print(f"[playwright-auditor] Run directory: {run_dir}")
    print(f"[playwright-auditor] Workspace: {workspace_dir}")
    print(f"[playwright-auditor] Artifacts: {artifacts_dir}")

    run_command(["bash", str(install_script), "--browsers", args.browser, "--no-deps"], cwd=workspace_dir)
    run_command(
        [
            "python3",
            str(scaffold_script),
            "--url",
            args.url,
            "--scenario",
            args.scenario,
            "--output-dir",
            "tests",
        ],
        cwd=workspace_dir,
    )

    audit_result = run_command(
        [
            "bash",
            str(audit_script),
            "--browser",
            args.browser,
            "--workers",
            str(args.workers),
            "--retries",
            str(args.retries),
            "--no-open",
            "--url",
            args.url,
        ],
        cwd=workspace_dir,
        check=False,
    )

    results_json = workspace_dir / "test-results" / "results.json"
    copied_results_json = artifacts_dir / "test-results" / "results.json"

    copy_tree_if_exists(workspace_dir / "test-results", artifacts_dir / "test-results")
    if args.keep_evidence:
        copy_tree_if_exists(workspace_dir / "playwright-report", artifacts_dir / "playwright-report")
        copy_tree_if_exists(workspace_dir / "tests" / "visual.spec.ts-snapshots", artifacts_dir / "visual-baselines")
        copy_file_if_exists(workspace_dir / "playwright.config.ts", artifacts_dir / "playwright.config.ts")
        copy_file_if_exists(results_json, artifacts_dir / "playwright-results.json")

    if copied_results_json.exists():
        run_command(
            [
                "python3",
                str(report_script),
                "--input",
                str(copied_results_json),
                "--base-url",
                args.url,
                "--output",
                str(artifacts_dir / "audit-report.md"),
                "--html-output",
                str(artifacts_dir / "audit-report.html"),
                "--json-output",
                str(artifacts_dir / "audit-summary.json"),
                "--attachments-mode",
                "links" if args.keep_evidence else "none",
            ],
            cwd=artifacts_dir,
        )

    if not args.keep_evidence:
        remove_path_if_exists(artifacts_dir / "test-results")
        remove_path_if_exists(artifacts_dir / "playwright-report")
        remove_path_if_exists(artifacts_dir / "visual-baselines")
        remove_path_if_exists(artifacts_dir / "playwright-results.json")
        remove_path_if_exists(artifacts_dir / "playwright.config.ts")

    if args.keep_workspace:
        print("[playwright-auditor] Workspace kept on disk.")
    else:
        shutil.rmtree(workspace_dir)
        print("[playwright-auditor] Workspace removed after artifact export.")

    print("[playwright-auditor] Final artifacts:")
    for path in sorted(artifacts_dir.rglob("*")):
        if path.is_file():
            print(f"  - {path}")

    sys.exit(audit_result.returncode)


if __name__ == "__main__":
    main()

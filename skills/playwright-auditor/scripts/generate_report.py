#!/usr/bin/env python3
"""
generate_report.py — Playwright Audit Report Generator
=======================================================
Parses Playwright's JSON reporter output and produces a structured
Markdown audit report with pass/fail tables, performance metrics,
accessibility violations, and optional AI-generated recommendations.

Usage:
    python scripts/generate_report.py --input test-results/results.json
    python scripts/generate_report.py --input test-results/results.json --ai-recommendations
    python scripts/generate_report.py --input test-results/results.json --embed-screenshots
    python scripts/generate_report.py --help

Requirements:
    pip install requests          (only needed for --ai-recommendations)

Output:
    audit-report-{TIMESTAMP}.md
"""

import argparse
import base64
import html
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


# ── Data extraction ────────────────────────────────────────────────────────────

def load_results(path: str) -> dict:
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        print(f"[✗] Results file not found: {path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[✗] Invalid JSON in {path}: {e}")
        sys.exit(1)


def extract_tests(suite: dict, results: list, parent_title: str = ""):
    """Recursively extract all test results from nested suite structure."""
    title = suite.get("title", "")
    full_title = f"{parent_title} › {title}".strip(" › ") if title else parent_title

    for spec in suite.get("specs", []):
        spec_title = spec.get("title", "Unknown Test")
        for test in spec.get("tests", []):
            result = test.get("results", [{}])[0]
            results.append({
                "suite": full_title,
                "title": spec_title,
                "status": result.get("status", "unknown"),
                "duration": result.get("duration", 0),
                "browser": test.get("projectName", "—"),
                "error": clean_text(result.get("error", {}).get("message", "") if result.get("error") else ""),
                "attachments": result.get("attachments", []),
            })

    for child in suite.get("suites", []):
        extract_tests(child, results, full_title)


def compute_stats(tests: list) -> dict:
    total = len(tests)
    passed = sum(1 for t in tests if t["status"] == "passed")
    failed = sum(1 for t in tests if t["status"] == "failed")
    skipped = sum(1 for t in tests if t["status"] == "skipped")
    flaky = sum(1 for t in tests if t["status"] == "flaky")
    duration_total = sum(t["duration"] for t in tests)
    pass_rate = (passed / total * 100) if total > 0 else 0.0

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "flaky": flaky,
        "duration_ms": duration_total,
        "pass_rate": pass_rate,
    }


def clean_text(value: str) -> str:
    return ANSI_ESCAPE_RE.sub("", value or "").strip()


def normalize_attachment_path(raw_path: str, input_path: Path) -> Path | None:
    if not raw_path:
        return None

    normalized = raw_path.replace("\\", "/")
    marker = "/test-results/"
    if marker in normalized:
        suffix = normalized.split(marker, 1)[1]
        copied_candidate = input_path.parent / suffix
        if copied_candidate.exists():
            return copied_candidate

    candidate = Path(raw_path)
    if candidate.exists():
        return candidate

    return None


def rewrite_attachments_for_reports(tests: list, input_path: Path, report_dir: Path | None):
    for test in tests:
        normalized_attachments = []
        for attachment in test.get("attachments", []):
            raw_path = attachment.get("path", "")
            resolved_path = normalize_attachment_path(raw_path, input_path)
            normalized = dict(attachment)
            normalized["path"] = str(resolved_path) if resolved_path else raw_path
            if resolved_path and report_dir:
                normalized["href"] = os.path.relpath(resolved_path, report_dir)
            elif raw_path:
                normalized["href"] = raw_path
            normalized_attachments.append(normalized)
        test["attachments"] = normalized_attachments


def group_tests_by_suite(tests: list) -> dict[str, list]:
    suites: dict[str, list] = {}
    for test in tests:
        suites.setdefault(test["suite"] or "Root", []).append(test)
    return suites


def build_summary_payload(tests: list, stats: dict, results_data: dict, base_url: str) -> dict:
    suites_payload = []
    for suite_name, suite_tests in group_tests_by_suite(tests).items():
        suites_payload.append({
            "suite": suite_name,
            "tests": suite_tests,
        })

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "base_url": base_url,
        "playwright_version": results_data.get("version", "unknown"),
        "stats": stats,
        "suites": suites_payload,
    }


# ── Screenshot embedding ───────────────────────────────────────────────────────

def embed_screenshot(path: str) -> str:
    """Return a base64-encoded markdown image tag, or a plain link."""
    try:
        data = Path(path).read_bytes()
        b64 = base64.b64encode(data).decode()
        return f"![Screenshot](data:image/png;base64,{b64})"
    except Exception:
        return f"[Screenshot]({path})"


# ── AI recommendations ────────────────────────────────────────────────────────

def get_ai_recommendations(tests: list, stats: dict) -> str:
    """Call Claude API to generate improvement suggestions based on failures."""
    try:
        import requests
    except ImportError:
        return "*Install `requests` to enable AI recommendations: `pip install requests`*"

    failures = [t for t in tests if t["status"] in ("failed", "flaky")]
    if not failures:
        return "✅ All tests passed — no issues to address."

    failure_summary = "\n".join(
        f"- [{t['browser']}] {t['suite']} › {t['title']}: {t['error'][:200]}"
        for t in failures[:10]
    )

    prompt = f"""You are a senior SDET reviewing Playwright test results.

Test summary:
- Total: {stats['total']} | Passed: {stats['passed']} | Failed: {stats['failed']} | Flaky: {stats['flaky']}
- Pass rate: {stats['pass_rate']:.1f}%

Failing tests:
{failure_summary}

Provide concrete, actionable recommendations to fix these failures.
Format as a numbered list. Focus on:
1. Root cause analysis for each failure pattern
2. Specific code changes (prefer getByRole over CSS selectors)
3. Config changes (retries, timeouts, waitFor strategies)
4. CI/CD considerations if relevant

Be concise and technical. No introductory text."""

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        data = resp.json()
        text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
        return "\n".join(text_blocks) if text_blocks else "*No recommendations generated.*"
    except Exception as e:
        return f"*Could not generate AI recommendations: {e}*"


# ── Report assembly ────────────────────────────────────────────────────────────

def build_report(
    tests: list,
    stats: dict,
    results_data: dict,
    embed_screenshots: bool,
    ai_recommendations: str | None,
    base_url: str,
    include_attachments: bool,
) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    duration_s = stats["duration_ms"] / 1000

    lines = [
        f"# Playwright Audit Report",
        f"",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| **URL** | {base_url or '*(not set)*'} |",
        f"| **Date** | {now} |",
        f"| **Duration** | {duration_s:.1f}s |",
        f"| **Playwright** | {results_data.get('version', 'unknown')} |",
        f"",
        f"---",
        f"",
        f"## Summary",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Tests | {stats['total']} |",
        f"| ✅ Passed | {stats['passed']} |",
        f"| ❌ Failed | {stats['failed']} |",
        f"| ⚠️ Flaky | {stats['flaky']} |",
        f"| ⏭ Skipped | {stats['skipped']} |",
        f"| **Pass Rate** | **{stats['pass_rate']:.1f}%** |",
        f"",
    ]

    # ── Per-browser breakdown ──────────────────────────────────────────────────
    browsers = {}
    for t in tests:
        b = t["browser"] or "unknown"
        if b not in browsers:
            browsers[b] = {"passed": 0, "failed": 0, "flaky": 0}
        status = t["status"]
        if status == "passed":
            browsers[b]["passed"] += 1
        elif status == "failed":
            browsers[b]["failed"] += 1
        elif status == "flaky":
            browsers[b]["flaky"] += 1

    if len(browsers) > 1:
        lines += [
            f"### By Browser",
            f"",
            f"| Browser | ✅ Passed | ❌ Failed | ⚠️ Flaky |",
            f"|---------|----------|----------|---------|",
        ]
        for browser, counts in sorted(browsers.items()):
            lines.append(f"| {browser} | {counts['passed']} | {counts['failed']} | {counts['flaky']} |")
        lines.append("")

    # ── Test results ───────────────────────────────────────────────────────────
    lines += ["---", "", "## Test Results", ""]

    # Group by suite
    for suite_name, suite_tests in group_tests_by_suite(tests).items():
        suite_passed = sum(1 for t in suite_tests if t["status"] == "passed")
        suite_total = len(suite_tests)
        suite_icon = "✅" if suite_passed == suite_total else "❌"

        lines += [
            f"### {suite_icon} {suite_name} ({suite_passed}/{suite_total})",
            f"",
            f"| Test | Status | Duration | Browser |",
            f"|------|--------|----------|---------|",
        ]

        for t in suite_tests:
            icon = {"passed": "✅", "failed": "❌", "skipped": "⏭", "flaky": "⚠️"}.get(t["status"], "?")
            duration_s = t["duration"] / 1000
            lines.append(f"| {t['title']} | {icon} {t['status'].upper()} | {duration_s:.1f}s | {t['browser']} |")

        lines.append("")

        # Failure details
        failures = [t for t in suite_tests if t["status"] in ("failed", "flaky")]
        for t in failures:
            lines += [
                f"<details>",
                f"<summary>❌ Failure detail: {t['title']} ({t['browser']})</summary>",
                f"",
                f"```",
                f"{t['error'][:1000] if t['error'] else 'No error message captured'}",
                f"```",
            ]

            # Screenshots
            if include_attachments:
                screenshots = [a for a in t.get("attachments", []) if a.get("contentType", "").startswith("image")]
                for sc in screenshots[:1]:  # Show max 1 screenshot per failure
                    sc_path = sc.get("path", "")
                    if sc_path and Path(sc_path).exists():
                        if embed_screenshots:
                            lines.append(embed_screenshot(sc_path))
                        else:
                            lines.append(f"![Screenshot]({sc.get('href', sc_path)})")

            lines += ["", "</details>", ""]

    # ── Performance section (if perf tests ran) ────────────────────────────────
    perf_tests = [t for t in tests if "perf" in t["suite"].lower() or "performance" in t["title"].lower()]
    if perf_tests:
        lines += [
            "---",
            "",
            "## Performance Metrics",
            "",
            "| Metric | Threshold | Status |",
            "|--------|-----------|--------|",
            "| LCP (Largest Contentful Paint) | configured via `PERF_LCP_MS` | *(see test output)* |",
            "| CLS (Cumulative Layout Shift) | configured via `PERF_CLS` | *(see test output)* |",
            "| Response Time | configured via `PERF_RESPONSE_MS` | *(see test output)* |",
            "",
        ]

    # ── Accessibility section ──────────────────────────────────────────────────
    a11y_tests = [t for t in tests if "a11y" in t["suite"].lower() or "accessibility" in t["title"].lower()]
    if a11y_tests:
        a11y_failed = [t for t in a11y_tests if t["status"] == "failed"]
        lines += [
            "---",
            "",
            "## Accessibility",
            "",
            f"- Tests run: {len(a11y_tests)}",
            f"- Violations detected: {len(a11y_failed)}",
            "",
        ]
        if a11y_failed:
            lines += ["**Failed accessibility checks:**", ""]
            for t in a11y_failed:
                lines.append(f"- ❌ {t['title']}: `{clean_text(t['error'])[:200]}`")
            lines.append("")

    # ── AI Recommendations ─────────────────────────────────────────────────────
    lines += ["---", "", "## AI Recommendations", ""]
    if ai_recommendations:
        lines.append(ai_recommendations)
    else:
        failed_tests = [t for t in tests if t["status"] in ("failed", "flaky")]
        if not failed_tests:
            lines.append("✅ All tests passed — no issues to address.")
        else:
            lines += [
                "Run with `--ai-recommendations` flag to get Claude-generated suggestions.",
                "",
                "**Quick diagnosis based on failure patterns:**",
                "",
            ]
            for t in failed_tests[:5]:
                err = clean_text(t["error"])
                if "TimeoutError" in err or "timeout" in err.lower():
                    lines.append(f"- **{t['title']}**: Timeout — consider using `waitFor` or increasing timeout for flaky elements")
                elif "locator" in err.lower() or "selector" in err.lower():
                    lines.append(f"- **{t['title']}**: Selector issue — switch to `getByRole` or `getByLabel`")
                elif "net::" in err or "ERR_CONNECTION" in err:
                    lines.append(f"- **{t['title']}**: Network error — verify server is running and `baseURL` is set")
                else:
                    lines.append(f"- **{t['title']}**: {err[:120]}")
    lines.append("")

    # ── CI/CD snippet ──────────────────────────────────────────────────────────
    lines += [
        "---",
        "",
        "## CI/CD Integration",
        "",
        "See `references/ci_templates.md` for full pipeline configurations.",
        "",
        "**Quick GitHub Actions snippet:**",
        "",
        "```yaml",
        "- name: Run Playwright Audit",
        "  uses: microsoft/playwright-github-action@v1",
        "- run: bash scripts/run_audit.sh",
        "  env:",
        "    BASE_URL: ${{ secrets.STAGING_URL }}",
        "- uses: actions/upload-artifact@v4",
        "  if: always()",
        "  with:",
        "    name: playwright-report",
        "    path: playwright-report/",
        "```",
        "",
        "---",
        "",
        f"*Generated by playwright-auditor · {now}*",
    ]

    return "\n".join(lines)


def build_html_report(payload: dict, include_attachments: bool) -> str:
    stats = payload["stats"]
    suites = payload["suites"]
    failures = [
        test
        for suite in suites
        for test in suite["tests"]
        if test["status"] in ("failed", "flaky")
    ]

    def esc(value: str) -> str:
        return html.escape(str(value))

    cards = f"""
    <section class="cards">
      <article class="card"><span>Total</span><strong>{stats['total']}</strong></article>
      <article class="card good"><span>Passed</span><strong>{stats['passed']}</strong></article>
      <article class="card bad"><span>Failed</span><strong>{stats['failed']}</strong></article>
      <article class="card muted"><span>Skipped</span><strong>{stats['skipped']}</strong></article>
      <article class="card accent"><span>Pass rate</span><strong>{stats['pass_rate']:.1f}%</strong></article>
    </section>
    """

    suite_sections = []
    for suite in suites:
        rows = []
        for test in suite["tests"]:
            status = esc(test["status"]).upper()
            rows.append(
                "<tr>"
                f"<td>{esc(test['title'])}</td>"
                f"<td class='status {esc(test['status'])}'>{status}</td>"
                f"<td>{test['duration'] / 1000:.1f}s</td>"
                f"<td>{esc(test['browser'])}</td>"
                "</tr>"
            )

        details = []
        for test in suite["tests"]:
            if test["status"] not in ("failed", "flaky"):
                continue
            attachments_html = ""
            if include_attachments:
                attachments = []
                for attachment in test.get("attachments", []):
                    path = attachment.get("path")
                    if path:
                        attachments.append(
                            f"<li><a href='{esc(attachment.get('href', path))}'>{esc(Path(path).name)}</a> "
                            f"<span>{esc(attachment.get('contentType', ''))}</span></li>"
                        )
                attachments_html = f"<ul>{''.join(attachments)}</ul>" if attachments else "<p>No attachments captured.</p>"
            details.append(
                "<details>"
                f"<summary>{esc(test['title'])} ({esc(test['browser'])})</summary>"
                f"<pre>{esc(clean_text(test['error'])[:2000] or 'No error message captured')}</pre>"
                f"{attachments_html}"
                "</details>"
            )

        suite_sections.append(
            "<section class='suite'>"
            f"<h2>{esc(suite['suite'])}</h2>"
            "<table><thead><tr><th>Test</th><th>Status</th><th>Duration</th><th>Browser</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
            f"{''.join(details)}"
            "</section>"
        )

    failure_summary = ""
    if failures:
        items = "".join(
            f"<li><strong>{esc(test['title'])}</strong>: {esc((clean_text(test['error']) or 'No error').splitlines()[0][:220])}</li>"
            for test in failures[:10]
        )
        failure_summary = f"<section class='failures'><h2>Top Failures</h2><ul>{items}</ul></section>"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Playwright Audit Report</title>
  <style>
    :root {{
      --bg: #f4f1ea;
      --ink: #1e2430;
      --muted: #667085;
      --card: #fffdf8;
      --line: #d8d2c6;
      --accent: #0f766e;
      --good: #166534;
      --bad: #b42318;
      --warn: #9a6700;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: "IBM Plex Sans", "Segoe UI", sans-serif; background: var(--bg); color: var(--ink); }}
    main {{ max-width: 1200px; margin: 0 auto; padding: 32px 20px 80px; }}
    h1, h2 {{ margin: 0 0 12px; }}
    p.meta {{ color: var(--muted); margin: 8px 0 0; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin: 24px 0 32px; }}
    .card {{ background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 16px; }}
    .card span {{ display: block; color: var(--muted); font-size: 13px; margin-bottom: 8px; }}
    .card strong {{ font-size: 28px; }}
    .card.good strong {{ color: var(--good); }}
    .card.bad strong {{ color: var(--bad); }}
    .card.accent strong {{ color: var(--accent); }}
    .suite, .failures {{ background: var(--card); border: 1px solid var(--line); border-radius: 18px; padding: 18px; margin-top: 18px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
    th, td {{ text-align: left; border-bottom: 1px solid var(--line); padding: 10px 8px; vertical-align: top; }}
    th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
    .status.passed {{ color: var(--good); font-weight: 700; }}
    .status.failed {{ color: var(--bad); font-weight: 700; }}
    .status.flaky {{ color: var(--warn); font-weight: 700; }}
    .status.skipped {{ color: var(--muted); font-weight: 700; }}
    details {{ margin-top: 14px; border-top: 1px dashed var(--line); padding-top: 14px; }}
    summary {{ cursor: pointer; font-weight: 600; }}
    pre {{ white-space: pre-wrap; word-break: break-word; background: #221f1a; color: #f8f5ee; padding: 14px; border-radius: 12px; overflow: auto; }}
    a {{ color: var(--accent); }}
    ul {{ padding-left: 20px; }}
  </style>
</head>
<body>
  <main>
    <h1>Playwright Audit Report</h1>
    <p class="meta">URL: {esc(payload['base_url'] or '(not set)')} · Playwright: {esc(payload['playwright_version'])} · Generated: {esc(payload['generated_at'])}</p>
    {cards}
    {failure_summary}
    {''.join(suite_sections)}
  </main>
</body>
</html>"""


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate a Markdown audit report from Playwright JSON results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--input", required=True, help="Path to Playwright JSON results file")
    parser.add_argument("--output", help="Markdown output path (default: audit-report-{TIMESTAMP}.md)")
    parser.add_argument("--html-output", help="HTML output path")
    parser.add_argument("--json-output", help="JSON summary output path")
    parser.add_argument("--all-formats", action="store_true",
                        help="Write Markdown, HTML, and JSON summary files together")
    parser.add_argument("--ai-recommendations", action="store_true",
                        help="Call Claude API for AI improvement suggestions")
    parser.add_argument("--embed-screenshots", action="store_true",
                        help="Embed screenshots as base64 in the report")
    parser.add_argument("--attachments-mode", choices=["links", "none"], default="links",
                        help="Whether reports should include links to raw evidence artifacts")
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", ""),
                        help="Base URL that was tested")
    args = parser.parse_args()

    print("\n[playwright-auditor] Generating audit report...\n")

    # Load results
    input_path = Path(args.input).resolve()
    results_data = load_results(args.input)

    # Extract all tests
    tests = []
    for suite in results_data.get("suites", []):
        extract_tests(suite, tests)

    if not tests:
        print("[!] No test results found in the JSON file.")
        sys.exit(0)

    stats = compute_stats(tests)

    print(f"  Found {stats['total']} tests across {len(set(t['suite'] for t in tests))} suites")
    print(f"  Pass rate: {stats['pass_rate']:.1f}%")

    report_dir_candidates = [
        Path(value).resolve().parent
        for value in (args.output, args.html_output, args.json_output)
        if value
    ]
    report_dir = report_dir_candidates[0] if report_dir_candidates else None
    rewrite_attachments_for_reports(tests, input_path, report_dir)

    # AI recommendations
    ai_recommendations = None
    if args.ai_recommendations:
        print("  Fetching AI recommendations from Claude...")
        ai_recommendations = get_ai_recommendations(tests, stats)

    # Build report
    report = build_report(
        tests=tests,
        stats=stats,
        results_data=results_data,
        embed_screenshots=args.embed_screenshots,
        ai_recommendations=ai_recommendations,
        base_url=args.base_url,
        include_attachments=args.attachments_mode == "links",
    )
    payload = build_summary_payload(
        tests=tests,
        stats=stats,
        results_data=results_data,
        base_url=args.base_url,
    )
    html_report = build_html_report(payload, include_attachments=args.attachments_mode == "links")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = args.output or f"audit-report-{timestamp}.md"
    html_output = args.html_output
    json_output = args.json_output

    if args.all_formats:
      base_stem = Path(output_path).with_suffix("")
      html_output = html_output or f"{base_stem}.html"
      json_output = json_output or f"{base_stem}.json"

    Path(output_path).write_text(report)

    if html_output:
        Path(html_output).write_text(html_report)
    if json_output:
        Path(json_output).write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    print(f"\n[✓] Markdown report written to {output_path}")
    if html_output:
        print(f"[✓] HTML report written to {html_output}")
    if json_output:
        print(f"[✓] JSON summary written to {json_output}")
    print(f"    {stats['passed']} passed · {stats['failed']} failed · {stats['pass_rate']:.1f}% pass rate\n")


if __name__ == "__main__":
    main()

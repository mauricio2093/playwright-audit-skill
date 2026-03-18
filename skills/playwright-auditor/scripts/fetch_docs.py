#!/usr/bin/env python3
"""
fetch_docs.py — Playwright Documentation Fetcher & Cache Manager
=================================================================
Downloads, parses, and caches Playwright documentation from official
sources. Extracts API references, CLI commands, and best practices into
a structured Markdown cheatsheet for use during test authoring.

Usage:
    python scripts/fetch_docs.py --all
    python scripts/fetch_docs.py --section locators
    python scripts/fetch_docs.py --section assertions
    python scripts/fetch_docs.py --section network
    python scripts/fetch_docs.py --section auth
    python scripts/fetch_docs.py --section cli
    python scripts/fetch_docs.py --help

Requirements:
    pip install requests beautifulsoup4 markdownify

Output:
    references/playwright_api_cheatsheet.md
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("[✗] Missing dependencies. Run: pip install requests beautifulsoup4")
    sys.exit(1)

# ── Constants ─────────────────────────────────────────────────────────────────
BASE_URL = "https://playwright.dev"
DOCS_BASE = "https://playwright.dev/docs"
GITHUB_FALLBACK = "https://raw.githubusercontent.com/microsoft/playwright/main/docs/api/python/api.md"
OUTPUT_DIR = Path("references")
OUTPUT_FILE = OUTPUT_DIR / "playwright_api_cheatsheet.md"
CACHE_FILE = OUTPUT_DIR / ".docs_cache.json"

SECTIONS = {
    "locators": "/docs/locators",
    "assertions": "/docs/test-assertions",
    "network": "/docs/network",
    "auth": "/docs/auth",
    "cli": "/docs/test-cli",
    "configuration": "/docs/test-configuration",
    "fixtures": "/docs/test-fixtures",
    "screenshots": "/docs/screenshots",
}

HEADERS = {
    "User-Agent": "playwright-auditor-skill/1.0 (documentation fetcher)",
    "Accept": "text/html,application/xhtml+xml",
}


# ── Core fetching ─────────────────────────────────────────────────────────────

def fetch_page(url: str, timeout: int = 15) -> str | None:
    """Fetch a URL and return its HTML content, or None on failure."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        print(f"  [!] Failed to fetch {url}: {e}")
        return None


def extract_version(soup: BeautifulSoup) -> str:
    """Try to extract the Playwright version from the docs page."""
    # Version often appears in meta tags or nav
    meta = soup.find("meta", {"name": "playwright-version"})
    if meta and meta.get("content"):
        return meta["content"]
    # Fallback: look for version in page text
    for tag in soup.find_all(["span", "a"], string=lambda t: t and "v1." in t):
        text = tag.get_text(strip=True)
        if text.startswith("v1."):
            return text
    return "latest"


def html_to_markdown(soup: BeautifulSoup, section_name: str) -> str:
    """Convert a docs page's main content to clean Markdown."""
    lines = []

    # Find the main content area
    main = (
        soup.find("article")
        or soup.find("main")
        or soup.find(class_="theme-doc-markdown")
        or soup.body
    )

    if not main:
        return f"*Could not extract content for section: {section_name}*\n"

    # Walk through meaningful tags
    for tag in main.find_all(
        ["h1", "h2", "h3", "h4", "p", "pre", "ul", "ol", "li", "table", "code"],
        recursive=True,
    ):
        name = tag.name
        text = tag.get_text(strip=True)

        if not text:
            continue

        if name == "h1":
            lines.append(f"\n# {text}\n")
        elif name == "h2":
            lines.append(f"\n## {text}\n")
        elif name == "h3":
            lines.append(f"\n### {text}\n")
        elif name == "h4":
            lines.append(f"\n#### {text}\n")
        elif name == "pre":
            code = tag.get_text()
            lang = "typescript"
            code_tag = tag.find("code")
            if code_tag and code_tag.get("class"):
                classes = " ".join(code_tag.get("class", []))
                if "python" in classes:
                    lang = "python"
                elif "bash" in classes or "sh" in classes:
                    lang = "bash"
            lines.append(f"\n```{lang}\n{code}\n```\n")
        elif name == "p":
            if tag.find_parent(["pre", "code"]):
                continue
            lines.append(f"\n{text}\n")
        elif name == "li":
            if tag.find_parent(["pre", "code"]):
                continue
            lines.append(f"- {text}")

    return "\n".join(lines)


# ── Cache management ──────────────────────────────────────────────────────────

def load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_cache(cache: dict):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, indent=2))


# ── Section fetchers ──────────────────────────────────────────────────────────

def fetch_section(name: str, path: str, cache: dict, force: bool = False) -> str:
    """Fetch a single documentation section, using cache if available."""
    cache_key = name
    cached = cache.get(cache_key)

    # Use cache if fresh (< 24h) and not forced
    if cached and not force:
        age_h = (time.time() - cached.get("timestamp", 0)) / 3600
        if age_h < 24:
            print(f"  [cache] {name} (age: {age_h:.1f}h)")
            return cached["content"]

    url = urljoin(BASE_URL, path)
    print(f"  [fetch] {name} → {url}")
    html = fetch_page(url)

    if html is None:
        print(f"  [!] Falling back to cache for {name}")
        return cached["content"] if cached else f"*Section {name} unavailable*\n"

    soup = BeautifulSoup(html, "html.parser")
    content = html_to_markdown(soup, name)

    cache[cache_key] = {
        "content": content,
        "timestamp": time.time(),
        "url": url,
    }
    return content


def fetch_playwright_version() -> str:
    """Fetch the current stable Playwright version from npm registry."""
    try:
        resp = requests.get(
            "https://registry.npmjs.org/@playwright/test/latest",
            timeout=10,
            headers=HEADERS,
        )
        data = resp.json()
        return data.get("version", "unknown")
    except Exception:
        return "unknown"


# ── Report assembly ───────────────────────────────────────────────────────────

def build_cheatsheet(sections_content: dict[str, str], version: str) -> str:
    """Assemble all sections into a single cheatsheet document."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    header = f"""# Playwright API Cheatsheet

> **Version:** `@playwright/test@{version}`  
> **Fetched:** {now}  
> **Source:** https://playwright.dev/docs

---

## Quick Selector Priority Guide

Prefer selectors in this order (most → least resilient):

1. `getByRole('button', {{ name: 'Submit' }})` — ARIA role + accessible name
2. `getByLabel('Email address')` — visible label text
3. `getByPlaceholder('Search...')` — placeholder attribute
4. `getByText('Welcome')` — visible text content
5. `getByTestId('submit-btn')` — `data-testid` attribute
6. `locator('css=.submit')` — CSS selector (last resort)
7. `locator('xpath=//button')` — XPath (avoid when possible)

---

## Most-Used Assertions

```typescript
// Visibility
await expect(locator).toBeVisible();
await expect(locator).toBeHidden();

// Text content
await expect(locator).toHaveText('Expected text');
await expect(locator).toContainText('partial match');

// Value and state
await expect(locator).toHaveValue('input value');
await expect(locator).toBeChecked();
await expect(locator).toBeDisabled();
await expect(locator).toBeEnabled();

// URL and title
await expect(page).toHaveURL('/dashboard');
await expect(page).toHaveTitle(/Dashboard/);

// Count
await expect(locator).toHaveCount(3);

// Soft assertion (non-blocking — collects all failures)
await expect.soft(locator).toHaveText('text');
```

---

"""

    sections_order = ["locators", "assertions", "network", "auth", "cli",
                      "configuration", "fixtures", "screenshots"]

    body = ""
    for section in sections_order:
        if section in sections_content:
            body += f"\n---\n\n## Section: {section.title()}\n\n"
            body += sections_content[section]

    return header + body


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Fetch and cache Playwright documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--section",
        choices=list(SECTIONS.keys()),
        help="Fetch a specific documentation section",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Fetch all sections",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore cache and re-fetch all sections",
    )
    args = parser.parse_args()

    if not args.section and not args.all:
        parser.print_help()
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cache = load_cache()

    # Determine which sections to fetch
    if args.all:
        to_fetch = SECTIONS
    else:
        to_fetch = {args.section: SECTIONS[args.section]}

    print(f"\n[playwright-auditor] Fetching {len(to_fetch)} documentation section(s)...\n")

    # Fetch version
    version = fetch_playwright_version()
    print(f"  [info] Latest @playwright/test version: {version}\n")

    # Fetch each section
    sections_content = {}
    for name, path in to_fetch.items():
        sections_content[name] = fetch_section(name, path, cache, force=args.force)

    save_cache(cache)

    # Build and write cheatsheet
    if args.all:
        cheatsheet = build_cheatsheet(sections_content, version)
        OUTPUT_FILE.write_text(cheatsheet)
        print(f"\n[✓] Cheatsheet written to {OUTPUT_FILE}")
    else:
        # Append / update single section
        section_name = args.section
        section_md = f"\n\n---\n\n## Section: {section_name.title()}\n\n"
        section_md += sections_content[section_name]

        if OUTPUT_FILE.exists():
            existing = OUTPUT_FILE.read_text()
            marker = f"## Section: {section_name.title()}"
            if marker in existing:
                # Replace existing section
                start = existing.index(marker)
                next_section = existing.find("\n---\n", start + 1)
                if next_section == -1:
                    updated = existing[:start] + section_md.lstrip()
                else:
                    updated = existing[:start] + section_md.lstrip() + existing[next_section:]
                OUTPUT_FILE.write_text(updated)
            else:
                OUTPUT_FILE.write_text(existing + section_md)
        else:
            OUTPUT_FILE.write_text(f"# Playwright API Cheatsheet\n{section_md}")

        print(f"\n[✓] Section '{section_name}' written to {OUTPUT_FILE}")

    print(f"[✓] Cache saved to {CACHE_FILE}")
    print("\nDone. Use this cheatsheet when writing or debugging tests.\n")


if __name__ == "__main__":
    main()

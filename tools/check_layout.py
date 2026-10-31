#!/usr/bin/env python3
"""Check the source -> Markdown -> test ownership contract.

No network, third-party dependencies, or environment installation required.
Python 3.11+ (tomllib).
"""
from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path


def check_layout(root: Path, config: dict) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    if config.get("schema_version") != 1:
        errors.append("Unsupported project-layout.toml schema version")
    entries = config.get("module")
    if not isinstance(entries, list) or not entries:
        return errors + ["No modules declared in project-layout.toml"]
    owned: dict[str, str] = {}
    seen_ids: set[str] = set()
    expected_checks = {"frontend-build", "backend-tests", "rust-tests"}
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("Manifest module must be a table")
            continue
        mid = entry.get("id")
        if not isinstance(mid, str) or not mid.strip() or mid in seen_ids:
            errors.append(f"Invalid or duplicate module id: {mid!r}")
            continue
        seen_ids.add(mid)
        sources = entry.get("source")
        docs = entry.get("doc")
        tests = entry.get("tests")
        verify = entry.get("verification")
        if verify not in expected_checks:
            errors.append(f"{mid}: unknown verification type {verify!r}")
        if not isinstance(sources, list) or not sources:
            errors.append(f"{mid}: missing source paths")
            continue
        if not isinstance(docs, str) or not docs.endswith(".md"):
            errors.append(f"{mid}: one Markdown document path is required")
        if not isinstance(tests, list) or (verify in ("backend-tests", "rust-tests") and not tests):
            errors.append(f"{mid}: backend and Rust modules require test paths")
            tests = []
        for role, paths in (("source", sources), ("doc", [docs]), ("test", tests)):
            for raw in paths:
                if not isinstance(raw, str) or not raw or raw.startswith("/"):
                    errors.append(f"{mid}: invalid {role} path {raw!r}")
                    continue
                path = Path(raw)
                if ".." in path.parts or path.is_absolute() or path.drive:
                    errors.append(f"{mid}: {role} path escapes repository: {raw!r}")
                    continue
                resolved = (root / path).resolve()
                if not resolved.is_relative_to(root) or not resolved.is_file():
                    errors.append(f"{mid}: missing or unsafe {role} file: {raw}")
                    continue
                if role == "source":
                    if raw in owned:
                        errors.append(f"{mid}: source also owned by {owned[raw]}: {raw}")
                    else:
                        owned[raw] = mid
        if verify == "backend-tests" and any(not isinstance(t, str) or not t.startswith("backend/tests/") for t in tests):
            errors.append(f"{mid}: backend test path must reside in backend/tests/")
        if verify == "rust-tests" and not any(
            isinstance(t, str) and t.startswith("scheduler/tests/") for t in tests
        ):
            errors.append(f"{mid}: Rust module requires scheduler/tests/ coverage")
    # Prevent backend modules or newly added Image Studio files from silently
    # escaping the source/document/test ownership index.
    for folder in ("backend/lumacarve_server", "backend/lumacarve_runtime"):
        location = root / folder
        if not location.is_dir():
            errors.append(f"Missing backend package: {folder}")
            continue
        for file in location.rglob("*.py"):
            if file.name == "__init__.py":
                continue
            name = file.relative_to(root).as_posix()
            if name not in owned:
                errors.append(f"Unregistered backend source: {name}")
    rust_src = root / "scheduler/src"
    if rust_src.exists():
        for file in rust_src.rglob("*.rs"):
            name = file.relative_to(root).as_posix()
            if name not in owned:
                errors.append(f"Unregistered Rust source: {name}")
    studio = root / "frontend/src/features/image-studio"
    if studio.exists():
        for file in studio.iterdir():
            if file.is_file() and file.suffix in (".ts", ".tsx", ".css"):
                name = file.relative_to(root).as_posix()
                if name not in owned:
                    errors.append(f"Unregistered Image Studio source: {name}")
    ignore = root / ".gitignore"
    if not ignore.exists():
        errors.append("Missing .gitignore")
    else:
        content = ignore.read_text(encoding="utf-8")
        for must_ignore in (".venv/", "LumaCarveData/"):
            if must_ignore not in content.splitlines():
                errors.append(f"Sensitive local directory not ignored: {must_ignore}")
    return errors


def run(root: Path, manifest: Path) -> list[str]:
    with manifest.open("rb") as stream:
        data = tomllib.load(stream)
    return check_layout(root, data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check LumaCarve module ownership and Markdown")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    errors = run(args.root, args.root / "project-layout.toml")
    if errors:
        print("LumaCarve layout check FAILED:", file=sys.stderr)
        for error in errors:
            print(" - " + error, file=sys.stderr)
        return 1
    print("LumaCarve layout OK: all registered sources, docs and tests exist")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

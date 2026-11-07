#!/usr/bin/env python3
"""Offline release metadata check. Uses only Python 3.11 standard library."""
from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from datetime import date
from pathlib import Path

VERSIONS = {
    "frontend/package.json": "json",
    "frontend/src-tauri/tauri.conf.json": "json",
    "frontend/src-tauri/Cargo.toml": "toml",
}
FORMATS = {"Windows x64": ".zip", "Linux x64": ".AppImage"}
STATES = {"CI 已验证", "代码已接入，GPU 未验证", "未打包", "未实现", "仅规划"}


def check_release_status(root: Path, data: dict) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    if data.get("schema_version") != 1:
        errors.append("Unsupported release status schema")
    expected = data.get("source_version")
    if not isinstance(expected, str) or not re.fullmatch(r"\d+\.\d+\.\d+", expected):
        errors.append("Invalid source_version")
    try:
        date.fromisoformat(data["checked_on"])
    except (KeyError, TypeError, ValueError):
        errors.append("Invalid checked_on ISO date")

    for path, kind in VERSIONS.items():
        try:
            if kind == "toml":
                with (root / path).open("rb") as stream:
                    current = tomllib.load(stream)["package"]["version"]
            else:
                current = json.loads((root / path).read_text(encoding="utf-8"))["version"]
        except (OSError, KeyError, ValueError, tomllib.TOMLDecodeError):
            errors.append(f"Could not read version from {path}")
            continue
        if current != expected:
            errors.append(f"Version drift: {path} = {current}; expected {expected}")

    releases = data.get("releases")
    if not isinstance(releases, list):
        return errors + ["Missing releases list"]
    seen: set[str] = set()
    for rel in releases:
        if not isinstance(rel, dict):
            errors.append("Invalid release record")
            continue
        platform = rel.get("platform")
        if platform not in FORMATS or platform in seen:
            errors.append(f"Invalid or duplicate platform {platform}")
            continue
        seen.add(platform)
        tag = rel.get("tag")
        version = rel.get("version")
        asset = rel.get("asset")
        if not isinstance(tag, str) or not isinstance(version, str) or not tag.startswith("v" + version + "-"):
            errors.append(f"Invalid tag for {platform}")
        if not isinstance(asset, str) or not asset.endswith(FORMATS[platform]) or "/" in asset:
            errors.append(f"Non-portable release asset for {platform}")
        if not isinstance(rel.get("checksum"), str) or not rel["checksum"].startswith("SHA256SUMS"):
            errors.append(f"Missing SHA256 manifest for {platform}")
        if not re.fullmatch(r"[a-f0-9]{40}", str(rel.get("source_sha", ""))):
            errors.append(f"Invalid source SHA for {platform}")
    if seen != set(FORMATS):
        errors.append("Release history must distinguish Windows and Linux")

    capabilities = data.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        return errors + ["Missing capabilities"]
    seen_ids: set[str] = set()
    for cap in capabilities:
        if not isinstance(cap, dict):
            errors.append("Invalid capability record")
            continue
        cid = cap.get("id")
        if not isinstance(cid, str) or cid in seen_ids:
            errors.append(f"Invalid or duplicate capability ID: {cid}")
        seen_ids.add(cid)
        if cap.get("state") not in STATES:
            errors.append(f"Invalid capability state for {cid}")
        if not isinstance(cap.get("name"), str) or not isinstance(cap.get("detail"), str):
            errors.append(f"Missing capability description for {cid}")
        evidence = cap.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"Missing evidence paths for {cid}")
            continue
        for item in evidence:
            if not isinstance(item, str) or Path(item).is_absolute() or ".." in Path(item).parts:
                errors.append(f"Unsafe evidence path for {cid}")
            elif not (root / item).is_file():
                errors.append(f"Missing evidence file for {cid}: {item}")

    return errors


def run(root: Path) -> list[str]:
    try:
        data = json.loads((root / "docs/release-status.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ["Missing/invalid docs/release-status.json"]
    issues = check_release_status(root, data)
    page = root / "docs/release-status.md"
    if not page.is_file():
        issues.append("Missing docs/release-status.md")
    else:
        text = page.read_text(encoding="utf-8")
        for rel in data.get("releases", []):
            if isinstance(rel, dict):
                for field in ("tag", "asset"):
                    if isinstance(rel.get(field), str) and rel[field] not in text:
                        issues.append(f"Markdown missing {field}: {rel[field]}")
        for cap in data.get("capabilities", []):
            if isinstance(cap, dict) and (cap.get("name") not in text or cap.get("state") not in text):
                issues.append(f"Markdown missing capability {cap.get('id')}")
        if data.get("source_version") not in text:
            issues.append("Markdown missing source_version")
    readme = root / "README.md"
    if not readme.is_file() or "docs/release-status.md" not in readme.read_text(encoding="utf-8"):
        issues.append("README.md must link to docs/release-status.md")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify source and release documentation")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    errors = run(args.root)
    for error in errors:
        print("ERROR: " + error, file=sys.stderr)
    if errors:
        return 1
    print("Release/source status OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Local model discovery. Never execute model code or follow symlink escapes."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

KNOWN_FAMILIES = ("qwen-image-2.1", "anima-base-1", "moss-image", "krea-2-raw")
CATEGORIES = ("dit", "te", "vae", "lora", "checkpoints")
SUFFIXES = {".safetensors"}


@dataclass(frozen=True, slots=True)
class ModelFile:
    id: str
    category: str
    name: str
    relative_path: str
    size_bytes: int


def scan_models(root: Path, limit: int = 3000) -> list[ModelFile]:
    root = root.resolve()
    results: list[ModelFile] = []
    for category in CATEGORIES:
        directory = root / category
        if not directory.exists():
            continue
        # rglob paths may include symlink entries; resolved target MUST stay below model root.
        for item in directory.rglob("*"):
            if len(results) >= limit:
                return results
            if item.suffix.lower() not in SUFFIXES or not item.is_file():
                continue
            resolved = item.resolve()
            if not resolved.is_relative_to(root) or item.is_symlink():
                continue
            relative = item.relative_to(root).as_posix()
            stat = resolved.stat()
            results.append(ModelFile(
                id=relative, category=category, name=item.name,
                relative_path=relative, size_bytes=stat.st_size,
            ))
    return sorted(results, key=lambda model: (model.category, model.name.lower(), model.id))

"""Explicit model downloads with safe destinations and in-process progress state.

The service never downloads on import, health check or workflow validation.
Only supported registry IDs are accepted; no arbitrary local path is permitted.
"""
from __future__ import annotations

import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import Settings

MODEL_CATALOG = {
    "qwen-image-2.1": {
        "title": "Qwen-Image-2.1",
        "cn": "Qwen/Qwen-Image-2.1",
        "global": "Qwen/Qwen-Image-2.1",
        "license_note": "qwen-research; review terms before downloading",
    },
    "anima-base-1": {
        "title": "Anima Base 1.0",
        "cn": "circlestone-labs/Anima",
        "global": "circlestone-labs/Anima-Base-v1.0-Diffusers",
        "cn_format": "comfyui_split",
        "global_format": "diffusers_modular",
        "default_cn_revision": "master",
        "default_global_revision": "main",
        "cn_patterns": [
            "split_files/diffusion_models/anima-base-v1.0.safetensors",
            "split_files/text_encoders/qwen_3_06b_base.safetensors",
            "split_files/vae/qwen_image_vae.safetensors",
            "LICENSE.md", "README.md",
        ],
        "license_note": "CircleStone Labs Non-Commercial License; NVIDIA Open Model License may also apply",
    },
    "moss-image-base": {
        "title": "MOSS-Image Base",
        "cn": "openmoss/MOSS-Image-Base",
        "global": "OpenMOSS-Team/MOSS-Image-Base",
        "license_note": "apache-2.0; review model card",
    },
}


class ModelDownloadError(ValueError):
    pass


def validate_revision(revision: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,90}", revision):
        raise ModelDownloadError("Invalid revision; use branch, tag or commit ID")
    if revision in (".", "..") or ".." in revision:
        raise ModelDownloadError("Unsafe revision")
    return revision


def model_destination(settings: Settings, model_id: str, revision: str, *, provider: str | None = None) -> Path:
    if model_id not in MODEL_CATALOG:
        raise ModelDownloadError("Unsupported model ID; use the published model catalog")
    revision = validate_revision(revision)
    if model_id == "anima-base-1":
        if provider not in ("modelscope", "huggingface"):
            raise ModelDownloadError("Anima downloads require an explicit provider")
        return settings.models_dir / "bundles" / model_id / provider / revision
    return settings.models_dir / "bundles" / model_id / revision


def download_snapshot(provider: str, repo_id: str, revision: str, destination: Path, *, allow_patterns: list[str] | None = None) -> Path:
    """Network boundary; imported lazily to keep the API lightweight.

    Hub SDK validates remote hashes when metadata is available. Downloads are
    resumable within .partial; completion is marked only after SDK returns.
    """
    if provider == "modelscope":
        from modelscope_hub import HubApi
        client = HubApi(endpoint="https://modelscope.cn")
        downloaded = client.download_repo(
            repo_id, "model", revision=revision, local_dir=destination,
            allow_patterns=allow_patterns, max_workers=4
        )
    elif provider == "huggingface":
        from huggingface_hub import snapshot_download
        downloaded = snapshot_download(
            repo_id=repo_id, revision=revision, local_dir=destination,
            max_workers=4, allow_patterns=allow_patterns,
        )
    else:
        raise ModelDownloadError("Unsupported provider")
    return Path(downloaded)


@dataclass(slots=True)
class DownloadStatus:
    id: str
    model_id: str
    provider: str
    repository: str
    revision: str
    state: str = "queued"
    error: str | None = None
    destination: str | None = None
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None

    def json(self) -> dict:
        return asdict(self)


class ModelDownloadManager:
    """One active download at a time to bound disk and network contention."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._lock = threading.RLock()
        self._jobs: dict[str, DownloadStatus] = {}
        self._active: str | None = None

    def catalog(self) -> list[dict]:
        region = self.settings.resolved_download_region
        return [
            {
                "id": key, "title": item["title"],
                "provider": "modelscope" if region == "cn" else "huggingface",
                "repository": item[region], "license_note": item["license_note"],
                "format": item.get(f"{region}_format", "unknown"),
                "supports_lumacarve_inference": key == "anima-base-1" and region == "global",
            }
            for key, item in MODEL_CATALOG.items()
        ]

    def get(self, job_id: str) -> dict:
        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(job_id)
            return self._jobs[job_id].json()

    def submit(self, model_id: str, revision: str | None = None, *, provider: str | None = None) -> dict:
        if not self.settings.allow_model_download:
            raise PermissionError("Model downloads disabled; set LUMACARVE_ALLOW_MODEL_DOWNLOAD=1")
        region = self.settings.resolved_download_region
        selected = provider or ("modelscope" if region == "cn" else "huggingface")
        if selected not in ("modelscope", "huggingface"):
            raise ModelDownloadError("Unsupported provider")
        if model_id not in MODEL_CATALOG:
            raise ModelDownloadError("Unsupported model ID")
        entry = MODEL_CATALOG[model_id]
        variant = "cn" if selected == "modelscope" else "global"
        revision = revision or entry.get(f"default_{variant}_revision", "master")
        destination = model_destination(self.settings, model_id, revision, provider=selected)
        repository = entry[variant]
        with self._lock:
            if self._active is not None:
                raise RuntimeError("Another model download is in progress")
            if (destination / ".lumacarve-complete").is_file():
                raise FileExistsError("This model revision is already installed")
            job = DownloadStatus(uuid.uuid4().hex, model_id, selected, repository, revision)
            self._jobs[job.id] = job
            self._active = job.id
            threading.Thread(target=self._run, args=(job.id,), daemon=True, name="model-download").start()
            return job.json()

    def _run(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.state = "running"
            destination = model_destination(
                self.settings, job.model_id, job.revision, provider=job.provider
            )
        partial = destination.parent / (destination.name + ".partial")
        try:
            partial.mkdir(parents=True, exist_ok=True)
            entry = MODEL_CATALOG[job.model_id]
            patterns = entry.get("cn_patterns") if job.provider == "modelscope" else None
            if patterns:
                download_snapshot(
                    job.provider, job.repository, job.revision, partial,
                    allow_patterns=patterns,
                )
            else:
                download_snapshot(job.provider, job.repository, job.revision, partial)
            # SDK has completed; an unfinished snapshot must never be advertised.
            if not any(p.is_file() for p in partial.rglob("*")):
                raise ModelDownloadError("Download returned an empty snapshot")
            if job.model_id == "anima-base-1":
                if job.provider == "huggingface":
                    expected = ["modular_model_index.json", "transformer", "vae",
                                "text_encoder", "text_conditioner", "tokenizer", "t5_tokenizer"]
                    if not (partial / expected[0]).is_file() or any(
                        not (partial / name).is_dir() for name in expected[1:]
                    ):
                        raise ModelDownloadError("Anima ModularPipeline snapshot is incomplete")
                    for component in ("transformer", "vae", "text_encoder", "text_conditioner"):
                        if not any(
                            p.is_file() for p in (partial / component).rglob("*.safetensors")
                        ):
                            raise ModelDownloadError(f"Anima weight files missing: {component}")
                else:
                    required = [
                        "split_files/diffusion_models/anima-base-v1.0.safetensors",
                        "split_files/text_encoders/qwen_3_06b_base.safetensors",
                        "split_files/vae/qwen_image_vae.safetensors",
                    ]
                    if any(not (partial / name).is_file() for name in required):
                        raise ModelDownloadError("Anima ComfyUI model components are incomplete")
            if destination.exists():
                raise ModelDownloadError("Destination already exists; refusing to overwrite")
            partial.rename(destination)
            (destination / ".lumacarve-complete").write_text(
                f"{job.provider}\n{job.repository}\n{job.revision}\n", encoding="utf-8"
            )
            with self._lock:
                job.state = "completed"
                job.destination = str(destination)
        except Exception as exc:
            # Keep .partial for resuming on the next attempt.
            with self._lock:
                job.state = "failed"
                job.error = str(exc)[:450]
        finally:
            with self._lock:
                job.finished_at = time.time()
                self._active = None

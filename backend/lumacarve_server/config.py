"""Explicit localhost configuration and on-disk workspace layout."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")


@dataclass(frozen=True, slots=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parents[2] / "LumaCarveData")
    host: str = "127.0.0.1"
    port: int = 8000
    allowed_origins: tuple[str, ...] = DEFAULT_ORIGINS
    max_asset_bytes: int = 25 * 1024 * 1024
    max_image_pixels: int = 40_000_000
    max_pending_jobs: int = 16
    inference_offload: str = "auto"  # auto | full | model_cpu
    allow_model_download: bool = False

    def __post_init__(self) -> None:
        if self.max_asset_bytes < 1024 or self.max_image_pixels < 1024:
            raise ValueError("Asset limits must be positive")
        if self.max_pending_jobs < 1 or self.max_pending_jobs > 256:
            raise ValueError("max_pending_jobs outside supported range")
        if self.inference_offload not in ("auto", "full", "model_cpu"):
            raise ValueError("inference_offload must be auto, full or model_cpu")
        if not 1 <= self.port <= 65535:
            raise ValueError("Invalid HTTP port")

    @classmethod
    def from_env(cls) -> Settings:
        default = cls()
        origins = os.environ.get("LUMACARVE_ALLOWED_ORIGINS")
        return cls(
            data_dir=Path(os.environ.get("LUMACARVE_DATA_DIR", str(default.data_dir))).expanduser().resolve(),
            host=os.environ.get("LUMACARVE_HOST", default.host),
            port=int(os.environ.get("LUMACARVE_PORT", str(default.port))),
            allowed_origins=tuple(x.strip().rstrip("/") for x in origins.split(",") if x.strip()) if origins is not None else DEFAULT_ORIGINS,
            inference_offload=os.environ.get("LUMACARVE_INFERENCE_OFFLOAD", "auto"),
            allow_model_download=os.environ.get("LUMACARVE_ALLOW_MODEL_DOWNLOAD", "0") == "1",
        )

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "model"

    @property
    def assets_dir(self) -> Path:
        return self.data_dir / "assets"

    @property
    def outputs_dir(self) -> Path:
        return self.data_dir / "outputs"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "jobs.sqlite3"

    def ensure_dirs(self) -> None:
        for directory in (
            self.data_dir, self.models_dir, self.assets_dir, self.outputs_dir,
            *(self.models_dir / kind for kind in ("dit", "te", "vae", "lora", "checkpoints")),
        ):
            directory.mkdir(parents=True, exist_ok=True)

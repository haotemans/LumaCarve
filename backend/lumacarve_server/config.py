"""Explicit localhost configuration and on-disk workspace layout."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .download_sources import resolve_region

DEFAULT_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")


def default_data_dir(repository: Path | None = None) -> Path:
    """New installs use repository root while preserving existing legacy data."""
    root = repository or Path(__file__).resolve().parents[3]
    legacy = root / "backend" / "LumaCarveData"
    return legacy if legacy.exists() else root / "LumaCarveData"


@dataclass(frozen=True, slots=True)
class Settings:
    data_dir: Path = field(default_factory=default_data_dir)
    host: str = "127.0.0.1"
    port: int = 8000
    allowed_origins: tuple[str, ...] = DEFAULT_ORIGINS
    max_asset_bytes: int = 25 * 1024 * 1024
    max_image_pixels: int = 40_000_000
    max_pending_jobs: int = 16
    inference_offload: str = "auto"  # auto | full | model_cpu
    inference_backend: str = "disabled"  # disabled | anima
    anima_model_path: Path | None = None
    anima_triton: str = "off"  # off | experimental; requires compatible CUDA and Triton
    anima_triton_rope: str = "off"  # off | experimental; fuse Anima Cosmos Q/K rotary
    anima_triton_residual: str = "off"  # off | experimental; fuse gated attention/FFN residuals
    anima_triton_ffn: str = "off"  # off | experimental; fused FFN Linear+GELU, full GPU only
    allow_model_download: bool = False
    download_region: str = "auto"   # auto | cn | global; no IP geolocation

    def __post_init__(self) -> None:
        if self.inference_backend not in ("disabled", "anima"):
            raise ValueError("Unsupported inference backend")
        if self.download_region not in ("auto", "cn", "global"):
            raise ValueError("Invalid download region")
        if self.max_asset_bytes < 1024 or self.max_image_pixels < 1024:
            raise ValueError("Asset limits must be positive")
        if self.max_pending_jobs < 1 or self.max_pending_jobs > 256:
            raise ValueError("max_pending_jobs outside supported range")
        if self.inference_offload not in ("auto", "full", "model_cpu"):
            raise ValueError("inference_offload must be auto, full or model_cpu")
        if self.anima_triton not in ("off", "experimental"):
            raise ValueError("anima_triton must be off or experimental")
        if self.anima_triton_rope not in ("off", "experimental"):
            raise ValueError("anima_triton_rope must be off or experimental")
        if self.anima_triton_residual not in ("off", "experimental"):
            raise ValueError("anima_triton_residual must be off or experimental")
        if self.anima_triton_ffn not in ("off", "experimental"):
            raise ValueError("anima_triton_ffn must be off or experimental")
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
            anima_triton=os.environ.get("LUMACARVE_ANIMA_TRITON", "off"),
            anima_triton_rope=os.environ.get("LUMACARVE_ANIMA_TRITON_ROPE", "off"),
            anima_triton_residual=os.environ.get("LUMACARVE_ANIMA_TRITON_RESIDUAL", "off"),
            anima_triton_ffn=os.environ.get("LUMACARVE_ANIMA_TRITON_FFN", "off"),
            inference_backend=os.environ.get("LUMACARVE_INFERENCE_BACKEND", "disabled"),
            anima_model_path=(
                Path(os.environ["LUMACARVE_ANIMA_MODEL_PATH"]).expanduser().resolve()
                if os.environ.get("LUMACARVE_ANIMA_MODEL_PATH") else None
            ),
            allow_model_download=os.environ.get("LUMACARVE_ALLOW_MODEL_DOWNLOAD", "0") == "1",
            download_region=os.environ.get("LUMACARVE_DOWNLOAD_REGION", "auto"),
        )

    @property
    def resolved_download_region(self) -> str:
        return resolve_region(self.download_region)

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "model"

    @property
    def assets_dir(self) -> Path:
        return self.data_dir / "assets"

    @property
    def datasets_dir(self) -> Path:
        return self.data_dir / "datasets"

    @property
    def outputs_dir(self) -> Path:
        return self.data_dir / "outputs"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "jobs.sqlite3"

    def ensure_dirs(self) -> None:
        for directory in (
            self.data_dir, self.models_dir, self.assets_dir, self.outputs_dir, self.datasets_dir,
            *(self.models_dir / kind for kind in ("dit", "te", "vae", "lora", "checkpoints", "bundles")),
        ):
            directory.mkdir(parents=True, exist_ok=True)

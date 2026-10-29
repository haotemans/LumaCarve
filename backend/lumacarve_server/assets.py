"""Image uploads: bounded streaming, Pillow validation, content-addressed persistence."""
from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError, ImageOps

from .config import Settings

ALLOWED_FORMATS = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp"}


class AssetError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Asset:
    id: str
    filename: str
    media_type: str
    width: int
    height: int
    size_bytes: int

    def json(self):
        return asdict(self)


async def store_asset(upload: UploadFile, settings: Settings) -> Asset:
    settings.assets_dir.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256()
    total = 0
    fd, temp_path = tempfile.mkstemp(prefix=".upload-", suffix=".tmp", dir=settings.assets_dir)
    os.close(fd)
    temp = Path(temp_path)
    try:
        with temp.open("wb") as output:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                if total > settings.max_asset_bytes:
                    raise AssetError("Image exceeds configured size limit")
                sha.update(chunk)
                output.write(chunk)
        if total == 0:
            raise AssetError("Empty image")
        try:
            with Image.open(temp) as image:
                if image.format not in ALLOWED_FORMATS:
                    raise AssetError("Only PNG, JPEG and WebP are supported")
                if image.width * image.height > settings.max_image_pixels:
                    raise AssetError("Image dimensions exceed pixel limit")
                image.verify()
            with Image.open(temp) as image:
                image.load()
                width, height = image.size
                fmt = image.format
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise AssetError("Invalid or unsafe image") from exc
        ext = ALLOWED_FORMATS[fmt]
        asset_id = sha.hexdigest()
        target = settings.assets_dir / f"{asset_id}.{ext}"
        if not target.exists():
            os.replace(temp, target)
        return Asset(asset_id, target.name, f"image/{'jpeg' if ext == 'jpg' else ext}", width, height, total)
    finally:
        temp.unlink(missing_ok=True)
        await upload.close()


def locate_asset(settings: Settings, asset_id: str) -> Path:
    if len(asset_id) != 64 or any(ch not in "0123456789abcdef" for ch in asset_id):
        raise AssetError("Invalid asset ID")
    for extension in ("png", "jpg", "webp"):
        path = settings.assets_dir / f"{asset_id}.{extension}"
        if path.is_file() and not path.is_symlink():
            return path
    raise FileNotFoundError(asset_id)

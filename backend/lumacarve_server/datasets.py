"""Persistent training datasets, with image.tags.txt sidecars beside each image.

Files always remain under LumaCarveData/datasets/<dataset-id>/. The index only
stores lightweight metadata; no tensors, models, or GPU resources are loaded.
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from .config import Settings

DATASET_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
ITEM_ID = re.compile(r"^[0-9a-f]{64}$")
FORMATS = {"PNG": ("png", "image/png"), "JPEG": ("jpg", "image/jpeg"), "WEBP": ("webp", "image/webp")}
MAX_CAPTION_CHARS = 20_000


class DatasetError(ValueError):
    pass


class DatasetNotFound(LookupError):
    pass


class DatasetConflict(RuntimeError):
    pass


def validate_dataset_id(identifier: str) -> str:
    if not DATASET_ID.fullmatch(identifier):
        raise DatasetError("Dataset ID must be 1-48 lowercase letters, digits, _ or -")
    return identifier


def validate_caption(value: str) -> str:
    if not isinstance(value, str) or len(value) > MAX_CAPTION_CHARS or "\x00" in value:
        raise DatasetError("Caption must be UTF-8 text of at most 20000 characters")
    return value


class DatasetStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.root = settings.data_dir / "datasets"
        self.db = settings.data_dir / "datasets.sqlite3"
        self._lock = threading.RLock()
        self.root.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS datasets (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS dataset_items (
                    dataset_id TEXT NOT NULL,
                    id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    ext TEXT NOT NULL,
                    width INTEGER NOT NULL,
                    height INTEGER NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    caption TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY(dataset_id,id),
                    FOREIGN KEY(dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_dataset_items_order
                ON dataset_items(dataset_id,created_at DESC);
            """)

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.db, timeout=5)
        connection.execute("PRAGMA foreign_keys=ON")
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _folder(self, identifier: str) -> Path:
        validate_dataset_id(identifier)
        folder = self.root / identifier
        if folder.is_symlink() or not folder.resolve().is_relative_to(self.root.resolve()):
            raise DatasetError("Dataset path is not allowed")
        return folder

    def list_datasets(self) -> list[dict]:
        with self._lock, self._connect() as db:
            rows = db.execute("""
                SELECT d.id,d.title,d.created_at,COUNT(i.id) AS image_count,
                       COALESCE(SUM(i.size_bytes),0) AS size_bytes
                FROM datasets d LEFT JOIN dataset_items i ON i.dataset_id=d.id
                GROUP BY d.id ORDER BY d.created_at DESC,d.id
            """).fetchall()
        return [dict(row) for row in rows]

    def create_dataset(self, identifier: str, title: str) -> dict:
        validate_dataset_id(identifier)
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 80:
            raise DatasetError("Dataset title must contain 1-80 characters")
        with self._lock:
            folder = self._folder(identifier)
            if folder.exists() and not folder.is_dir():
                raise DatasetConflict("Dataset path is occupied")
            with self._connect() as db:
                if db.execute("SELECT 1 FROM datasets WHERE id=?", (identifier,)).fetchone():
                    raise DatasetConflict("Dataset already exists")
                folder.mkdir(parents=True, exist_ok=True)
                db.execute("INSERT INTO datasets(id,title,created_at) VALUES(?,?,?)", (identifier, title.strip(), time.time()))
        return {"id": identifier, "title": title.strip(), "image_count": 0, "size_bytes": 0}

    def require_dataset(self, identifier: str) -> Path:
        folder = self._folder(identifier)
        with self._connect() as db:
            if not db.execute("SELECT 1 FROM datasets WHERE id=?", (identifier,)).fetchone():
                raise DatasetNotFound(identifier)
        return folder

    def list_items(self, identifier: str, *, limit: int = 48, offset: int = 0) -> dict:
        if not 1 <= limit <= 100 or not 0 <= offset <= 1_000_000:
            raise DatasetError("Invalid page")
        with self._lock, self._connect() as db:
            if not db.execute("SELECT 1 FROM datasets WHERE id=?", (validate_dataset_id(identifier),)).fetchone():
                raise DatasetNotFound(identifier)
            total = db.execute("SELECT COUNT(*) FROM dataset_items WHERE dataset_id=?", (identifier,)).fetchone()[0]
            rows = db.execute("""
                SELECT id,name,ext,width,height,size_bytes,caption,created_at,updated_at
                FROM dataset_items WHERE dataset_id=?
                ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?
            """, (identifier, limit, offset)).fetchall()
        return {"items": [dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}

    @staticmethod
    def _atomic_text(path: Path, value: str) -> None:
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".caption-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as output:
                output.write(value)
            os.replace(tmp, path)
        finally:
            Path(tmp).unlink(missing_ok=True)

    async def import_image(self, identifier: str, image: UploadFile, caption: str = "") -> dict:
        validate_caption(caption)
        folder = self.require_dataset(identifier)
        fd, name = tempfile.mkstemp(prefix=".upload-", suffix=".tmp", dir=folder)
        temp = Path(name)
        sha = hashlib.sha256()
        size = 0
        try:
            with os.fdopen(fd, "wb") as stream:
                while chunk := await image.read(1024 * 1024):
                    size += len(chunk)
                    if size > self.settings.max_asset_bytes:
                        raise DatasetError("Image exceeds the configured size limit")
                    sha.update(chunk)
                    stream.write(chunk)
            if size == 0:
                raise DatasetError("Empty image")
            try:
                with Image.open(temp) as picture:
                    if picture.format not in FORMATS:
                        raise DatasetError("Only PNG, JPEG and WebP are supported")
                    if picture.width * picture.height > self.settings.max_image_pixels:
                        raise DatasetError("Image dimensions exceed pixel limit")
                    width, height, fmt = picture.width, picture.height, picture.format
                    picture.verify()
                with Image.open(temp) as picture:
                    picture.load()
            except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
                raise DatasetError("Invalid image") from exc
            ext, _media = FORMATS[fmt]
            digest = sha.hexdigest()
            original_name = (image.filename or "image").replace("\\", "/").split("/")[-1][:180]
            with self._lock:
                folder = self.require_dataset(identifier)
                with self._connect() as db:
                    exists = db.execute("SELECT 1 FROM dataset_items WHERE dataset_id=? AND id=?", (identifier, digest)).fetchone()
                    if exists:
                        raise DatasetConflict("This image is already present in the dataset")
                    target = folder / f"{digest}.{ext}"
                    sidecar = folder / f"{digest}.tags.txt"
                    if target.is_symlink() or sidecar.is_symlink():
                        raise DatasetError("Unsafe dataset file")
                    created_image = False
                    try:
                        if not target.exists():
                            os.replace(temp, target)
                            created_image = True
                        self._atomic_text(sidecar, caption)
                        now = time.time()
                        db.execute("""
                            INSERT INTO dataset_items(dataset_id,id,name,ext,width,height,size_bytes,caption,created_at,updated_at)
                            VALUES (?,?,?,?,?,?,?,?,?,?)
                        """, (identifier, digest, original_name, ext, width, height, size, caption, now, now))
                    except Exception:
                        if created_image:
                            target.unlink(missing_ok=True)
                        sidecar.unlink(missing_ok=True)
                        raise
            return {"id": digest, "name": original_name, "ext": ext, "width": width, "height": height,
                    "size_bytes": size, "caption": caption, "created_at": now, "updated_at": now}
        finally:
            temp.unlink(missing_ok=True)
            await image.close()

    def update_caption(self, identifier: str, item_id: str, caption: str) -> dict:
        validate_caption(caption)
        with self._lock:
            folder = self.require_dataset(identifier)
            if not ITEM_ID.fullmatch(item_id):
                raise DatasetError("Invalid image ID")
            with self._connect() as db:
                row = db.execute("SELECT id FROM dataset_items WHERE dataset_id=? AND id=?", (identifier, item_id)).fetchone()
                if not row:
                    raise DatasetNotFound(item_id)
                sidecar = folder / f"{item_id}.tags.txt"
                if sidecar.is_symlink():
                    raise DatasetError("Unsafe caption file")
                self._atomic_text(sidecar, caption)
                now = time.time()
                db.execute("UPDATE dataset_items SET caption=?, updated_at=? WHERE dataset_id=? AND id=?", (caption, now, identifier, item_id))
        return {"id": item_id, "caption": caption, "updated_at": now}

    def image_path(self, identifier: str, item_id: str) -> tuple[Path, str]:
        if not ITEM_ID.fullmatch(item_id):
            raise DatasetError("Invalid image ID")
        folder = self.require_dataset(identifier)
        with self._lock, self._connect() as db:
            row = db.execute("SELECT ext FROM dataset_items WHERE dataset_id=? AND id=?", (identifier, item_id)).fetchone()
        if row is None:
            raise DatasetNotFound(item_id)
        ext = row["ext"]
        if ext not in ("png", "jpg", "webp"):
            raise DatasetError("Invalid stored image format")
        path = folder / f"{item_id}.{ext}"
        if not path.is_file() or path.is_symlink():
            raise DatasetNotFound(item_id)
        return path, "image/jpeg" if ext == "jpg" else f"image/{ext}"

    def delete_item(self, identifier: str, item_id: str) -> None:
        if not ITEM_ID.fullmatch(item_id):
            raise DatasetError("Invalid image ID")
        with self._lock:
            folder = self.require_dataset(identifier)
            with self._connect() as db:
                row = db.execute("SELECT ext FROM dataset_items WHERE dataset_id=? AND id=?", (identifier, item_id)).fetchone()
                if not row:
                    raise DatasetNotFound(item_id)
                db.execute("DELETE FROM dataset_items WHERE dataset_id=? AND id=?", (identifier, item_id))
            for path in (folder / f"{item_id}.{row['ext']}", folder / f"{item_id}.tags.txt"):
                if not path.is_symlink():
                    path.unlink(missing_ok=True)

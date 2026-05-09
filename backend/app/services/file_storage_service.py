from __future__ import annotations

import csv
import io
import json
import re
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path

import anyio
from fastapi import UploadFile

from app.core.config import settings


class FileStorageError(Exception):
    pass


class UnsupportedFileTypeError(FileStorageError):
    pass


class FileSizeLimitExceededError(FileStorageError):
    pass


class UnsafeFileError(FileStorageError):
    pass


@dataclass(frozen=True)
class StoredFile:
    file_name: str
    mime_type: str
    file_path: str


class FileStorageService:
    _allowed_image_mime_types = {
        "image/png",
        "image/jpeg",
        "image/webp",
        "image/gif",
        "image/bmp",
        "image/tiff",
        "image/svg+xml",
        "image/heic",
        "image/heif",
        "image/avif",
        "image/x-icon",
        "image/vnd.microsoft.icon",
    }
    _allowed_video_mime_types = {
        "video/mp4",
        "video/webm",
        "video/quicktime",
        "video/x-msvideo",
    }
    _allowed_doc_mime_types = {
        "application/pdf",
        "text/plain",
        "text/markdown",
        "text/html",
        "text/xml",
        "application/xml",
        "application/rtf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
    _allowed_table_mime_types = {
        "text/csv",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    }
    _allowed_code_extensions = {
        ".py", ".js", ".ts", ".json", ".sql",
        ".jsx", ".tsx", ".html", ".css", ".xml",
        ".yaml", ".yml", ".md", ".sh", ".bash",
        ".rb", ".go", ".rs", ".java", ".kt",
        ".c", ".cpp", ".h", ".cs", ".php",
        ".swift", ".r", ".toml", ".ini", ".env",
    }

    _blocked_signatures = (
        b"MZ",  # Windows executables
        b"\x7fELF",  # Linux executables
    )

    def __init__(self) -> None:
        self._root = Path(settings.upload_dir)
        self._root.mkdir(parents=True, exist_ok=True)
        self._max_upload_bytes = settings.max_upload_bytes

    @property
    def root(self) -> Path:
        return self._root

    async def save_upload(self, thread_id: uuid.UUID, upload: UploadFile) -> StoredFile:
        raw_name = upload.filename or "upload"
        sanitized_name = self._sanitize_filename(raw_name)

        payload = await self._read_bounded(upload)
        self._assert_safe_payload(payload)
        detected_mime = self._detect_mime_type(payload, sanitized_name)
        self._validate_supported_type(sanitized_name, detected_mime)

        destination_dir = self._root / str(thread_id)
        destination_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid.uuid4().hex}_{sanitized_name}"
        destination_path = destination_dir / stored_name

        await anyio.to_thread.run_sync(destination_path.write_bytes, payload)

        relative_path = destination_path.relative_to(self._root).as_posix()
        return StoredFile(file_name=sanitized_name, mime_type=detected_mime, file_path=relative_path)

    def resolve_path(self, relative_path: str) -> Path:
        return self._root / relative_path

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        safe = Path(name).name
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", safe)
        safe = safe.strip("._") or "upload"
        if len(safe) > 120:
            stem = Path(safe).stem[:100]
            suffix = Path(safe).suffix[:20]
            safe = f"{stem}{suffix}"
        return safe

    async def _read_bounded(self, upload: UploadFile) -> bytes:
        chunks: list[bytes] = []
        total = 0

        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > self._max_upload_bytes:
                raise FileSizeLimitExceededError(
                    f"File exceeds max upload size of {self._max_upload_bytes} bytes."
                )
            chunks.append(chunk)

        await upload.close()

        payload = b"".join(chunks)
        if not payload:
            raise FileStorageError("Uploaded file is empty.")
        return payload

    def _assert_safe_payload(self, payload: bytes) -> None:
        for signature in self._blocked_signatures:
            if payload.startswith(signature):
                raise UnsafeFileError("Executable files are not allowed.")

        if payload.startswith(b"#!"):
            # Reject script binaries disguised as text uploads.
            blocked = (b"/bin/bash", b"/bin/sh", b"powershell", b"python")
            header = payload[:120].lower()
            if any(token in header for token in blocked):
                raise UnsafeFileError("Executable scripts are not allowed.")

    def _detect_mime_type(self, payload: bytes, filename: str) -> str:  # noqa: PLR0911
        head = payload[:64]
        suffix = Path(filename).suffix.lower()

        # ── Binary image formats ─────────────────────────────────────────────
        if head.startswith(b"%PDF-"):
            return "application/pdf"
        if head.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if head.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if payload[:4] == b"RIFF" and payload[8:12] == b"WEBP":
            return "image/webp"
        if head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):
            return "image/gif"
        if head[:2] == b"BM" and len(payload) > 6:
            return "image/bmp"
        if head.startswith(b"II*\x00") or head.startswith(b"MM\x00*"):
            return "image/tiff"
        if head[:4] == b"\x00\x00\x01\x00":
            return "image/x-icon"

        # ── ftyp-box formats (MP4, MOV, HEIC, AVIF) ─────────────────────────
        if len(payload) > 12 and payload[4:8] == b"ftyp":
            brand = payload[8:12].lower()
            if brand in (b"heic", b"heix", b"heim", b"heis"):
                return "image/heic"
            if brand in (b"heif", b"mif1", b"msf1"):
                return "image/heif"
            if brand in (b"avif", b"avis"):
                return "image/avif"
            if brand in (b"qt  ",):
                return "video/quicktime"
            return "video/mp4"

        # ── Video ────────────────────────────────────────────────────────────
        if head.startswith(b"\x1aE\xdf\xa3"):
            return "video/webm"
        if head[:4] == b"RIFF" and payload[8:12] == b"AVI ":
            return "video/x-msvideo"

        # ── OLE2 compound documents (legacy .doc / .ppt / .xls) ─────────────
        if head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
            if suffix == ".ppt":
                return "application/vnd.ms-powerpoint"
            if suffix == ".xls":
                return "application/vnd.ms-excel"
            return "application/msword"  # default to .doc

        # ── ZIP-based Office formats ─────────────────────────────────────────
        zip_type = self._detect_zip_office(payload)
        if zip_type:
            return zip_type

        # ── RTF ──────────────────────────────────────────────────────────────
        if head.startswith(b"{\\rtf"):
            return "application/rtf"

        # ── Text-based formats ───────────────────────────────────────────────
        if self._is_text(payload):
            text = payload.decode("utf-8", errors="ignore")

            if suffix == ".json" or self._is_json(text):
                return "application/json"
            if suffix == ".csv" or self._is_csv(text):
                return "text/csv"
            if suffix in (".md", ".markdown"):
                return "text/markdown"
            if suffix in (".htm", ".html") or text.lstrip().lower().startswith(("<!doctype html", "<html")):
                return "text/html"
            if suffix in (".xml",) or text.lstrip().startswith("<?xml"):
                return "text/xml"
            if text.lstrip().startswith("<svg"):
                return "image/svg+xml"
            return "text/plain"

        raise UnsupportedFileTypeError("Unsupported file type.")

    def _validate_supported_type(self, filename: str, detected_mime: str) -> None:
        suffix = Path(filename).suffix.lower()

        allowed_mime = (
            self._allowed_image_mime_types
            | self._allowed_video_mime_types
            | self._allowed_doc_mime_types
            | self._allowed_table_mime_types
            | {"application/json"}
        )

        if detected_mime in allowed_mime:
            return

        # Code / config files stored as text/plain or application/json
        if suffix in self._allowed_code_extensions and detected_mime in {"text/plain", "application/json"}:
            return

        # SVG may arrive as text/plain from the detector before SVG check — re-check
        if detected_mime in {"text/plain", "text/xml"} and suffix == ".svg":
            return

        raise UnsupportedFileTypeError("This file type is not supported for upload.")

    @staticmethod
    def _is_text(payload: bytes) -> bool:
        try:
            payload.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False

    @staticmethod
    def _is_json(text: str) -> bool:
        try:
            json.loads(text)
            return True
        except json.JSONDecodeError:
            return False

    @staticmethod
    def _is_csv(text: str) -> bool:
        sample = text[:4096]
        if "\n" not in sample:
            return False
        try:
            dialect = csv.Sniffer().sniff(sample)
            return dialect.delimiter in {",", ";", "\t"}
        except csv.Error:
            return False

    @staticmethod
    def _detect_zip_office(payload: bytes) -> str | None:
        """Return the Office MIME type for ZIP-based formats, or None if not an Office ZIP."""
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                names = archive.namelist()
                if "[Content_Types].xml" not in names:
                    return None
                if any(n.startswith("xl/") for n in names):
                    return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                if any(n.startswith("word/") for n in names):
                    return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                if any(n.startswith("ppt/") for n in names):
                    return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        except zipfile.BadZipFile:
            pass
        return None

    @staticmethod
    def _is_xlsx(payload: bytes) -> bool:
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                return "[Content_Types].xml" in archive.namelist() and any(
                    item.startswith("xl/") for item in archive.namelist()
                )
        except zipfile.BadZipFile:
            return False

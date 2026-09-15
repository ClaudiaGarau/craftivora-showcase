from __future__ import annotations

import hashlib
import json
import mimetypes
import shutil
import subprocess
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image
from pypdf import PdfReader


@dataclass(frozen=True)
class ArtifactReport:
    path: str
    kind: str
    bytes: int
    sha256: str
    valid: bool
    details: dict

    def to_dict(self) -> dict:
        return asdict(self)


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def detect_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".pdf": "pdf", ".zip": "archive", ".png": "image", ".jpg": "image",
        ".jpeg": "image", ".webp": "image", ".gif": "image", ".mp4": "video",
        ".mov": "video", ".mkv": "video", ".webm": "video", ".pptx": "presentation",
        ".docx": "document", ".xlsx": "spreadsheet", ".csv": "spreadsheet",
        ".txt": "text", ".md": "text", ".json": "text",
    }.get(suffix, "binary")


def inspect_artifact(path: str | Path) -> ArtifactReport:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    kind = detect_kind(source)
    details: dict = {"mime": mimetypes.guess_type(source.name)[0] or "application/octet-stream"}
    valid = True
    try:
        if kind == "pdf":
            reader = PdfReader(str(source))
            details.update(pages=len(reader.pages), encrypted=reader.is_encrypted,
                           text_characters=sum(len(page.extract_text() or "") for page in reader.pages))
        elif kind == "archive":
            with zipfile.ZipFile(source) as archive:
                corrupt = archive.testzip()
                details.update(members=len(archive.infolist()), corrupt_member=corrupt,
                               uncompressed_bytes=sum(x.file_size for x in archive.infolist()))
                valid = corrupt is None
        elif kind == "image":
            with Image.open(source) as image:
                image.verify()
                details.update(width=image.width, height=image.height, format=image.format)
        elif kind in {"video"}:
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(source)],
                capture_output=True, text=True, check=True,
            )
            details.update(json.loads(probe.stdout))
        elif kind in {"presentation", "document", "spreadsheet"} and source.suffix.lower() != ".csv":
            with zipfile.ZipFile(source) as archive:
                details["members"] = len(archive.infolist())
                valid = archive.testzip() is None
        elif kind == "text":
            details["characters"] = len(source.read_text(encoding="utf-8"))
    except Exception as exc:
        valid = False
        details["error"] = type(exc).__name__
    return ArtifactReport(str(source.resolve()), kind, source.stat().st_size, _digest(source), valid, details)


def safe_extract_zip(path: str | Path, destination: str | Path) -> list[str]:
    source, target = Path(path), Path(destination)
    target.mkdir(parents=True, exist_ok=True)
    extracted: list[str] = []
    with zipfile.ZipFile(source) as archive:
        for member in archive.infolist():
            resolved = (target / member.filename).resolve()
            if target.resolve() not in resolved.parents and resolved != target.resolve():
                raise ValueError("unsafe archive member")
            if member.file_size > 250 * 1024 * 1024:
                raise ValueError("archive member too large")
            archive.extract(member, target)
            extracted.append(str(resolved))
    return extracted


def package_artifacts(paths: list[str | Path], output: str | Path) -> Path:
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for raw in paths:
            path = Path(raw)
            if path.is_file():
                archive.write(path, path.name)
            elif path.is_dir():
                for item in path.rglob("*"):
                    if item.is_file():
                        archive.write(item, str(Path(path.name) / item.relative_to(path)))
    return destination

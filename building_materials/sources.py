"""Content-addressed source blob archive and data/sources/ YAML writer."""

from datetime import UTC, datetime
import hashlib
import mimetypes
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen

import yaml

from .model import ID_RE, MAX_ASSET_BYTES


def asset_path(assets: Path, digest: str, media_type: str) -> Path:
    """Return the content-addressed blob path for a source digest and media type."""
    known = {
        "application/pdf": ".pdf",
        "text/html": ".html",
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "application/json": ".json",
    }
    suffix = known.get(media_type) or mimetypes.guess_extension(media_type) or ""
    return assets / "blobs" / f"{digest}{suffix}"


def source_url(value: str) -> str:
    """Validate and normalize a public HTTP(S) origin URL."""
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("Source URL must be HTTP(S) without embedded credentials")
    return parsed.geturl()


def read_asset(location: str) -> tuple[bytes, str, str]:
    """Read a public HTTP(S) URL or local file and sniff its media type."""
    url = urlsplit(location)
    if url.scheme in {"http", "https"}:
        request = Request(source_url(location), headers={"User-Agent": "BuildingMaterials/2.0"})
        with urlopen(request, timeout=20) as response:
            data = response.read(MAX_ASSET_BYTES + 1)
            media_type = response.headers.get_content_type()
        name = unquote(Path(url.path).name) or url.hostname
    elif url.scheme and not Path(location).drive:
        raise ValueError("Source must be a local file or a public HTTP(S) URL")
    else:
        path = Path(location).resolve(strict=True)
        if not path.is_file():
            raise ValueError("Source path must point to a file")
        with path.open("rb") as handle:
            data = handle.read(MAX_ASSET_BYTES + 1)
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        name = path.name

    if not data or len(data) > MAX_ASSET_BYTES:
        raise ValueError(f"Source must contain 1 to {MAX_ASSET_BYTES} bytes")
    if data.startswith(b"%PDF-"):
        media_type = "application/pdf"
    elif media_type == "application/pdf" or name.lower().endswith(".pdf"):
        raise ValueError("Expected a PDF but received different content")
    elif data.lstrip()[:20].lower().startswith((b"<!doctype html", b"<html")):
        media_type = "text/html"
    return data, media_type, name


def publish_once(path: Path, data: bytes) -> None:
    """Write an immutable file atomically before exposing it at its final path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    with NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
        try:
            temporary.write(data)
        except BaseException:
            temporary.close()
            temporary_path.unlink(missing_ok=True)
            raise
    try:
        os.link(temporary_path, path)
    except FileExistsError:
        pass
    except OSError:
        if not path.exists():
            os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _load_source_yaml(path: Path) -> dict:
    from .compiler import load_yaml

    data = load_yaml(path)
    if not isinstance(data, dict) or data.get("kind") != "source":
        raise ValueError(f"Expected a single source entity in {path}")
    return data


def import_source(
    location: str,
    *,
    slug: str,
    data_dir: Path,
    assets: Path,
    url: str | None = None,
    title: str | None = None,
    issuer: str | None = None,
    revision: str | None = None,
    expect_sha256: str | None = None,
) -> dict:
    """Archive a source blob and write a tracked YAML entry to data/sources/<slug>.yaml."""
    if not slug or not ID_RE.match(slug):
        raise ValueError(
            f"Invalid source --id '{slug}': must match lowercase dotted slug pattern (e.g. 'demo-doc' or 'usgs.silica-2025')"
        )
    if url is None and urlsplit(location).scheme not in {"http", "https"}:
        raise ValueError("Local source files require --url with their original HTTP(S) URL")

    origin = source_url(url if url is not None else location)
    data, media_type, inferred_title = read_asset(location)
    digest = hashlib.sha256(data).hexdigest()
    if expect_sha256 and digest != expect_sha256.lower():
        raise ValueError(f"Expected SHA-256 {expect_sha256}, received {digest}")

    slug_file = slug[len("source."):] if slug.startswith("source.") else slug
    source_id = slug if slug.startswith("source.") else f"source.{slug}"
    sources_dir = data_dir / "sources"
    slug_parts = slug_file.split(".")
    yaml_path = sources_dir.joinpath(*slug_parts[:-1], f"{slug_parts[-1]}.yaml")

    # Immutability firewall: refuse to mutate an existing slug with different bytes or origin.
    if yaml_path.is_file():
        existing = _load_source_yaml(yaml_path)
        meta = existing.get("source", {})
        if meta.get("origin") == origin and meta.get("sha256") == digest:
            snapshot = asset_path(assets, digest, media_type)
            publish_once(snapshot, data)
            return {
                "status": "unchanged",
                "source": existing,
                "yamlPath": str(yaml_path.resolve()),
                "savedPath": str(snapshot.resolve()),
            }
        raise ValueError(
            f"Source slug '{slug_file}' already exists at {yaml_path} with a different origin or sha256. "
            f"Sources are immutable; mint a new versioned slug (e.g. '{slug_file}-v2') instead."
        )

    # Deduplicate against other source YAML files with identical (origin, sha256).
    if sources_dir.is_dir():
        for other_path in sorted(sources_dir.rglob("*.yaml")):
            other = _load_source_yaml(other_path)
            meta = other.get("source", {})
            if meta.get("origin") == origin and meta.get("sha256") == digest:
                snapshot = asset_path(assets, digest, media_type)
                publish_once(snapshot, data)
                return {
                    "status": "duplicate",
                    "duplicateOf": other["id"],
                    "source": other,
                    "yamlPath": str(other_path.resolve()),
                    "savedPath": str(snapshot.resolve()),
                }

    snapshot = asset_path(assets, digest, media_type)
    publish_once(snapshot, data)
    if hashlib.sha256(snapshot.read_bytes()).hexdigest() != digest:
        raise ValueError(f"Snapshot hash mismatch for {snapshot}")

    record: dict = {
        "id": source_id,
        "kind": "source",
        "label": title or inferred_title,
        "source": {
            "origin": origin,
            "mediaType": media_type,
            "sha256": digest,
            "retrievedAt": datetime.now(UTC).isoformat(),
        },
    }
    if issuer:
        record["source"]["issuer"] = issuer
    if revision:
        record["revision"] = revision

    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = yaml.safe_dump(record, sort_keys=False, allow_unicode=True)
    yaml_path.write_text(rendered, encoding="utf-8")

    return {
        "status": "created",
        "source": record,
        "yamlPath": str(yaml_path.resolve()),
        "savedPath": str(snapshot.resolve()),
    }

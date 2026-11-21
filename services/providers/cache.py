"""Caché JSON local con claves canónicas y reemplazos atómicos."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile


DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache" / "power"


class CacheError(ValueError):
    pass


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def parse_timestamp(value):
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError("Se requiere zona horaria")
        return parsed
    except (TypeError, ValueError) as exc:
        raise CacheError("Fecha de obtención inválida") from exc


def write_json_atomic(path, value):
    """Serializa antes de escribir; un fallo no sustituye el archivo anterior."""
    serialized = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".tmp-", suffix=".json", delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


class JsonCache:
    def __init__(self, directory=DEFAULT_CACHE_DIR):
        self.directory = Path(directory)

    def path_for(self, query):
        canonical = json.dumps(query, sort_keys=True, separators=(",", ":"), allow_nan=False)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return self.directory / f"{digest}.json"

    def read(self, query):
        path = self.path_for(query)
        try:
            with path.open(encoding="utf-8") as stream:
                entry = json.load(stream)
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as exc:
            raise CacheError(f"No se pudo leer la caché {path.name}") from exc
        if (not isinstance(entry, dict) or entry.get("schema_version") != 1
                or entry.get("query") != query or not isinstance(entry.get("data"), dict)):
            raise CacheError("La entrada de caché no coincide con la consulta")
        parse_timestamp(entry.get("fetched_at"))
        return entry

    def write(self, query, data, fetched_at, *, location=None):
        parse_timestamp(fetched_at)
        entry = {"schema_version": 1, "query": query, "fetched_at": fetched_at, "data": data}
        if location is not None:
            entry["location"] = location
        write_json_atomic(self.path_for(query), entry)
        return entry

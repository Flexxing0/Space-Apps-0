"""Package application code from the running image; never export its volumes."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[2]
DIRECTORIES = {"api", "services", "web", "templates", "static", "scripts"}
CATALOGS = {
    "cities.json", "water_features.json", "missions.json", "variables.json",
    "guided_missions.json", "mission_variables.json",
}
DOCKERFILE = r'''FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt
RUN groupadd --gid 10001 earthlens && useradd --uid 10001 --gid 10001 --create-home earthlens
COPY app.py ./
COPY api/ ./api/
COPY services/ ./services/
COPY web/ ./web/
COPY templates/ ./templates/
COPY static/ ./static/
COPY scripts/ ./scripts/
COPY data/ ./data/
RUN mkdir -p /app/data/cache/power /app/data/runtime && chown -R earthlens:earthlens /app
USER earthlens
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8080') + '/api/health', timeout=2).close()"]
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 8 --timeout 60 app:app"]
'''
IGNORE = """.git
**/__pycache__
**/*.pyc
**/.env
**/.env.*
data/cache
data/runtime
tests
venv
.venv
"""


def docker(*args: str) -> bytes:
    return subprocess.run(
        ["docker", *args], check=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


def selected(path: PurePosixPath) -> bool:
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Unexpected path in image archive")
    if any(part == "__pycache__" or part.startswith(".env") for part in path.parts):
        return False
    if path.suffix.lower() in {".pyc", ".pyo", ".sqlite", ".sqlite3", ".db", ".key", ".pem"}:
        return False
    return (
        path.as_posix() in {"app.py", "requirements.txt"}
        or (len(path.parts) > 1 and path.parts[0] in DIRECTORIES)
        or (len(path.parts) == 2 and path.parts[0] == "data" and path.name in CATALOGS)
    )


def main() -> None:
    running = json.loads(docker("inspect", "earthlens-runtime-backend-1"))[0]
    if not running["State"]["Running"]:
        raise RuntimeError("The local backend must be running before packaging")
    image_id = running["Image"]
    image = json.loads(docker("image", "inspect", image_id))[0]
    if (image["Os"], image["Architecture"]) != ("linux", "amd64"):
        raise RuntimeError("The image must be linux/amd64")
    for entry in image["Config"].get("Env", []):
        name, _, value = entry.partition("=")
        if value and re.search(r"TOKEN|SECRET|PASSWORD|CREDENTIAL|API_KEY", name, re.I):
            raise RuntimeError("Credential environment found in image; packaging cancelled")

    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    marker = dist / ".gitignore"
    if not marker.exists():
        marker.write_text("*\n", encoding="utf-8")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    release = dist / ("earthlens-cloud-" + stamp)
    application = release / "app"
    application.mkdir(parents=True, exist_ok=False)

    # A fresh, stopped container contains image files only, never runtime mounts.
    container_id = docker("create", "--network", "none", image_id).decode().strip()
    if not re.fullmatch(r"[0-9a-f]{64}", container_id):
        raise RuntimeError("Unexpected temporary container identifier")
    try:
        archive = docker("cp", container_id + ":/app/.", "-")
    finally:
        docker("rm", container_id)
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:*") as tar:
        for member in tar:
            relative = PurePosixPath(member.name)
            if not selected(relative):
                continue
            if member.issym() or member.islnk():
                raise RuntimeError("Unexpected link in application code")
            if not member.isfile():
                continue
            target = application.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            content = tar.extractfile(member)
            if content is None:
                raise RuntimeError("Cannot read application file")
            target.write_bytes(content.read())

    required = ["app.py", "api/workspace.py", "templates/pages/workspace.html", "static/js/time-machine/workspace.js", "data/cities.json"]
    if not all((application / name).is_file() for name in required):
        raise RuntimeError("Image does not contain the expected integrated application")
    (application / "Dockerfile").write_text(DOCKERFILE, encoding="utf-8", newline="\n")
    for name in (".dockerignore", ".gcloudignore"):
        (application / name).write_text(IGNORE, encoding="utf-8", newline="\n")
    for name in ("deploy.sh", "verify_release.py"):
        source = ROOT / "deployment" / "cloud-run" / name
        (release / name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    files = {
        path.relative_to(application).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(application.rglob("*")) if path.is_file()
    }
    javascript = (application / "static/js/time-machine/workspace.js").read_text(encoding="utf-8-sig")
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "application files from running local image; runtime volumes excluded",
        "source_image_id": image_id,
        "project_number": "224139449590", "region": "us-central1", "service": "earthlens",
        "target_url": "https://earthlens-224139449590.us-central1.run.app",
        "workspace_js_sha256": hashlib.sha256(javascript.encode()).hexdigest(),
        "files": files,
    }
    (release / "release.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    shutil.copyfile(ROOT / "deployment" / "cloud-run" / "README.md", release / "README.md")
    output = ROOT / "dist" / "earthlens-cloud-release.zip"
    if output.exists():
        with ZipFile(output) as previous:
            previous_manifest = json.loads(previous.read("release.json"))
        if previous_manifest.get("source") != manifest["source"]:
            raise RuntimeError("An unrelated release ZIP exists; it was not overwritten")
        output.rename(dist / ("earthlens-cloud-release-previous-" + stamp + ".zip"))
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as zip_file:
        for path in sorted(release.rglob("*")):
            if path.is_file():
                zip_file.write(path, path.relative_to(release).as_posix())
    print(json.dumps({"release_directory": str(release), "zip": str(output), "files": len(files), "zip_bytes": output.stat().st_size, "source_image_id": image_id, "zip_sha256": hashlib.sha256(output.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()

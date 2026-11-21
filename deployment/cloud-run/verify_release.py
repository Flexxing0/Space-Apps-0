"""Verify packaged files or reject an HTTP deployment of a different interface."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import time
import urllib.request


def verify_files(directory):
    directory = Path(directory).resolve()
    manifest = json.loads((directory / "release.json").read_text(encoding="utf-8"))
    application = directory / "app"
    for name, expected in manifest["files"].items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Invalid file path in manifest")
        path = application.joinpath(*relative.parts)
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(application):
            raise ValueError("Missing or unsafe source file: " + name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Modified source file: " + name)
    return {"source_files_verified": len(manifest["files"])}


def verify_url(url, manifest):
    def get(path):
        request = urllib.request.Request(url.rstrip("/") + path, headers={"Cache-Control": "no-cache"})
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status != 200:
                raise ValueError("Unexpected HTTP status for " + path)
            return response.read()

    health = json.loads(get("/api/health"))
    if not isinstance(health, dict):
        raise ValueError("Invalid health response")
    page = get("/").decode("utf-8")
    if 'id="scrubber"' not in page or 'id="map"' not in page:
        raise ValueError("The unified map and timeline are missing")
    script = get("/static/js/time-machine/workspace.js").decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    if hashlib.sha256(script.encode()).hexdigest() != manifest["workspace_js_sha256"]:
        raise ValueError("The deployed interface differs from the packaged local version")
    return {"url": url, "health": 200, "map": True, "timeline": True, "javascript_matches_release": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url", nargs="?")
    parser.add_argument("--directory", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--files", action="store_true")
    parser.add_argument("--attempts", type=int, default=6)
    args = parser.parse_args()
    if args.files:
        print(json.dumps(verify_files(args.directory)))
        return
    if not args.url:
        parser.error("A URL or --files is required")
    if not 1 <= args.attempts <= 20:
        parser.error("Attempts must be between 1 and 20")
    manifest = json.loads((args.directory / "release.json").read_text(encoding="utf-8"))
    for attempt in range(args.attempts):
        try:
            print(json.dumps(verify_url(args.url, manifest)))
            return
        except (OSError, ValueError):
            if attempt == args.attempts - 1:
                raise SystemExit("Release verification failed: health, map/timeline or JavaScript did not match. Traffic must not be promoted.") from None
            time.sleep(3)


if __name__ == "__main__":
    main()

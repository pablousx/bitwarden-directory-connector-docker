"""Update the release lock from authenticated GitHub release metadata, fail closed."""
import argparse
import json
import os
from pathlib import Path
import re
import urllib.request

REPOSITORY = "bitwarden/directory-connector"


def candidate(release, current):
    tag = release.get("tag_name", "")
    if release.get("draft") or release.get("prerelease") or not re.fullmatch(r"v[0-9]{4}\.[0-9]+\.[0-9]+", tag):
        raise ValueError("Expected a stable official release")
    version = tag[1:]
    assets = [a for a in release.get("assets", []) if a.get("name") == f"bwdc-linux-{version}.zip"]
    if len(assets) != 1:
        raise ValueError("Expected exactly one official Linux CLI asset")
    asset = assets[0]
    expected_url = f"https://github.com/{REPOSITORY}/releases/download/{tag}/bwdc-linux-{version}.zip"
    digest = asset.get("digest", "")
    if asset.get("browser_download_url") != expected_url or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise ValueError("Missing trustworthy asset URL or SHA-256 digest")
    checksum = digest.removeprefix("sha256:")
    if version == current["version"]:
        if checksum != current["sha256"]:
            raise ValueError("Published asset changed at the same version; manual review required")
        return current
    if tuple(map(int, version.split("."))) <= tuple(map(int, current["version"].split("."))):
        raise ValueError("Refusing a release downgrade")
    return {"version": version, "sha256": checksum, "revision": 1}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", type=Path, help="Local fixture for offline validation")
    parser.add_argument("--lock", type=Path, default=Path("release.json"))
    args = parser.parse_args()
    if args.metadata:
        release = json.loads(args.metadata.read_text())
    else:
        request = urllib.request.Request(f"https://api.github.com/repos/{REPOSITORY}/releases/latest",
                                         headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
        if os.environ.get("GH_TOKEN"):
            request.add_header("Authorization", "Bearer " + os.environ["GH_TOKEN"])
        with urllib.request.urlopen(request, timeout=30) as response:
            release = json.load(response)
    current = json.loads(args.lock.read_text())
    result = candidate(release, current)
    if result != current:
        args.lock.write_text(json.dumps(result, indent=2) + "\n")
        notice = Path("third_party/NOTICE")
        notice.write_text(notice.read_text().replace(
            f"/tags/v{current['version']}.tar.gz", f"/tags/v{result['version']}.tar.gz"))
        print("Updated release lock to " + result["version"])


if __name__ == "__main__":
    main()

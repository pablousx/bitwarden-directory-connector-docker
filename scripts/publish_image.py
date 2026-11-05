"""Copy only the tested OCI artifact to GHCR, rejecting obsolete default-branch runs."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.parse
import urllib.request

from oci_archive import inspect_archive


def publication_tags(repository, ref, sha, default_branch, head, release):
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Expected a full commit SHA")
    version = f"{release['version']}-r{release['revision']}"
    if not re.fullmatch(r"[0-9]{4}\.[0-9]+\.[0-9]+-r[1-9][0-9]*", version):
        raise ValueError("Invalid release version")
    if ref == "refs/heads/" + default_branch:
        if sha != head:
            return []
        return ["sha-" + sha, version, "latest"]
    if ref == "refs/tags/v" + version:
        return ["sha-" + sha, version]
    raise ValueError("Publication requires the default branch or matching release tag")


def current_head(repository, branch):
    url = f"https://api.github.com/repos/{repository}/git/ref/heads/{urllib.parse.quote(branch, safe='')}"
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": "Bearer " + os.environ["GH_TOKEN"],
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)["object"]["sha"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--digest", required=True)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    inspect_archive(args.archive, args.digest, args.sha256)
    repository = os.environ["GITHUB_REPOSITORY"]
    branch = os.environ["DEFAULT_BRANCH"]
    ref, sha = os.environ["GITHUB_REF"], os.environ["GITHUB_SHA"]
    tags = publication_tags(repository, ref, sha, branch, current_head(repository, branch), json.loads(Path("release.json").read_text()))
    image = "ghcr.io/" + repository.lower()
    for tag in tags:
        # Serialize publishers in the workflow and recheck HEAD immediately before
        # each mutable alias. A rerun of an old main never updates any tag.
        if ref.startswith("refs/heads/") and current_head(repository, branch) != sha:
            print("Default branch advanced; skipping remaining publication tags")
            break
        subprocess.run(["skopeo", "copy", "--all", "--preserve-digests",
                        "--authfile", str(Path.home() / ".docker/config.json"),
                        "--digestfile", "published.digest", "oci-archive:" + str(args.archive),
                        "docker://" + image + ":" + tag], check=True)
        if Path("published.digest").read_text().strip() != args.digest:
            raise ValueError("Published digest differs from the tested OCI artifact")
        print(f"Published {image}:{tag}@{args.digest}")
    if not tags:
        print("Obsolete default-branch run; publication skipped")


if __name__ == "__main__":
    main()

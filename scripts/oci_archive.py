"""Inspect a BuildKit OCI archive without extracting paths or trusting its filenames."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tarfile

DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


def file_sha256(path):
    with Path(path).open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def inspect_archive(path, expected_digest, expected_sha256=None):
    if not DIGEST.fullmatch(expected_digest):
        raise ValueError("Invalid expected OCI digest")
    if expected_sha256 is not None and file_sha256(path) != expected_sha256:
        raise ValueError("OCI archive checksum mismatch")
    with tarfile.open(path) as archive:
        def read_json(name, digest=None):
            member = archive.getmember(name)
            if not member.isfile() or member.size > 8 * 1024 * 1024:
                raise ValueError("Invalid OCI metadata member")
            content = archive.extractfile(member).read()
            if digest and "sha256:" + hashlib.sha256(content).hexdigest() != digest:
                raise ValueError("OCI metadata digest mismatch")
            return json.loads(content)

        def blob(descriptor):
            digest = descriptor["digest"]
            if not DIGEST.fullmatch(digest):
                raise ValueError("Invalid OCI descriptor digest")
            return read_json("blobs/sha256/" + digest[7:], digest)

        root = read_json("index.json")
        descriptors = root.get("manifests", [])
        if len(descriptors) != 1 or descriptors[0]["digest"] != expected_digest:
            raise ValueError("OCI index differs from the build output")
        index = blob(descriptors[0])
        manifests = index.get("manifests", [])
        images = [m for m in manifests if m.get("platform", {}).get("os") == "linux" and m["platform"].get("architecture") == "amd64"]
        if len(images) != 1:
            raise ValueError("Expected exactly one Linux amd64 image")
        image = images[0]
        manifest = blob(image)
        config = manifest["config"]["digest"]
        blob(manifest["config"])
        predicates = set()
        for item in manifests:
            if item.get("annotations", {}).get("vnd.docker.reference.type") == "attestation-manifest":
                if item["annotations"].get("vnd.docker.reference.digest") != image["digest"]:
                    raise ValueError("Attestation does not refer to the tested image")
                for layer in blob(item).get("layers", []):
                    statement = blob(layer)
                    predicates.add(statement.get("predicateType"))
        if "https://spdx.dev/Document" not in predicates or not predicates.intersection({
            "https://slsa.dev/provenance/v0.2", "https://slsa.dev/provenance/v1",
        }):
            raise ValueError("OCI archive must contain SBOM and provenance")
        return config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--digest", required=True)
    parser.add_argument("--sha256")
    args = parser.parse_args()
    print(inspect_archive(args.archive, args.digest, args.sha256))


if __name__ == "__main__":
    main()

import hashlib
import importlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
oci = importlib.import_module("oci_archive")
publisher = importlib.import_module("publish_image")


def make_archive(path, *, sbom=True, wrong_subject=False):
    members = {}

    def add(value):
        content = json.dumps(value).encode()
        digest = "sha256:" + hashlib.sha256(content).hexdigest()
        members["blobs/sha256/" + digest[7:]] = content
        return {"digest": digest, "size": len(content)}

    config = add({"architecture": "amd64", "os": "linux"})
    image = add({"schemaVersion": 2, "config": config, "layers": []})
    image["platform"] = {"os": "linux", "architecture": "amd64"}
    predicates = ["https://slsa.dev/provenance/v0.2"]
    if sbom:
        predicates.append("https://spdx.dev/Document")
    layers = [add({"predicateType": p}) for p in predicates]
    attestation = add({"schemaVersion": 2, "layers": layers})
    attestation["annotations"] = {
        "vnd.docker.reference.type": "attestation-manifest",
        "vnd.docker.reference.digest": "sha256:" + "0" * 64 if wrong_subject else image["digest"],
    }
    index = add({"schemaVersion": 2, "manifests": [image, attestation]})
    members["index.json"] = json.dumps({"schemaVersion": 2, "manifests": [index]}).encode()
    with tarfile.open(path, "w") as archive:
        for name, value in members.items():
            member = tarfile.TarInfo(name)
            member.size = len(value)
            archive.addfile(member, io.BytesIO(value))
    return index["digest"], config["digest"]


class PublicationTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.archive = Path(self.directory.name) / "image.tar"
        self.release = {"version": "2026.10.0", "revision": 1}
        self.old = "a" * 40
        self.head = "b" * 40

    def tags(self, ref, sha, head=None):
        return publisher.publication_tags("owner/repo", ref, sha, "main", head or self.head, self.release)

    def test_obsolete_main_rerun_cannot_publish_any_alias(self):
        self.assertEqual(self.tags("refs/heads/main", self.old), [])
        self.assertEqual(self.tags("refs/heads/main", self.head), ["sha-" + self.head, "2026.10.0-r1", "latest"])

    def test_historical_release_never_receives_latest(self):
        self.assertEqual(self.tags("refs/tags/v2026.10.0-r1", self.old), ["sha-" + self.old, "2026.10.0-r1"])
        for ref in ("refs/heads/automation/official-release", "refs/pull/1/merge", "refs/tags/v2026.9.0-r1"):
            with self.assertRaises(ValueError):
                self.tags(ref, self.head)

    def test_stale_or_superseded_run_never_calls_the_registry(self):
        digest, _ = make_archive(self.archive)
        environment = {"GITHUB_REPOSITORY": "owner/repo", "DEFAULT_BRANCH": "main",
                       "GITHUB_REF": "refs/heads/main", "GITHUB_SHA": self.old}
        for heads in ([self.head], [self.old, self.head]):
            with patch.object(sys, "argv", ["publish", str(self.archive), "--digest", digest,
                                           "--sha256", oci.file_sha256(self.archive)]), \
                 patch.dict(publisher.os.environ, environment), \
                 patch.object(publisher, "current_head", side_effect=heads), \
                 patch.object(publisher.Path, "read_text", return_value=json.dumps(self.release)), \
                 patch.object(publisher.subprocess, "run") as copy:
                publisher.main()
            copy.assert_not_called()

    def test_archive_identity_and_attestations_are_verified(self):
        digest, config = make_archive(self.archive)
        checksum = oci.file_sha256(self.archive)
        self.assertEqual(oci.inspect_archive(self.archive, digest, checksum), config)
        with self.assertRaises(ValueError):
            oci.inspect_archive(self.archive, "sha256:" + "f" * 64, checksum)
        with self.assertRaises(ValueError):
            oci.inspect_archive(self.archive, digest, "0" * 64)
        for options in ({"sbom": False}, {"wrong_subject": True}):
            digest, _ = make_archive(self.archive, **options)
            with self.assertRaises(ValueError):
                oci.inspect_archive(self.archive, digest)

    def test_archive_corruption_cannot_pass_identity_checks(self):
        digest, _ = make_archive(self.archive)
        content = self.archive.read_bytes()
        self.archive.write_bytes(content.replace(b'"amd64"', b'"arm64"', 1))
        with self.assertRaises(ValueError):
            oci.inspect_archive(self.archive, digest)

    def test_loaded_image_must_match_the_tested_archive(self):
        smoke = importlib.import_module("check_image")
        with patch.object(sys, "argv", ["check_image", "--image", "tested", "--config-digest", "sha256:expected"]), \
             patch.object(smoke, "image_config_digest", return_value="sha256:different") as identity:
            with self.assertRaises(ValueError):
                smoke.main()
        identity.assert_called_once_with("tested")


if __name__ == "__main__":
    unittest.main()

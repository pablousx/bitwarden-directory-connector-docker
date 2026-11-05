import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("updater", Path(__file__).resolve().parents[1] / "scripts/update_release.py")
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


class UpdaterTest(unittest.TestCase):
    def setUp(self):
        self.current = {"version": "2026.9.0", "sha256": "a" * 64, "revision": 2}
        self.release = {"tag_name": "v2026.10.0", "draft": False, "prerelease": False, "assets": [{
            "name": "bwdc-linux-2026.10.0.zip", "digest": "sha256:" + "b" * 64,
            "browser_download_url": "https://github.com/bitwarden/directory-connector/releases/download/v2026.10.0/bwdc-linux-2026.10.0.zip"}]}

    def test_stable_upgrade(self):
        self.assertEqual(updater.candidate(self.release, self.current), {"version": "2026.10.0", "sha256": "b" * 64, "revision": 1})

    def test_rejects_untrusted_metadata(self):
        for field, value in (("digest", ""), ("digest", "sha256:wrong"), ("browser_download_url", "https://evil.invalid/a.zip")):
            release = copy.deepcopy(self.release)
            release["assets"][0][field] = value
            with self.assertRaises(ValueError):
                updater.candidate(release, self.current)
        for field in ("draft", "prerelease"):
            with self.assertRaises(ValueError):
                updater.candidate({**self.release, field: True}, self.current)
        with self.assertRaises(ValueError):
            updater.candidate({**self.release, "assets": []}, self.current)

    def test_same_version_digest_change_and_downgrade_fail(self):
        with self.assertRaises(ValueError):
            updater.candidate(self.release, {**self.current, "version": "2026.10.0"})
        with self.assertRaises(ValueError):
            updater.candidate(self.release, {**self.current, "version": "2026.11.0"})
        same = {"version": "2026.10.0", "sha256": "b" * 64, "revision": 7}
        self.assertEqual(updater.candidate(self.release, same), same)


if __name__ == "__main__":
    unittest.main()

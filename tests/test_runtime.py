import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "scripts/entrypoint.py"


class RuntimeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        mock = self.path / "bwdc"
        mock.write_text('''#!/usr/bin/env python3
import json, os, sys, time
with open(os.environ["CALL_LOG"], "a") as f:
    f.write(json.dumps({"args": sys.argv[1:], "secret": os.environ.get("GSUITE_KEY")}) + "\\n")
if "sync" in sys.argv:
    if os.environ.get("BLOCK_SYNC"):
        time.sleep(60)
    sys.exit(int(os.environ.get("SYNC_EXIT", "0")))
if "config" in sys.argv:
    sys.exit(int(os.environ.get("CONFIG_EXIT", "0")))
''')
        mock.chmod(0o755)
        self.env = {**os.environ, "PATH": str(self.path) + os.pathsep + os.environ["PATH"],
                    "BITWARDENCLI_CONNECTOR_APPDATA_DIR": str(self.path / "data"),
                    "CALL_LOG": str(self.path / "calls")}
        for name in tuple(self.env):
            if name.startswith(("BW_", "BWDC_", "LDAP_", "ENTRA_", "GSUITE_", "OKTA_", "ONELOGIN_")):
                del self.env[name]

    def run_cli(self, *args, **env):
        return subprocess.run([os.sys.executable, str(ENTRY), *args], env={**self.env, **env},
                              capture_output=True, text=True, timeout=5)

    def calls(self):
        path = self.path / "calls"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def test_default_is_dry_test(self):
        self.assertEqual(self.run_cli().returncode, 0)
        self.assertEqual(self.calls()[0]["args"], ["test"])

    def test_multiline_secret_is_environment_not_argument(self):
        secret = self.path / "secret"
        secret.write_text("first\nsecond\n")
        result = self.run_cli("configure", GSUITE_KEY_FILE=str(secret))
        self.assertEqual(result.returncode, 0, result.stderr)
        call = self.calls()[0]
        self.assertEqual(call["args"], ["--nointeraction", "config", "gsuite.key", "--secretenv", "GSUITE_KEY"])
        self.assertEqual(call["secret"], "first\nsecond")
        self.assertNotIn("first", result.stdout + result.stderr)

    def test_all_provider_enumerations(self):
        for directory in "01234":
            self.assertEqual(self.run_cli("configure", BWDC_DIRECTORY=directory).returncode, 0)
        self.assertEqual(len(self.calls()), 5)
        self.assertNotEqual(self.run_cli("configure", BWDC_DIRECTORY="5").returncode, 0)

    def test_conflicting_and_incomplete_credentials(self):
        self.assertNotEqual(self.run_cli("login", BW_CLIENTID="x").returncode, 0)
        self.assertNotEqual(self.run_cli("test", GSUITE_KEY="x", GSUITE_KEY_FILE="/missing").returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_seed_is_only_imported_once_and_private(self):
        seed = self.path / "seed.json"
        seed.write_text('{"directoryType": 0}')
        self.assertEqual(self.run_cli("configure", BWDC_CONFIG_FILE=str(seed)).returncode, 0)
        target = self.path / "data/data.json"
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        seed.write_text('{"directoryType": 4}')
        self.run_cli("configure", BWDC_CONFIG_FILE=str(seed))
        self.assertEqual(json.loads(target.read_text())["directoryType"], 0)

    def test_invalid_json_and_intervals(self):
        seed = self.path / "seed"
        seed.write_text('secret bad JSON')
        result = self.run_cli("configure", BWDC_CONFIG_FILE=str(seed))
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("secret bad JSON", result.stderr)
        for value in ("0", "-1", "foo", "1.5", "100000000"):
            self.assertNotEqual(self.run_cli("run", BWDC_SYNC_INTERVAL=value).returncode, 0)

    def test_failures_are_propagated_without_sensitive_logs(self):
        result = self.run_cli("run", SYNC_EXIT="7", BW_CLEANEXIT="true")
        self.assertEqual(result.returncode, 7)
        self.assertIn("failed (exit 7)", result.stdout)
        self.assertNotEqual(self.run_cli("configure", LDAP_PASSWORD="private", CONFIG_EXIT="1").returncode, 0)

    def test_lock_and_signal_forwarding(self):
        process = subprocess.Popen([os.sys.executable, str(ENTRY), "run"], env={**self.env, "BLOCK_SYNC": "1"},
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: process.poll() is None and process.kill())
        deadline = time.monotonic() + 4
        while not self.calls() and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(self.calls())
        result = self.run_cli("test")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Another connector", result.stderr)
        process.send_signal(signal.SIGTERM)
        process.communicate(timeout=3)
        self.assertEqual(process.returncode, 0)
        self.assertEqual(self.run_cli("test").returncode, 0)

    def test_serial_schedule_stops_during_wait(self):
        process = subprocess.Popen([os.sys.executable, str(ENTRY), "run"], env={**self.env, "BWDC_SYNC_INTERVAL": "1"},
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: process.poll() is None and process.kill())
        deadline = time.monotonic() + 4
        while len(self.calls()) < 2 and time.monotonic() < deadline:
            time.sleep(0.03)
        process.terminate()
        process.communicate(timeout=3)
        self.assertEqual(process.returncode, 0)
        self.assertGreaterEqual(len(self.calls()), 2)


if __name__ == "__main__":
    unittest.main()

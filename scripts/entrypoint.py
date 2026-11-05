"""Small, serial supervisor for the unmodified official CLI (Linux only)."""
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading

SECRET_SETTINGS = {
    "LDAP_PASSWORD": "ldap.password", "ENTRA_KEY": "entra.key",
    "GSUITE_KEY": "gsuite.key", "OKTA_TOKEN": "okta.token",
    "ONELOGIN_SECRET": "onelogin.secret",
}
SECRET_NAMES = ("BW_CLIENTID", "BW_CLIENTSECRET", *SECRET_SETTINGS)
child = None
stopped = threading.Event()


def stop(signum, _frame):
    stopped.set()
    if child is not None:
        try:
            os.killpg(child.pid, signum)
        except ProcessLookupError:
            pass


def load_secrets(env):
    for name in SECRET_NAMES:
        filename = env.get(name + "_FILE")
        if filename:
            if name in env:
                raise ValueError(f"Use only {name} or {name}_FILE")
            value = Path(filename).read_text().rstrip("\r\n")
            if not value:
                raise ValueError(f"Empty secret: {name}_FILE")
            env[name] = value
    if bool(env.get("BW_CLIENTID")) != bool(env.get("BW_CLIENTSECRET")):
        raise ValueError("BW_CLIENTID and BW_CLIENTSECRET must be supplied together")


def call(args, env, quiet=False):
    global child
    if stopped.is_set():
        return 143
    child = subprocess.Popen(["bwdc", *args], env=env, start_new_session=True,
                             stdout=subprocess.DEVNULL if quiet else None,
                             stderr=subprocess.DEVNULL if quiet else None)
    if stopped.is_set():
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    result = child.wait()
    child = None
    return result if result >= 0 else 128 - result


def configure(env, data):
    seed = env.get("BWDC_CONFIG_FILE")
    target = data / "data.json"
    if seed and not target.exists():
        value = json.loads(Path(seed).read_text())
        if not isinstance(value, dict):
            raise ValueError("BWDC_CONFIG_FILE must contain a JSON object")
        with target.open("x") as file:
            json.dump(value, file)
    if target.exists():
        target.chmod(0o600)
    settings = []
    if "BWDC_SERVER" in env:
        settings.append(["server", env["BWDC_SERVER"]])
    if "BWDC_DIRECTORY" in env:
        if env["BWDC_DIRECTORY"] not in ("0", "1", "2", "3", "4"):
            raise ValueError("BWDC_DIRECTORY must be 0, 1, 2, 3 or 4")
        settings.append(["directory", env["BWDC_DIRECTORY"]])
    for name, setting in SECRET_SETTINGS.items():
        if name in env:
            settings.append([setting, "--secretenv", name])
    for args in settings:
        if call(["--nointeraction", "config", *args], env, quiet=True):
            raise ValueError(f"Configuration failed for {args[0]}; check input and volume permissions")


def main(args):
    os.umask(0o077)
    env = os.environ.copy()
    # Never let caller options turn operational failures into success.
    env.pop("BW_CLEANEXIT", None)
    env["BW_NOINTERACTION"] = "true"
    load_secrets(env)
    data = Path(env.get("BITWARDENCLI_CONNECTOR_APPDATA_DIR", "/data"))
    data.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not data.is_dir():
        raise ValueError("Application data path must be a directory")
    with (data / ".connector.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Another connector command is using this data volume") from None
        args = args or ["test"]
        if args[0] in ("run", "test", "sync", "login", "configure"):
            configure(env, data)
        if args == ["configure"]:
            return 0
        if args[0] != "run":
            return call(args, env)
        if len(args) != 1:
            raise ValueError("run takes no arguments")
        interval = env.get("BWDC_SYNC_INTERVAL", "300")
        if not re.fullmatch(r"[1-9][0-9]{0,7}", interval):
            raise ValueError("BWDC_SYNC_INTERVAL must be a positive integer (seconds, max 99999999)")
        while not stopped.is_set():
            # No user/group data or CLI diagnostics in unattended logs.
            result = call(["--nointeraction", "sync"], env, quiet=True)
            if stopped.is_set():
                return 0
            print(f"Directory sync {'succeeded' if result == 0 else 'failed'} (exit {result})", flush=True)
            if result:
                return result
            stopped.wait(int(interval))
        return 0


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        sys.exit(main(sys.argv[1:]))
    except (OSError, ValueError) as error:
        # File paths/JSON parser errors could contain sensitive input. Keep generic.
        message = str(error) if isinstance(error, ValueError) and not isinstance(error, json.JSONDecodeError) else "Cannot read configuration, secret or data volume"
        print(f"connector: {message}", file=sys.stderr)
        sys.exit(1)

"""Build and smoke-test against disposable local containers, never production data."""
import json
from pathlib import Path
import subprocess


def run(*args, capture=False):
    result = subprocess.run(args, check=True, text=True, capture_output=capture)
    return result.stdout.strip() if capture else None


def main():
    image = "bwdc-ci:local"
    run("docker", "build", "--platform", "linux/amd64", "-t", image, ".")
    lock = json.loads(Path("release.json").read_text())
    base = ("docker", "run", "--rm", "--platform", "linux/amd64", "--read-only",
            "--cap-drop=ALL", "--security-opt=no-new-privileges", "--network=none",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m", "--tmpfs", "/data:rw,uid=10001,gid=10001,mode=0700")
    assert run(*base, image, "--version", capture=True) == lock["version"]
    assert run(*base, image, "data-file", capture=True) == "/data/data.json"
    assert run(*base, "--entrypoint", "id", image, "-u", capture=True) == "10001"
    # Loads the native credential library and writes persistent-format configuration.
    run(*base, "-e", "BWDC_DIRECTORY=0", "-e", "LDAP_PASSWORD=disposable-test-secret", image, "configure")
    failure = subprocess.run([*base, image, "test"], capture_output=True, text=True)
    assert failure.returncode != 0, "Unauthenticated dry test must fail"
    print("Image smoke checks passed (official version, native module, data path, UID and failure status)")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        if error.stderr:
            print(error.stderr)
        raise

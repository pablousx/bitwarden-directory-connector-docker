"""Build and smoke-test against disposable local containers, never production data."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile


def run(*args, capture=False):
    result = subprocess.run(args, check=True, text=True, capture_output=capture)
    return result.stdout.strip() if capture else None


def image_config_digest(image):
    # Docker's containerd image store reports a manifest digest as .Id, while
    # the classic store reports the config digest. Inspect the saved config
    # bytes instead so both stores verify the same image content.
    with tempfile.TemporaryFile() as output:
        subprocess.run(["docker", "image", "save", image], stdout=output, check=True)
        output.seek(0)
        with tarfile.open(fileobj=output) as archive:
            manifests = json.load(archive.extractfile("manifest.json"))
            if len(manifests) != 1:
                raise ValueError("Expected one image in the Docker archive")
            content = archive.extractfile(manifests[0]["Config"]).read()
            return "sha256:" + hashlib.sha256(content).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", help="Test an existing image without rebuilding it")
    parser.add_argument("--config-digest", help="Require this exact Docker image ID")
    args = parser.parse_args()
    image = args.image or "bwdc-ci:local"
    if args.image is None:
        run("docker", "build", "--platform", "linux/amd64", "-t", image, ".")
    if args.config_digest and image_config_digest(image) != args.config_digest:
        raise ValueError("Loaded image differs from the tested OCI archive")
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

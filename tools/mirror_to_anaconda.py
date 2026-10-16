"""Mirror a prefix.dev channel to an anaconda.org channel.

The distributions upload to prefix.dev. Users who still install from the old
anaconda.org channels get the same packages through this mirror: every package of
the prefix.dev channel that the anaconda.org channel does not have yet is downloaded,
checked against the sha256 of the prefix.dev repodata and uploaded with
`anaconda upload` (the token is read from ANACONDA_API_TOKEN).
"""

import argparse
import hashlib
import subprocess
import tempfile
from pathlib import Path

import niquests
from urllib3.util.retry import Retry

SOURCE_URL = "https://prefix.dev"
DESTINATION_URL = "https://conda.anaconda.org"
PLATFORMS = [
    "linux-64",
    "linux-aarch64",
    "win-64",
    "osx-64",
    "osx-arm64",
    "noarch",
    "emscripten-wasm32",
]

session = niquests.Session(
    retries=Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
)


def fetch_packages(base_url: str, channel: str, platform: str) -> dict[str, dict]:
    """The packages of a channel's platform by file name.

    A 404 means the channel has no such platform yet and reads as empty. Anything
    else raises: treating a transient error as an empty channel would make the run
    upload everything again or nothing at all.
    """
    response = session.get(f"{base_url}/{channel}/{platform}/repodata.json")
    if response.status_code == 404:
        return {}
    response.raise_for_status()
    repodata = response.json() or {}
    return {**repodata.get("packages", {}), **repodata.get("packages.conda", {})}


def missing_packages(source: dict[str, dict], destination: dict[str, dict]) -> list[str]:
    """File names in the source channel that the destination channel doesn't have."""
    return sorted(set(source) - set(destination))


def download(url: str, sha256: str, target: Path) -> None:
    response = session.get(url)
    response.raise_for_status()
    content = response.content or b""
    if hashlib.sha256(content).hexdigest() != sha256:
        raise RuntimeError(f"sha256 mismatch for {url}")
    target.write_bytes(content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", help="prefix.dev channel, e.g. robostack-jazzy")
    parser.add_argument("destination", help="anaconda.org channel, e.g. robostack-jazzy")
    parser.add_argument(
        "--dry-run", action="store_true", help="only list the packages that would be uploaded"
    )
    args = parser.parse_args()

    failed = []
    for platform in PLATFORMS:
        source = fetch_packages(SOURCE_URL, args.source, platform)
        destination = fetch_packages(DESTINATION_URL, args.destination, platform)
        missing = missing_packages(source, destination)
        print(f"{platform}: {len(missing)} of {len(source)} packages to upload")
        if args.dry_run:
            for filename in missing:
                print(f"  {filename}")
            continue

        with tempfile.TemporaryDirectory() as directory:
            for filename in missing:
                path = Path(directory) / filename
                try:
                    download(
                        f"{SOURCE_URL}/{args.source}/{platform}/{filename}",
                        source[filename]["sha256"],
                        path,
                    )
                    subprocess.run(
                        ["anaconda", "upload", "--user", args.destination, str(path)],
                        check=True,
                    )
                    print(f"uploaded {platform}/{filename}")
                except (
                    niquests.RequestException,
                    RuntimeError,
                    subprocess.CalledProcessError,
                ) as e:
                    print(f"failed {platform}/{filename}: {e}")
                    failed.append(f"{platform}/{filename}")
                finally:
                    path.unlink(missing_ok=True)

    if failed:
        raise SystemExit(f"{len(failed)} packages could not be mirrored")


if __name__ == "__main__":
    main()

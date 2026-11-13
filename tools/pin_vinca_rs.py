"""Pin vinca-rs in pixi.toml to the conda packages of a vinca-rs GitHub release.

    pixi run python tools/pin_vinca_rs.py v0.1.2

The release (vinca-rs's release workflow) has a package per platform and SHA256SUMS;
pixi.toml gets a url dependency per platform, in its target table.
"""

import json
import subprocess
import sys
from pathlib import Path

REPO = "Tobias-Fischer/vinca-rs"
PIXI_TOML = Path(__file__).resolve().parent.parent / "pixi.toml"
# on every line this script writes, so that it can replace them
MARK = "# vinca-rs: tools/pin_vinca_rs.py"


def package_subdir(url: str) -> str:
    """The platform a .conda package was built for, from its info/index.json."""
    import io
    import tarfile
    import urllib.request
    import zipfile

    import zstandard

    data = urllib.request.urlopen(url).read()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        info = next(n for n in z.namelist() if n.startswith("info-"))
        tar = zstandard.ZstdDecompressor().stream_reader(io.BytesIO(z.read(info)))
        with tarfile.open(fileobj=tar, mode="r|") as t:
            for member in t:
                if member.name == "info/index.json":
                    return json.load(t.extractfile(member))["subdir"]
    raise SystemExit(f"{url}: no info/index.json")


def main(tag: str) -> int:
    release = json.loads(subprocess.run(
        ["gh", "release", "view", tag, "--repo", REPO, "--json", "assets"],
        capture_output=True, text=True, check=True).stdout)
    urls = {a["name"]: a["url"] for a in release["assets"]}
    sums_url = f"https://github.com/{REPO}/releases/download/{tag}/SHA256SUMS"
    sums = dict(line.split()[::-1] for line in subprocess.run(
        ["curl", "-sfL", sums_url], capture_output=True, text=True, check=True).stdout.splitlines())
    lines = {}
    for name in sorted(n for n in urls if n.endswith(".conda")):
        subdir = package_subdir(f"https://github.com/{REPO}/releases/download/{tag}/{name}")
        lines[subdir] = f'vinca-rs = {{ url = "{urls[name]}", sha256 = "{sums[name]}" }}  {MARK}'
    # the previous pins out, then each into its platform's table (a new one if needed)
    text = "\n".join(l for l in PIXI_TOML.read_text().splitlines() if not l.endswith(MARK)) + "\n"
    for subdir, line in sorted(lines.items()):
        header = f"[target.{subdir}.dependencies]"
        if header in text:
            text = text.replace(header + "\n", f"{header}\n{line}\n", 1)
        else:
            text = text.rstrip("\n") + f"\n\n{header}  {MARK}\n{line}\n"
    PIXI_TOML.write_text(text)
    print(f"pinned vinca-rs {tag} for {len(lines)} platforms; now run `pixi lock`")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))

"""Pin vinca-rs in pixi.toml to the conda packages of a vinca-rs GitHub release.

    pixi run python tools/pin_vinca_rs.py v0.1.1

The release (vinca-rs's release workflow) has a package per platform and SHA256SUMS;
pixi.toml gets a url dependency per platform, between the vinca-rs markers.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = "Tobias-Fischer/vinca-rs"
PIXI_TOML = Path(__file__).resolve().parent.parent / "pixi.toml"
BEGIN, END = "# vinca-rs: begin (tools/pin_vinca_rs.py)", "# vinca-rs: end"


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
    blocks = []
    for name in sorted(n for n in urls if n.endswith(".conda")):
        subdir = package_subdir(f"https://github.com/{REPO}/releases/download/{tag}/{name}")
        blocks.append(f'[target.{subdir}.dependencies]\n'
                      f'vinca-rs = {{ url = "{urls[name]}", sha256 = "{sums[name]}" }}\n')
    text = PIXI_TOML.read_text()
    section = f"{BEGIN}\n# the recipe and workflow generator, {REPO} {tag}\n" + "\n".join(blocks) + END
    if BEGIN in text:
        text = re.sub(re.escape(BEGIN) + ".*?" + re.escape(END), lambda _: section, text, flags=re.S)
    else:
        text = text.rstrip("\n") + "\n\n" + section + "\n"
    PIXI_TOML.write_text(text)
    print(f"pinned vinca-rs {tag} for {len(blocks)} platforms; now run `pixi lock`")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))

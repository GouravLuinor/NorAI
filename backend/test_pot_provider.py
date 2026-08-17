"""
Offline smoke test for the PO-token provider (P8.x).

Checks that, when the `bgutil-pot` binary + yt-dlp plugin are installed in the
runtime image, yt-dlp advertises `bgutil` as a PO Token Provider. Runs a real
`yt-dlp --verbose` against a YouTube URL (network) ONLY when the provider is
installed; otherwise it skips silently so the offline suite stays green in local
dev (no binary, no plugin).

Run directly: python backend/test_pot_provider.py
"""
import shutil
import subprocess
import sys
from pathlib import Path

PASS = 0
FAIL = 1


def check(name: str, ok: bool) -> None:
    print(f"  {'ok' if ok else 'FAIL'}  {name}")
    global PASS, FAIL
    if ok:
        PASS += 1
    else:
        FAIL += 1


def _dir_exists(path: Path) -> bool:
    try:
        return path.is_dir()
    except PermissionError:
        return False


def main() -> int:
    has_binary = shutil.which("bgutil-pot") is not None
    plugin_dirs = [
        Path.home() / ".config/yt-dlp/plugins",
        Path("/root/.config/yt-dlp/plugins"),
    ]
    has_plugin = any(
        _dir_exists(d / "bgutil-ytdlp-pot-provider") for d in plugin_dirs
    )

    if not (has_binary or has_plugin):
        print("  skipped: bgutil POT provider not installed in this environment")
        return 0

    print("  checking bgutil POT provider availability")

    # 1. Binary is runnable
    if has_binary:
        try:
            out = subprocess.run(
                ["bgutil-pot", "--help"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            check("bgutil-pot --help runs", out.returncode == 0)
        except Exception:
            check("bgutil-pot --help runs", False)
    else:
        check("bgutil-pot --help runs", False)

    # 2. yt-dlp advertises the provider (network; only when provider installed)
    try:
        out = subprocess.run(
            [
                sys.executable,
                "-m",
                "yt_dlp",
                "--verbose",
                "--simulate",
                "--skip-download",
                "https://www.youtube.com/watch?v=BaW_jenozKc",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        combined = (out.stdout + out.stderr).lower()
        check("yt-dlp reports bgutil PO Token Provider", "bgutil" in combined and "po token providers" in combined)
    except Exception:
        check("yt-dlp reports bgutil PO Token Provider", False)

    print(f"\n{PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import requests


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import pandoc_runtime  # noqa: E402


class PandocRuntimeTests(unittest.TestCase):
    def test_apple_silicon_selects_native_asset_key(self) -> None:
        with patch("pandoc_runtime.platform.system", return_value="Darwin"), patch(
            "pandoc_runtime.platform.machine", return_value="arm64"
        ):
            self.assertEqual(pandoc_runtime.platform_key(), "darwin-arm64")

    def test_official_failure_falls_back_to_verified_mirror(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            fixture = temp / "pandoc-test.zip"
            program = b"#!/bin/sh\necho 'pandoc 9.9 test'\n"
            with zipfile.ZipFile(fixture, "w") as bundle:
                bundle.writestr("pandoc-test/bin/pandoc", program)
            digest = hashlib.sha256(fixture.read_bytes()).hexdigest()
            manifest = {
                "version": "9.9",
                "official_release_base": "https://official.invalid/{version}/{asset}",
                "assets": {
                    "linux-x86_64": {
                        "filename": fixture.name,
                        "sha256": digest,
                    }
                },
            }

            def fake_download(url: str, output: Path, timeout: float) -> None:
                del timeout
                if url.startswith("https://official.invalid/"):
                    raise requests.ConnectionError("official unavailable")
                shutil.copyfile(fixture, output)

            with patch("pandoc_runtime.resolve_pandoc", side_effect=RuntimeError("missing")), patch(
                "pandoc_runtime.load_manifest", return_value=manifest
            ), patch("pandoc_runtime.platform_key", return_value="linux-x86_64"), patch(
                "pandoc_runtime.executable_name", return_value="pandoc"
            ), patch("pandoc_runtime.cache_root", return_value=temp / "cache"), patch(
                "pandoc_runtime._download", side_effect=fake_download
            ):
                binary, source = pandoc_runtime.install_verified_pandoc(
                    ["https://mirror.example/{version}/{asset}"]
                )

            self.assertTrue(binary.is_file())
            self.assertEqual(source, f"https://mirror.example/9.9/{fixture.name}")
            self.assertEqual(pandoc_runtime.probe_pandoc(binary), (True, "pandoc 9.9 test"))

    def test_checksum_mismatch_rejects_mirror(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            fixture = temp / "pandoc-test.zip"
            with zipfile.ZipFile(fixture, "w") as bundle:
                bundle.writestr("pandoc", "not trusted")
            manifest = {
                "version": "9.9",
                "official_release_base": "https://official.invalid/{version}/{asset}",
                "assets": {
                    "linux-x86_64": {
                        "filename": fixture.name,
                        "sha256": "0" * 64,
                    }
                },
            }

            def fake_download(url: str, output: Path, timeout: float) -> None:
                del url, timeout
                shutil.copyfile(fixture, output)

            with patch("pandoc_runtime.resolve_pandoc", side_effect=RuntimeError("missing")), patch(
                "pandoc_runtime.load_manifest", return_value=manifest
            ), patch("pandoc_runtime.platform_key", return_value="linux-x86_64"), patch(
                "pandoc_runtime.cache_root", return_value=temp / "cache"
            ), patch("pandoc_runtime._download", side_effect=fake_download):
                with self.assertRaisesRegex(RuntimeError, "checksum_mismatch"):
                    pandoc_runtime.install_verified_pandoc(
                        ["https://mirror.example/{version}/{asset}"]
                    )


if __name__ == "__main__":
    unittest.main()

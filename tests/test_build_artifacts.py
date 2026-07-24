import os
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import build


class BuildArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_cwd = Path.cwd()
        os.chdir(self.temp_dir.name)

    def tearDown(self):
        os.chdir(self.previous_cwd)
        self.temp_dir.cleanup()

    def create_app_with_symlink(self, parent):
        app = parent / "YouTube_Downloader.app"
        versions = app / "Contents" / "Frameworks" / "Example.framework" / "Versions"
        target = versions / "A"
        target.mkdir(parents=True)
        (target / "Example").write_bytes(b"binary")
        (versions / "Current").symlink_to("A", target_is_directory=True)
        return app

    def test_copy_to_release_preserves_framework_symlink(self):
        source_app = self.create_app_with_symlink(Path("dist"))

        with patch.object(build, "SYSTEM_NAME", "Darwin"):
            release_app = build.copy_to_release()

        copied_link = (
            release_app
            / "Contents"
            / "Frameworks"
            / "Example.framework"
            / "Versions"
            / "Current"
        )
        self.assertTrue(copied_link.is_symlink())
        self.assertEqual(os.readlink(copied_link), "A")
        self.assertTrue(source_app.exists())

    def test_zip_package_preserves_framework_symlink(self):
        release_app = self.create_app_with_symlink(Path("release"))

        with patch.object(build, "SYSTEM_NAME", "Darwin"):
            zip_path = build.create_zip_package(release_app)

        link_name = (
            "YouTube_Downloader.app/Contents/Frameworks/"
            "Example.framework/Versions/Current"
        )
        with zipfile.ZipFile(zip_path) as archive:
            link_info = archive.getinfo(link_name)
            mode = link_info.external_attr >> 16
            self.assertEqual(stat.S_IFMT(mode), stat.S_IFLNK)
            self.assertEqual(archive.read(link_info), b"A")


if __name__ == "__main__":
    unittest.main()

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

    def test_main_uses_project_directory_before_cleaning(self):
        unrelated_build = Path("build")
        unrelated_build.mkdir()
        marker = unrelated_build / "keep.txt"
        marker.write_text("user data", encoding="utf-8")
        original_marker = marker.resolve()
        clean_directories = []
        with patch.object(build, "clean_build_dirs", side_effect=lambda: clean_directories.append(Path.cwd())), patch.object(
            build, "build_executable", return_value=False
        ):
            self.assertFalse(build.main())
        self.assertEqual(clean_directories, [Path(build.__file__).resolve().parent])
        self.assertEqual(original_marker.read_text(encoding="utf-8"), "user data")

    def test_windows_build_prefers_system_dlls_without_changing_parent_environment(self):
        original_path = os.environ.get('PATH', '')
        with patch.object(build, 'SYSTEM_NAME', 'Windows'), patch.object(build.subprocess, 'run') as run:
            self.assertTrue(build.build_executable())
        child_env = run.call_args.kwargs['env']
        system_root = os.environ.get('SystemRoot', r'C:\Windows')
        self.assertEqual(child_env['PATH'].split(os.pathsep)[0], str(Path(system_root) / 'System32'))
        self.assertEqual(os.environ.get('PATH', ''), original_path)

    def create_app_with_symlink(self, parent):
        app = parent / "YouTube_Downloader.app"
        versions = app / "Contents" / "Frameworks" / "Example.framework" / "Versions"
        target = versions / "A"
        target.mkdir(parents=True)
        (target / "Example").write_bytes(b"binary")
        try:
            (versions / "Current").symlink_to("A", target_is_directory=True)
        except OSError as exc:
            # Windows requires Developer Mode or admin rights to create symlinks;
            # this test exercises macOS packaging behavior, not the Windows host.
            self.skipTest(f"symlink creation not permitted on this host: {exc}")
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

import io
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from ffmpeg_installer import FFmpegInstaller
from utils import check_ffmpeg_installed


class FFmpegArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.destination = self.root / "extracted"
        self.installer = FFmpegInstaller()

    def test_unusable_ffmpeg_is_treated_as_unavailable(self):
        for error in (PermissionError("not executable"), OSError(193, "invalid executable")):
            with self.subTest(error=error), patch("utils.shutil.which", return_value="broken-ffmpeg"), patch(
                "utils.subprocess.run", side_effect=error
            ), patch("utils.os.environ", {"PATH": str(self.root)}), patch(
                "utils.Path.exists", return_value=True
            ):
                self.assertIsNone(check_ffmpeg_installed())

    def test_extensionless_zip_is_extracted(self):
        archive = self.root / "zip"
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr("ffmpeg", b"binary")
        self.assertTrue(self.installer.extract_archive(archive, self.destination))
        self.assertEqual((self.destination / "ffmpeg").read_bytes(), b"binary")

    def test_extensionless_tar_is_extracted(self):
        archive = self.root / "archive"
        with tarfile.open(archive, "w:gz") as packed:
            directory = tarfile.TarInfo("bin")
            directory.type = tarfile.DIRTYPE
            packed.addfile(directory)
            member = tarfile.TarInfo("bin/ffmpeg")
            member.size = 6
            packed.addfile(member, io.BytesIO(b"binary"))
        self.assertTrue(self.installer.extract_archive(archive, self.destination))
        self.assertEqual((self.destination / "bin/ffmpeg").read_bytes(), b"binary")

    def test_unknown_or_missing_archive_fails(self):
        archive = self.root / "archive.zip"
        self.assertFalse(self.installer.extract_archive(archive, self.destination))
        archive.write_bytes(b"not an archive")
        self.assertFalse(self.installer.extract_archive(archive, self.destination))
        self.assertFalse(self.destination.exists())

    def test_tar_rejects_links_and_special_files_before_extraction(self):
        for member_type in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE,
                            tarfile.CHRTYPE, tarfile.BLKTYPE):
            with self.subTest(member_type=member_type):
                archive = self.root / "unsafe.tar"
                with tarfile.open(archive, "w") as packed:
                    ordinary = tarfile.TarInfo("ffmpeg")
                    ordinary.size = 6
                    packed.addfile(ordinary, io.BytesIO(b"binary"))
                    member = tarfile.TarInfo("unsafe")
                    member.type = member_type
                    member.linkname = "../outside"
                    packed.addfile(member)
                self.assertFalse(self.installer.extract_archive(archive, self.destination))
                self.assertFalse(self.destination.exists())
                self.assertFalse((self.root / "outside").exists())

    def test_zip_and_tar_reject_parent_traversal(self):
        zipped_path = self.root / "unsafe.zip"
        with zipfile.ZipFile(zipped_path, "w") as zipped:
            zipped.writestr("../outside", b"unsafe")
        tar_path = self.root / "unsafe.tar"
        with tarfile.open(tar_path, "w") as packed:
            member = tarfile.TarInfo("../outside")
            member.size = 6
            packed.addfile(member, io.BytesIO(b"unsafe"))
        for archive in (zipped_path, tar_path):
            with self.subTest(archive=archive.name):
                self.assertFalse(self.installer.extract_archive(archive, self.destination))
                self.assertFalse((self.root / "outside").exists())


if __name__ == "__main__":
    unittest.main()

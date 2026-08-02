import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from config import Config
from youtube_downloader import YouTubeDownloader


class ConfigMigrationTests(unittest.TestCase):
    def test_legacy_web_client_is_migrated_to_recommended_client(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            config_file = home / ".youtube_downloader_config.json"
            config_file.write_text(
                json.dumps({
                    "download_path": str(home / "Videos"),
                    "player_client": "web",
                }),
                encoding="utf-8",
            )

            with patch("config.Path.home", return_value=home), patch(
                "config.platform.system", return_value="Darwin"
            ):
                config = Config()

            self.assertEqual(config.get("player_client"), "android_vr")
            saved = json.loads(config_file.read_text(encoding="utf-8"))
            self.assertEqual(saved["config_version"], Config.CURRENT_CONFIG_VERSION)
            self.assertEqual(saved["player_client"], "android_vr")

    def test_version_two_android_client_is_migrated_to_recommended_client(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            config_file = home / ".youtube_downloader_config.json"
            config_file.write_text(
                json.dumps({
                    "config_version": 2,
                    "download_path": str(home / "Videos"),
                    "player_client": "android",
                }),
                encoding="utf-8",
            )

            with patch("config.Path.home", return_value=home), patch(
                "config.platform.system", return_value="Darwin"
            ):
                config = Config()

            self.assertEqual(config.get("player_client"), "android_vr")

    def test_current_web_client_selection_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            config_file = home / ".youtube_downloader_config.json"
            config_file.write_text(
                json.dumps({
                    "config_version": Config.CURRENT_CONFIG_VERSION,
                    "download_path": str(home / "Videos"),
                    "player_client": "web",
                }),
                encoding="utf-8",
            )

            with patch("config.Path.home", return_value=home), patch(
                "config.platform.system", return_value="Darwin"
            ):
                config = Config()

            self.assertEqual(config.get("player_client"), "web")


class ConfigQualitySelectionTests(unittest.TestCase):
    def create_config(self):
        config = Config.__new__(Config)
        config.default_config = {
            "download_path": "/tmp",
        }
        config.config = {
            "download_path": "/tmp",
            "download_audio_only": False,
            "quality": "best",
            "preferred_quality": "best",
            "video_format": "mp4",
            "max_retries": 3,
            "playlist_download": False,
            "proxy_mode": "none",
        }
        return config

    def test_best_quality_prioritizes_resolution(self):
        opts = self.create_config().get_ydl_opts()

        self.assertEqual(
            opts["format"],
            "bestvideo*+bestaudio/bestvideo*",
        )
        self.assertEqual(opts["format_sort"], ["res", "fps", "hdr:12", "br"])

    def test_limited_quality_includes_combined_video_formats(self):
        config = self.create_config()
        config.config["preferred_quality"] = "1080p"

        opts = config.get_ydl_opts()

        self.assertEqual(
            opts["format"],
            "bestvideo*[height<=1080]+bestaudio/"
            "bestvideo*[height<=1080]",
        )

    def test_building_options_does_not_create_download_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            download_path = Path(temp_dir) / "disconnected-volume" / "Videos"
            config = self.create_config()
            config.config["download_path"] = str(download_path)

            opts = config.get_ydl_opts()

            self.assertFalse(download_path.exists())
            self.assertEqual(
                opts["outtmpl"],
                str(download_path / "%(title)s.%(ext)s"),
            )


class DownloadPathTests(unittest.TestCase):
    def test_unavailable_download_path_is_reported_without_crashing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            blocking_file = Path(temp_dir) / "external-drive"
            blocking_file.write_text("not a directory", encoding="utf-8")
            download_path = blocking_file / "Videos"
            messages = []

            downloader = YouTubeDownloader.__new__(YouTubeDownloader)
            downloader.status_callback = messages.append
            downloader.progress_callback = None
            downloader.config = Mock()
            downloader.config.get_download_path.return_value = download_path

            with patch.object(downloader, "validate_url"), patch.object(
                downloader,
                "get_ffmpeg_path",
                return_value="/usr/bin/ffmpeg",
            ):
                result = downloader.download_video()

            self.assertFalse(result)
            self.assertTrue(messages)
            self.assertIn("다운로드 경로 생성에 실패했습니다", messages[-1])


class YouTubeFallbackTests(unittest.TestCase):
    def setUp(self):
        self.downloader = YouTubeDownloader.__new__(YouTubeDownloader)
        self.downloader.is_youtube = True
        self.downloader.max_retries = 3

    def test_format_unavailable_retries_with_recommended_client(self):
        opts = {"extractor_args": {"youtube": {"player_client": ["web"]}}}

        should_retry = self.downloader._should_retry_with_compatible_client(
            "requested format is not available",
            opts,
            attempt=0,
        )

        self.assertTrue(should_retry)

    def test_recommended_client_is_not_retried_with_itself(self):
        opts = {"extractor_args": {"youtube": {"player_client": ["android_vr"]}}}

        should_retry = self.downloader._should_retry_with_compatible_client(
            "http error 403",
            opts,
            attempt=0,
        )

        self.assertFalse(should_retry)

    def test_private_video_error_does_not_trigger_client_fallback(self):
        opts = {"extractor_args": {"youtube": {"player_client": ["web"]}}}

        should_retry = self.downloader._should_retry_with_compatible_client(
            "this video is unavailable",
            opts,
            attempt=0,
        )

        self.assertFalse(should_retry)


if __name__ == "__main__":
    unittest.main()

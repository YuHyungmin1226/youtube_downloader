import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import Config
from youtube_downloader import YouTubeDownloader


class ConfigMigrationTests(unittest.TestCase):
    def test_legacy_web_client_is_migrated_to_android(self):
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

            self.assertEqual(config.get("player_client"), "android")
            saved = json.loads(config_file.read_text(encoding="utf-8"))
            self.assertEqual(saved["config_version"], Config.CURRENT_CONFIG_VERSION)
            self.assertEqual(saved["player_client"], "android")

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


class YouTubeFallbackTests(unittest.TestCase):
    def setUp(self):
        self.downloader = YouTubeDownloader.__new__(YouTubeDownloader)
        self.downloader.is_youtube = True
        self.downloader.max_retries = 3

    def test_format_unavailable_retries_with_android(self):
        opts = {"extractor_args": {"youtube": {"player_client": ["web"]}}}

        should_retry = self.downloader._should_retry_with_android(
            "requested format is not available",
            opts,
            attempt=0,
        )

        self.assertTrue(should_retry)

    def test_android_client_is_not_retried_with_itself(self):
        opts = {"extractor_args": {"youtube": {"player_client": ["android"]}}}

        should_retry = self.downloader._should_retry_with_android(
            "http error 403",
            opts,
            attempt=0,
        )

        self.assertFalse(should_retry)

    def test_private_video_error_does_not_trigger_client_fallback(self):
        opts = {"extractor_args": {"youtube": {"player_client": ["web"]}}}

        should_retry = self.downloader._should_retry_with_android(
            "this video is unavailable",
            opts,
            attempt=0,
        )

        self.assertFalse(should_retry)


if __name__ == "__main__":
    unittest.main()

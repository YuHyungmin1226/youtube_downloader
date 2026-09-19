import json
from unittest.mock import patch

import pytest
from yt_dlp import YoutubeDL

from config import Config


@pytest.fixture
def config(tmp_path):
    with patch("config.Path.home", return_value=tmp_path):
        return Config()


@pytest.mark.parametrize("value", [[], None, "settings", 42, True])
def test_non_object_config_is_backed_up_and_defaults_are_loaded(tmp_path, value):
    with patch("config.Path.home", return_value=tmp_path):
        path = Config().config_file
        original = json.dumps(value)
        path.write_text(original, encoding="utf-8")
        config = Config()
    assert config.get("max_retries") == 3
    assert path.with_suffix(".json.bak").read_text(encoding="utf-8") == original


def test_disabled_proxy_overrides_system_proxy(config):
    config.config["proxy_mode"] = "none"
    with patch("urllib.request.getproxies", return_value={"https": "http://proxy.invalid:8080"}):
        with YoutubeDL(config.get_ydl_opts(), auto_init=False) as ydl:
            assert ydl.proxies == {"all": "__noproxy__"}


def test_manual_proxy_is_preserved(config):
    config.config.update(proxy_mode="manual", proxy_url="127.0.0.1:8080")
    assert config.get_ydl_opts()["proxy"] == "http://127.0.0.1:8080"


def test_ydl_progress_output_is_disabled_for_gui(config):
    assert config.get_ydl_opts()["noprogress"] is True


def test_po_token_is_scoped_to_selected_player_client(config):
    config.config.update(
        use_po_token=True,
        po_token="token-value",
        player_client="android_vr",
    )
    assert config.get_ydl_opts(is_youtube=True)["extractor_args"]["youtube"]["po_token"] == [
        "android_vr.gvs+token-value"
    ]


def test_scoped_po_token_is_not_prefixed_again(config):
    config.config.update(
        use_po_token=True,
        po_token="mweb.gvs+token-value",
        player_client="mweb",
    )
    assert config.get_ydl_opts(is_youtube=True)["extractor_args"]["youtube"]["po_token"] == [
        "mweb.gvs+token-value"
    ]


def test_youtube_without_po_token_uses_stable_combined_format(config):
    config.config.update(
        quality="best",
        preferred_quality="1080p",
        player_client="android_vr",
        use_po_token=False,
        po_token="",
    )
    with patch("config.pot_server.is_available", return_value=False):
        assert config.get_ydl_opts(is_youtube=True)["format"] == "best[height<=1080]/best"


def test_bundled_pot_server_unlocks_high_quality_without_manual_token(config):
    config.config.update(
        quality="best",
        preferred_quality="1080p",
        player_client="android_vr",
        use_po_token=False,
        po_token="",
    )
    with patch("config.pot_server.is_available", return_value=True):
        assert config.get_ydl_opts(is_youtube=True)["format"] == (
            "bestvideo*[height<=1080]+bestaudio/bestvideo*[height<=1080]"
        )


def test_default_youtube_profile_prioritizes_high_quality(config):
    opts = config.get_ydl_opts(is_youtube=True)
    assert "extractor_args" not in opts
    assert opts["format"] == "bestvideo*[height<=1080]+bestaudio/bestvideo*[height<=1080]"


def test_youtube_with_po_token_keeps_separate_best_video_and_audio(config):
    config.config.update(
        quality="best",
        preferred_quality="1080p",
        player_client="android_vr",
        use_po_token=True,
        po_token="token-value",
    )
    assert config.get_ydl_opts(is_youtube=True)["format"] == (
        "bestvideo*[height<=1080]+bestaudio/bestvideo*[height<=1080]"
    )


def test_tv_embedded_uses_high_quality_separate_streams_without_token(config):
    config.config.update(
        quality="best",
        preferred_quality="1080p",
        player_client="tv_embedded",
        use_po_token=False,
        po_token="",
    )
    assert config.get_ydl_opts(is_youtube=True)["format"] == (
        "bestvideo*[height<=1080]+bestaudio/bestvideo*[height<=1080]"
    )


def test_audio_only_prefers_available_audio_without_m4a(config):
    config.config.update(download_audio_only=True, proxy_mode="none")
    with YoutubeDL(config.get_ydl_opts()) as ydl:
        info = ydl.process_ie_result({
            "id": "test", "title": "test", "extractor": "test",
            "formats": [
                {"format_id": "audio", "url": "https://example.com/audio.webm",
                 "ext": "webm", "vcodec": "none", "acodec": "opus", "abr": 128},
                {"format_id": "combined", "url": "https://example.com/video.mp4",
                 "ext": "mp4", "vcodec": "h264", "acodec": "aac", "height": 720},
            ],
        }, download=False)
    assert info["format_id"] == "audio"


@pytest.mark.parametrize("quality", ["best", "worst"])
def test_audio_only_extracts_audio_from_combined_fallback(config, quality):
    config.config.update(download_audio_only=True, quality=quality)
    opts = config.get_ydl_opts()
    assert any(pp["key"] == "FFmpegExtractAudio" for pp in opts.get("postprocessors", []))

"""
YouTube 다운로더 설정 파일
"""
import json
import os
from pathlib import Path
import platform
import re
from urllib.parse import urlsplit, urlunsplit

class Config:
    """설정 관리 클래스"""
    def __init__(self):
        # Windows에서는 숨김 파일 대신 일반 파일로 저장
        if platform.system() == "Windows":
            self.config_file = Path.home() / "youtube_downloader_config.json"
        else:
            self.config_file = Path.home() / ".youtube_downloader_config.json"
        self.default_config = {
            "download_path": str(Path.home() / "Videos"),
            "ffmpeg_path": "",
            "video_format": "mp4",
            "quality": "best",
            "window_size": [700, 400],
            "auto_paste": True,
            "max_retries": 3,
            "retry_delay": 3,
            "show_progress": True,
            "auto_open_folder": False,
            "download_audio_only": False,
            "preferred_quality": "1080p",
            "use_cookies": False,
            "cookies_source": "file",
            "cookies_file": "",
            "cookies_browser": "chrome",
            "use_po_token": False,
            "po_token": "",
            "visitor_data": "",
            "player_client": "web",
            "subtitle_download": False,
            "subtitle_language": "ko",
            "playlist_download": False,
            "max_playlist_items": 10,
            "proxy_mode": "auto",
            "proxy_url": ""
        }
        self.config = self.load_config()

    def load_config(self):
        """설정 파일 로드"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 기본값과 병합
                    for key, value in self.default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
            else:
                return self.default_config.copy()
        except (json.JSONDecodeError, UnicodeDecodeError):
            # 설정 파일이 손상된 경우 백업 후 기본값 사용
            try:
                if self.config_file.exists():
                    backup_file = self.config_file.with_suffix('.json.bak')
                    self.config_file.rename(backup_file)
                    print(f"손상된 설정 파일을 백업했습니다: {backup_file}")
            except OSError:
                pass
            return self.default_config.copy()
        except (IOError, OSError):
            return self.default_config.copy()

    def save_config(self):
        """설정 파일 저장"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return True
        except (IOError, OSError):
            return False

    def get(self, key, default=None):
        """설정값 가져오기"""
        return self.config.get(key, default)

    def set(self, key, value):
        """설정값 설정"""
        self.config[key] = value
        self.save_config()

    def get_download_path(self):
        """다운로드 경로 가져오기"""
        path = Path(str(self.config.get("download_path", self.default_config["download_path"])))
        path.mkdir(parents=True, exist_ok=True)
        return path

    def set_download_path(self, path):
        """다운로드 경로 설정"""
        self.set("download_path", str(path))

    def get_video_format(self):
        """비디오 형식 가져오기"""
        return self.get("video_format", "mp4")

    def get_quality(self):
        """품질 설정 가져오기"""
        return self.get("quality", "best")

    def get_max_retries(self):
        """최대 재시도 횟수 가져오기"""
        return self.get("max_retries", 3)

    def get_retry_delay(self):
        """재시도 지연 시간 가져오기"""
        return self.get("retry_delay", 3)

    def is_audio_only(self):
        """오디오만 다운로드 여부"""
        return self.get("download_audio_only", False)

    def get_preferred_quality(self):
        """선호 품질 가져오기"""
        return self.get("preferred_quality", "1080p")

    def should_show_progress(self):
        """진행률 표시 여부"""
        return self.get("show_progress", True)

    def should_auto_open_folder(self):
        """다운로드 후 폴더 자동 열기 여부"""
        return self.get("auto_open_folder", False)

    def get_ydl_opts(self, is_youtube=False):
        """yt-dlp 옵션 딕셔너리 반환
        is_youtube: True면 YouTube 전용 extractor_args(po_token 등)를 포함"""
        quality_val = self.get_quality()
        preferred = self.get_preferred_quality()

        if self.is_audio_only():
            if quality_val == "worst":
                format_str = "worstaudio/worst"
            else:
                format_str = "bestaudio[ext=m4a]/best[ext=m4a]/best"
        else:
            if quality_val == "worst":
                format_str = "worstvideo+worstaudio/worst"
            else:
                # 해상도 제한 파싱 (예: "1080p" -> 1080)
                height_match = re.search(r'\d+', str(preferred))
                if height_match:
                    h = height_match.group()
                    format_str = f"bestvideo[height<={h}]+bestaudio/best[height<={h}]/best"
                else:
                    format_str = "bestvideo+bestaudio/best"

        opts = {
            'format': format_str,
            'outtmpl': str(self.get_download_path() / "%(title)s.%(ext)s"),
            'noplaylist': not self.get("playlist_download", False),
            'quiet': True,
            'merge_output_format': self.get_video_format(),
            'retries': self.get_max_retries(),
            'fragment_retries': self.get_max_retries(),
            'ignoreerrors': False,
        }

        # 자막 다운로드 설정
        if self.get("subtitle_download", False):
            opts['writesubtitles'] = True
            opts['writeautomaticsub'] = True
            opts['subtitleslangs'] = [self.get("subtitle_language", "ko")]

        # 쿠키 설정 (파일 또는 브라우저)
        if self.get("use_cookies", False):
            if self.get("cookies_source", "file") == "file" and self.get("cookies_file"):
                opts['cookiefile'] = self.get("cookies_file")
            elif self.get("cookies_source", "file") == "browser" and self.get("cookies_browser"):
                opts['cookiesfrombrowser'] = (self.get("cookies_browser"),)

        # PO Token 및 Extractor Args 설정 (YouTube 전용)
        if is_youtube and self.get("use_po_token", False):
            youtube_args = {}
            if self.get("po_token"):
                youtube_args['po_token'] = [self.get("po_token")]
            if self.get("visitor_data"):
                youtube_args['visitor_data'] = [self.get("visitor_data")]
            if self.get("player_client"):
                youtube_args['player_client'] = [self.get("player_client")]
            if youtube_args:
                opts['extractor_args'] = {'youtube': youtube_args}

        # 프록시 설정
        proxy_url = self.get_proxy()
        if proxy_url:
            opts['proxy'] = proxy_url

        # 재생목록 제한
        if self.get("playlist_download", False):
            opts['playlist_items'] = f"1-{self.get('max_playlist_items', 10)}"

        return opts

    def get_proxy(self):
        """프록시 URL 반환 (자동 감지 + 수동 설정 통합)"""
        mode = self.get("proxy_mode", "auto")
        if mode == "none":
            return None
        if mode == "manual":
            return self._normalize_proxy_url(self.get("proxy_url", ""))
        return self._detect_system_proxy()

    @staticmethod
    def _detect_system_proxy():
        """시스템 프록시 자동 감지"""
        for var in ('HTTPS_PROXY', 'https_proxy', 'HTTP_PROXY', 'http_proxy', 'ALL_PROXY', 'all_proxy'):
            proxy_url = Config._normalize_proxy_url(os.environ.get(var, ''))
            if proxy_url:
                return proxy_url

        if platform.system() == "Windows":
            return Config._detect_windows_proxy()
        return None 

    @staticmethod
    def _detect_windows_proxy():
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings") as key:
                enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
                if not enabled:
                    return None
                proxy_server, _ = winreg.QueryValueEx(key, "ProxyServer")
        except (OSError, ImportError):
            return None

        return Config._normalize_windows_proxy(proxy_server)

    @staticmethod
    def _normalize_windows_proxy(proxy_server):
        if not proxy_server:
            return None
        entries = [part.strip() for part in str(proxy_server).split(';') if part.strip()]
        for preferred in ('https=', 'http='):
            for entry in entries:
                lowered = entry.lower()
                if lowered.startswith(preferred):
                    return Config._normalize_proxy_url(entry.split('=', 1)[1])
        for entry in entries:
            if entry.lower().startswith('socks='):
                return Config._normalize_proxy_url(entry.split('=', 1)[1], default_scheme='socks5')
        return Config._normalize_proxy_url(entries[0].split('=', 1)[-1])

    @staticmethod
    def _normalize_proxy_url(value, default_scheme='http'):
        url = str(value or '').strip()
        if not url:
            return None
        if '://' not in url:
            url = f"{default_scheme}://{url}"
        return url

    @staticmethod
    def mask_proxy_url(value):
        url = Config._normalize_proxy_url(value)
        if not url:
            return ""
        parsed = urlsplit(url)
        if '@' not in parsed.netloc:
            return url
        userinfo, host = parsed.netloc.rsplit('@', 1)
        user = userinfo.split(':', 1)[0] or "***"
        netloc = f"{user}:***@{host}"
        return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))

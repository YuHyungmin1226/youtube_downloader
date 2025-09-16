"""
YouTube 다운로더 설정 파일
"""
import json
from pathlib import Path
import platform

class Config:
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
            "cookies_file": "",
            "subtitle_download": False,
            "subtitle_language": "ko",
            "playlist_download": False,
            "max_playlist_items": 10
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
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            # 설정 파일이 손상된 경우 백업 후 기본값 사용
            try:
                if self.config_file.exists():
                    backup_file = self.config_file.with_suffix('.json.bak')
                    self.config_file.rename(backup_file)
                    print(f"손상된 설정 파일을 백업했습니다: {backup_file}")
            except:
                pass
            return self.default_config.copy()
        except Exception:
            return self.default_config.copy()
    
    def save_config(self):
        """설정 파일 저장"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
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
        path = Path(self.config.get("download_path", self.default_config["download_path"]))
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
    
    def get_ydl_opts(self):
        """yt-dlp 옵션 딕셔너리 반환"""
        format_str = "bestaudio[ext=m4a]/best[ext=m4a]/best" if self.is_audio_only() else f'bestvideo[ext={self.get_video_format()}]+bestaudio[ext=m4a]/{self.get_video_format()}'
        
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
        
        # 쿠키 파일 설정
        if self.get("use_cookies", False) and self.get("cookies_file"):
            opts['cookiefile'] = self.get("cookies_file")
        
        # 재생목록 제한
        if self.get("playlist_download", False):
            opts['playlist_items'] = f"1-{self.get('max_playlist_items', 10)}"
        
        return opts 
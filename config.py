"""
YouTube 다운로더 설정 파일
"""
import json
from pathlib import Path

class Config:
    def __init__(self):
        self.config_file = Path.home() / ".youtube_downloader_config.json"
        self.default_config = {
            "download_path": str(Path.home() / "Videos"),
            "video_format": "mp4",
            "quality": "best",
            "window_size": [700, 400],
            "auto_paste": True
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
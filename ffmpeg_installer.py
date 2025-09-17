import os
import platform
import sys
import zipfile
import tarfile
import requests
import subprocess
import shutil
from pathlib import Path
from utils import check_ffmpeg_installed

class FFmpegInstaller:
    def __init__(self, status_callback=None, progress_callback=None):
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.system = platform.system()
        self.machine = platform.machine()
        self.ffmpeg_path = None
        
    def get_ffmpeg_url(self):
        """OS별 FFmpeg 다운로드 URL 반환"""
        base_url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest"
        
        if self.system == "Windows":
            if "64" in self.machine or "AMD64" in self.machine:
                return f"{base_url}/ffmpeg-master-latest-win64-gpl.zip"
            else:
                return f"{base_url}/ffmpeg-master-latest-win32-gpl.zip"
        
        elif self.system == "Darwin":  # macOS
            if "arm64" in self.machine.lower():
                return f"{base_url}/ffmpeg-master-latest-macos-arm64-gpl.zip"
            else: # Intel
                return f"{base_url}/ffmpeg-master-latest-macos64-gpl.zip"
        
        elif self.system == "Linux":
            if "64" in self.machine or "x86_64" in self.machine:
                return f"{base_url}/ffmpeg-master-latest-linux64-gpl.tar.xz"
            else:
                return f"{base_url}/ffmpeg-master-latest-linux32-gpl.tar.xz"
        
        else:
            raise ValueError(f"지원하지 않는 운영체제: {self.system}")

    def get_install_path(self):
        """FFmpeg 설치 경로 반환"""
        if self.system == "Windows":
            return Path.home() / "ffmpeg"
        else:
            return Path.home() / ".local" / "ffmpeg"

    def download_file(self, url, filepath):
        """파일 다운로드"""
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0 and self.progress_callback:
                            progress = (downloaded / total_size) * 100
                            self.progress_callback(progress)
            
            return True
        except Exception as e:
            if self.status_callback:
                self.status_callback(f"다운로드 오류: {e}")
            return False

    def extract_archive(self, archive_path, extract_path):
        """압축 파일 해제"""
        try:
            if archive_path.suffix == '.zip':
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_path)
            elif archive_path.suffix in ['.tar.xz', '.tar.gz']:
                with tarfile.open(archive_path, 'r:*') as tar_ref:
                    tar_ref.extractall(extract_path)
            return True
        except Exception as e:
            if self.status_callback:
                self.status_callback(f"압축 해제 오류: {e}")
            return False

    def find_ffmpeg_binary(self, extract_path):
        """압축 해제된 폴더에서 ffmpeg 실행 파일 찾기"""
        for root, dirs, files in os.walk(extract_path):
            for file in files:
                if file == 'ffmpeg' or file == 'ffmpeg.exe':
                    return Path(root) / file
        return None

    def install_ffmpeg(self):
        """FFmpeg 설치 메인 함수. 성공 시 ffmpeg 실행 파일 경로를, 실패 시 None을 반환합니다."""
        try:
            # 1. URL 가져오기
            if self.status_callback:
                self.status_callback("FFmpeg 다운로드 URL을 확인하는 중...")
            url = self.get_ffmpeg_url()
            
            # 2. 설치 경로 설정
            install_path = self.get_install_path()
            install_path.mkdir(parents=True, exist_ok=True)
            
            # 3. 임시 파일 경로
            archive_name = url.split('/')[-1]
            archive_path = install_path / archive_name
            
            # 4. 다운로드
            if self.status_callback:
                self.status_callback(f"FFmpeg 다운로드 중... ({archive_name})")
            if not self.download_file(url, archive_path):
                return None
            
            # 5. 압축 해제
            if self.status_callback:
                self.status_callback("압축 파일 해제 중...")
            if not self.extract_archive(archive_path, install_path):
                return None
            
            # 6. ffmpeg 실행 파일 찾기
            ffmpeg_binary = self.find_ffmpeg_binary(install_path)
            if not ffmpeg_binary:
                if self.status_callback:
                    self.status_callback("FFmpeg 실행 파일을 찾을 수 없습니다.")
                return None
            
            # 7. 임시 파일 정리
            try:
                archive_path.unlink()
            except OSError as e:
                if self.status_callback:
                    self.status_callback(f"임시 파일 삭제 오류: {e}")

            self.ffmpeg_path = str(ffmpeg_binary)
            
            if self.status_callback:
                self.status_callback("FFmpeg 설치가 완료되었습니다!")
                self.status_callback(f"설치 경로: {self.ffmpeg_path}")
            
            return self.ffmpeg_path
            
        except Exception as e:
            if self.status_callback:
                self.status_callback(f"설치 중 오류 발생: {e}")
            return None
    
    def check_ffmpeg(self):
        """FFmpeg 설치 여부 확인"""
        return check_ffmpeg_installed() 
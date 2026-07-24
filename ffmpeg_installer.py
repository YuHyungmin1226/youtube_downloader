"""
FFmpeg 자동 설치 모듈
"""
import os
import platform
import re
import sys
import zipfile
import tarfile
import requests
import shutil
from pathlib import Path
from utils import check_ffmpeg_installed

class FFmpegInstaller:
    """FFmpeg 설치 클래스"""
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
            return f"{base_url}/ffmpeg-master-latest-win32-gpl.zip"

        if self.system == "Darwin":  # macOS
            return self.get_macos_ffmpeg_url()

        if self.system == "Linux":
            if "64" in self.machine or "x86_64" in self.machine:
                return f"{base_url}/ffmpeg-master-latest-linux64-gpl.tar.xz"
            return f"{base_url}/ffmpeg-master-latest-linux32-gpl.tar.xz"

        raise ValueError(f"지원하지 않는 운영체제: {self.system}")

    def get_macos_ffmpeg_url(self):
        """macOS용 FFmpeg ZIP URL을 반환합니다."""
        arch = "arm64" if self.machine.lower() in ("arm64", "aarch64") else "amd64"
        index_url = "https://ffmpeg.martin-riedl.de/"
        try:
            response = requests.get(index_url, timeout=15)
            response.raise_for_status()
            release_html = response.text.split("Download Release Build", 1)[-1]
            pattern = rf'href="(/download/macos/{arch}/[^"]+/ffmpeg\.zip)"'
            match = re.search(pattern, release_html)
            if match:
                return f"{index_url.rstrip('/')}{match.group(1)}"
        except requests.exceptions.RequestException:
            pass

        if arch == "amd64":
            return "https://evermeet.cx/ffmpeg/getrelease/zip"
        raise ValueError("macOS Apple Silicon용 FFmpeg 다운로드 URL을 확인할 수 없습니다. Homebrew로 FFmpeg를 설치하거나 나중에 다시 시도하세요.")

    def get_install_path(self):
        """FFmpeg 설치 경로 반환"""
        if self.system == "Windows":
            return Path.home() / "ffmpeg"
        return Path.home() / ".local" / "ffmpeg"

    def download_file(self, url, filepath):
        """파일 다운로드"""
        import time
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # 10초 타임아웃은 너무 짧을 수 있으므로 30초로 증가
                response = requests.get(url, stream=True, timeout=30)
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
            except (requests.exceptions.RequestException, IOError) as e:
                if attempt < max_retries - 1:
                    if self.status_callback:
                        self.status_callback(f"다운로드 지연/오류 발생 (재시도 {attempt+1}/{max_retries})...")
                    time.sleep(2)
                else:
                    if self.status_callback:
                        self.status_callback(f"다운로드 오류: {e}")
                    return False

    def extract_archive(self, archive_path, extract_path):
        """압축 파일 해제"""
        try:
            suffixes = ''.join(archive_path.suffixes)
            if archive_path.suffix == '.zip':
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    self._safe_extract_zip(zip_ref, extract_path)
            elif suffixes.endswith(('.tar.xz', '.tar.gz')):
                with tarfile.open(archive_path, 'r:*') as tar_ref:
                    self._safe_extract_tar(tar_ref, extract_path)
            return True
        except (zipfile.BadZipFile, tarfile.TarError, IOError) as e:
            if self.status_callback:
                self.status_callback(f"압축 해제 오류: {e}")
            return False

    @staticmethod
    def _is_within_directory(base_dir, target_path):
        base_dir = Path(base_dir).resolve()
        target_path = Path(target_path).resolve()
        try:
            target_path.relative_to(base_dir)
            return True
        except ValueError:
            return False

    def _safe_extract_zip(self, zip_ref, extract_path):
        for member in zip_ref.infolist():
            target = Path(extract_path) / member.filename
            if not self._is_within_directory(extract_path, target):
                raise zipfile.BadZipFile(f"안전하지 않은 ZIP 경로: {member.filename}")
        zip_ref.extractall(extract_path)

    def _safe_extract_tar(self, tar_ref, extract_path):
        for member in tar_ref.getmembers():
            target = Path(extract_path) / member.name
            if not self._is_within_directory(extract_path, target):
                raise tarfile.TarError(f"안전하지 않은 TAR 경로: {member.name}")
        tar_ref.extractall(extract_path)

    def find_ffmpeg_binary(self, extract_path):
        """압축 해제된 폴더에서 ffmpeg 실행 파일 찾기"""
        for root, _, files in os.walk(extract_path):
            for file in files:
                if file in ('ffmpeg', 'ffmpeg.exe'):
                    binary_path = Path(root) / file
                    if self.system != "Windows":
                        try:
                            binary_path.chmod(binary_path.stat().st_mode | 0o755)
                        except OSError:
                            pass
                    return binary_path
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
            archive_name = url.rsplit('/', maxsplit=1)[-1]
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

        except (ValueError, OSError) as e:
            if self.status_callback:
                self.status_callback(f"설치 중 오류 발생: {e}")
            return None

    def check_ffmpeg(self):
        """FFmpeg 설치 여부 확인"""
        return check_ffmpeg_installed() 

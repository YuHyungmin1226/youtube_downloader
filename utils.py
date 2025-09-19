"""
공통 유틸리티 함수들
"""
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
import yt_dlp

def check_ffmpeg_installed(debug=False):
    """FFmpeg 설치 여부를 다양한 경로와 환경변수로 확인"""

    def debug_log(msg):
        if debug:
            print(f"[FFmpeg Debug] {msg}")

    debug_log("FFmpeg 감지 시작...")

    # 1. shutil.which() 사용
    ffmpeg_path = shutil.which("ffmpeg.exe") or shutil.which("ffmpeg")
    debug_log(f"shutil.which: {ffmpeg_path}")

    # 2. macOS Homebrew 등 추가 경로
    if not ffmpeg_path and platform.system() == "Darwin":
        if os.path.exists("/opt/homebrew/bin/ffmpeg"):
            ffmpeg_path = "/opt/homebrew/bin/ffmpeg"
            debug_log("Found in /opt/homebrew/bin/ffmpeg")
        elif os.path.exists("/usr/local/bin/ffmpeg"):
            ffmpeg_path = "/usr/local/bin/ffmpeg"
            debug_log("Found in /usr/local/bin/ffmpeg")

    # 3. Windows 일반 경로
    if not ffmpeg_path and platform.system() == "Windows":
        possible_paths = [
            Path.home() / "ffmpeg" / "bin" / "ffmpeg.exe",
            "C:/ffmpeg/bin/ffmpeg.exe",
        ]
        for path in possible_paths:
            if path.exists():
                ffmpeg_path = str(path)
                debug_log(f"Found in: {ffmpeg_path}")
                break

    # 4. 실제 실행 테스트
    if ffmpeg_path:
        try:
            debug_log(f"Testing execution: {ffmpeg_path}")
            result = subprocess.run([ffmpeg_path, "-version"], capture_output=True, text=True, timeout=5, check=True)
            if result.returncode == 0:
                debug_log(f"FFmpeg 실행 성공: {ffmpeg_path}")
                return ffmpeg_path
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
            debug_log(f"FFmpeg 실행 예외: {e}")

    # 5. 환경변수 PATH 직접 탐색
    debug_log("PATH 환경변수 직접 탐색 시작...")
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    debug_log(f"PATH 디렉토리 수: {len(path_dirs)}")

    for p in path_dirs:
        if not p.strip():
            continue
        candidate = Path(p) / ("ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg")
        if candidate.exists():
            debug_log(f"Found candidate: {candidate}")
            try:
                result = subprocess.run([str(candidate), "-version"], capture_output=True, text=True, timeout=5, check=True)
                if result.returncode == 0:
                    debug_log(f"FFmpeg 실행 성공: {candidate}")
                    return str(candidate)
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
                debug_log(f"FFmpeg 실행 예외: {candidate} - {e}")

    debug_log("FFmpeg를 찾을 수 없습니다.")
    return None

def open_folder(folder_path):
    """폴더를 시스템 기본 파일 관리자로 열기"""
    if not os.path.exists(folder_path):
        return False

    try:
        if platform.system() == 'Darwin':
            subprocess.run(['open', folder_path], check=True)
        elif platform.system() == 'Windows':
            os.startfile(folder_path)
        else:
            subprocess.run(['xdg-open', folder_path], check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False

def format_file_size(size_bytes):
    """바이트 크기를 사람이 읽기 쉬운 형태로 변환"""
    if size_bytes == 0:
        return "0B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1

    return f"{size_bytes:.1f}{size_names[i]}"

def validate_youtube_url(url):
    """YouTube URL 유효성 검증"""
    if not url or not url.strip():
        return False, "URL이 입력되지 않았습니다."

    url = url.strip()

    # 기본 URL 패턴 검증
    if not re.match(r'^(https?://)?(www\.)?(youtube\.com|youtu\.be)/', url):
        return False, "유효하지 않은 YouTube URL입니다."

    video_id = None
    patterns = [
        r'(?:v=|/)([0-9A-Za-z_-]{11}).*',
        r'shorts/([0-9A-Za-z_-]{11})',
        r'embed/([0-9A-Za-z_-]{11})',
        r'v/([0-9A-Za-z_-]{11})'
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            break

    if not video_id or len(video_id) != 11:
        return False, "유효하지 않은 YouTube 영상 ID입니다."

    # 정규화된 URL 반환
    normalized_url = f"https://www.youtube.com/watch?v={video_id}"

    return True, normalized_url

def check_video_availability(url):
    """YouTube 영상의 실제 존재 여부 확인 (선택적 기능)"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info:
                return True, "영상이 존재합니다."
            return False, "영상을 찾을 수 없습니다."
    except yt_dlp.utils.DownloadError as e:
        # 네트워크 오류 등으로 확인할 수 없는 경우
        return None, f"영상 존재 여부를 확인할 수 없습니다: {e}"
"""
YouTube 최고화질 다운로더 (YouTube Best Quality Downloader)
- 완전 독립형 단일 파일 프로그램 (All-in-One Standalone)
- 원본 최고화질(4K / 2K / 1080p60) 무손실 병합 다운로드
- 영상 썸네일/제목/최고화질 실시간 미리보기 카드 UI
- 무설치 포터블 FFmpeg 자동 감지 및 무설치 자동 다운로드
"""
import sys
import os
import argparse
import json
import re
import platform
import shutil
import subprocess
import threading
import time
import urllib.request
import urllib.parse
from pathlib import Path


class _NullOutput:
    """콘솔이 없는 환경용 출력 스트림"""
    def write(self, text):
        return len(text)
    def flush(self):
        return None
    def isatty(self):
        return False


def _ensure_frozen_output_streams():
    if not getattr(sys, "frozen", False):
        return
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        try:
            stream.flush()
        except (AttributeError, OSError):
            setattr(sys, name, _NullOutput())


_ensure_frozen_output_streams()

from PySide6.QtGui import QIcon, QImage, QPixmap, QDesktopServices, QFont
from PySide6.QtCore import QObject, Signal, Qt, QThread, QUrl, QTimer
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QTextEdit, QVBoxLayout,
    QWidget, QFrame, QFileDialog, QRadioButton, QButtonGroup, QCheckBox,
    QFormLayout
)

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

import yt_dlp as youtube_dl


# ============================================================================
# 1. 설정 관리 (Config)
# ============================================================================
class Config:
    """설정 관리 클래스 (로컬 JSON 저장)"""

    def __init__(self):
        self.config_file = Path.home() / "youtube_downloader_config.json"
        downloads_dir = Path.home() / "Downloads"
        if not downloads_dir.exists():
            downloads_dir = Path.home() / "Videos"

        self.default_config = {
            "download_path": str(downloads_dir),
            "preferred_quality": "best",
            "video_format": "mp4",
            "auto_open_folder": False,
            "max_retries": 3,
            "retry_delay": 3,
            "show_progress": True,
        }
        self.config = self.load_config()

    def load_config(self):
        try:
            if self.config_file.exists():
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        for k, v in self.default_config.items():
                            data.setdefault(k, v)
                        return data
        except Exception:
            pass
        return dict(self.default_config)

    def save_config(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"설정 저장 실패: {e}")

    def get(self, key, default=None):
        return self.config.get(key, self.default_config.get(key, default))

    def set(self, key, value):
        self.config[key] = value
        self.save_config()

    def get_download_path(self):
        p = Path(self.get("download_path", str(Path.home() / "Downloads")))
        return p

    def get_ydl_opts(self, is_youtube=True, audio_only=False, player_client=None):
        """최고화질 다운로드를 위한 최적화 yt-dlp 옵션 생성"""
        if audio_only:
            format_str = "bestaudio[ext=m4a]/bestaudio/best"
        else:
            # 해상도 제한 없이 항상 최고의 영상 스트림 + 최고 음원 스트림 병합
            format_str = "bestvideo*+bestaudio/bestvideo*/best"

        opts = {
            "format": format_str,
            "outtmpl": str(self.get_download_path() / "%(title)s.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "noprogress": True,
            "merge_output_format": "mp4",
            "retries": self.get("max_retries", 3),
            "fragment_retries": self.get("max_retries", 3),
            "ignoreerrors": False,
            "remote_components": {"ejs:github"},
        }

        if is_youtube:
            # YouTube 403 Forbidden 우회 및 최고화질(4K) 지원 클라이언트 체인
            clients = player_client if player_client else ["web_embedded", "android"]
            opts["extractor_args"] = {
                "youtube": {
                    "player_client": clients
                }
            }

        # JS 런타임 연동 (YouTube n-sig 챌린지 및 403 차단 완벽 해결)
        js_path = JsRuntimeHelper.check_js_runtime()
        if js_path:
            pname = Path(js_path).name.lower()
            if "qjs" in pname or "quickjs" in pname:
                opts["js_runtimes"] = {"quickjs": {"path": js_path}}
            elif "deno" in pname:
                opts["js_runtimes"] = {"deno": {"path": js_path}}
            elif "node" in pname:
                opts["js_runtimes"] = {"node": {"path": js_path}}

        if not audio_only:
            opts["format_sort"] = ["res", "fps", "hdr:12", "vcodec", "channels", "br"]
        else:
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }]

        return opts


# ============================================================================
# 2. 포터블 FFmpeg 자동 감지 및 온디맨드 프로비저닝 (FFmpegHelper)
# ============================================================================
class FFmpegHelper:
    """포터블 FFmpeg 탐색 및 무설치 자동 다운로드 유틸리티"""

    @staticmethod
    def check_ffmpeg(debug=False):
        """1) 로컬/포터블 폴더 2) imageio-ffmpeg 3) 사용자 폴더 4) 시스템 PATH 탐색"""
        exe_name = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
        candidates = []

        # 1. 실행 파일/스크립트 동일 폴더 및 ./bin/ 폴더
        if getattr(sys, "frozen", False):
            base_dir = Path(sys.executable).resolve().parent
        else:
            base_dir = Path(__file__).resolve().parent

        candidates.append(base_dir / exe_name)
        candidates.append(base_dir / "bin" / exe_name)

        # PyInstaller 번들 임시 폴더
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / exe_name)
            candidates.append(Path(meipass) / "bin" / exe_name)

        # 2. imageio-ffmpeg 패키지 내장 정적 바이너리
        try:
            import imageio_ffmpeg
            img_exe = imageio_ffmpeg.get_ffmpeg_exe()
            if img_exe:
                candidates.append(Path(img_exe))
        except Exception:
            pass

        # 3. 사용자 홈 디렉토리 포터블 폴더 (Windows: ~/ffmpeg, Mac/Linux: ~/.local/ffmpeg)
        if platform.system() == "Windows":
            user_ffmpeg = Path.home() / "ffmpeg"
            if user_ffmpeg.exists():
                for found in user_ffmpeg.glob("**/ffmpeg.exe"):
                    if found.is_file():
                        candidates.append(found)
                        break
            candidates.append(Path("C:/ffmpeg/bin/ffmpeg.exe"))
        else:
            candidates.extend([
                Path.home() / ".local" / "ffmpeg" / "ffmpeg",
                Path("/opt/homebrew/bin/ffmpeg"),
                Path("/usr/local/bin/ffmpeg"),
                Path("/usr/bin/ffmpeg"),
            ])

        # 4. 시스템 PATH 탐색
        which_path = shutil.which(exe_name) or shutil.which("ffmpeg")
        if which_path:
            candidates.append(Path(which_path))

        # 유효성 검사 (실행 테스트)
        for cand in candidates:
            if cand and cand.is_file():
                try:
                    res = subprocess.run(
                        [str(cand), "-version"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        check=True
                    )
                    if res.returncode == 0:
                        if debug:
                            print(f"[FFmpeg] 유효한 바이너리 발견: {cand}")
                        return str(cand)
                except Exception:
                    continue

        return None

    @staticmethod
    def install_portable_ffmpeg(status_callback=None, progress_callback=None):
        """관리자 권한 없이 사용자 디렉토리에 포터블 FFmpeg 자동 다운로드 및 압축 해제"""
        system = platform.system()
        target_dir = Path.home() / "ffmpeg" if system == "Windows" else Path.home() / ".local" / "ffmpeg"
        target_dir.mkdir(parents=True, exist_ok=True)

        if status_callback:
            status_callback("포터블 FFmpeg 다운로드 정보를 확인 중입니다...")

        if system == "Windows":
            url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
            zip_path = target_dir / "ffmpeg_download.zip"
        elif system == "Darwin":
            url = "https://evermeet.cx/ffmpeg/getrelease/zip"
            zip_path = target_dir / "ffmpeg_download.zip"
        else:
            url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz"
            zip_path = target_dir / "ffmpeg_download.tar.xz"

        if status_callback:
            status_callback(f"포터블 FFmpeg 다운로드 중... (약 50~80MB)")

        # 다운로드 실행
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                with open(zip_path, "wb") as f:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0 and progress_callback:
                            progress_callback(min(90, (downloaded / total) * 90))
        except Exception as e:
            if status_callback:
                status_callback(f"FFmpeg 다운로드 실패: {e}")
            return None

        # 압축 해제
        if status_callback:
            status_callback("포터블 FFmpeg 압축 해제 중...")

        try:
            import zipfile
            if zipfile.is_zipfile(zip_path):
                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(target_dir)
            else:
                shutil.unpack_archive(str(zip_path), str(target_dir))

            # 임시 다운로드 파일 삭제
            if zip_path.exists():
                zip_path.unlink()

            # 설치된 바이너리 탐색
            exe_name = "ffmpeg.exe" if system == "Windows" else "ffmpeg"
            for p in target_dir.glob(f"**/{exe_name}"):
                if p.is_file():
                    if system != "Windows":
                        os.chmod(p, 0o755)
                    if status_callback:
                        status_callback(f"포터블 FFmpeg 준비 완료: {p}")
                    if progress_callback:
                        progress_callback(100)
                    return str(p)
        except Exception as e:
            if status_callback:
                status_callback(f"FFmpeg 압축 해제 실패: {e}")

        return None


# ============================================================================
# 2-1. 포터블 JS 런타임 자동 감지 및 온디맨드 프로비저닝 (JsRuntimeHelper)
# ============================================================================
class JsRuntimeHelper:
    """포터블 JS 런타임 (QuickJS/Deno/Node) 탐색 및 온디맨드 자동 다운로드 유틸리티"""

    @staticmethod
    def check_js_runtime(debug=False):
        """1) 로컬 ./bin/qjs.exe 2) 시스템 PATH (deno, node, bun, qjs) 3) 사용자 홈 폴더 탐색"""
        system = platform.system()
        exe_names = ["qjs.exe", "deno.exe", "node.exe", "bun.exe"] if system == "Windows" else ["qjs", "deno", "node", "bun"]

        candidates = []
        if getattr(sys, "frozen", False):
            base_dir = Path(sys.executable).resolve().parent
        else:
            base_dir = Path(__file__).resolve().parent

        # 1. 로컬 폴더 및 ./bin/ 폴더
        for name in exe_names:
            candidates.append(base_dir / "bin" / name)
            candidates.append(base_dir / name)

        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            for name in exe_names:
                candidates.append(Path(meipass) / "bin" / name)
                candidates.append(Path(meipass) / name)

        # 2. 시스템 PATH 탐색
        for name in ["deno", "node", "bun", "qjs"]:
            which_path = shutil.which(name)
            if which_path:
                candidates.append(Path(which_path))

        # 3. 사용자 홈 디렉토리 (~/ffmpeg, ~/.local/bin 등)
        user_home = Path.home()
        candidates.extend([
            user_home / "ffmpeg" / "qjs.exe",
            user_home / "bin" / "qjs.exe",
            user_home / ".local" / "bin" / "qjs",
            user_home / ".deno" / "bin" / "deno.exe",
            user_home / ".deno" / "bin" / "deno",
        ])

        for cand in candidates:
            if cand and cand.is_file():
                try:
                    cname = cand.name.lower()
                    if "qjs" in cname:
                        cmd = [str(cand), "--help"]
                    else:
                        cmd = [str(cand), "--version"]
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                    if "QuickJS" in res.stdout or "QuickJS" in res.stderr or res.returncode == 0:
                        if debug:
                            print(f"[JS] 유효한 JS 런타임 발견: {cand}")
                        return str(cand)
                except Exception:
                    continue

        return None

    @staticmethod
    def install_portable_quickjs(status_callback=None, progress_callback=None):
        """약 2MB 크기의 초경량 QuickJS 바이너리를 bin 폴더에 자동 다운로드"""
        system = platform.system()
        if getattr(sys, "frozen", False):
            base_dir = Path(sys.executable).resolve().parent
        else:
            base_dir = Path(__file__).resolve().parent

        target_dir = base_dir / "bin"
        target_dir.mkdir(parents=True, exist_ok=True)

        if system == "Windows":
            target_exe = target_dir / "qjs.exe"
            url = "https://github.com/quickjs-ng/quickjs/releases/download/v0.17.0/qjs-windows-x86_64.exe"
        elif system == "Darwin":
            target_exe = target_dir / "qjs"
            url = "https://github.com/quickjs-ng/quickjs/releases/download/v0.17.0/qjs-darwin-arm64"
        else:
            target_exe = target_dir / "qjs"
            url = "https://github.com/quickjs-ng/quickjs/releases/download/v0.17.0/qjs-linux-x86_64"

        if status_callback:
            status_callback("YouTube 차단 우회용 초경량 JS 엔진 준비 중 (약 2MB)...")

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                with open(target_exe, "wb") as f:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0 and progress_callback:
                            progress_callback(min(90, (downloaded / total) * 90))

            if system != "Windows":
                os.chmod(target_exe, 0o755)

            if status_callback:
                status_callback("JS 엔진 준비 완료!")
            if progress_callback:
                progress_callback(100)
            return str(target_exe)
        except Exception as e:
            if status_callback:
                status_callback(f"JS 엔진 다운로드 실패: {e}")
            return None


# ============================================================================
# 3. URL 검증 및 시스템 유틸리티
# ============================================================================
def validate_url(url):
    """YouTube 및 영상 URL 검증 및 정규화"""
    if not url or not isinstance(url, str):
        return False, "URL을 입력해주세요."

    clean = url.strip()
    if len(clean) < 10:
        return False, "유효한 URL을 입력해주세요."

    try:
        parsed = urllib.parse.urlsplit(clean)
    except Exception:
        return False, "URL 형식이 올바르지 않습니다."

    if not parsed.scheme or parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False, "http:// 또는 https:// 로 시작하는 올바른 웹 주소를 입력해주세요."

    netloc = parsed.netloc.lower()

    # 1. youtu.be 단축 URL (예: https://youtu.be/VIDEO_ID)
    if "youtu.be" in netloc:
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        if path_parts:
            vid = path_parts[0].split("?")[0]
            if re.match(r'^[a-zA-Z0-9_-]{11}$', vid):
                return True, f"https://www.youtube.com/watch?v={vid}"
            elif len(vid) >= 5:
                return True, clean
        return False, "유효한 YouTube 영상 ID를 찾을 수 없습니다."

    # 2. youtube.com URL
    if "youtube.com" in netloc:
        # 2-1. /watch?v=VIDEO_ID
        qs = urllib.parse.parse_qs(parsed.query)
        if "v" in qs and qs["v"]:
            vid = qs["v"][0]
            if re.match(r'^[a-zA-Z0-9_-]{11}$', vid):
                return True, f"https://www.youtube.com/watch?v={vid}"
            elif len(vid) >= 5:
                return True, clean
            return False, "YouTube 영상 ID가 올바르지 않습니다."

        # 2-2. /shorts/VIDEO_ID, /live/VIDEO_ID, /embed/VIDEO_ID
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(path_parts) >= 2 and path_parts[0] in ("shorts", "live", "embed"):
            vid = path_parts[1].split("?")[0]
            if re.match(r'^[a-zA-Z0-9_-]{11}$', vid):
                return True, f"https://www.youtube.com/watch?v={vid}"
            elif len(vid) >= 5:
                return True, clean
            return False, "YouTube 영상 ID가 올바르지 않습니다."

        # 2-3. 기타 채널/재생목록 등
        if parsed.path.strip("/") or parsed.query:
            if parsed.query.strip() in ("v=", "v"):
                return False, "영상 ID가 비어있습니다."
            return True, clean

        return False, "유효한 YouTube 링크가 아닙니다."

    # 3. 기타 yt-dlp 지원 사이트 URL (도메인과 경로가 온전한 경우)
    if "." in netloc and len(netloc.split(".")) >= 2 and len(parsed.path) >= 1:
        return True, clean

    return False, "유효한 영상 링크 형식이 아닙니다."


def open_folder(path):
    """운영체제별 폴더 열기"""
    try:
        folder = Path(path).resolve()
        if not folder.exists():
            folder.mkdir(parents=True, exist_ok=True)

        system = platform.system()
        if system == "Windows":
            os.startfile(str(folder))
        elif system == "Darwin":
            subprocess.run(["open", str(folder)])
        else:
            subprocess.run(["xdg-open", str(folder)])
        return True
    except Exception as e:
        print(f"폴더 열기 실패: {e}")
        return False


def play_file(filepath):
    """운영체제 기본 플레이어로 영상 재생"""
    try:
        fp = Path(filepath).resolve()
        if fp.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(fp)))
            return True
    except Exception:
        pass
    return False


# ============================================================================
# 4. 실시간 비디오 정보 조회 워커 (VideoInfoWorker)
# ============================================================================
class VideoInfoWorker(QThread):
    """영상 썸네일, 제목, 채널, 재생 시간, 지원 최고화질 비동기 조회"""
    info_ready = Signal(dict)
    info_failed = Signal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            is_valid, clean_url = validate_url(self.url)
            if not is_valid:
                self.info_failed.emit(clean_url)
                return

            config = Config()
            ydl_opts = config.get_ydl_opts(is_youtube=True)
            ydl_opts.update({
                "quiet": True,
                "skip_download": True,
                "extract_flat": False,
                "no_warnings": True,
            })

            ffmpeg_path = FFmpegHelper.check_ffmpeg()
            if ffmpeg_path:
                ydl_opts["ffmpeg_location"] = ffmpeg_path

            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(clean_url, download=False)

            if not info:
                self.info_failed.emit("영상 정보를 가져올 수 없습니다.")
                return

            title = info.get("title") or "제목 없음"
            uploader = info.get("uploader") or info.get("channel") or "알 수 없는 채널"
            duration = info.get("duration")

            if duration:
                mins, secs = divmod(int(duration), 60)
                hours, mins = divmod(mins, 60)
                dur_str = f"{hours}:{mins:02d}:{secs:02d}" if hours > 0 else f"{mins:02d}:{secs:02d}"
            else:
                dur_str = "실시간 스트리밍" if info.get("is_live") else "알 수 없음"

            # 지원 최고 해상도 및 프레임 레이트 감지
            formats = info.get("formats") or []
            video_formats = [
                f for f in formats
                if f.get("vcodec") != "none" and f.get("height")
            ]
            max_height = 0
            max_fps = 30
            for f in video_formats:
                h = int(f.get("height") or 0)
                fps = int(f.get("fps") or 0)
                if h > max_height:
                    max_height = h
                    max_fps = fps
                elif h == max_height and fps > max_fps:
                    max_fps = fps

            fps_str = f" {max_fps}fps" if max_fps > 30 else ""
            if max_height >= 4320:
                res_badge = f"8K UHD ({max_height}p{fps_str})"
            elif max_height >= 2160:
                res_badge = f"4K UHD ({max_height}p{fps_str})"
            elif max_height >= 1440:
                res_badge = f"2K QHD ({max_height}p{fps_str})"
            elif max_height >= 1080:
                res_badge = f"1080p FHD ({max_height}p{fps_str})"
            elif max_height > 0:
                res_badge = f"{max_height}p HD"
            else:
                res_badge = "최고화질 지원"

            # 썸네일 이미지 다운로드
            thumb_url = info.get("thumbnail")
            thumb_data = None
            if thumb_url:
                try:
                    req = urllib.request.Request(
                        thumb_url,
                        headers={"User-Agent": "Mozilla/5.0"}
                    )
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        thumb_data = resp.read()
                except Exception:
                    pass

            result = {
                "url": clean_url,
                "title": title,
                "uploader": uploader,
                "duration": dur_str,
                "max_res": res_badge,
                "max_height": max_height,
                "thumbnail_data": thumb_data,
            }
            self.info_ready.emit(result)
        except Exception as e:
            self.info_failed.emit(f"정보 분석 실패: {e}")


# ============================================================================
# 5. 비디오 다운로더 엔진 (YouTubeDownloader)
# ============================================================================
class YouTubeDownloader:
    """최고화질 비디오 및 오디오 다운로드 엔진"""

    def __init__(self, url, status_callback=None, progress_callback=None, detailed_callback=None):
        self.url = url
        self.config = Config()
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.detailed_callback = detailed_callback
        self.last_percent = 0.0
        self.downloaded_file = None

    def get_ffmpeg_path(self):
        """포터블 FFmpeg 경로 자동 탐색 또는 자동 다운로드"""
        path = FFmpegHelper.check_ffmpeg()
        if not path:
            if self.status_callback:
                self.status_callback("최고화질 영상 병합을 위한 포터블 FFmpeg를 자동으로 준비 중입니다 (최초 1회)...")
            path = FFmpegHelper.install_portable_ffmpeg(
                status_callback=self.status_callback,
                progress_callback=self.progress_callback
            )
        return path

    def get_js_runtime_path(self):
        """포터블 JS 런타임 경로 자동 탐색 또는 자동 다운로드"""
        path = JsRuntimeHelper.check_js_runtime()
        if not path:
            if self.status_callback:
                self.status_callback("YouTube 차단 방지를 위한 초경량 JS 엔진을 준비 중입니다 (최초 1회)...")
            path = JsRuntimeHelper.install_portable_quickjs(
                status_callback=self.status_callback,
                progress_callback=self.progress_callback
            )
        return path

    def download(self, audio_only=False):
        """최고화질 다운로드 실행 및 403 오류 시 자동 복구/대체 다운로드"""
        is_valid, clean_url = validate_url(self.url)
        if not is_valid:
            if self.status_callback:
                self.status_callback(f"오류: {clean_url}")
            return False

        ffmpeg_path = self.get_ffmpeg_path()
        if not ffmpeg_path:
            if self.status_callback:
                self.status_callback("FFmpeg를 준비하지 못했습니다. 인터넷 연결 상태를 확인해주세요.")
            return False

        # 차단 우회용 JS 런타임 준비
        js_path = self.get_js_runtime_path()

        download_path = self.config.get_download_path()
        try:
            download_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            if self.status_callback:
                self.status_callback(f"저장 폴더 생성 실패: {e}")
            return False

        # 1차 시도: 최고화질 web_embedded + android
        ydl_opts = self.config.get_ydl_opts(is_youtube=True, audio_only=audio_only, player_client=["web_embedded", "android"])
        ydl_opts.update({
            "progress_hooks": [self._progress_hook],
            "postprocessor_hooks": [self._postprocessor_hook],
            "ffmpeg_location": ffmpeg_path,
        })
        if js_path:
            pname = Path(js_path).name.lower()
            if "qjs" in pname or "quickjs" in pname:
                ydl_opts["js_runtimes"] = {"quickjs": {"path": js_path}}
            elif "deno" in pname:
                ydl_opts["js_runtimes"] = {"deno": {"path": js_path}}
            elif "node" in pname:
                ydl_opts["js_runtimes"] = {"node": {"path": js_path}}

        if self.status_callback:
            mode_desc = "고음질 오디오(MP3)" if audio_only else "지원 최고화질 영상(MP4)"
            self.status_callback(f"{mode_desc} 다운로드를 시작합니다...")

        try:
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                ydl.download([clean_url])

            if self.status_callback:
                self.status_callback("성공적으로 다운로드되었습니다.")
            if self.progress_callback:
                self.progress_callback(100)
            return True
        except Exception as e:
            err_msg = str(e)
            # 403 Forbidden 또는 스트림 차단 발생 시 Android 클라이언트 단독 대체 모드로 자동 복구
            if "403" in err_msg or "Forbidden" in err_msg or "unable to download" in err_msg:
                if self.status_callback:
                    self.status_callback("YouTube 403 접근 제한 감지: 호환 프로필(Android)로 자동 전환하여 재시도합니다...")
                try:
                    fallback_opts = dict(ydl_opts)
                    fallback_opts["extractor_args"] = {"youtube": {"player_client": ["android"]}}
                    fallback_opts["format"] = "best[ext=mp4]/bestvideo*+bestaudio/best"
                    with youtube_dl.YoutubeDL(fallback_opts) as ydl_fb:
                        ydl_fb.download([clean_url])
                    if self.status_callback:
                        self.status_callback("성공적으로 다운로드되었습니다 (호환 프로필).")
                    if self.progress_callback:
                        self.progress_callback(100)
                    return True
                except Exception as fb_err:
                    err_msg = str(fb_err)

            if self.status_callback:
                self.status_callback(f"다운로드 중 오류가 발생했습니다: {err_msg}")
            return False

    def _progress_hook(self, d):
        if d["status"] == "downloading":
            raw_percent = re.sub(r"\x1b\[[0-9;]*m", "", str(d.get("_percent_str", "0%") or "0%"))
            try:
                percent = float(raw_percent.strip("%"))
            except Exception:
                percent = 0.0

            speed = re.sub(r"\x1b\[[0-9;]*m", "", str(d.get("_speed_str", "") or "")).strip()
            eta = re.sub(r"\x1b\[[0-9;]*m", "", str(d.get("_eta_str", "") or "")).strip()
            size = re.sub(r"\x1b\[[0-9;]*m", "", str(d.get("_total_bytes_str", "") or d.get("_total_bytes_estimate_str", "") or "")).strip()

            if self.detailed_callback:
                self.detailed_callback(percent, speed, eta, size)

            if abs(percent - self.last_percent) >= 1.0 or percent == 100:
                if self.progress_callback:
                    self.progress_callback(percent)
                self.last_percent = percent

        elif d["status"] == "finished":
            fn = d.get("filename")
            if fn:
                self.downloaded_file = fn
            if self.status_callback:
                self.status_callback("다운로드 완료. 영상과 오디오를 최고품질로 병합하고 있습니다 (FFmpeg)...")
            if self.progress_callback:
                self.progress_callback(90)

    def _postprocessor_hook(self, d):
        status = d.get("status")
        if status == "started":
            pp = str(d.get("postprocessor") or "FFmpeg")
            if self.status_callback:
                self.status_callback(f"후처리 작업 중... ({pp})")
            if self.progress_callback:
                self.progress_callback(93)
        elif status == "finished":
            fp = d.get("filepath") or (d.get("info_dict") or {}).get("_filename")
            if fp:
                self.downloaded_file = fp
            if self.progress_callback:
                self.progress_callback(98)


# ============================================================================
# 6. UI 스타일시트 (Clean & Modern Dark Theme)
# ============================================================================
STYLE = """
QMainWindow {
    background-color: #121215;
}
QWidget {
    color: #f4f4f5;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Malgun Gothic", sans-serif;
}
QDialog {
    background-color: #18181b;
}
#HeaderFrame {
    background-color: #18181c;
    border-bottom: 1px solid #27272f;
    padding: 12px 20px;
}
#CardFrame {
    background-color: #1a1a1f;
    border: 1px solid #292933;
    border-radius: 10px;
    padding: 12px;
}
#PreviewCard {
    background-color: #18181d;
    border: 1px solid #2c2c36;
    border-radius: 10px;
}
#SuccessCard {
    background-color: #0d281e;
    border: 1px solid #059669;
    border-radius: 10px;
    padding: 12px;
}
QLineEdit {
    background-color: #202026;
    color: #f4f4f5;
    border: 1px solid #363642;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
    selection-background-color: #ef4444;
}
QLineEdit:focus {
    border: 1px solid #ef4444;
    background-color: #23232b;
}
QPushButton {
    background-color: #26262e;
    color: #f4f4f5;
    border: 1px solid #3a3a46;
    font-size: 13px;
    padding: 7px 14px;
    border-radius: 6px;
    outline: none;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #32323d;
    border-color: #4a4a58;
}
QPushButton:pressed {
    background-color: #3f3f4e;
}
QPushButton:disabled {
    color: #71717a;
    background-color: #1e1e24;
    border-color: #27272f;
}
#PrimaryButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e50914, stop:1 #dc2626);
    color: #ffffff;
    border: none;
    font-size: 14px;
    font-weight: bold;
    padding: 11px 18px;
    border-radius: 8px;
}
#PrimaryButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f43f5e, stop:1 #e11d48);
}
#PrimaryButton:pressed {
    background: #b91c1c;
}
#PrimaryButton:disabled {
    background: #27272f;
    color: #71717a;
}
#SuccessButton {
    background-color: #059669;
    color: #ffffff;
    border: none;
    font-weight: bold;
    padding: 8px 14px;
    border-radius: 6px;
}
#SuccessButton:hover {
    background-color: #10b981;
}
#SecondaryButton {
    background-color: #24242c;
    color: #e4e4e7;
    border: 1px solid #383844;
}
#SecondaryButton:hover {
    background-color: #2f2f3a;
    border-color: #4e4e5e;
}
#BadgeLabel {
    background-color: #064e3b;
    color: #34d399;
    border: 1px solid #059669;
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: bold;
}
QRadioButton {
    color: #e4e4e7;
    font-size: 13px;
    spacing: 8px;
}
QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border-radius: 8px;
    border: 2px solid #52525b;
    background-color: #27272a;
}
QRadioButton::indicator:checked {
    border-color: #ef4444;
    background-color: #ef4444;
}
QProgressBar {
    border: none;
    border-radius: 7px;
    background-color: #24242c;
    text-align: center;
    color: #f4f4f5;
    font-size: 11px;
    font-weight: bold;
    height: 14px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e50914, stop:1 #3b82f6);
    border-radius: 7px;
}
QTextEdit {
    background-color: #161619;
    color: #d4d4d8;
    border: 1px solid #27272f;
    border-radius: 6px;
    padding: 8px;
    font-family: Consolas, Monaco, monospace;
    font-size: 12px;
}
"""


# ============================================================================
# 7. 설정 대화상자 (SettingsDialog)
# ============================================================================
class SettingsDialog(QDialog):
    """간결하고 편리한 설정 대화상자"""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("설정")
        self.setFixedSize(450, 270)
        self.config = config

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(10)

        # 저장 폴더 설정
        folder_box = QHBoxLayout()
        self.path_edit = QLineEdit(str(self.config.get_download_path()))
        self.path_edit.setReadOnly(True)
        folder_box.addWidget(self.path_edit)

        browse_btn = QPushButton("찾아보기")
        browse_btn.clicked.connect(self.on_browse)
        folder_box.addWidget(browse_btn)
        form.addRow("저장 위치:", folder_box)

        # 완료 후 폴더 자동 열기
        self.auto_open_cb = QCheckBox("다운로드 완료 후 저장 폴더 자동으로 열기")
        self.auto_open_cb.setChecked(self.config.get("auto_open_folder", False))
        form.addRow("", self.auto_open_cb)

        # FFmpeg 상태 표시
        ffmpeg_path = FFmpegHelper.check_ffmpeg()
        status_text = f"정상 감지됨 ({Path(ffmpeg_path).name})" if ffmpeg_path else "미설치 (다운로드 시 자동 준비)"
        self.ffmpeg_status_label = QLabel(status_text)
        self.ffmpeg_status_label.setStyleSheet("color: #34d399;" if ffmpeg_path else "color: #f59e0b;")
        form.addRow("FFmpeg 상태:", self.ffmpeg_status_label)

        # JS 엔진 (차단 방지) 상태 표시
        js_path = JsRuntimeHelper.check_js_runtime()
        js_text = f"정상 감지됨 ({Path(js_path).name})" if js_path else "미설치 (다운로드 시 자동 준비)"
        self.js_status_label = QLabel(js_text)
        self.js_status_label.setStyleSheet("color: #34d399;" if js_path else "color: #f59e0b;")
        form.addRow("JS 엔진(403방지):", self.js_status_label)

        layout.addLayout(form)
        layout.addStretch()

        # 버튼
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("저장")
        save_btn.setObjectName("PrimaryButton")
        save_btn.clicked.connect(self.on_save)
        btn_box.addWidget(cancel_btn)
        btn_box.addWidget(save_btn)
        layout.addLayout(btn_box)

    def on_browse(self):
        cur = self.path_edit.text()
        folder = QFileDialog.getExistingDirectory(self, "저장 폴더 선택", cur)
        if folder:
            self.path_edit.setText(folder)

    def on_save(self):
        self.config.set("download_path", self.path_edit.text())
        self.config.set("auto_open_folder", self.auto_open_cb.isChecked())
        self.accept()


# ============================================================================
# 8. 메인 윈도우 (YouTubeDownloaderWindow)
# ============================================================================
class SignalProxy(QObject):
    status = Signal(str)
    progress = Signal(float)
    detailed_progress = Signal(float, str, str, str)
    download_btn_state = Signal(bool)
    complete = Signal(str)
    open_folder = Signal()


class YouTubeDownloaderWindow(QMainWindow):
    """Clean & Modern YouTube 최고화질 다운로더 메인 화면"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube 최고화질 다운로더")
        self.resize(760, 600)
        self.setMinimumSize(700, 520)
        self.config = Config()
        self.last_downloaded_file = None
        self.info_worker = None

        # 아이콘 설정
        icon_path = Path(__file__).resolve().parent / "icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # 시그널 연결
        self.signals = SignalProxy()
        self.signals.status.connect(self.set_status)
        self.signals.progress.connect(self.set_progress)
        self.signals.detailed_progress.connect(self.set_detailed_progress)
        self.signals.download_btn_state.connect(self.on_download_btn_state)
        self.signals.complete.connect(self.on_download_completed)
        self.signals.open_folder.connect(self.on_open_folder)

        # URL 입력 디바운스 타이머
        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(500)
        self.debounce_timer.timeout.connect(self.start_fetch_info)

        self._setup_ui()
        self.set_status("YouTube 영상 URL을 입력하면 지원하는 최고화질을 자동으로 분석합니다.")

    def _setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 1. 헤더 바
        header_frame = QFrame()
        header_frame.setObjectName("HeaderFrame")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(20, 14, 20, 14)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(3)
        title_label = QLabel("YouTube 최고화질 다운로더")
        font = title_label.font()
        font.setPointSize(15)
        font.setBold(True)
        title_label.setFont(font)
        title_label.setStyleSheet("color: #ffffff;")

        sub_label = QLabel("URL 입력 한 번으로 지원하는 최고 해상도(4K/1080p60) 영상을 다운로드합니다.")
        sub_label.setStyleSheet("color: #a1a1aa; font-size: 12px;")
        title_vbox.addWidget(title_label)
        title_vbox.addWidget(sub_label)
        header_layout.addLayout(title_vbox)

        header_layout.addStretch()

        settings_btn = QPushButton("⚙ 설정")
        settings_btn.setObjectName("SecondaryButton")
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.clicked.connect(self.on_open_settings)
        header_layout.addWidget(settings_btn)

        self.main_layout.addWidget(header_frame)

        # 2. 본문 레이아웃
        content_widget = QWidget()
        self.content_layout = QVBoxLayout(content_widget)
        self.content_layout.setContentsMargins(24, 18, 24, 18)
        self.content_layout.setSpacing(14)
        self.main_layout.addWidget(content_widget)

        # 2-1. URL 입력창
        url_box = QHBoxLayout()
        url_box.setSpacing(10)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("YouTube 영상 링크를 입력하거나 붙여넣으세요 (예: https://www.youtube.com/watch?v=...)")
        self.url_edit.setFixedHeight(42)
        self.url_edit.setClearButtonEnabled(True)
        self.url_edit.textChanged.connect(self.on_url_text_changed)
        self.url_edit.returnPressed.connect(self.on_download)
        url_box.addWidget(self.url_edit)

        paste_btn = QPushButton("📋 붙여넣기")
        paste_btn.setFixedHeight(42)
        paste_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        paste_btn.clicked.connect(self.on_paste_link)
        url_box.addWidget(paste_btn)

        self.content_layout.addLayout(url_box)

        # 2-2. 영상 정보 미리보기 카드 (Thumbnail & Metadata Card)
        self.preview_card = QFrame()
        self.preview_card.setObjectName("PreviewCard")
        self.preview_card.setMinimumHeight(120)
        self.preview_layout = QVBoxLayout(self.preview_card)
        self.preview_layout.setContentsMargins(14, 14, 14, 14)

        # 안내 문구 (기본)
        self.preview_placeholder = QLabel("💡 유튜브 링크를 입력하면 영상 썸네일과 지원 최고화질이 자동으로 감지됩니다.")
        self.preview_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_placeholder.setStyleSheet("color: #71717a; font-size: 13px;")
        self.preview_layout.addWidget(self.preview_placeholder)

        # 세부 정보 박스 (분석 후 표시)
        self.preview_content = QWidget()
        self.preview_content.setVisible(False)
        preview_box = QHBoxLayout(self.preview_content)
        preview_box.setContentsMargins(0, 0, 0, 0)
        preview_box.setSpacing(16)

        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(160, 90)
        self.thumb_label.setStyleSheet("background-color: #27272f; border-radius: 6px; border: 1px solid #3f3f4e;")
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_box.addWidget(self.thumb_label)

        meta_vbox = QVBoxLayout()
        meta_vbox.setSpacing(6)
        meta_vbox.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.video_title_label = QLabel()
        self.video_title_label.setWordWrap(True)
        self.video_title_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold;")
        meta_vbox.addWidget(self.video_title_label)

        self.video_meta_label = QLabel()
        self.video_meta_label.setStyleSheet("color: #a1a1aa; font-size: 12px;")
        meta_vbox.addWidget(self.video_meta_label)

        badge_row = QHBoxLayout()
        badge_row.setSpacing(8)
        self.quality_badge = QLabel("✨ 최고화질")
        self.quality_badge.setObjectName("BadgeLabel")
        badge_row.addWidget(self.quality_badge)

        self.format_note_label = QLabel("🎬 최고화질 영상 + 무손실 음원 자동 병합 (MP4)")
        self.format_note_label.setStyleSheet("color: #a1a1aa; font-size: 12px;")
        badge_row.addWidget(self.format_note_label)
        badge_row.addStretch()

        meta_vbox.addLayout(badge_row)
        preview_box.addLayout(meta_vbox)

        self.preview_layout.addWidget(self.preview_content)
        self.content_layout.addWidget(self.preview_card)

        # 2-3. 다운로드 옵션 및 저장 폴더 바
        options_frame = QFrame()
        options_frame.setObjectName("CardFrame")
        options_layout = QHBoxLayout(options_frame)
        options_layout.setContentsMargins(14, 10, 14, 10)
        options_layout.setSpacing(20)

        # 모드 선택 라디오
        mode_box = QHBoxLayout()
        mode_box.setSpacing(14)
        self.format_group = QButtonGroup(self)
        self.video_radio = QRadioButton("🎬 최고화질 영상 (MP4)")
        self.audio_radio = QRadioButton("🎵 고음질 음원 추출 (MP3)")
        self.video_radio.setChecked(True)
        self.video_radio.toggled.connect(self.on_format_changed)
        self.format_group.addButton(self.video_radio)
        self.format_group.addButton(self.audio_radio)
        mode_box.addWidget(self.video_radio)
        mode_box.addWidget(self.audio_radio)
        options_layout.addLayout(mode_box)

        options_layout.addStretch()

        # 저장 위치 표시
        save_box = QHBoxLayout()
        save_box.setSpacing(8)
        self.folder_label = QLabel(f"저장 폴더: {self.config.get_download_path().name}")
        self.folder_label.setStyleSheet("color: #a1a1aa; font-size: 12px;")
        self.folder_label.setToolTip(str(self.config.get_download_path()))
        save_box.addWidget(self.folder_label)

        change_folder_btn = QPushButton("폴더 변경")
        change_folder_btn.setObjectName("SecondaryButton")
        change_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        change_folder_btn.clicked.connect(self.on_change_folder)
        save_box.addWidget(change_folder_btn)

        open_folder_btn = QPushButton("폴더 열기")
        open_folder_btn.setObjectName("SecondaryButton")
        open_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_folder_btn.clicked.connect(self.on_open_folder)
        save_box.addWidget(open_folder_btn)

        options_layout.addLayout(save_box)
        self.content_layout.addWidget(options_frame)

        # 2-4. 대형 메인 다운로드 버튼
        self.download_btn = QPushButton("⬇ 지원 최고화질로 다운로드 시작")
        self.download_btn.setObjectName("PrimaryButton")
        self.download_btn.setFixedHeight(48)
        self.download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_btn.clicked.connect(self.on_download)
        self.content_layout.addWidget(self.download_btn)

        # 2-5. 진행 상태 및 프로그레스 바
        progress_vbox = QVBoxLayout()
        progress_vbox.setSpacing(6)

        status_row = QHBoxLayout()
        self.progress_status_label = QLabel("준비 완료")
        self.progress_status_label.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 500;")
        status_row.addWidget(self.progress_status_label)

        status_row.addStretch()

        self.progress_detail_label = QLabel("")
        self.progress_detail_label.setStyleSheet("color: #a1a1aa; font-size: 12px;")
        status_row.addWidget(self.progress_detail_label)
        progress_vbox.addLayout(status_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        progress_vbox.addWidget(self.progress)
        self.content_layout.addLayout(progress_vbox)

        # 2-6. 완료 액션 카드 (평소 숨김)
        self.complete_card = QFrame()
        self.complete_card.setObjectName("SuccessCard")
        self.complete_card.setVisible(False)
        complete_layout = QHBoxLayout(self.complete_card)
        complete_layout.setContentsMargins(14, 10, 14, 10)
        complete_layout.setSpacing(12)

        complete_msg = QLabel("🎉 다운로드가 성공적으로 완료되었습니다!")
        complete_msg.setStyleSheet("color: #34d399; font-size: 13px; font-weight: bold;")
        complete_layout.addWidget(complete_msg)

        complete_layout.addStretch()

        self.play_file_btn = QPushButton("▶ 영상 재생")
        self.play_file_btn.setObjectName("SuccessButton")
        self.play_file_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_file_btn.clicked.connect(self.on_play_downloaded_file)
        complete_layout.addWidget(self.play_file_btn)

        open_complete_folder_btn = QPushButton("📂 저장 폴더 열기")
        open_complete_folder_btn.setObjectName("SecondaryButton")
        open_complete_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_complete_folder_btn.clicked.connect(self.on_open_folder)
        complete_layout.addWidget(open_complete_folder_btn)

        self.content_layout.addWidget(self.complete_card)

        # 2-7. 접이식 상세 로그 (기본 닫힘)
        log_header = QHBoxLayout()
        self.toggle_log_btn = QPushButton("▼ 상세 로그 보기")
        self.toggle_log_btn.setObjectName("SecondaryButton")
        self.toggle_log_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_log_btn.setFixedHeight(28)
        self.toggle_log_btn.clicked.connect(self.on_toggle_log)
        log_header.addWidget(self.toggle_log_btn)
        log_header.addStretch()
        self.content_layout.addLayout(log_header)

        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setFixedHeight(120)
        self.status_text.setVisible(False)
        self.content_layout.addWidget(self.status_text)

    # --- 이벤트 핸들러 및 슬롯 ---

    def on_url_text_changed(self, text):
        clean = text.strip()
        is_valid, _ = validate_url(clean)
        if is_valid:
            self.debounce_timer.start()
        else:
            self.debounce_timer.stop()
            self.preview_placeholder.setText("💡 유튜브 링크를 입력하면 영상 썸네일과 지원 최고화질이 자동으로 감지됩니다.")
            self.preview_placeholder.setVisible(True)
            self.preview_content.setVisible(False)

    def start_fetch_info(self):
        url = self.url_edit.text().strip()
        is_valid, clean_url = validate_url(url)
        if not is_valid:
            return

        self.preview_placeholder.setText("🔍 영상 정보 및 지원 최고화질 분석 중...")
        self.preview_placeholder.setVisible(True)
        self.preview_content.setVisible(False)

        if self.info_worker and self.info_worker.isRunning():
            self.info_worker.terminate()
            self.info_worker.wait()

        self.info_worker = VideoInfoWorker(clean_url)
        self.info_worker.info_ready.connect(self.on_info_ready)
        self.info_worker.info_failed.connect(self.on_info_failed)
        self.info_worker.start()

    def on_info_ready(self, data):
        self.preview_placeholder.setVisible(False)
        self.preview_content.setVisible(True)

        self.video_title_label.setText(data.get("title", "제목 없음"))
        self.video_meta_label.setText(f"채널: {data.get('uploader')}   |   재생시간: {data.get('duration')}")
        self.quality_badge.setText(f"✨ 지원 최고화질: {data.get('max_res')}")

        thumb_data = data.get("thumbnail_data")
        if thumb_data:
            img = QImage.fromData(thumb_data)
            if not img.isNull():
                pm = QPixmap.fromImage(img)
                scaled = pm.scaled(160, 90, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                self.thumb_label.setPixmap(scaled)
        else:
            self.thumb_label.setText("썸네일 없음")

        if self.audio_radio.isChecked():
            self.download_btn.setText("⬇ 고음질 음원 추출 시작 (MP3)")
        else:
            self.download_btn.setText(f"⬇ 최고화질 영상 다운로드 ({data.get('max_res')})")

    def on_info_failed(self, msg):
        self.preview_placeholder.setText(f"⚠️ {msg}")
        self.preview_placeholder.setVisible(True)
        self.preview_content.setVisible(False)

    def on_format_changed(self):
        if self.audio_radio.isChecked():
            self.download_btn.setText("⬇ 고음질 음원 추출 시작 (MP3)")
            self.format_note_label.setText("🎵 고음질 오디오 무손실 추출 (MP3/320k)")
        else:
            self.download_btn.setText("⬇ 지원 최고화질로 다운로드 시작")
            self.format_note_label.setText("🎬 최고화질 영상 + 무손실 음원 자동 병합 (MP4)")

    def on_change_folder(self):
        cur = str(self.config.get_download_path())
        folder = QFileDialog.getExistingDirectory(self, "저장 폴더를 선택하세요", cur)
        if folder:
            self.config.set("download_path", folder)
            self.folder_label.setText(f"저장 폴더: {Path(folder).name}")
            self.folder_label.setToolTip(folder)
            self.set_status(f"저장 폴더가 변경되었습니다: {folder}")

    def on_open_folder(self):
        folder = self.config.get_download_path()
        if not open_folder(str(folder)):
            QMessageBox.warning(self, "오류", f"저장 폴더를 열 수 없습니다: {folder}")

    def on_play_downloaded_file(self):
        if self.last_downloaded_file and Path(self.last_downloaded_file).is_file():
            play_file(self.last_downloaded_file)
        else:
            self.on_open_folder()

    def on_toggle_log(self):
        vis = self.status_text.isVisible()
        self.status_text.setVisible(not vis)
        self.toggle_log_btn.setText("▲ 상세 로그 닫기" if not vis else "▼ 상세 로그 보기")

    def on_download_btn_state(self, enabled):
        self.download_btn.setEnabled(enabled)
        if enabled:
            self.on_format_changed()
        else:
            self.download_btn.setText("⏳ 다운로드 진행 중...")

    def set_status(self, msg):
        try:
            self.status_text.append(msg)
            self.status_text.moveCursor(self.status_text.textCursor().MoveOperation.End)
            line = msg.strip().split("\n")[-1]
            if line and hasattr(self, "progress_status_label"):
                self.progress_status_label.setText(line)
        except Exception:
            pass

    def set_progress(self, percent):
        try:
            self.progress.setValue(int(percent))
        except Exception:
            pass

    def set_detailed_progress(self, percent, speed, eta, size):
        try:
            self.progress.setValue(int(percent))
            details = []
            if speed:
                details.append(f"속도: {speed}")
            if eta:
                details.append(f"남은 시간: {eta}")
            if size:
                details.append(f"용량: {size}")
            self.progress_detail_label.setText(" · ".join(details))
        except Exception:
            pass

    def on_download_completed(self, filepath):
        self.last_downloaded_file = filepath
        self.complete_card.setVisible(True)
        self.progress_status_label.setText("✅ 다운로드가 성공적으로 완료되었습니다!")
        self.progress_detail_label.setText("")

    def on_paste_link(self):
        cb = QApplication.clipboard()
        text = cb.text().strip()
        if text:
            self.url_edit.setText(text)
            self.url_edit.setFocus()
            self.start_fetch_info()

    def on_download(self):
        url = self.url_edit.text().strip()
        is_valid, clean_url = validate_url(url)
        if not is_valid:
            QMessageBox.warning(self, "입력 오류", clean_url)
            return

        self.complete_card.setVisible(False)
        self.set_status("다운로드를 시작합니다...")
        self.signals.download_btn_state.emit(False)
        self.progress.setValue(0)
        self.progress_detail_label.setText("")

        audio_only = self.audio_radio.isChecked()
        threading.Thread(target=self._download_worker, args=(clean_url, audio_only), daemon=True).start()

    def _download_worker(self, url, audio_only=False):
        try:
            downloader = YouTubeDownloader(
                url,
                status_callback=lambda m: self.signals.status.emit(m),
                progress_callback=lambda p: self.signals.progress.emit(p),
                detailed_callback=lambda p, s, e, sz: self.signals.detailed_progress.emit(p, s, e, sz)
            )
            success = downloader.download(audio_only=audio_only)
            if success:
                self.signals.status.emit("다운로드가 완료되었습니다.")
                self.signals.complete.emit(str(downloader.downloaded_file or ""))
                if self.config.get("auto_open_folder", False):
                    self.signals.open_folder.emit()
            else:
                self.signals.status.emit("다운로드에 실패했습니다.")
        finally:
            self.signals.download_btn_state.emit(True)

    def on_open_settings(self):
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.folder_label.setText(f"저장 폴더: {self.config.get_download_path().name}")
            self.folder_label.setToolTip(str(self.config.get_download_path()))
            self.set_status("설정이 저장되었습니다.")


# ============================================================================
# 9. 메인 진입점
# ============================================================================
def main():
    parser = argparse.ArgumentParser(description="YouTube 최고화질 다운로더")
    parser.add_argument("--url", help="다운로드할 YouTube 영상 URL (CLI 모드)")
    parser.add_argument("--audio-only", action="store_true", help="오디오만 MP3로 다운로드")
    args = parser.parse_args()

    if args.url:
        downloader = YouTubeDownloader(
            args.url,
            status_callback=print,
            progress_callback=lambda p: print(f"진행률: {p:.1f}%", flush=True)
        )
        success = downloader.download(audio_only=args.audio_only)
        sys.exit(0 if success else 1)

    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    win = YouTubeDownloaderWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

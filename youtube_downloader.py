"""
YouTube 최고화질 다운로더 (YouTube Best Quality Downloader)
- 완전 독립형 단일 파일 프로그램 (All-in-One Standalone)
- 원본 최고화질(4K / 2K / 1080p60) 영상+음원 병합 다운로드 · MP3 음원 추출
- 영상 / 재생목록 / 채널 미리보기 카드 UI
- 포터블 FFmpeg · QuickJS 자동 감지 및 필요 시 자동 준비
"""
import sys
import os
import argparse
import glob
import json
import math
import re
import platform
import shutil
import subprocess
import tarfile
import tempfile
import threading
import time
import traceback
import urllib.request
import urllib.parse
import zipfile
from functools import lru_cache
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

from PySide6.QtGui import (
    QColor, QDesktopServices, QFont, QIcon, QImage, QPainter, QPainterPath,
    QPalette, QPen, QPixmap, QTextLayout,
)
from PySide6.QtCore import (
    QEvent, QLibraryInfo, QLocale, QObject, QPointF, QRectF, QSize, Qt,
    QTimer, QTranslator, QUrl, Signal,
)
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QDialog, QFileDialog, QFormLayout,
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSizePolicy,
    QSpinBox, QStackedLayout, QVBoxLayout, QWidget,
)

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

import yt_dlp as youtube_dl
from yt_dlp.utils import DownloadCancelled, DownloadError

try:
    from yt_dlp.networking.exceptions import HTTPError as YtdlHTTPError
except Exception:  # 구버전 yt-dlp
    YtdlHTTPError = None


APP_TITLE = "YouTube 최고화질 다운로더"
APP_ID = "YouTubeDownloader"


# ============================================================================
# 0. 공용 유틸리티
# ============================================================================
def app_base_dir():
    """실행 파일(frozen) 또는 스크립트가 위치한 폴더"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def user_data_dir():
    """자동으로 받은 FFmpeg/QuickJS를 둘 사용자 전용(쓰기 가능) 폴더"""
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    elif system == "Darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / APP_ID


def resource_path(name):
    """번들 리소스(PyInstaller _MEIPASS) → 실행 폴더 순으로 파일 탐색"""
    bases = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bases.append(Path(meipass))
    bases.append(app_base_dir())
    for base in bases:
        candidate = base / name
        if candidate.exists():
            return candidate
    return None


def _hidden_subprocess_kwargs():
    """Windows 창 모드(exe)에서 외부 프로그램 실행 시 콘솔 창이 깜빡이지 않도록 설정"""
    if platform.system() != "Windows":
        return {}
    kwargs = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        kwargs["startupinfo"] = si
    except Exception:
        pass
    return kwargs


def _run_probe(cmd, timeout=15):
    """외부 프로그램을 조용히 실행해 결과 반환 (실패 시 None)"""
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, **_hidden_subprocess_kwargs()
        )
    except Exception:
        return None


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def clean_message(text):
    """yt-dlp 메시지에서 ANSI 색상 코드, 'ERROR:' 접두어, [추출기] 머리말 제거"""
    if isinstance(text, BaseException):
        text = str(text) or type(text).__name__
    text = _ANSI_RE.sub("", str(text or "")).strip()
    text = re.sub(r"^(ERROR|WARNING):\s*", "", text)
    text = re.sub(r"^\[[\w:.-]+\]\s*(?:[\w-]+:\s+)?", "", text)
    return text.strip()


def friendly_error(err):
    """기술적인 오류 메시지를 이해하기 쉬운 한국어 안내로 변환"""
    raw = clean_message(err)
    low = raw.lower()
    rules = [
        (("private video",), "비공개 영상이라 받을 수 없습니다."),
        (("members-only", "join this channel"), "채널 멤버십 전용 영상이라 받을 수 없습니다."),
        (("confirm your age", "age-restricted", "age restricted", "inappropriate for some users"),
         "연령 제한 영상이라 로그인 없이는 받을 수 없습니다."),
        (("not a bot", "sign in to confirm"), "YouTube가 봇 확인을 요구하고 있습니다. 잠시 후 다시 시도해주세요."),
        (("does not have a videos tab", "this channel does not have"), "이 채널에는 받을 수 있는 동영상 목록이 없습니다."),
        (("incomplete youtube id", "looks truncated"), "영상 주소가 잘렸습니다. 링크를 끝까지 복사해주세요."),
        (("video unavailable", "video is unavailable", "this video is not available", "has been removed", "does not exist",
          "playlist does not exist", "this playlist is private", "unavailable video"),
         "영상을 찾을 수 없습니다. 삭제되었거나 볼 수 없는 영상입니다."),
        (("not available in your country", "geo restrict", "geo-restrict", "blocked it in your country"),
         "현재 지역에서는 볼 수 없는 영상입니다."),
        (("not currently live",), "지금은 라이브 방송 중이 아닙니다."),
        (("premieres in", "live event will begin", "this live event", "is_upcoming"),
         "아직 시작하지 않은 실시간/최초 공개 영상입니다."),
        (("unsupported url",), "지원하지 않는 주소입니다. 영상 페이지 주소를 확인해주세요."),
        (("requested format is not available", "no video formats found"),
         "받을 수 있는 화질/형식을 찾지 못했습니다. 잠시 후 다시 시도해주세요."),
        (("http error 429", "too many requests"), "요청이 너무 많아 YouTube가 잠시 막았습니다. 몇 분 뒤 다시 시도해주세요."),
        (("http error 403", "forbidden"), "YouTube가 접근을 거부했습니다(403). 잠시 후 다시 시도해주세요."),
        (("http error 400", "bad request"), "주소 형식이 올바르지 않습니다. 링크를 다시 복사해주세요."),
        (("http error 404", "requested entity was not found"), "주소에 해당하는 영상이나 채널을 찾을 수 없습니다(404)."),
        (("getaddrinfo", "name or service not known", "nodename nor servname", "no address associated",
          "failed to resolve", "temporary failure in name resolution", "network is unreachable",
          "connection refused", "connection reset", "timed out", "urlopen error", "remote end closed",
          "connection aborted", "unable to connect"),
         "인터넷 연결을 확인해주세요. (서버에 연결할 수 없습니다)"),
        (("certificate verify failed", "ssl:"), "보안 연결(SSL) 오류가 발생했습니다. 네트워크/백신 설정을 확인해주세요."),
        (("no space left", "disk full", "errno 28", "not enough space"), "저장 공간이 부족합니다."),
        (("permission denied", "access is denied", "errno 13", "winerror 5"),
         "저장 폴더에 쓸 권한이 없습니다. 설정에서 다른 폴더를 선택해주세요."),
        (("ffmpeg", "ffprobe", "postprocessing"), "FFmpeg 처리 중 오류가 발생했습니다. (영상/음원 변환 실패)"),
    ]
    for keys, message in rules:
        if any(k in low for k in keys):
            return message
    first = raw.splitlines()[0].strip() if raw else ""
    if not first:
        return "알 수 없는 오류가 발생했습니다."
    return first if len(first) <= 160 else first[:157] + "…"


def format_bytes(num):
    if num is None:
        return ""
    num = float(num)
    for unit in ("B", "KB", "MB", "GB"):
        if abs(num) < 1024 or unit == "GB":
            return f"{num:.0f} {unit}" if unit in ("B", "KB") else f"{num:.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} TB"


def format_seconds(sec):
    try:
        sec = int(sec)
    except (TypeError, ValueError):
        return ""
    if sec < 0:
        return ""
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class _KeepAwake:
    """긴 다운로드 중 Windows 절전 모드 진입 방지 (같은 스레드에서 해제)"""
    def __enter__(self):
        self._on = False
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
                self._on = True
            except Exception:
                pass
        return self

    def __exit__(self, *exc):
        if self._on:
            try:
                import ctypes
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            except Exception:
                pass
        return False


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
            "auto_open_folder": False,
            "max_retries": 3,
            "compat_mode": False,
        }
        self.config = self.load_config()

    def load_config(self):
        data = {}
        try:
            if self.config_file.exists():
                with open(self.config_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    data = loaded
        except Exception:
            pass
        # 값의 형식이 잘못되었으면(직접 편집 등) 기본값으로 복구
        for key, default in self.default_config.items():
            value = data.get(key)
            if type(value) is not type(default) or (isinstance(default, str) and not value.strip()):
                data[key] = default
        return data

    def save_config(self):
        tmp = self.config_file.with_name(self.config_file.name + ".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.config_file)
        except Exception as e:
            print(f"설정 저장 실패: {e}")
            try:
                tmp.unlink()
            except OSError:
                pass

    def get(self, key, default=None):
        return self.config.get(key, self.default_config.get(key, default))

    def get_int(self, key, default, lo, hi):
        try:
            value = int(self.get(key, default))
        except (TypeError, ValueError):
            value = default
        return max(lo, min(hi, value))

    def set(self, key, value):
        self.config[key] = value
        self.save_config()

    def update(self, values):
        self.config.update(values)
        self.save_config()

    def get_download_path(self):
        return Path(self.get("download_path") or self.default_config["download_path"])

    def get_ydl_opts(self, kind="video", audio_only=False, player_client=None):
        """최고화질 다운로드를 위한 yt-dlp 옵션 생성

        kind: "video"(단일 영상) / "playlist"(재생목록) / "channel"(채널)
        """
        base = self.get_download_path()
        # 제목이 같은 다른 영상이 '이미 받은 파일'로 건너뛰어지지 않도록 영상 ID를 파일명에 포함
        name = "%(title).150B [%(id)s].%(ext)s"
        if kind == "channel":
            outtmpl = str(base / "%(playlist_uploader,playlist_channel,uploader,channel|채널)s" / name)
        elif kind == "playlist":
            outtmpl = str(base / "%(playlist_title,playlist_uploader|재생목록)s" / name)
        else:
            outtmpl = str(base / name)

        retries = self.get_int("max_retries", 3, 0, 10)
        opts = {
            "outtmpl": outtmpl,
            "noplaylist": kind == "video",
            "nooverwrites": True,          # 이미 받은 파일은 건너뛰기
            "continuedl": True,
            "quiet": True,
            "noprogress": True,
            "color": "no_color",
            "retries": retries,
            "fragment_retries": retries,
            "ignoreerrors": kind != "video",  # 재생목록/채널: 삭제·비공개 영상은 건너뛰고 계속
            "remote_components": {"ejs:github"},
            "js_runtimes": JsRuntimeHelper.ydl_runtimes(),
        }

        # player_client는 지정하지 않음 → yt-dlp가 관리하는 최신 기본 클라이언트 조합 사용
        if player_client:
            opts["extractor_args"] = {"youtube": {"player_client": list(player_client)}}

        if audio_only:
            opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"
            opts["final_ext"] = "mp3"  # 이미 변환된 MP3가 있으면 건너뛰기
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }]
        elif self.get("compat_mode", False):
            # 호환성 우선: H.264 + AAC (PowerPoint·한컴·구형 플레이어에서도 재생, 최대 1080p)
            opts["format"] = "bv*[vcodec^=avc1]+ba[acodec^=mp4a]/b[ext=mp4]/bv*+ba/b"
            opts["format_sort"] = ["vcodec:h264", "acodec:aac", "res", "fps"]
            opts["merge_output_format"] = "mp4"
        else:
            # 해상도 제한 없이 가장 좋은 영상 + 가장 좋은 음원 병합
            opts["format"] = "bestvideo*+bestaudio/best"
            opts["format_sort"] = ["res", "fps", "hdr:12", "vcodec", "channels", "br"]
            opts["merge_output_format"] = "mp4"
        return opts


# ============================================================================
# 2. 포터블 FFmpeg / JS 런타임 감지 및 필요 시 자동 준비
# ============================================================================
_TOOL_CACHE = {}
_TOOL_LOCK = threading.Lock()


def _cached_tool(key, finder, refresh=False):
    with _TOOL_LOCK:
        if not refresh and key in _TOOL_CACHE:
            cached = _TOOL_CACHE[key]
            if cached is None or Path(cached).is_file():
                return cached
    found = finder()
    with _TOOL_LOCK:
        _TOOL_CACHE[key] = found
    return found


def _download_to_file(url, target, progress_callback=None, cancel_check=None, span=(0, 90)):
    """URL을 target.part로 받은 뒤 완료되면 target으로 교체"""
    part = Path(str(target) + ".part")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp, open(part, "wb") as f:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            while True:
                if cancel_check and cancel_check():
                    raise DownloadCancelled("사용자가 중지했습니다.")
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if total and progress_callback:
                    progress_callback(span[0] + (span[1] - span[0]) * done / total)
        os.replace(part, target)
        return Path(target)
    finally:
        if part.exists():
            try:
                part.unlink()
            except OSError:
                pass


class FFmpegHelper:
    """포터블 FFmpeg 탐색 및 무설치 자동 다운로드 유틸리티"""

    @staticmethod
    def _candidates():
        exe_name = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
        base_dir = app_base_dir()
        candidates = [base_dir / exe_name, base_dir / "bin" / exe_name]
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates += [Path(meipass) / exe_name, Path(meipass) / "bin" / exe_name]
        candidates.append(user_data_dir() / "ffmpeg" / exe_name)

        # imageio-ffmpeg 패키지 내장 정적 바이너리
        try:
            import imageio_ffmpeg
            img_exe = imageio_ffmpeg.get_ffmpeg_exe()
            if img_exe:
                candidates.append(Path(img_exe))
        except Exception:
            pass

        if platform.system() == "Windows":
            legacy = Path.home() / "ffmpeg"  # 이전 버전이 설치하던 위치
            if legacy.is_dir():
                candidates.extend(p for p in legacy.glob("**/ffmpeg.exe") if p.is_file())
            candidates.append(Path("C:/ffmpeg/bin/ffmpeg.exe"))
        else:
            candidates.extend([
                Path.home() / ".local" / "ffmpeg" / "ffmpeg",
                Path("/opt/homebrew/bin/ffmpeg"),
                Path("/usr/local/bin/ffmpeg"),
                Path("/usr/bin/ffmpeg"),
            ])
        which_path = shutil.which("ffmpeg")
        if which_path:
            candidates.append(Path(which_path))
        return candidates

    @staticmethod
    def _find():
        seen = set()
        for cand in FFmpegHelper._candidates():
            key = str(cand).lower()
            if key in seen or not cand.is_file():
                continue
            seen.add(key)
            res = _run_probe([str(cand), "-version"])
            if res is not None and res.returncode == 0:
                return str(cand)
        return None

    @staticmethod
    def check_ffmpeg(debug=False, refresh=False):
        """1) 실행 폴더/bin 2) 사용자 폴더 3) imageio-ffmpeg 4) 시스템 PATH 순으로 탐색 (결과 캐시)"""
        path = _cached_tool("ffmpeg", FFmpegHelper._find, refresh)
        if debug and path:
            print(f"[FFmpeg] 유효한 바이너리 발견: {path}")
        return path

    @staticmethod
    def install_portable_ffmpeg(status_callback=None, progress_callback=None, cancel_check=None):
        """관리자 권한 없이 사용자 폴더에 포터블 FFmpeg 자동 다운로드 (ffmpeg/ffprobe만 추출)"""
        system = platform.system()
        if system == "Windows":
            url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
            archive_name = "ffmpeg_download.zip"
        elif system == "Darwin":
            url = "https://evermeet.cx/ffmpeg/getrelease/zip"
            archive_name = "ffmpeg_download.zip"
        else:
            url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz"
            archive_name = "ffmpeg_download.tar.xz"

        exe_suffix = ".exe" if system == "Windows" else ""
        wanted = {f"ffmpeg{exe_suffix}", f"ffprobe{exe_suffix}"}
        target_dir = user_data_dir() / "ffmpeg"
        archive = target_dir / archive_name
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            if status_callback:
                status_callback("FFmpeg 내려받는 중… (최초 1회, 약 150MB)")
            _download_to_file(url, archive, progress_callback, cancel_check)

            if status_callback:
                status_callback("FFmpeg 압축을 푸는 중…")
            if zipfile.is_zipfile(archive):
                with zipfile.ZipFile(archive) as zf:
                    for member in zf.infolist():
                        name = Path(member.filename).name
                        if name in wanted and not member.is_dir():
                            with zf.open(member) as src, open(target_dir / name, "wb") as dst:
                                shutil.copyfileobj(src, dst)
            else:
                with tarfile.open(archive) as tf:
                    for member in tf.getmembers():
                        name = Path(member.name).name
                        if name in wanted and member.isfile():
                            src = tf.extractfile(member)
                            if src:
                                with src, open(target_dir / name, "wb") as dst:
                                    shutil.copyfileobj(src, dst)

            exe = target_dir / f"ffmpeg{exe_suffix}"
            if system != "Windows":
                for name in wanted:
                    if (target_dir / name).exists():
                        os.chmod(target_dir / name, 0o755)
            res = _run_probe([str(exe), "-version"]) if exe.is_file() else None
            if res is None or res.returncode != 0:
                raise RuntimeError("내려받은 FFmpeg를 실행할 수 없습니다.")
            with _TOOL_LOCK:
                _TOOL_CACHE["ffmpeg"] = str(exe)
            if status_callback:
                status_callback("FFmpeg 준비 완료")
            if progress_callback:
                progress_callback(100)
            return str(exe)
        except DownloadCancelled:
            raise
        except Exception as e:
            if status_callback:
                status_callback(f"FFmpeg 준비 실패: {friendly_error(e)}")
            return None
        finally:
            if archive.exists():
                try:
                    archive.unlink()
                except OSError:
                    pass


class JsRuntimeHelper:
    """YouTube 서명(JS 챌린지) 해제용 JS 런타임 (QuickJS/Deno/Node/Bun) 탐색 및 자동 준비"""

    @staticmethod
    def _qjs_name():
        return "qjs.exe" if platform.system() == "Windows" else "qjs"

    @staticmethod
    def _find_quickjs():
        name = JsRuntimeHelper._qjs_name()
        base_dir = app_base_dir()
        candidates = [base_dir / "bin" / name, base_dir / name]
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates += [Path(meipass) / "bin" / name, Path(meipass) / name]
        candidates.append(user_data_dir() / "bin" / name)
        candidates.append(Path.home() / "ffmpeg" / name)  # 이전 버전 호환
        which_path = shutil.which("qjs")
        if which_path:
            candidates.append(Path(which_path))
        for cand in candidates:
            if cand.is_file():
                res = _run_probe([str(cand), "--help"])
                if res is not None and ("QuickJS" in (res.stdout or "") + (res.stderr or "") or res.returncode == 0):
                    return str(cand)
        return None

    @staticmethod
    def find_quickjs(refresh=False):
        return _cached_tool("quickjs", JsRuntimeHelper._find_quickjs, refresh)

    @staticmethod
    def _find_any():
        qjs = JsRuntimeHelper.find_quickjs()
        if qjs:
            return qjs
        for name in ("deno", "node", "bun"):
            path = shutil.which(name)
            if path:
                res = _run_probe([path, "--version"])
                if res is not None and res.returncode == 0:
                    return path
        return None

    @staticmethod
    def check_js_runtime(debug=False, refresh=False):
        """사용 가능한 JS 런타임 경로 (번들 QuickJS 우선, 결과 캐시)"""
        if refresh:
            JsRuntimeHelper.find_quickjs(refresh=True)
        path = _cached_tool("js_any", JsRuntimeHelper._find_any, refresh)
        if debug and path:
            print(f"[JS] 유효한 JS 런타임 발견: {path}")
        return path

    @staticmethod
    def ydl_runtimes():
        """yt-dlp에 넘길 js_runtimes (번들 QuickJS + 설치된 deno/node/bun 중 yt-dlp가 버전을 검증해 선택)"""
        runtimes = {}
        qjs = JsRuntimeHelper.find_quickjs()
        if qjs:
            runtimes["quickjs"] = {"path": qjs}
        for name in ("deno", "node", "bun"):
            runtimes[name] = {}
        return runtimes

    @staticmethod
    def install_portable_quickjs(status_callback=None, progress_callback=None, cancel_check=None):
        """약 2MB 크기의 초경량 QuickJS를 사용자 폴더에 자동 다운로드"""
        system = platform.system()
        if system == "Windows":
            url = "https://github.com/quickjs-ng/quickjs/releases/download/v0.17.0/qjs-windows-x86_64.exe"
        elif system == "Darwin":
            url = "https://github.com/quickjs-ng/quickjs/releases/download/v0.17.0/qjs-darwin-arm64"
        else:
            url = "https://github.com/quickjs-ng/quickjs/releases/download/v0.17.0/qjs-linux-x86_64"
        target = user_data_dir() / "bin" / JsRuntimeHelper._qjs_name()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if status_callback:
                status_callback("YouTube 서명 해제용 JS 엔진 준비 중… (최초 1회, 약 2MB)")
            _download_to_file(url, target, progress_callback, cancel_check)
            if system != "Windows":
                os.chmod(target, 0o755)
            res = _run_probe([str(target), "--help"])
            if res is None or "QuickJS" not in (res.stdout or "") + (res.stderr or ""):
                target.unlink(missing_ok=True)
                raise RuntimeError("내려받은 JS 엔진을 실행할 수 없습니다.")
            with _TOOL_LOCK:
                _TOOL_CACHE["quickjs"] = str(target)
                _TOOL_CACHE["js_any"] = str(target)
            if status_callback:
                status_callback("JS 엔진 준비 완료")
            if progress_callback:
                progress_callback(100)
            return str(target)
        except DownloadCancelled:
            raise
        except Exception as e:
            if status_callback:
                status_callback(f"JS 엔진 준비 실패: {friendly_error(e)} (기본 방식으로 계속합니다)")
            return None


# ============================================================================
# 3. URL 판별 · 정규화 및 시스템 유틸리티
# ============================================================================
_YT_ID_RE = re.compile(r"[A-Za-z0-9_-]{11}")
_YT_HOSTS = ("youtube.com", "youtube-nocookie.com")
_CHANNEL_TABS_KEEP = {"videos", "shorts", "streams", "playlists", "releases", "podcasts", "courses"}
# youtube.com/<이름> 형태의 옛 채널 주소와 구분하기 위한 예약 경로 (yt-dlp 목록 기준)
_YT_RESERVED = {
    "channel", "c", "user", "playlist", "watch", "w", "v", "embed", "e", "live", "watch_popup", "clip",
    "shorts", "movies", "results", "search", "shared", "hashtag", "trending", "explore", "feed", "feeds",
    "browse", "oembed", "get_video_info", "iframe_api", "s", "source", "storefront", "oops", "index",
    "account", "t", "about", "upload", "signin", "logout", "redirect", "premium", "attribution_link",
    "gaming", "kids", "music", "podcasts", "creator", "studio", "howyoutubeworks", "ads", "jobs",
}


def _is_youtube_host(host):
    host = (host or "").lower()
    return host in ("youtu.be", "www.youtu.be") or any(host == h or host.endswith("." + h) for h in _YT_HOSTS)


def extract_url(text):
    """붙여넣은 문장 속에서 첫 번째 링크를 찾아 반환 (https:// 가 없으면 붙여줌)"""
    text = str(text or "").strip()
    if not text:
        return ""
    m = re.search(r"https?://[^\s<>\"'`]+", text, re.IGNORECASE)
    url = m.group(0) if m else ""
    if not url:
        for token in text.split():
            if (re.match(r"^(?:[\w-]+\.)+[A-Za-z]{2,}(?::\d+)?/\S*$", token)
                    or re.match(r"^(?:(?:www|m|music)\.)?(?:youtube\.com|youtu\.be)(?:[/?#]|$)", token, re.IGNORECASE)):
                url = "https://" + token
                break
    return url.rstrip(").,;!?]}>'\"）」』】〉》。、，…") if url else ""


def classify_url(text):
    """주소 판별 및 정규화 → (성공 여부, 정규화된 URL 또는 오류 메시지, 종류)

    종류: "video"(단일 영상) / "playlist"(재생목록) / "channel"(채널)
    """
    raw = str(text or "").strip()
    if not raw:
        return False, "URL을 입력해주세요.", None
    url = extract_url(raw)
    if not url:
        return False, "영상 주소를 찾을 수 없습니다. https:// 로 시작하는 링크를 넣어주세요.", None
    try:
        parsed = urllib.parse.urlsplit(url)
        host = (parsed.hostname or "").lower()
    except ValueError:
        return False, "URL 형식이 올바르지 않습니다.", None
    if parsed.scheme.lower() not in ("http", "https") or "." not in host:
        return False, "올바른 웹 주소가 아닙니다.", None

    parts = [p for p in parsed.path.split("/") if p]
    qs = urllib.parse.parse_qs(parsed.query)

    def arg(key):
        values = qs.get(key) or [""]
        return values[0].strip()

    def video(vid):
        m = _YT_ID_RE.match(vid or "")
        if not m:
            return False, "영상 주소가 완전하지 않습니다. 링크를 끝까지 복사했는지 확인해주세요.", None
        return True, f"https://www.youtube.com/watch?v={m.group(0)}", "video"

    def playlist(list_id):
        m = re.match(r"[A-Za-z0-9_-]+", list_id or "")  # 링크 뒤에 붙은 글자 제거
        if not m:
            return False, "재생목록 ID(list=)가 없는 주소입니다.", None
        return True, f"https://www.youtube.com/playlist?list={m.group(0)}", "playlist"

    def channel(base, tab):
        tab = tab.lower()
        if tab == "live":  # 채널의 현재 라이브 방송 1개
            return True, f"https://www.youtube.com/{base}/live", "video"
        # 탭이 없거나(홈/정보/커뮤니티 등) → '동영상' 탭으로 통일
        tab = tab if tab in _CHANNEL_TABS_KEEP else "videos"
        return True, f"https://www.youtube.com/{base}/{tab}", "channel"

    # 1) youtu.be 단축 주소
    if host in ("youtu.be", "www.youtu.be"):
        if not parts:
            return False, "YouTube 영상 링크가 아닙니다.", None
        return video(parts[0])

    # 2) youtube.com (www / m / music / youtube-nocookie)
    if _is_youtube_host(host):
        if host.startswith("consent.") and arg("continue"):
            return classify_url(arg("continue"))  # 쿠키 동의 페이지를 거친 주소
        head = parts[0].lower() if parts else ""
        frag = urllib.parse.parse_qs(parsed.fragment.lstrip("!"))
        vid = arg("v") or (frag.get("v") or [""])[0].strip()
        if head in ("watch", "watch_popup") or (not parts and vid):
            if vid:
                return video(vid)  # 영상+재생목록 주소는 해당 영상 1개만
            if arg("list"):
                return playlist(arg("list"))
            return False, "영상 ID(v=)가 없는 주소입니다.", None
        if head == "embed" and len(parts) >= 2 and parts[1] == "videoseries":
            return playlist(arg("list"))
        if head == "embed" and len(parts) >= 2 and parts[1] == "live_stream":
            return True, url, "video"  # 채널의 현재 라이브 (퍼가기 코드)
        if head in ("shorts", "live", "embed", "v", "e") and len(parts) >= 2:
            return video(parts[1])
        if head in ("clip", "attribution_link"):
            return True, url, "video"
        if head == "playlist":
            return playlist(arg("list"))
        if head == "browse" and host.startswith("music.") and len(parts) >= 2:
            return True, url, "playlist"  # YouTube Music 앨범
        if head.startswith("@") or (head in ("channel", "c", "user") and len(parts) >= 2):
            if head.startswith("@") and len(head) < 2:
                return False, "채널 주소가 완전하지 않습니다.", None
            n = 1 if head.startswith("@") else 2
            return channel("/".join(parts[:n]), parts[n] if len(parts) > n else "")
        if head in ("results", "search", "feed", "feeds", "hashtag"):
            return False, "검색 결과·피드 페이지는 받을 수 없습니다. 영상·재생목록·채널 링크를 넣어주세요.", None
        # youtube.com/채널이름 형태의 옛 채널 주소 (입력 중인 'watch' 등 예약 경로의 앞부분은 제외)
        if head and re.fullmatch(r"[\w.-]+", head) and not any(r.startswith(head) for r in _YT_RESERVED):
            return channel(parts[0], parts[1] if len(parts) > 1 else "")
        return False, "YouTube 영상·재생목록·채널 링크가 아닙니다.", None

    # 3) 기타 yt-dlp 지원 사이트 (사이트 첫 화면 주소 제외)
    if not parsed.path.strip("/") and not parsed.query and not parsed.fragment.strip("#!/"):
        return False, "영상 페이지 주소를 넣어주세요. (사이트 첫 화면 주소로는 받을 수 없습니다)", None
    return True, url, "video"


def validate_url(url):
    """(유효 여부, 정규화 URL 또는 오류 메시지, 재생목록/채널 여부) — 이전 버전 호환용"""
    ok, value, kind = classify_url(url)
    return ok, value, kind in ("playlist", "channel")


def is_playlist_url(url):
    """채널 또는 재생목록 URL 여부 판별"""
    ok, _, kind = classify_url(url)
    return ok and kind in ("playlist", "channel")


def playlist_kind(url):
    ok, _, kind = classify_url(url)
    return kind if ok else None


def open_folder(path):
    """운영체제별 폴더 열기"""
    try:
        folder = Path(path).resolve()
        folder.mkdir(parents=True, exist_ok=True)
        system = platform.system()
        if system == "Windows":
            os.startfile(str(folder))
        elif system == "Darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])
        return True
    except Exception as e:
        print(f"폴더 열기 실패: {e}")
        return False


def reveal_in_folder(filepath):
    """탐색기에서 파일을 선택한 상태로 폴더 열기"""
    try:
        fp = Path(filepath).resolve()
        if not fp.exists():
            return False
        system = platform.system()
        if system == "Windows":
            subprocess.Popen(["explorer", "/select,", str(fp)])
        elif system == "Darwin":
            subprocess.Popen(["open", "-R", str(fp)])
        else:
            return open_folder(fp.parent)
        return True
    except Exception:
        return False


def play_file(filepath):
    """운영체제 기본 플레이어로 영상/음원 재생"""
    try:
        fp = Path(filepath).resolve()
        if fp.is_file():
            return QDesktopServices.openUrl(QUrl.fromLocalFile(str(fp)))
    except Exception:
        pass
    return False


# ============================================================================
# 4. 영상 정보 조회 (미리보기 카드용)
# ============================================================================
def _quality_label(formats, codec_prefix=None):
    """지원 최고 화질 문구 (세로 영상은 짧은 변 기준) 예: '4K · 2160p60'"""
    best_short, best_fps, portrait = 0, 0, False
    for f in formats or []:
        vcodec = str(f.get("vcodec") or "")
        if vcodec == "none":
            continue
        if codec_prefix and not vcodec.startswith(codec_prefix):
            continue
        h = int(f.get("height") or 0)
        w = int(f.get("width") or 0)
        if not h:
            continue
        short = min(h, w) if w else h
        fps = int(round(float(f.get("fps") or 0)))
        if (short, fps) > (best_short, best_fps):
            best_short, best_fps, portrait = short, fps, bool(w and h > w)
    if not best_short:
        return ""
    tier = ("8K" if best_short >= 4320 else "4K" if best_short >= 2160 else "QHD" if best_short >= 1440
            else "FHD" if best_short >= 1080 else "HD" if best_short >= 720 else "")
    res = f"{best_short}p" + (str(best_fps) if best_fps > 30 else "")
    label = f"{tier} · {res}" if tier else res
    return label + (" · 세로" if portrait else "")


def _thumbnail_candidates(*infos):
    """미리보기에 쓸 썸네일 URL 후보 (적당한 크기의 JPG 우선)"""
    urls = []
    for info in infos:
        if not info:
            continue
        thumbs = [t for t in (info.get("thumbnails") or []) if isinstance(t, dict) and t.get("url")]
        good = [t for t in thumbs
                if (t.get("width") or 0) >= 320 and not str(t["url"]).split("?")[0].lower().endswith(".webp")]
        good.sort(key=lambda t: t.get("width") or 0)
        urls += [t["url"] for t in good[:2]]
        if info.get("thumbnail"):
            urls.append(info["thumbnail"])
        urls += [t["url"] for t in reversed(thumbs[-2:])]
        vid = info.get("id")
        if (info.get("ie_key") == "Youtube" or info.get("extractor_key") == "Youtube") and vid:
            urls.append(f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg")
    seen, result = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            result.append(u)
    return result


def _download_thumbnail(urls):
    """후보를 차례로 받아 이미지로 열리는 첫 번째 데이터 반환"""
    for url in urls[:4]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = resp.read(5 * 1024 * 1024)
            if data and not QImage.fromData(data).isNull():
                return data
        except Exception:
            continue
    return None


def _strip_videos_tab(url):
    return url[:-len("/videos")] if url.endswith("/videos") else url


def fetch_video_info(url):
    """영상 썸네일, 제목, 채널, 재생 시간, 지원 최고화질 조회 (백그라운드 스레드에서 호출)"""
    ok, clean_url, kind = classify_url(url)
    if not ok:
        raise ValueError(clean_url)
    request_url = clean_url

    config = Config()
    opts = config.get_ydl_opts(kind=kind)
    opts.update({
        "skip_download": True,
        "no_warnings": True,
        "ignoreerrors": False,
        "extract_flat": "in_playlist",  # 재생목록은 목록만 빠르게 (단일 영상에는 영향 없음)
        "playlist_items": "1:20",
    })
    ffmpeg_path = FFmpegHelper.check_ffmpeg()
    if ffmpeg_path:
        opts["ffmpeg_location"] = ffmpeg_path

    def extract(target):
        with youtube_dl.YoutubeDL(opts) as ydl:
            return ydl.extract_info(target, download=False)

    try:
        info = extract(clean_url)
    except DownloadError as e:
        # 동영상 탭이 없는 채널(음악 'Topic' 채널, 쇼츠 전용 채널 등) → 채널 전체로 재시도
        if kind == "channel" and clean_url.endswith("/videos") and "does not have a videos tab" in str(e).lower():
            clean_url = _strip_videos_tab(clean_url)
            info = extract(clean_url)
        else:
            raise
    if not info:
        raise ValueError("영상 정보를 가져올 수 없습니다.")

    if info.get("_type") in ("playlist", "multi_video") and kind == "video":
        kind = "playlist"  # 다른 사이트의 재생목록/앨범

    result = {
        "url": clean_url,
        "request_url": request_url,
        "kind": kind,
        "live": False,
        "badge": "",
        "badge_compat": "",
    }

    if kind in ("playlist", "channel"):
        entries = [e for e in (info.get("entries") or []) if isinstance(e, dict)]
        nested = bool(entries) and all(
            e.get("_type") == "playlist"
            or re.search(r"/(videos|shorts|streams)/?$", str(e.get("url") or e.get("webpage_url") or ""))
            for e in entries)
        count = info.get("playlist_count")
        if nested:
            count_text = "채널 전체 (동영상 · 쇼츠 · 라이브)"
        elif count:
            count_text = f"동영상 {count}개"
        elif len(entries) >= 20:
            count_text = "동영상 20개 이상"
        elif entries:
            count_text = f"동영상 {len(entries)}개"
        else:
            raise ValueError("이 목록에는 받을 수 있는 동영상이 없습니다.")
        owner = info.get("channel") or info.get("uploader") or ""
        if kind == "channel":
            title = owner or re.sub(r"\s+-\s+\w+$", "", info.get("title") or "") or "YouTube 채널"
            meta = [count_text]
            result["badge"] = "채널"
        else:
            title = info.get("title") or "재생목록"
            meta = [owner, count_text]
            result["badge"] = "재생목록"
        result.update({
            "title": title,
            "uploader": owner,
            "duration": count_text,
            "meta": "  ·  ".join(m for m in meta if m),
            "count": count or len(entries),
            "exact_count": not nested and (bool(count) or 0 < len(entries) < 20),
        })
        thumb_urls = _thumbnail_candidates(entries[0] if entries and not nested else None, info)
    else:
        live_status = info.get("live_status")
        is_live = bool(info.get("is_live")) or live_status in ("is_live", "is_upcoming")
        duration = info.get("duration")
        if duration:
            dur_str = format_seconds(duration)
        elif live_status == "is_upcoming":
            dur_str = "방송 예정"
        elif is_live:
            dur_str = "실시간 방송 중"
        else:
            dur_str = ""
        formats = info.get("formats") or []
        badge = _quality_label(formats)
        result.update({
            "title": info.get("title") or "제목 없음",
            "uploader": info.get("uploader") or info.get("channel") or "",
            "duration": dur_str,
            "meta": "  ·  ".join(m for m in (info.get("uploader") or info.get("channel"), dur_str) if m),
            "live": is_live,
            "badge": ("방송 예정" if live_status == "is_upcoming" else "LIVE") if is_live else badge,
            "badge_compat": "" if is_live else (_quality_label(formats, "avc1") or badge),
        })
        thumb_urls = _thumbnail_candidates(info)

    result["max_res"] = result["badge"]  # 이전 버전 호환 키
    result["thumbnail_data"] = _download_thumbnail(thumb_urls)
    return result


# ============================================================================
# 5. 다운로드 엔진 (YouTubeDownloader)
# ============================================================================
_PART_RE = re.compile(r"\.f[\w-]+\.\w+$")  # 병합 전 영상/음성 조각 파일명 (예: 제목.f137.mp4)
_FALLBACK_CLIENTS = ("tv", "web_embedded")  # 403 차단 시 재시도할 YouTube 접속 방식

_PP_LABELS = {
    "Merger": "영상과 음성을 합치는 중…",
    "ExtractAudio": "MP3로 변환하는 중…",
    "FFmpegExtractAudio": "MP3로 변환하는 중…",
    "VideoConvertor": "영상 형식을 변환하는 중…",
    "VideoRemuxer": "영상 형식을 정리하는 중…",
}
_PP_STAGE = {"Merger": 94.0, "ExtractAudio": 88.0, "FFmpegExtractAudio": 88.0}


def _is_http_403(err):
    exc = err.exc_info[1] if isinstance(err, DownloadError) and getattr(err, "exc_info", None) else None
    if YtdlHTTPError is not None and isinstance(exc, YtdlHTTPError) and getattr(exc, "status", None) == 403:
        return True
    return bool(re.search(r"HTTP Error 403", str(err)))


class _YdlLogger:
    """yt-dlp 메시지를 상세 로그/오류 집계로 전달 (창 모드 exe에서도 원인을 볼 수 있게)"""

    def __init__(self, owner):
        self.owner = owner

    def debug(self, msg):
        if not str(msg).startswith("[debug] "):
            self.owner._on_ydl_debug(str(msg))

    def info(self, msg):
        self.debug(msg)

    def warning(self, msg):
        self.owner._on_ydl_warning(str(msg))

    def error(self, msg):
        self.owner._on_ydl_error(str(msg))


class YouTubeDownloader:
    """최고화질 비디오 및 오디오 다운로드 엔진"""

    def __init__(self, url, status_callback=None, progress_callback=None,
                 detailed_callback=None, log_callback=None, kind=None, total_hint=None):
        self.url = url
        self.total_hint = total_hint  # 미리보기에서 확인한 전체 항목 수 ([3/24] 표시용)
        self.config = Config()
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.detailed_callback = detailed_callback
        self.log_callback = log_callback
        self.kind_override = kind
        self.kind = "video"
        self.audio_only = False

        self.downloaded_file = None     # 마지막으로 완성된 최종 파일 경로
        self.completed_files = []       # 완성된(또는 이미 있던) 최종 파일 목록
        self.skipped_existing = 0       # 이미 받아 둔 파일이라 건너뛴 수
        self.failed_count = 0           # 재생목록에서 실패한 항목 수
        self.error_message = ""         # 실패 시 사용자용 메시지
        self.output_folder = None
        self.cancelled = False
        self._is_cancelled = False

        self._run_errors = []
        self._live_ids = set()
        self._existing_names = set()   # yt-dlp가 '이미 있음'으로 알린 최종 파일 경로
        self._last_info = None
        self._ydl = None
        self._item = {}
        self._last_status = None
        self._last_detail_at = 0.0

    # ---------------------------------------------------------------- 공용
    def cancel(self):
        """다운로드 중단 요청"""
        self._is_cancelled = True

    def _status(self, msg):
        if msg and msg != self._last_status:
            self._last_status = msg
            if self.status_callback:
                self.status_callback(msg)

    def _log(self, msg):
        if not msg:
            return
        if self.log_callback:
            self.log_callback(msg)
        elif self.status_callback is print:
            print(msg)

    def _progress(self, percent):
        if self.progress_callback:
            self.progress_callback(max(0.0, min(100.0, float(percent))))

    def _detail(self, text):
        if self.detailed_callback:
            self.detailed_callback(text)

    def get_ffmpeg_path(self):
        """FFmpeg 경로 자동 탐색, 없으면 자동 다운로드"""
        path = FFmpegHelper.check_ffmpeg()
        if not path:
            self._status("영상 병합에 필요한 FFmpeg를 준비합니다 (최초 1회)…")
            path = FFmpegHelper.install_portable_ffmpeg(
                status_callback=self._status,
                progress_callback=self._progress,
                cancel_check=lambda: self._is_cancelled,
            )
        return path

    def get_js_runtime_path(self):
        """JS 런타임 경로 자동 탐색, 없으면 QuickJS 자동 다운로드"""
        path = JsRuntimeHelper.check_js_runtime()
        if not path:
            path = JsRuntimeHelper.install_portable_quickjs(
                status_callback=self._status,
                progress_callback=self._progress,
                cancel_check=lambda: self._is_cancelled,
            )
        return path

    # ---------------------------------------------------------------- 다운로드
    def download(self, audio_only=False):
        """최고화질 다운로드 실행 (403 차단 시 다른 접속 방식으로 자동 재시도)"""
        with _KeepAwake():
            try:
                return self._download(audio_only)
            except DownloadCancelled:
                return self._finish_cancelled()

    def _download(self, audio_only):
        self.audio_only = audio_only
        ok, clean_url, kind = classify_url(self.url)
        if not ok:
            self.error_message = clean_url
            self._status(f"오류: {clean_url}")
            return False
        if self.kind_override in ("video", "playlist", "channel"):
            kind = self.kind_override
        self.kind = kind

        try:
            ffmpeg_path = self.get_ffmpeg_path()
            if self._is_cancelled:
                return self._finish_cancelled()
            if not ffmpeg_path:
                self.error_message = "FFmpeg를 준비하지 못했습니다. 인터넷 연결을 확인한 뒤 다시 시도해주세요."
                self._status(self.error_message)
                return False
            self.get_js_runtime_path()
            if self._is_cancelled:
                return self._finish_cancelled()
            download_path = self.config.get_download_path()
            download_path.mkdir(parents=True, exist_ok=True)
        except DownloadCancelled:
            return self._finish_cancelled()
        except Exception as e:
            self.error_message = friendly_error(e)
            self._log(f"준비 중 오류: {clean_message(e)}")
            self._status(f"다운로드 준비 실패: {self.error_message}")
            return False
        self.output_folder = str(download_path)

        opts = self.config.get_ydl_opts(kind=kind, audio_only=audio_only)
        opts.update({
            "progress_hooks": [self._progress_hook],
            "postprocessor_hooks": [self._postprocessor_hook],
            "post_hooks": [self._post_hook],
            "match_filter": self._match_filter,
            "ffmpeg_location": ffmpeg_path,
            "logger": _YdlLogger(self),
        })
        if kind != "video":
            opts["lazy_playlist"] = True  # 채널 목록을 끝까지 읽기 전에 바로 받기 시작

        target = {"video": "", "playlist": "재생목록 전체 ", "channel": "채널 전체 "}[kind]
        what = "MP3 음원" if audio_only else "최고화질 영상"
        self._status(f"{target}{what} 다운로드를 시작합니다…")

        url = clean_url
        clients = None
        tried_root = tried_fallback = False
        while True:
            self._run_errors = []
            self._item = {}
            run_opts = dict(opts)
            if clients:
                run_opts["extractor_args"] = {"youtube": {"player_client": list(clients)}}
            error = None
            try:
                with youtube_dl.YoutubeDL(run_opts) as ydl:
                    self._ydl = ydl
                    ydl.download([url])
            except DownloadCancelled:
                return self._finish_cancelled()
            except Exception as e:
                if self._is_cancelled:
                    return self._finish_cancelled()
                error = e

            if (kind == "channel" and not tried_root and not self.completed_files and url.endswith("/videos")
                    and "does not have a videos tab" in (str(error) + " ".join(self._run_errors)).lower()):
                tried_root = True
                url = _strip_videos_tab(url)
                self._log("이 채널에는 '동영상' 탭이 없어 채널 전체 목록으로 다시 시도합니다.")
                continue
            if (error is not None and kind == "video" and not tried_fallback
                    and _is_youtube_host(urllib.parse.urlsplit(url).hostname) and _is_http_403(error)):
                tried_fallback = True
                clients = _FALLBACK_CLIENTS
                self._log(f"403 차단 상세: {clean_message(error)}")
                self._status("YouTube 접근 제한(403) 감지 — 다른 접속 방식으로 다시 시도합니다…")
                self._progress(0)
                continue
            break

        return self._finish(error)

    def _finish(self, error):
        n = len(self.completed_files)
        if self._is_cancelled and not (self.kind == "video" and n):
            return self._finish_cancelled()

        if self.kind == "video":
            if n == 0:
                if error is not None:
                    self.error_message = friendly_error(error)
                    self._log(f"오류 상세: {clean_message(error)}")
                elif self._live_ids:
                    self.error_message = "실시간(라이브) 방송은 방송이 끝난 뒤에 받을 수 있습니다."
                elif self._run_errors:
                    self.error_message = friendly_error(self._run_errors[-1])
                else:
                    self.error_message = "받은 파일이 없습니다. 주소를 확인해주세요."
                self._status(f"다운로드 실패: {self.error_message}")
                return False
            self._progress(100)
            self._status("이미 받아 둔 파일입니다." if self.skipped_existing else "다운로드 완료")
            return True

        # 재생목록 / 채널
        self.failed_count = len(self._run_errors)
        if n == 0:
            if error is not None:
                self.error_message = friendly_error(error)
            elif self._run_errors:
                self.error_message = friendly_error(self._run_errors[0])
            elif self._live_ids:
                self.error_message = "라이브 방송만 있어서 받을 동영상이 없습니다."
            else:
                self.error_message = "받을 수 있는 동영상이 없습니다."
            self._status(f"다운로드 실패: {self.error_message}")
            return False
        summary = f"{n}개 저장"
        if self.skipped_existing:
            summary += f" (이미 있던 {self.skipped_existing}개 포함)"
        if self.failed_count:
            summary += f", {self.failed_count}개 실패"
        self._progress(100)
        self._status(f"완료: {summary}")
        return True

    def _finish_cancelled(self):
        self.cancelled = True
        self._cleanup_partial()
        n = len(self.completed_files)
        if self.kind != "video" and n:
            self._status(f"다운로드를 중지했습니다. (완료된 {n}개 파일은 저장되어 있습니다)")
        else:
            self._status("다운로드를 중지했습니다.")
        return False

    def _cleanup_partial(self):
        """중지된 항목의 임시 파일(.part, .ytdl, 병합 전 조각) 정리"""
        item = self._item or {}
        if item.get("done"):
            return
        targets = set(item.get("tmp") or ())
        for f in item.get("files") or ():
            targets.add(f + ".ytdl")
            if _PART_RE.search(os.path.basename(f)):
                targets.add(f)
        for tmp in list(item.get("tmp") or ()):
            targets.update(glob.glob(glob.escape(tmp) + "-Frag*"))
        for f in targets:
            try:
                if os.path.isfile(f):
                    os.remove(f)
            except OSError:
                pass

    # ---------------------------------------------------------------- yt-dlp 훅
    def _match_filter(self, info, *, incomplete=False):
        if self._is_cancelled:
            raise DownloadCancelled("사용자가 다운로드를 중지했습니다.")
        if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming"):
            self._live_ids.add(info.get("id") or info.get("url") or len(self._live_ids))
            return "실시간/예정된 라이브 방송은 건너뜁니다"
        if not incomplete:
            self._last_info = info
            legacy = self._legacy_file(info)
            if legacy:
                self.completed_files.append(legacy)
                self.downloaded_file = legacy
                self.skipped_existing += 1
                self._log(f"이전 버전으로 받은 파일이 있어 건너뜀: {os.path.basename(legacy)}")
                if self.kind != "video":
                    self._status(f"{self._prefix(info)}이미 받은 파일 건너뜀: {os.path.basename(legacy)}")
                return "이전 버전으로 받은 파일이 있어 건너뜁니다"
        return None

    def _legacy_file(self, info):
        """이전 버전 파일명('제목.mp4', 채널은 '업로더/제목.mp4')으로 이미 받은 영상 찾기"""
        if self.audio_only or self._ydl is None:
            return None
        base = self.config.get_download_path()
        if self.kind == "video":
            old = str(base / "%(title)s.%(ext)s")
        else:
            old = str(base / "%(uploader,channel|Unknown)s" / "%(title)s.%(ext)s")
        try:
            path = self._ydl.prepare_filename(dict(info, ext="mp4"), outtmpl=old)
        except Exception:
            return None
        return path if path and os.path.isfile(path) else None

    def _prefix(self, info):
        idx = info.get("playlist_index") or info.get("playlist_autonumber")
        if self.kind == "video" or not idx:
            return ""
        total = info.get("n_entries") or info.get("playlist_count") or self.total_hint
        return f"[{idx}/{total}] " if total else f"[{idx}] "

    def _begin_item(self, item_id, info):
        self._item = {"id": item_id, "parts": [], "tmp": set(), "files": set(), "max": 0.0,
                      "done": False, "phase": None, "info": info}
        self._progress(0)
        self._detail("")
        if self.kind != "video":
            title = info.get("title") or ""
            self._status(f"{self._prefix(info)}{title}".strip())

    def _set_item_progress(self, value):
        value = max(self._item.get("max", 0.0), float(value))  # 진행률이 뒤로 가지 않도록
        self._item["max"] = value
        self._progress(value)

    def _progress_hook(self, d):
        info = d.get("info_dict") or {}
        item_id = info.get("id") or info.get("webpage_url") or info.get("title") or "?"
        if item_id != self._item.get("id"):
            self._begin_item(item_id, info)
        item = self._item

        filename = d.get("filename") or ""
        if d.get("tmpfilename"):
            item["tmp"].add(d["tmpfilename"])
        if filename:
            item["files"].add(filename)
        if self._is_cancelled:  # 새로 만든 임시 파일까지 기록한 뒤 중지해야 정리됨
            raise DownloadCancelled("사용자가 다운로드를 중지했습니다.")

        multipart = bool(_PART_RE.search(os.path.basename(filename)))
        part_idx = 0
        if multipart:
            if filename not in item["parts"]:
                item["parts"].append(filename)
            part_idx = item["parts"].index(filename)

        # 구간 배분: 영상 조각 0~80%, 음성 조각 80~92%, 병합 92~99% / MP3: 받기 0~85%, 변환 85~99%
        if self.audio_only:
            lo, hi = 0.0, 85.0
        elif multipart:
            lo, hi = [(0.0, 80.0), (80.0, 92.0)][part_idx] if part_idx < 2 else (92.0, 92.0)
        else:
            lo, hi = 0.0, 92.0

        phase = "audio" if info.get("vcodec") == "none" else "video"
        if self.kind == "video" and item["phase"] != (phase, part_idx):
            item["phase"] = (phase, part_idx)
            if self.audio_only:
                self._status("음원 받는 중…")
            elif multipart:
                self._status("음성 받는 중…" if phase == "audio" else "영상 받는 중…")
            else:
                self._status("다운로드 중…")

        status = d.get("status")
        if status == "downloading":
            done = d.get("downloaded_bytes") or 0
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            frac = None
            if total:
                frac = min(1.0, done / total)
            elif d.get("fragment_count"):
                frac = min(1.0, (d.get("fragment_index") or 0) / d["fragment_count"])
            if frac is not None:
                self._set_item_progress(lo + (hi - lo) * frac)
            now = time.monotonic()
            if now - self._last_detail_at >= 0.25:
                self._last_detail_at = now
                bits = []
                speed = d.get("speed")
                if speed:
                    bits.append(f"{format_bytes(speed)}/s")
                    eta = d.get("eta")
                    if eta is not None:
                        bits.append(f"남은 시간 {format_seconds(eta)}")
                if total:
                    bits.append(("약 " if not d.get("total_bytes") else "") + format_bytes(total))
                self._detail("  ·  ".join(bits))
        elif status == "finished":
            self._set_item_progress(hi)
            if self.kind == "video" and multipart and part_idx == 0 and not self.audio_only:
                self._status("영상 받기 완료 · 음성 받는 중…")

    def _postprocessor_hook(self, d):
        # 여기서는 중지 예외를 발생시키지 않음: 시작된 병합/변환은 끝까지 마쳐야 파일이 깨지지 않음
        if d.get("status") != "started":
            return
        pp = str(d.get("postprocessor") or "")
        label = _PP_LABELS.get(pp)
        if not label:
            if pp.startswith("Fixup"):
                label = "파일을 정리하는 중…"
            else:
                return  # MoveFiles 등 내부 단계는 표시하지 않음
        info = d.get("info_dict") or {}
        if self._norm(info.get("filepath")) in self._existing_names:
            return  # 이미 있는 파일 (실제 변환 없음)
        self._status(f"{self._prefix(info)}{label}")
        self._detail("")
        if self._item:
            self._set_item_progress(_PP_STAGE.get(pp, 96.0))

    @staticmethod
    def _norm(path):
        return os.path.normcase(os.path.abspath(str(path))) if path else ""

    def _post_hook(self, filepath):
        """모든 후처리가 끝난 최종 파일 경로 (yt-dlp post_hooks)"""
        if self._norm(filepath) in self._existing_names:
            self.skipped_existing += 1
        self.downloaded_file = filepath
        self.completed_files.append(filepath)
        if self._item:
            self._item["done"] = True
            self._set_item_progress(100)
        self._log(f"저장됨: {filepath}")

    def _on_ydl_debug(self, msg):
        text = clean_message(msg)
        if "has already been downloaded" in text:
            name = text.replace("has already been downloaded", "").strip()
            if _PART_RE.search(os.path.basename(name)):
                return  # 병합 전 조각 파일 (영상은 계속 처리됨)
            self._existing_names.add(self._norm(name))
            self._log(f"이미 있는 파일이라 건너뜀: {os.path.basename(name)}")
            if self.kind != "video":
                self._status(f"{self._prefix(self._last_info or {})}이미 받은 파일 건너뜀: {os.path.basename(name)}")
        elif "does not pass filter" in text or "건너뜁니다" in text:
            self._log(text)

    def _on_ydl_warning(self, msg):
        text = clean_message(msg)
        if text:
            self._log(f"주의: {text}")

    def _on_ydl_error(self, msg):
        text = clean_message(msg)
        if not text:
            return
        self._run_errors.append(text)
        self._log(f"오류: {text}")
        if self.kind != "video" and "does not have a videos tab" not in text.lower():
            self._status(f"건너뜀: {friendly_error(text)}")


# ============================================================================
# 6. UI 테마 · 아이콘 · 공용 위젯 (Clean Dark Theme)
# ============================================================================
STYLE = """
QMainWindow, QDialog {
    background-color: #111114;
}
QWidget {
    color: #f4f4f5;
    font-size: 13px;
}
QToolTip {
    background-color: #26262e;
    color: #f4f4f5;
    border: 1px solid #3a3a46;
    padding: 4px 6px;
}
QMenu {
    background-color: #1f1f26;
    color: #f4f4f5;
    border: 1px solid #36363f;
    padding: 4px;
}
QMenu::item {
    padding: 5px 22px 5px 14px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #b91c1c;
}
QMenu::item:disabled {
    color: #5f5f68;
}
QMenu::separator {
    height: 1px;
    background: #33333d;
    margin: 4px 6px;
}
#Header {
    background-color: #16161a;
    border-bottom: 1px solid #25252c;
}
#AppTitle {
    font-size: 17px;
    font-weight: 700;
    color: #ffffff;
}
#AppSubtitle, #Muted, #FieldLabel {
    color: #a1a1aa;
    font-size: 12px;
}
#Subtle {
    color: #71717a;
    font-size: 12px;
}
#Card, #PreviewCard {
    background-color: #18181c;
    border: 1px solid #27272f;
    border-radius: 10px;
}
#ResultCard {
    border-radius: 10px;
    background-color: #1c1c22;
    border: 1px solid #33333d;
}
#ResultCard[kind="success"] {
    background-color: #0f2a20;
    border: 1px solid #1f6f50;
}
#ResultCard[kind="error"] {
    background-color: #2a1414;
    border: 1px solid #7f2d2d;
}
#Thumb {
    background-color: #222229;
    border-radius: 6px;
    color: #71717a;
    font-size: 12px;
}
#PreviewTitle {
    color: #ffffff;
    font-size: 14px;
    font-weight: 700;
}
#PreviewMessage {
    color: #a1a1aa;
    font-size: 13px;
}
#PreviewMessage[kind="error"] {
    color: #fca5a5;
}
#PreviewMessage[kind="warn"] {
    color: #fcd34d;
}
#Chip {
    background-color: #0f3a2c;
    color: #6ee7b7;
    border: 1px solid #1f6f50;
    border-radius: 5px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 700;
}
#Chip[kind="list"] {
    background-color: #172554;
    color: #93c5fd;
    border: 1px solid #1e40af;
}
#Chip[kind="live"] {
    background-color: #3f1215;
    color: #fca5a5;
    border: 1px solid #991b1b;
}
#ChipNeutral {
    background-color: #222229;
    color: #c4c4cc;
    border: 1px solid #33333d;
    border-radius: 5px;
    padding: 2px 8px;
    font-size: 11px;
}
QLineEdit {
    background-color: #1c1c22;
    color: #f4f4f5;
    border: 1px solid #33333d;
    border-radius: 8px;
    padding: 7px 12px;
    selection-background-color: #b91c1c;
}
QLineEdit:focus {
    border: 1px solid #ef4444;
    background-color: #1f1f26;
}
QLineEdit:read-only {
    color: #c4c4cc;
    background-color: #18181d;
}
QLineEdit:read-only:focus {
    border: 1px solid #33333d;
}
#UrlEdit {
    font-size: 14px;
    padding: 0 14px;
    min-height: 44px;
    max-height: 44px;
}
#UrlSideButton {
    min-height: 32px;
    max-height: 32px;
    padding: 5px 14px;
}
QPushButton {
    background-color: #23232a;
    color: #f4f4f5;
    border: 1px solid #36363f;
    padding: 6px 14px;
    border-radius: 7px;
}
QPushButton:focus {
    border-color: #6b6b76;
}
QPushButton:hover {
    background-color: #2d2d35;
    border-color: #474753;
}
QPushButton:pressed {
    background-color: #36363f;
}
QPushButton:disabled {
    color: #5f5f68;
    background-color: #1a1a1f;
    border-color: #25252c;
}
#GhostButton {
    background-color: transparent;
    border: 1px solid transparent;
    color: #c4c4cc;
    padding: 5px 10px;
}
#GhostButton:hover {
    background-color: #23232a;
    border-color: #33333d;
    color: #ffffff;
}
#GhostButton:disabled {
    background-color: transparent;
    border-color: transparent;
    color: #5f5f68;
}
#PrimaryButton {
    background-color: #e11d2a;
    color: #ffffff;
    border: none;
    font-size: 15px;
    font-weight: 700;
    border-radius: 9px;
    padding: 0 18px;
    min-height: 50px;
    max-height: 50px;
}
#PrimaryButton:hover {
    background-color: #ef3340;
}
#PrimaryButton:pressed {
    background-color: #c0141f;
}
#PrimaryButton:disabled {
    background-color: #25252b;
    color: #6b6b74;
}
#PrimaryButton[state="stop"] {
    background-color: #26262d;
    border: 1px solid #7f2d2d;
    color: #fca5a5;
}
#PrimaryButton[state="stop"]:hover {
    background-color: #2f2227;
    border-color: #ef4444;
}
#PrimaryButton[state="stop"]:disabled {
    background-color: #1e1e23;
    color: #8a8a93;
    border-color: #33333d;
}
#AccentButton {
    background-color: #059669;
    color: #ffffff;
    border: none;
    font-weight: 700;
}
#AccentButton:hover {
    background-color: #10b981;
}
#AccentButton:pressed {
    background-color: #047857;
}
#SegLeft, #SegRight {
    background-color: #1c1c22;
    color: #a1a1aa;
    border: 1px solid #33333d;
    padding: 5px 14px;
}
#SegLeft {
    border-top-right-radius: 0;
    border-bottom-right-radius: 0;
}
#SegRight {
    border-left: none;
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
}
#SegLeft:hover, #SegRight:hover {
    color: #f4f4f5;
    background-color: #23232a;
}
#SegLeft:checked, #SegRight:checked {
    background-color: #3a1519;
    color: #ffffff;
    border: 1px solid #b91c1c;
    font-weight: 700;
}
#SegLeft:disabled, #SegRight:disabled {
    color: #5f5f68;
    background-color: #19191e;
}
#SegLeft:checked:disabled, #SegRight:checked:disabled {
    background-color: #26181a;
    border: 1px solid #4a2a2d;
    color: #a1a1aa;
}
QProgressBar {
    border: none;
    border-radius: 3px;
    background-color: #25252c;
    max-height: 6px;
    min-height: 6px;
}
QProgressBar::chunk {
    border-radius: 3px;
    background-color: #ef4444;
}
#StatusText {
    color: #e4e4e7;
    font-size: 13px;
}
#PercentText {
    color: #f4f4f5;
    font-size: 13px;
    font-weight: 700;
}
QPlainTextEdit {
    background-color: #141418;
    color: #c4c4cc;
    border: 1px solid #25252c;
    border-radius: 8px;
    padding: 6px;
    font-family: Consolas, "D2Coding", "Malgun Gothic", monospace;
    font-size: 12px;
    selection-background-color: #b91c1c;
}
QCheckBox {
    spacing: 8px;
    color: #e4e4e7;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #52525b;
    background-color: #1c1c22;
}
QCheckBox::indicator:hover {
    border-color: #a1a1aa;
}
QCheckBox::indicator:checked {
    border-color: #ef4444;
    background-color: #ef4444;
    image: url("__CHECK_ICON__");
}
QSpinBox {
    background-color: #1c1c22;
    border: 1px solid #33333d;
    border-radius: 7px;
    padding: 4px 8px;
    min-height: 22px;
    min-width: 70px;
}
QSpinBox:focus {
    border-color: #ef4444;
}
QSpinBox::up-button, QSpinBox::down-button {
    subcontrol-origin: border;
    width: 20px;
    border: none;
    background: transparent;
}
QSpinBox::up-button {
    subcontrol-position: top right;
    border-top-right-radius: 7px;
}
QSpinBox::down-button {
    subcontrol-position: bottom right;
    border-bottom-right-radius: 7px;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background: #2d2d35;
}
QSpinBox::up-arrow {
    image: url("__UP_ICON__");
    width: 10px;
    height: 10px;
}
QSpinBox::down-arrow {
    image: url("__DOWN_ICON__");
    width: 10px;
    height: 10px;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #3a3a44;
    border-radius: 3px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: #52525b;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
    height: 0;
}
QScrollBar:horizontal {
    height: 0;
}
"""


def _draw_icon_path(p, kind):
    """24x24 그리드 기준 라인 아이콘 (외부 이미지/SVG 없이 QPainter로 직접 렌더링)"""
    path = QPainterPath()
    if kind == "download":
        path.moveTo(12, 4); path.lineTo(12, 15)
        path.moveTo(7, 10.5); path.lineTo(12, 15.5); path.lineTo(17, 10.5)
        path.moveTo(5, 19.5); path.lineTo(19, 19.5)
    elif kind == "stop":
        p.setBrush(p.pen().color())
        p.drawRoundedRect(QRectF(7, 7, 10, 10), 1.8, 1.8)
        return
    elif kind == "settings":
        teeth = 8
        half = math.pi / (teeth * 2) * 0.55
        for i in range(teeth * 2):
            ang = math.pi * 2 * i / (teeth * 2)
            r = 9.2 if i % 2 == 0 else 7.2
            p0 = QPointF(12 + r * math.cos(ang - half), 12 + r * math.sin(ang - half))
            p1 = QPointF(12 + r * math.cos(ang + half), 12 + r * math.sin(ang + half))
            if i == 0:
                path.moveTo(p0)
            else:
                path.lineTo(p0)
            path.lineTo(p1)
        path.closeSubpath()
        path.addEllipse(QPointF(12, 12), 2.8, 2.8)
    elif kind == "paste":
        path.addRoundedRect(QRectF(5.5, 5, 13, 15.5), 2, 2)
        path.addRoundedRect(QRectF(9, 3, 6, 4), 1.2, 1.2)
        path.moveTo(9, 11.5); path.lineTo(15, 11.5)
        path.moveTo(9, 15.5); path.lineTo(13.5, 15.5)
    elif kind == "folder":
        path.moveTo(3.5, 7); path.quadTo(3.5, 5, 5.5, 5); path.lineTo(9.5, 5); path.lineTo(11.5, 7.5)
        path.lineTo(18.5, 7.5); path.quadTo(20.5, 7.5, 20.5, 9.5); path.lineTo(20.5, 17)
        path.quadTo(20.5, 19, 18.5, 19); path.lineTo(5.5, 19); path.quadTo(3.5, 19, 3.5, 17)
        path.closeSubpath()
    elif kind == "play":
        p.setBrush(p.pen().color())
        path.moveTo(8, 5.5); path.lineTo(18.5, 12); path.lineTo(8, 18.5); path.closeSubpath()
    elif kind == "check":
        path.addEllipse(QPointF(12, 12), 9, 9)
        path.moveTo(8, 12.3); path.lineTo(10.8, 15); path.lineTo(16.2, 9.2)
    elif kind == "tick":
        path.moveTo(5.5, 12.5); path.lineTo(10, 17); path.lineTo(18.5, 7.5)
    elif kind == "alert":
        path.addEllipse(QPointF(12, 12), 9, 9)
        path.moveTo(12, 7.5); path.lineTo(12, 13)
        p.drawPath(path)
        p.setBrush(p.pen().color())
        p.drawEllipse(QPointF(12, 16.3), 0.6, 0.6)
        return
    elif kind == "video":
        path.addRoundedRect(QRectF(3.5, 6, 12, 12), 2.2, 2.2)
        path.moveTo(15.5, 10.5); path.lineTo(20.5, 7.5); path.lineTo(20.5, 16.5); path.lineTo(15.5, 13.5)
    elif kind == "music":
        path.moveTo(9.5, 17); path.lineTo(9.5, 5.5); path.lineTo(19, 3.8); path.lineTo(19, 15.5)
        path.addEllipse(QPointF(7.3, 17), 2.3, 2.1)
        path.addEllipse(QPointF(16.8, 15.5), 2.3, 2.1)
    elif kind == "chevron-down":
        path.moveTo(7, 10); path.lineTo(12, 15); path.lineTo(17, 10)
    elif kind == "chevron-right":
        path.moveTo(10, 7); path.lineTo(15, 12); path.lineTo(10, 17)
    elif kind == "chevron-up":
        path.moveTo(7, 14); path.lineTo(12, 9); path.lineTo(17, 14)
    elif kind == "refresh":
        path.arcMoveTo(QRectF(5, 5, 14, 14), 60)
        path.arcTo(QRectF(5, 5, 14, 14), 60, 280)
        path.moveTo(15.2, 3.8); path.lineTo(15.8, 6.9); path.lineTo(12.7, 7.6)
    elif kind == "spinner":
        path.arcMoveTo(QRectF(4, 4, 16, 16), 90)
        path.arcTo(QRectF(4, 4, 16, 16), 90, 270)
    elif kind == "link":
        path.moveTo(10.5, 13.5); path.lineTo(13.5, 10.5)
        path.moveTo(9, 11.5); path.lineTo(7, 13.5)
        path.arcTo(QRectF(4.2, 12.7, 7, 7), 135, 180)
        path.lineTo(12.5, 15)
        path.moveTo(15, 12.5); path.lineTo(17, 10.5)
        path.arcTo(QRectF(12.8, 4.3, 7, 7), -45, 180)
        path.lineTo(11.5, 9)
    p.drawPath(path)


@lru_cache(maxsize=None)
def make_icon(kind, color="#f4f4f5", size=18, stroke=2.0):
    """HiDPI 대응 벡터 라인 아이콘 생성 (결과 캐시)"""
    icon = QIcon()
    for dpr in (1.0, 1.25, 1.5, 2.0, 3.0):
        px = QPixmap(max(1, round(size * dpr)), max(1, round(size * dpr)))
        px.setDevicePixelRatio(dpr)
        px.fill(Qt.GlobalColor.transparent)
        painter = QPainter(px)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(color))
        pen.setWidthF(stroke)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.scale(size / 24.0, size / 24.0)
        _draw_icon_path(painter, kind)
        painter.end()
        icon.addPixmap(px)
    return icon


class ElidedLabel(QLabel):
    """폭이 모자라면 말줄임(…)으로 표시하는 라벨 (최대 줄 수 지정, 잘리면 전체 내용을 툴팁으로)"""

    def __init__(self, text="", max_lines=1, mode=Qt.TextElideMode.ElideRight, parent=None):
        super().__init__(parent)
        self._full_text = ""
        self._tip = ""
        self._max_lines = max(1, max_lines)
        self._mode = mode
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setFullText(text)

    def fullText(self):
        return self._full_text

    def setFullText(self, text):
        self._full_text = str(text or "")
        self._refresh()
        self.updateGeometry()  # sizeHint가 전체 문구 기준이므로 레이아웃 캐시 갱신

    def setToolTip(self, tip):
        self._tip = tip or ""
        super().setToolTip(self._tip)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._refresh()

    def minimumSizeHint(self):
        return QSize(0, super().minimumSizeHint().height())

    def sizeHint(self):
        hint = super().sizeHint()
        if self._max_lines == 1:
            fm = self.fontMetrics()
            extra = fm.horizontalAdvance(self._full_text) - fm.horizontalAdvance(self.text())
            hint.setWidth(hint.width() + max(0, extra))
        return hint

    def _refresh(self):
        text = " ".join(self._full_text.split())
        width = self.contentsRect().width()
        if width <= 0:
            shown = text
        elif self._max_lines == 1:
            shown = self.fontMetrics().elidedText(text, self._mode, width)
        else:
            shown = self._elide_multiline(text, width)
        elided = shown.replace("\n", " ") != text
        QLabel.setToolTip(self, self._full_text if elided else self._tip)
        if shown != self.text():
            super().setText(shown)
            self.updateGeometry()

    def _elide_multiline(self, text, width):
        layout = QTextLayout(text, self.font())
        layout.beginLayout()
        lines = []
        while True:
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(width)
            lines.append((line.textStart(), line.textLength()))
        layout.endLayout()
        if len(lines) <= self._max_lines:
            return "\n".join(text[s:s + n].strip() for s, n in lines)
        kept = [text[s:s + n].strip() for s, n in lines[:self._max_lines - 1]]
        rest = text[lines[self._max_lines - 1][0]:].strip()
        kept.append(self.fontMetrics().elidedText(rest, Qt.TextElideMode.ElideRight, width))
        return "\n".join(kept)


def rounded_pixmap(image, width, height, radius, dpr):
    """썸네일을 지정 영역에 꽉 채워(가운데 기준 자르기) 모서리를 둥글게 처리 — HiDPI 선명도 유지"""
    dpr = max(1.0, float(dpr))
    target = QPixmap(round(width * dpr), round(height * dpr))
    target.setDevicePixelRatio(dpr)
    target.fill(Qt.GlobalColor.transparent)
    scaled = image.scaled(
        round(width * dpr), round(height * dpr),
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    painter = QPainter(target)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, width, height), radius, radius)
    painter.setClipPath(clip)
    sw, sh = scaled.width() / dpr, scaled.height() / dpr
    painter.drawImage(QRectF((width - sw) / 2, (height - sh) / 2, sw, sh), scaled)
    painter.end()
    return target


def _safe_emit(signal, *args):
    """창이 닫힌 뒤 백그라운드 스레드가 시그널을 보내도 예외가 나지 않도록 보호"""
    try:
        signal.emit(*args)
    except RuntimeError:
        pass


def repolish(widget):
    """동적 속성 변경 후 스타일시트 다시 적용"""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def _prepare_qss_images():
    """QSS image:url 에 쓸 작은 아이콘(체크 표시, 위/아래 화살표)을 임시 폴더에 준비"""
    images = {}
    for key, kind, color, size, stroke in (("__CHECK_ICON__", "tick", "#ffffff", 16, 2.6),
                                          ("__UP_ICON__", "chevron-up", "#c4c4cc", 10, 2.4),
                                          ("__DOWN_ICON__", "chevron-down", "#c4c4cc", 10, 2.4)):
        try:
            target = Path(tempfile.gettempdir()) / f"ytdl_{kind}_{size}.png"
            make_icon(kind, color, size, stroke).pixmap(QSize(size, size), 2.0).save(str(target), "PNG")
            images[key] = target.as_posix()
        except Exception:
            images[key] = ""
    return images


def apply_app_style(app):
    """Fusion + 다크 팔레트 + 스타일시트 (Windows 라이트/다크 모드와 관계없이 같은 모습)"""
    app.setStyle("Fusion")
    try:
        app.styleHints().setColorScheme(Qt.ColorScheme.Dark)  # Windows 다크 타이틀바 (Qt 6.8+)
    except Exception:
        pass

    font = QFont()
    font.setFamilies(["Segoe UI", "Malgun Gothic", "Apple SD Gothic Neo", "Noto Sans CJK KR"])
    font.setPointSizeF(9.5 if platform.system() == "Windows" else 12.5)
    app.setFont(font)

    pal = QPalette()
    colors = {
        QPalette.ColorRole.Window: "#111114",
        QPalette.ColorRole.WindowText: "#f4f4f5",
        QPalette.ColorRole.Base: "#1c1c22",
        QPalette.ColorRole.AlternateBase: "#18181c",
        QPalette.ColorRole.Text: "#f4f4f5",
        QPalette.ColorRole.Button: "#23232a",
        QPalette.ColorRole.ButtonText: "#f4f4f5",
        QPalette.ColorRole.Highlight: "#b91c1c",
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.ToolTipBase: "#26262e",
        QPalette.ColorRole.ToolTipText: "#f4f4f5",
        QPalette.ColorRole.PlaceholderText: "#71717a",
        QPalette.ColorRole.Link: "#f87171",
    }
    for role, color in colors.items():
        pal.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor("#5f5f68"))
    app.setPalette(pal)
    style = STYLE
    for key, path in _prepare_qss_images().items():
        style = style.replace(key, path)
    app.setStyleSheet(style)


def install_korean_translations(app):
    """Qt 기본 문구(오른쪽 클릭 메뉴, 확인/취소 버튼 등)를 한국어로"""
    translator = QTranslator(app)
    paths = [QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)]
    try:
        import PySide6
        paths.append(os.path.join(os.path.dirname(PySide6.__file__), "translations"))
    except Exception:
        pass
    for path in paths:
        if translator.load(QLocale(QLocale.Language.Korean, QLocale.Country.SouthKorea), "qtbase", "_", path):
            app.installTranslator(translator)
            return translator
    return None


# ============================================================================
# 7. 설정 대화상자 (SettingsDialog)
# ============================================================================
class SettingsDialog(QDialog):
    """저장 위치 · 완료 후 동작 · 화질 방식 · 재시도 횟수 · 구성 요소 상태"""
    _tools_checked = Signal(object, object)

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("설정")
        self.setModal(True)
        self.setMinimumWidth(520)
        self.config = config

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(16)

        title = QLabel("설정")
        title.setObjectName("AppTitle")
        layout.addWidget(title)

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)
        self.path_edit = QLineEdit(str(self.config.get_download_path()))
        self.path_edit.setReadOnly(True)
        self.path_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.path_edit.setMinimumWidth(260)
        folder_row.addWidget(self.path_edit, 1)
        browse_btn = QPushButton("변경…")
        browse_btn.setIcon(make_icon("folder", "#f4f4f5", 16))
        browse_btn.setAutoDefault(False)
        browse_btn.clicked.connect(self.on_browse)
        folder_row.addWidget(browse_btn)
        form.addRow(self._field_label("저장 위치"), folder_row)

        self.auto_open_cb = QCheckBox("다운로드가 끝나면 저장 폴더 열기")
        self.auto_open_cb.setChecked(bool(self.config.get("auto_open_folder", False)))
        form.addRow(self._field_label("완료 후"), self.auto_open_cb)

        compat_box = QVBoxLayout()
        compat_box.setSpacing(3)
        self.compat_cb = QCheckBox("호환성 우선 (H.264 · 최대 1080p)")
        self.compat_cb.setChecked(bool(self.config.get("compat_mode", False)))
        compat_box.addWidget(self.compat_cb)
        compat_hint = QLabel("PowerPoint · 한컴 · 오래된 플레이어에서 재생이 안 될 때 켜세요.\n"
                             "끄면 4K · HDR 등 영상이 지원하는 최고화질(AV1/VP9)로 받습니다.")
        compat_hint.setObjectName("Subtle")
        compat_box.addWidget(compat_hint)
        form.addRow(self._field_label("화질 방식"), compat_box)

        retry_row = QHBoxLayout()
        retry_row.setSpacing(10)
        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(0, 10)
        self.retry_spin.setValue(self.config.get_int("max_retries", 3, 0, 10))
        self.retry_spin.setSuffix(" 회")
        retry_row.addWidget(self.retry_spin)
        retry_hint = QLabel("네트워크가 불안정할 때 자동으로 다시 시도합니다.")
        retry_hint.setObjectName("Subtle")
        retry_row.addWidget(retry_hint, 1)
        form.addRow(self._field_label("재시도 횟수"), retry_row)

        self.ffmpeg_status_label = QLabel("확인 중…")
        self.ffmpeg_status_label.setObjectName("Subtle")
        form.addRow(self._field_label("FFmpeg"), self.ffmpeg_status_label)
        self.js_status_label = QLabel("확인 중…")
        self.js_status_label.setObjectName("Subtle")
        form.addRow(self._field_label("JS 엔진"), self.js_status_label)

        layout.addLayout(form)
        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("취소")
        cancel_btn.setAutoDefault(False)
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("저장")
        save_btn.setObjectName("AccentButton")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self.on_save)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        # 구성 요소 확인은 외부 프로그램을 실행하므로 백그라운드에서 (UI 멈춤 방지)
        self._tools_checked.connect(self._on_tools_checked)
        threading.Thread(target=self._check_tools, daemon=True).start()

    @staticmethod
    def _field_label(text):
        label = QLabel(text)
        label.setObjectName("FieldLabel")
        label.setMinimumWidth(72)
        return label

    def _check_tools(self):
        ffmpeg_path = FFmpegHelper.check_ffmpeg(refresh=True)
        js_path = JsRuntimeHelper.check_js_runtime(refresh=True)
        _safe_emit(self._tools_checked, ffmpeg_path, js_path)

    def _on_tools_checked(self, ffmpeg_path, js_path):
        for label, path in ((self.ffmpeg_status_label, ffmpeg_path), (self.js_status_label, js_path)):
            if path:
                label.setText(f"● 사용 가능  ·  {Path(path).name}")
                label.setToolTip(str(path))
                label.setStyleSheet("color: #34d399;")
            else:
                label.setText("● 없음 — 첫 다운로드 때 자동으로 준비합니다")
                label.setStyleSheet("color: #fbbf24;")

    def on_browse(self):
        folder = QFileDialog.getExistingDirectory(self, "저장 폴더 선택", self.path_edit.text())
        if folder:
            self.path_edit.setText(os.path.normpath(folder))

    def on_save(self):
        folder = Path(self.path_edit.text())
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            QMessageBox.warning(self, "저장 위치 오류", f"이 폴더를 사용할 수 없습니다.\n{folder}\n\n{friendly_error(e)}")
            return
        self.config.update({
            "download_path": str(folder),
            "auto_open_folder": self.auto_open_cb.isChecked(),
            "compat_mode": self.compat_cb.isChecked(),
            "max_retries": self.retry_spin.value(),
        })
        self.accept()


# ============================================================================
# 8. 메인 윈도우 (YouTubeDownloaderWindow)
# ============================================================================
class SignalProxy(QObject):
    """백그라운드 스레드 → UI 스레드 안전 전달용 시그널 모음"""
    status = Signal(str)
    log = Signal(str)
    progress = Signal(float)
    detail = Signal(str)
    finished = Signal(object)
    info_ready = Signal(int, object)
    info_failed = Signal(int, str)


IDLE_HINT = "YouTube 영상 · 쇼츠 · 재생목록 · 채널 주소를 붙여넣으세요."


class YouTubeDownloaderWindow(QMainWindow):
    """YouTube 최고화질 다운로더 메인 화면"""

    THUMB_W, THUMB_H = 168, 94

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.config = Config()
        self.signals = SignalProxy()

        self.info_seq = 0              # 최신 정보 조회 요청 번호 (오래된 응답 무시용)
        self.info_data = None          # 현재 주소의 분석 결과
        self.info_request_url = None   # 분석 결과가 해당하는 정규화 주소
        self.is_downloading = False
        self.is_cancelling = False
        self.current_downloader = None
        self.download_thread = None
        self.active_job = None         # 진행 중(또는 직전) 다운로드 정보
        self.last_result = None
        self._loading_step = 0
        self._started_at = 0.0

        icon_path = resource_path("icon.png")
        self.app_icon = QIcon(str(icon_path)) if icon_path else QIcon()
        if icon_path:
            self.setWindowIcon(self.app_icon)

        self.signals.status.connect(self.set_status)
        self.signals.log.connect(self.append_log)
        self.signals.progress.connect(self.set_progress)
        self.signals.detail.connect(self.set_detail)
        self.signals.finished.connect(self.on_download_finished)
        self.signals.info_ready.connect(self.on_info_ready)
        self.signals.info_failed.connect(self.on_info_failed)

        # 주소 입력이 멈춘 뒤 자동 분석
        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(600)
        self.debounce_timer.timeout.connect(self.start_fetch_info)

        self.loading_timer = QTimer(self)
        self.loading_timer.setInterval(80)
        self.loading_timer.timeout.connect(self._tick_loading)

        self._setup_ui()
        self.setAcceptDrops(True)
        self.setMinimumWidth(680)
        self.resize(780, 640)
        self._show_preview_message(IDLE_HINT)
        self._reset_progress("준비됨")
        self.update_controls()

    # ------------------------------------------------------------------ UI 구성
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 1) 헤더
        header = QFrame()
        header.setObjectName("Header")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(22, 14, 18, 14)
        hl.setSpacing(12)
        if not self.app_icon.isNull():
            logo = QLabel()
            logo.setPixmap(self.app_icon.pixmap(QSize(34, 34), self.devicePixelRatioF()))
            logo.setFixedSize(34, 34)
            hl.addWidget(logo)
        titles = QVBoxLayout()
        titles.setSpacing(1)
        title = QLabel(APP_TITLE)
        title.setObjectName("AppTitle")
        subtitle = QLabel("영상이 지원하는 최고 해상도(4K · 1080p60 등)로 자동 다운로드합니다.")
        subtitle.setObjectName("AppSubtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        hl.addLayout(titles, 1)
        self.settings_btn = QPushButton("설정")
        self.settings_btn.setObjectName("GhostButton")
        self.settings_btn.setIcon(make_icon("settings", "#c4c4cc", 16))
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.clicked.connect(self.on_open_settings)
        hl.addWidget(self.settings_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(header)

        # 2) 본문
        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(22, 18, 22, 14)
        bl.setSpacing(12)
        root.addWidget(body, 1)

        # 2-1) 주소 입력
        url_row = QHBoxLayout()
        url_row.setSpacing(8)
        self.url_edit = QLineEdit()
        self.url_edit.setObjectName("UrlEdit")
        self.url_edit.setPlaceholderText("https://www.youtube.com/watch?v=…   주소를 입력하거나 붙여넣으세요")
        self.url_edit.setClearButtonEnabled(True)
        self.url_edit.setAcceptDrops(False)  # 드롭은 창에서 처리 → 기존 주소를 새 주소로 교체
        self.url_edit.textChanged.connect(self.on_url_text_changed)
        self.url_edit.returnPressed.connect(self.on_return_pressed)
        url_row.addWidget(self.url_edit, 1)
        self.paste_btn = QPushButton("붙여넣기")
        self.paste_btn.setIcon(make_icon("paste", "#f4f4f5", 16))
        self.paste_btn.setObjectName("UrlSideButton")
        self.paste_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.paste_btn.clicked.connect(self.on_paste_link)
        url_row.addWidget(self.paste_btn)
        bl.addLayout(url_row)

        # 2-2) 미리보기 카드 (안내 · 분석 중 · 오류 메시지 ↔ 영상 정보)
        self.preview_card = QFrame()
        self.preview_card.setObjectName("PreviewCard")
        self.preview_card.setFixedHeight(self.THUMB_H + 30)
        self.preview_stack = QStackedLayout(self.preview_card)

        msg_page = QWidget()
        ml = QHBoxLayout(msg_page)
        ml.setContentsMargins(20, 12, 20, 12)
        ml.setSpacing(10)
        ml.addStretch(1)
        self.preview_msg_icon = QLabel()
        self.preview_msg_icon.setFixedSize(20, 20)
        ml.addWidget(self.preview_msg_icon)
        self.preview_msg = QLabel()
        self.preview_msg.setObjectName("PreviewMessage")
        self.preview_msg.setWordWrap(True)
        self.preview_msg.setTextFormat(Qt.TextFormat.PlainText)
        self.preview_msg.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        ml.addWidget(self.preview_msg, 0)
        self.retry_btn = QPushButton("다시 시도")
        self.retry_btn.setObjectName("GhostButton")
        self.retry_btn.setIcon(make_icon("refresh", "#c4c4cc", 15))
        self.retry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.retry_btn.clicked.connect(self.start_fetch_info)
        ml.addWidget(self.retry_btn)
        ml.addStretch(1)
        self.preview_stack.addWidget(msg_page)

        info_page = QWidget()
        il = QHBoxLayout(info_page)
        il.setContentsMargins(14, 14, 16, 14)
        il.setSpacing(16)
        self.thumb_label = QLabel()
        self.thumb_label.setObjectName("Thumb")
        self.thumb_label.setFixedSize(self.THUMB_W, self.THUMB_H)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        il.addWidget(self.thumb_label)
        meta = QVBoxLayout()
        meta.setSpacing(5)
        meta.addStretch(1)
        self.video_title_label = ElidedLabel(max_lines=2)
        self.video_title_label.setObjectName("PreviewTitle")
        meta.addWidget(self.video_title_label)
        self.video_meta_label = ElidedLabel()
        self.video_meta_label.setObjectName("Muted")
        meta.addWidget(self.video_meta_label)
        chips = QHBoxLayout()
        chips.setSpacing(6)
        chips.setContentsMargins(0, 3, 0, 0)
        self.quality_badge = QLabel()
        self.quality_badge.setObjectName("Chip")
        chips.addWidget(self.quality_badge)
        self.format_note_label = ElidedLabel()
        self.format_note_label.setObjectName("ChipNeutral")
        self.format_note_label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        chips.addWidget(self.format_note_label, 1)
        chips.addStretch(0)
        meta.addLayout(chips)
        meta.addStretch(1)
        il.addLayout(meta, 1)
        self.preview_stack.addWidget(info_page)
        bl.addWidget(self.preview_card)

        # 2-3) 옵션 카드: 형식 + 저장 위치
        options = QFrame()
        options.setObjectName("Card")
        grid = QGridLayout(options)
        grid.setContentsMargins(16, 12, 14, 12)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)

        fmt_label = QLabel("형식")
        fmt_label.setObjectName("FieldLabel")
        grid.addWidget(fmt_label, 0, 0)
        seg = QHBoxLayout()
        seg.setSpacing(0)
        self.video_btn = QPushButton("영상  MP4")
        self.video_btn.setObjectName("SegLeft")
        self.video_btn.setIcon(make_icon("video", "#f4f4f5", 16))
        self.audio_btn = QPushButton("음원  MP3")
        self.audio_btn.setObjectName("SegRight")
        self.audio_btn.setIcon(make_icon("music", "#f4f4f5", 16))
        self.format_group = QButtonGroup(self)
        self.format_group.setExclusive(True)
        for i, btn in enumerate((self.video_btn, self.audio_btn)):
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumWidth(118)
            self.format_group.addButton(btn, i)
            seg.addWidget(btn)
        self.video_btn.setChecked(True)
        self.format_group.idToggled.connect(self.on_format_changed)
        seg.addStretch(1)
        grid.addLayout(seg, 0, 1, 1, 3)

        dir_label = QLabel("저장 위치")
        dir_label.setObjectName("FieldLabel")
        grid.addWidget(dir_label, 1, 0)
        self.folder_label = ElidedLabel(mode=Qt.TextElideMode.ElideMiddle)
        grid.addWidget(self.folder_label, 1, 1)
        self.change_folder_btn = QPushButton("변경")
        self.change_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.change_folder_btn.clicked.connect(self.on_change_folder)
        grid.addWidget(self.change_folder_btn, 1, 2)
        self.open_folder_btn = QPushButton("열기")
        self.open_folder_btn.setIcon(make_icon("folder", "#f4f4f5", 15))
        self.open_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_folder_btn.clicked.connect(self.on_open_folder)
        grid.addWidget(self.open_folder_btn, 1, 3)
        grid.setColumnStretch(1, 1)
        bl.addWidget(options)
        self._refresh_folder_label()

        # 2-4) 메인 버튼
        self.download_btn = QPushButton()
        self.download_btn.setObjectName("PrimaryButton")
        self.download_btn.setIconSize(QSize(20, 20))
        self.download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_btn.clicked.connect(self.on_download)
        bl.addWidget(self.download_btn)

        # 2-5) 진행 상태 ↔ 결과 카드 (같은 자리 · 같은 높이 → 상태가 바뀌어도 레이아웃이 흔들리지 않음)
        self.activity = QWidget()
        self.activity.setFixedHeight(64)
        self.activity_stack = QStackedLayout(self.activity)

        prog = QWidget()
        pl = QVBoxLayout(prog)
        pl.setContentsMargins(2, 4, 2, 0)
        pl.setSpacing(7)
        top = QHBoxLayout()
        top.setSpacing(10)
        self.progress_status_label = ElidedLabel()
        self.progress_status_label.setObjectName("StatusText")
        top.addWidget(self.progress_status_label, 1)
        self.percent_label = QLabel("")
        self.percent_label.setObjectName("PercentText")
        top.addWidget(self.percent_label)
        pl.addLayout(top)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        pl.addWidget(self.progress)
        self.progress_detail_label = ElidedLabel()
        self.progress_detail_label.setObjectName("Subtle")
        pl.addWidget(self.progress_detail_label)
        pl.addStretch(1)
        self.activity_stack.addWidget(prog)

        self.result_card = QFrame()
        self.result_card.setObjectName("ResultCard")
        rl = QHBoxLayout(self.result_card)
        rl.setContentsMargins(14, 8, 12, 8)
        rl.setSpacing(12)
        self.result_icon = QLabel()
        self.result_icon.setFixedSize(24, 24)
        rl.addWidget(self.result_icon)
        rtext = QVBoxLayout()
        rtext.setSpacing(2)
        self.result_title = ElidedLabel()
        rtext.addWidget(self.result_title)
        self.result_sub = ElidedLabel(mode=Qt.TextElideMode.ElideMiddle)
        self.result_sub.setObjectName("Muted")
        rtext.addWidget(self.result_sub)
        rl.addLayout(rtext, 1)
        self.play_file_btn = QPushButton("재생")
        self.play_file_btn.setObjectName("AccentButton")
        self.play_file_btn.setIcon(make_icon("play", "#ffffff", 14))
        self.play_file_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_file_btn.clicked.connect(self.on_play_downloaded_file)
        rl.addWidget(self.play_file_btn)
        self.result_folder_btn = QPushButton("폴더 열기")
        self.result_folder_btn.setIcon(make_icon("folder", "#f4f4f5", 15))
        self.result_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.result_folder_btn.clicked.connect(self.on_open_result_folder)
        rl.addWidget(self.result_folder_btn)
        self.result_log_btn = QPushButton("로그 보기")
        self.result_log_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.result_log_btn.clicked.connect(lambda: self.set_log_visible(True))
        rl.addWidget(self.result_log_btn)
        self.activity_stack.addWidget(self.result_card)
        bl.addWidget(self.activity)

        bl.addStretch(1)

        # 2-6) 상세 로그 (접이식)
        log_row = QHBoxLayout()
        log_row.setSpacing(6)
        self.toggle_log_btn = QPushButton()
        self.toggle_log_btn.setObjectName("GhostButton")
        self.toggle_log_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_log_btn.clicked.connect(self.on_toggle_log)
        log_row.addWidget(self.toggle_log_btn)
        log_row.addStretch(1)
        self.copy_log_btn = QPushButton("로그 복사")
        self.copy_log_btn.setObjectName("GhostButton")
        self.copy_log_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_log_btn.clicked.connect(self.on_copy_log)
        log_row.addWidget(self.copy_log_btn)
        bl.addLayout(log_row)

        self.status_text = QPlainTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumBlockCount(3000)
        self.status_text.setMinimumHeight(60)
        self.status_text.setMaximumHeight(160)
        bl.addWidget(self.status_text, 100)  # 남는 공간을 먼저 사용
        self.set_log_visible(False)

    # ------------------------------------------------------------ 표시 도우미
    def _pixmap(self, kind, color, size):
        return make_icon(kind, color, size).pixmap(QSize(size, size), self.devicePixelRatioF())

    def _show_preview_message(self, text, kind="info", icon="link", retry=False):
        self.loading_timer.stop()
        self.preview_msg.setProperty("kind", kind)
        repolish(self.preview_msg)
        shown = text if len(text) <= 180 else text[:177] + "…"
        self.preview_msg.setText(shown)
        self.preview_msg.setToolTip(text if len(text) > 180 else "")
        # 짧은 안내는 한 줄로, 긴 오류만 줄바꿈 (가운데 정렬 유지)
        self.preview_msg.setMinimumWidth(min(self.preview_msg.fontMetrics().horizontalAdvance(shown) + 6, 380))
        color = {"error": "#fca5a5", "warn": "#fcd34d", "loading": "#a1a1aa"}.get(kind, "#71717a")
        self.preview_msg_icon.setPixmap(self._pixmap(icon, color, 20))
        self.retry_btn.setVisible(retry)
        self.preview_stack.setCurrentIndex(0)

    def _show_preview_loading(self, text):
        self._show_preview_message(text, "loading", "spinner")
        self._loading_step = 0
        self.loading_timer.start()

    def _tick_loading(self):
        self._loading_step = (self._loading_step + 1) % 24
        dpr = self.devicePixelRatioF()
        base = self._pixmap("spinner", "#a1a1aa", 20)
        rotated = QPixmap(base.size())
        rotated.setDevicePixelRatio(dpr)
        rotated.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rotated)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.translate(10, 10)
        painter.rotate(self._loading_step * 15)
        painter.translate(-10, -10)
        painter.drawPixmap(0, 0, base)
        painter.end()
        self.preview_msg_icon.setPixmap(rotated)

    def _reset_progress(self, status=""):
        self.activity_stack.setCurrentIndex(0)
        self.progress.setValue(0)
        self.percent_label.setText("")
        self.progress_detail_label.setFullText("")
        if status:
            self.progress_status_label.setFullText(status)

    def _show_result(self, kind, icon, title, subtitle="", play=False, folder=False, log=False, tooltip=""):
        color = {"success": "#34d399", "error": "#f87171"}.get(kind, "#d4d4d8")
        self.result_card.setProperty("kind", kind)
        repolish(self.result_card)
        self.result_icon.setPixmap(self._pixmap(icon, color, 24))
        self.result_title.setStyleSheet(f"font-weight: 700; color: {color};")
        self.result_title.setFullText(title)
        self.result_sub.setToolTip(tooltip)
        self.result_sub.setFullText(subtitle)
        self.play_file_btn.setVisible(play)
        self.result_folder_btn.setVisible(folder)
        self.result_log_btn.setVisible(log)
        self.activity_stack.setCurrentIndex(1)

    def _refresh_folder_label(self):
        path = str(self.config.get_download_path())
        self.folder_label.setToolTip(path)
        self.folder_label.setFullText(path)

    def _current_target(self):
        """입력창 주소 판별 결과 → (유효 여부, 정규화 주소 또는 메시지, 종류)"""
        ok, value, kind = classify_url(self.url_edit.text().strip())
        if ok and self.info_data and self.info_request_url == value:
            kind = self.info_data.get("kind", kind)  # 미리보기에서 확인한 실제 종류 우선
        return ok, value, kind

    def _format_note(self, kind):
        audio = self.audio_btn.isChecked()
        if kind in ("playlist", "channel"):
            where = "채널 이름 폴더" if kind == "channel" else "재생목록 이름 폴더"
            return f"{'MP3' if audio else 'MP4'} · {where}에 저장 · 받은 항목 건너뜀"
        if audio:
            return "MP3 320kbps로 변환"
        if self.config.get("compat_mode", False):
            return "MP4 · 호환성 우선 (H.264)"
        return "MP4 · 최고화질 영상+음성 병합"

    def _download_label(self, kind):
        audio = self.audio_btn.isChecked()
        if kind == "channel":
            return "채널 전체 음원 받기 (MP3)" if audio else "채널 전체 영상 받기 (MP4)"
        if kind == "playlist":
            return "재생목록 전체 음원 받기 (MP3)" if audio else "재생목록 전체 영상 받기 (MP4)"
        return "음원만 추출하기 (MP3)" if audio else "최고화질로 다운로드"

    def _playlist_total(self, url):
        """미리보기에서 정확히 센 항목 수 (20개 이상으로만 알려진 경우는 None)"""
        data = self.info_data if self.info_request_url == url else None
        if data and data.get("kind") in ("playlist", "channel") and data.get("exact_count"):
            return data.get("count")
        return None

    def _is_live_target(self, url):
        return bool(self.info_data and self.info_request_url == url and self.info_data.get("live"))

    def update_controls(self):
        """현재 상태(대기 · 다운로드 · 중지 중)에 맞게 버튼 활성화와 문구를 한곳에서 갱신"""
        busy = self.is_downloading
        self.url_edit.setReadOnly(busy)
        for w in (self.paste_btn, self.video_btn, self.audio_btn, self.change_folder_btn, self.settings_btn):
            w.setEnabled(not busy)

        ok, value, kind = self._current_target()
        if busy:
            self.download_btn.setProperty("state", "stop")
            self.download_btn.setIcon(make_icon("stop", "#fca5a5", 20))
            self.download_btn.setText("중지하는 중…" if self.is_cancelling else "다운로드 중지")
            self.download_btn.setEnabled(not self.is_cancelling)
        else:
            live = ok and self._is_live_target(value)
            enabled = ok and not live
            self.download_btn.setProperty("state", "")
            self.download_btn.setIcon(make_icon("download", "#ffffff" if enabled else "#6b6b74", 20))
            self.download_btn.setText("라이브 방송은 끝난 뒤에 받을 수 있어요" if live
                                      else self._download_label(kind or "video"))
            self.download_btn.setEnabled(enabled)
        repolish(self.download_btn)
        if self.info_data and self.preview_stack.currentIndex() == 1:
            self._fill_chips(self.info_data)

    def _fill_chips(self, data):
        kind = data.get("kind", "video")
        if data.get("live"):
            chip_kind, badge = "live", data.get("badge") or "LIVE"
            note = "방송이 끝난 뒤 다시 시도해주세요"
        elif kind in ("playlist", "channel"):
            chip_kind, badge = "list", data.get("badge") or ("채널" if kind == "channel" else "재생목록")
            note = self._format_note(kind)
        else:
            chip_kind = ""
            compat = self.config.get("compat_mode", False) and not self.audio_btn.isChecked()
            badge = (data.get("badge_compat") if compat else data.get("badge")) or "최고화질 자동 선택"
            if not self.audio_btn.isChecked():
                badge = f"최고 {badge}" if data.get("badge") else badge
            note = self._format_note(kind)
        if self.quality_badge.property("kind") != chip_kind:
            self.quality_badge.setProperty("kind", chip_kind)
            repolish(self.quality_badge)
        self.quality_badge.setText(badge)
        self.quality_badge.setVisible(not (self.audio_btn.isChecked() and kind == "video" and not data.get("live")))
        self.format_note_label.setFullText(note)

    # ------------------------------------------------------------ 주소 입력 & 미리보기
    def on_url_text_changed(self, text):
        if self.is_downloading:
            return
        self.debounce_timer.stop()
        if self.activity_stack.currentIndex() == 1:
            self._reset_progress("준비됨")
        clean = text.strip()
        ok, value, _ = classify_url(clean) if clean else (False, "", None)
        if ok and self.info_data and value == self.info_request_url:
            pass  # 같은 영상 (공유 파라미터 ?si= 등만 달라짐)
        else:
            self.info_seq += 1  # 진행 중인 이전 분석 결과는 무시
            self.info_data = self.info_request_url = None
            self._show_preview_message(IDLE_HINT)
            if clean:
                self.debounce_timer.start()  # 입력이 멈추면 분석(또는 안내 표시)
        self.update_controls()

    def start_fetch_info(self):
        self.debounce_timer.stop()
        text = self.url_edit.text().strip()
        if not text:
            return
        ok, value, kind = classify_url(text)
        if not ok:
            self._show_preview_message(value, "warn", "alert")
            self.update_controls()
            return
        self.info_seq += 1
        seq = self.info_seq
        self.info_data = self.info_request_url = None
        if kind == "video":
            self._show_preview_loading("영상 정보와 지원 화질을 확인하는 중…")
        else:
            self._show_preview_loading("채널 · 재생목록 정보를 불러오는 중… (몇 초 걸릴 수 있어요)")
        threading.Thread(target=self._info_worker, args=(seq, value), daemon=True).start()
        self.update_controls()

    def _info_worker(self, seq, url):
        try:
            data = fetch_video_info(url)
        except Exception as e:
            _safe_emit(self.signals.info_failed, seq, friendly_error(e))
            _safe_emit(self.signals.log, f"정보 분석 실패 상세: {clean_message(e)}")
            return
        _safe_emit(self.signals.info_ready, seq, data)

    def on_info_ready(self, seq, data):
        if seq != self.info_seq:
            return  # 그 사이 주소가 바뀐 오래된 응답
        self.info_data = data
        self.info_request_url = data.get("request_url") or data.get("url")

        self.video_title_label.setFullText(data.get("title") or "제목 없음")
        self.video_meta_label.setFullText(data.get("meta") or "")

        thumb = None
        raw = data.get("thumbnail_data")
        if raw:
            img = QImage.fromData(raw)
            if not img.isNull():
                thumb = rounded_pixmap(img, self.THUMB_W, self.THUMB_H, 6, self.devicePixelRatioF())
        if thumb is not None:
            self.thumb_label.setPixmap(thumb)
        else:
            self.thumb_label.clear()
            self.thumb_label.setText("미리보기 없음")

        self.loading_timer.stop()
        self.preview_stack.setCurrentIndex(1)
        self.update_controls()

    def on_info_failed(self, seq, msg):
        if seq != self.info_seq:
            return
        self.info_data = self.info_request_url = None
        self._show_preview_message(msg, "error", "alert", retry=True)
        self.update_controls()

    def on_format_changed(self, *_):
        self.update_controls()

    def _put_url(self, text):
        url = extract_url(text) or str(text or "").strip().split()[0]
        self.url_edit.setText(url)
        self.url_edit.setCursorPosition(0)
        self.url_edit.setFocus()
        self.start_fetch_info()

    def on_paste_link(self):
        text = (QApplication.clipboard().text() or "").strip()
        if not text:
            self._show_preview_message("클립보드가 비어 있습니다. 영상 주소를 복사한 뒤 다시 눌러주세요.", "warn", "paste")
            if self.info_data:
                seq = self.info_seq

                def restore():
                    if seq == self.info_seq and self.info_data and self.preview_stack.currentIndex() == 0:
                        self.preview_stack.setCurrentIndex(1)
                        self.update_controls()
                QTimer.singleShot(2500, restore)
            return
        self._put_url(text)

    def on_return_pressed(self):
        # 다운로드 중에 Enter를 눌러도 중지되지 않도록, 대기 상태에서만 시작
        if not self.is_downloading and self.download_btn.isEnabled():
            self.on_download()

    def dragEnterEvent(self, event):
        md = event.mimeData()
        if not self.is_downloading and (md.hasUrls() or md.hasText()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        md = event.mimeData()
        text = md.urls()[0].toString() if md.hasUrls() and md.urls() else (md.text() or "")
        if text.strip():
            self._put_url(text)
            event.acceptProposedAction()

    # ------------------------------------------------------------ 폴더 · 로그
    def on_change_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "저장 폴더 선택", str(self.config.get_download_path()))
        if folder:
            folder = os.path.normpath(folder)
            self.config.set("download_path", folder)
            self._refresh_folder_label()
            self.append_log(f"저장 폴더 변경: {folder}")

    def on_open_folder(self):
        folder = self.config.get_download_path()
        if not open_folder(str(folder)):
            QMessageBox.warning(self, "폴더 열기 실패", f"저장 폴더를 열 수 없습니다.\n{folder}")

    def _result_folder(self):
        result = self.last_result or {}
        files = result.get("files") or []
        if (self.active_job or {}).get("playlist") and files:
            return str(Path(files[-1]).parent)  # 채널/재생목록 전용 하위 폴더
        return result.get("folder") or (self.active_job or {}).get("folder") or str(self.config.get_download_path())

    def on_open_result_folder(self):
        result = self.last_result or {}
        target = result.get("file")
        if target and not (self.active_job or {}).get("playlist") and reveal_in_folder(target):
            return
        folder = self._result_folder()
        if not open_folder(folder):
            QMessageBox.warning(self, "폴더 열기 실패", f"폴더를 열 수 없습니다.\n{folder}")

    def on_play_downloaded_file(self):
        target = (self.last_result or {}).get("file")
        if not (target and play_file(target)):
            self.on_open_result_folder()

    def set_log_visible(self, visible):
        self.status_text.setVisible(visible)
        self.copy_log_btn.setVisible(visible)
        self.toggle_log_btn.setText("상세 로그 숨기기" if visible else "상세 로그 보기")
        self.toggle_log_btn.setIcon(make_icon("chevron-down" if visible else "chevron-right", "#a1a1aa", 14))
        if visible:
            self._grow_for_log()
            bar = self.status_text.verticalScrollBar()
            bar.setValue(bar.maximum())

    def _grow_for_log(self):
        """로그를 펼칠 때 화면 안에서만 창을 늘림 (작은 화면에서는 로그 높이를 줄여서 표시)"""
        if not self.isVisible() or self.isMaximized():
            return
        self.centralWidget().layout().activate()
        screen = self.screen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        frame_extra = self.frameGeometry().height() - self.height()
        room = avail.bottom() + 1 - self.frameGeometry().top() - frame_extra
        want = min(self.sizeHint().height(), room)
        if want > self.height():
            self.resize(self.width(), want)

    def on_toggle_log(self):
        self.set_log_visible(not self.status_text.isVisible())

    def on_copy_log(self):
        QApplication.clipboard().setText(self.status_text.toPlainText())
        self.copy_log_btn.setText("복사됨 ✓")
        QTimer.singleShot(1500, lambda: self.copy_log_btn.setText("로그 복사"))

    def append_log(self, msg):
        msg = str(msg or "").rstrip()
        if not msg:
            return
        stamp = time.strftime("%H:%M:%S")
        for line in msg.splitlines():
            if line.strip():
                self.status_text.appendPlainText(f"[{stamp}] {line}")

    # ------------------------------------------------------------ 진행 상태
    def set_status(self, msg):
        msg = str(msg or "").strip()
        if not msg:
            return
        self.append_log(msg)
        if self.activity_stack.currentIndex() == 0:
            self.progress_status_label.setFullText(msg.splitlines()[-1])

    def set_progress(self, percent):
        try:
            percent = max(0.0, min(100.0, float(percent)))
        except (TypeError, ValueError):
            return
        self.progress.setValue(int(percent * 10))
        self.percent_label.setText(f"{percent:.0f}%" if self.is_downloading else "")

    def set_detail(self, text):
        self.progress_detail_label.setFullText(text or "")

    # ------------------------------------------------------------ 다운로드
    def on_download(self):
        if self.is_downloading:
            if time.monotonic() - self._started_at < QApplication.doubleClickInterval() / 1000:
                return  # 더블클릭의 두 번째 클릭 — 중지 요청이 아님
            self.request_cancel()
            return
        ok, value, kind = self._current_target()
        if not ok:
            self._show_preview_message(value, "warn", "alert")
            return
        if self._is_live_target(value):
            return

        if self.debounce_timer.isActive():
            self.start_fetch_info()  # 입력 직후 바로 시작해도 미리보기는 함께 불러옴
        audio = self.audio_btn.isChecked()
        folder = self.config.get_download_path()
        self.active_job = {"url": value, "kind": kind, "playlist": kind != "video",
                           "audio": audio, "folder": str(folder)}
        self.last_result = None
        self.is_downloading = True
        self.is_cancelling = False
        self._started_at = time.monotonic()
        self._reset_progress("다운로드를 준비하는 중…")
        self.percent_label.setText("0%")
        self.append_log("─" * 44)
        self.append_log(f"{'음원(MP3)' if audio else '영상(MP4)'} 다운로드 요청: {value}")

        downloader = YouTubeDownloader(
            value,
            status_callback=lambda m: _safe_emit(self.signals.status, m),
            progress_callback=lambda p: _safe_emit(self.signals.progress, p),
            detailed_callback=lambda t: _safe_emit(self.signals.detail, t),
            log_callback=lambda m: _safe_emit(self.signals.log, m),
            kind=kind,
            total_hint=self._playlist_total(value),
        )
        self.current_downloader = downloader
        self.download_thread = threading.Thread(target=self._download_worker, args=(downloader, audio), daemon=True)
        self.download_thread.start()
        self.download_btn.setFocus()
        self.update_controls()

    def request_cancel(self):
        if not self.is_downloading or self.is_cancelling:
            return
        self.is_cancelling = True
        if self.current_downloader:
            self.current_downloader.cancel()
        self.set_status("중지 요청됨 — 진행 중인 작업을 정리하고 있습니다…")
        self.update_controls()

    def _download_worker(self, downloader, audio_only):
        result = {"ok": False, "cancelled": False, "error": "", "file": None, "files": [],
                  "failed": 0, "existing": 0, "folder": None}
        try:
            ok = downloader.download(audio_only=audio_only)
            result.update(
                ok=bool(ok),
                cancelled=downloader.cancelled,
                error=downloader.error_message,
                file=downloader.downloaded_file,
                files=list(downloader.completed_files),
                failed=downloader.failed_count,
                existing=downloader.skipped_existing,
                folder=downloader.output_folder,
            )
        except Exception as e:  # 예상치 못한 오류도 UI가 멈추지 않도록 반드시 종료 신호 전달
            result["error"] = friendly_error(e)
            _safe_emit(self.signals.log, traceback.format_exc())
        finally:
            _safe_emit(self.signals.finished, result)

    def on_download_finished(self, result):
        self.is_downloading = False
        self.is_cancelling = False
        self.current_downloader = None
        self.download_thread = None
        self.last_result = result
        job = self.active_job or {}
        self.set_detail("")
        self.percent_label.setText("")

        if result.get("cancelled"):
            saved = len(result.get("files") or [])
            sub = (f"완료된 {saved}개 파일은 저장되어 있습니다." if job.get("playlist") and saved
                   else "받던 임시 파일은 정리했습니다.")
            self._show_result("info", "alert", "다운로드를 중지했습니다", sub, folder=bool(saved))
        elif result.get("ok"):
            files = result.get("files") or []
            if job.get("playlist"):
                failed = int(result.get("failed") or 0)
                title = f"{'채널' if job.get('kind') == 'channel' else '재생목록'} 다운로드 완료 · {len(files)}개"
                if result.get("existing"):
                    title += f" (이미 있던 {result['existing']}개 포함)"
                if failed:
                    title += f" · {failed}개 실패"
                folder = self._result_folder()
                self._show_result("success", "check", title, folder, folder=True, log=bool(failed), tooltip=folder)
            else:
                path = result.get("file")
                title = "이미 받아 둔 파일입니다" if result.get("existing") else "다운로드 완료"
                self._show_result("success", "check", title, Path(path).name if path else "",
                                  play=bool(path and Path(path).is_file()), folder=True, tooltip=path or "")
            if self.config.get("auto_open_folder", False):
                self.on_open_result_folder()
        else:
            err = result.get("error") or "알 수 없는 오류가 발생했습니다."
            self._show_result("error", "alert", "다운로드 실패", err, log=True, tooltip=err)
        self.update_controls()

    # ------------------------------------------------------------ 설정 · 종료
    def on_open_settings(self):
        if self.is_downloading:
            return
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._refresh_folder_label()
            self.append_log("설정이 저장되었습니다.")
            self.update_controls()
        dialog.deleteLater()

    def closeEvent(self, event):
        if self.is_downloading:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Question)
            box.setWindowTitle("다운로드 진행 중")
            box.setText("다운로드가 아직 진행 중입니다.\n중지하고 프로그램을 종료할까요?")
            quit_btn = box.addButton("중지하고 종료", QMessageBox.ButtonRole.AcceptRole)
            box.addButton("계속 받기", QMessageBox.ButtonRole.RejectRole)
            box.exec()
            if box.clickedButton() is not quit_btn:
                event.ignore()
                return
            if self.current_downloader:
                self.current_downloader.cancel()
            thread = self.download_thread
            if thread and thread.is_alive():
                self.hide()
                QApplication.processEvents()
                thread.join(timeout=10)
        self.info_seq += 1
        self.debounce_timer.stop()
        self.loading_timer.stop()
        event.accept()


# ============================================================================
# 9. 메인 진입점
# ============================================================================
def _parent_pid(pid):
    """Windows: 지정 프로세스의 부모 PID (없으면 0)"""
    import ctypes
    from ctypes import wintypes

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_void_p),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                    ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]

    k = ctypes.windll.kernel32
    k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snap = k.CreateToolhelp32Snapshot(0x00000002, 0)  # TH32CS_SNAPPROCESS
    if not snap or snap == wintypes.HANDLE(-1).value:
        return 0
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = k.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            if entry.th32ProcessID == pid:
                return entry.th32ParentProcessID
            ok = k.Process32NextW(snap, ctypes.byref(entry))
    finally:
        k.CloseHandle(snap)
    return 0


def _attach_parent_console():
    """창 모드 exe를 명령 프롬프트에서 --url 로 실행했을 때 출력이 보이도록 콘솔 연결"""
    if not (getattr(sys, "frozen", False) and sys.platform == "win32"):
        return
    if not isinstance(sys.stdout, _NullOutput):
        return  # 출력이 파일/파이프로 이미 연결된 경우는 그대로 사용
    try:
        import ctypes
        k = ctypes.windll.kernel32
        attached = k.AttachConsole(-1)
        if not attached and getattr(sys, "_MEIPASS", None):
            # onefile 빌드: 부모는 PyInstaller 부트로더이므로 그 부모(cmd)의 콘솔에 연결
            grandparent = _parent_pid(os.getppid())
            attached = bool(grandparent) and k.AttachConsole(grandparent)
        if attached:
            encoding = f"cp{k.GetConsoleOutputCP() or 65001}"
            sys.stdout = open("CONOUT$", "w", encoding=encoding, errors="replace", buffering=1)
            sys.stderr = sys.stdout
    except Exception:
        pass


def run_cli(url, audio_only=False):
    _attach_parent_console()
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")  # 제목의 이모지 등 콘솔 코드페이지에 없는 글자
        except Exception:
            pass
    last = {"step": -1}

    def on_progress(p):
        step = int(p // 10)
        if step != last["step"]:
            last["step"] = step
            print(f"진행률: {p:.0f}%", flush=True)

    downloader = YouTubeDownloader(url, status_callback=print, progress_callback=on_progress, log_callback=print)
    success = downloader.download(audio_only=audio_only)
    if success and downloader.downloaded_file:
        print(f"저장 위치: {downloader.downloaded_file}")
    elif not success and downloader.error_message:
        print(f"실패: {downloader.error_message}")
    return 0 if success else 1


def main():
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument("--url", help="다운로드할 영상/재생목록/채널 URL (CLI 모드)")
    parser.add_argument("--audio-only", action="store_true", help="오디오만 MP3로 다운로드")
    args, _unknown = parser.parse_known_args()  # 알 수 없는 인자가 있어도 GUI는 열리도록

    if args.url:
        sys.exit(run_cli(args.url, args.audio_only))

    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("YuHyungmin.YouTubeDownloader")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    icon_path = resource_path("icon.png")
    if icon_path:
        app.setWindowIcon(QIcon(str(icon_path)))
    install_korean_translations(app)
    apply_app_style(app)
    win = YouTubeDownloaderWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

"""PO Token 제공 서버 관리 모듈

YouTube가 요구하는 PO Token(고화질 스트림 잠금 해제용)을 로그인/쿠키 없이
자동으로 발급해주는 로컬 서버(bgutil-ytdlp-pot-provider)를 실행/관리한다.
"""
import platform
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PORT = 4416
_PING_URL = f"http://127.0.0.1:{PORT}/ping"
_process = None


def _app_root():
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def _node_executable():
    system = platform.system()
    name = {"Windows": "win", "Darwin": "mac", "Linux": "linux"}.get(system)
    if not name:
        return None
    exe_name = "node.exe" if system == "Windows" else "node"
    path = _app_root() / "pot_provider" / "runtime" / name / exe_name
    return path if path.is_file() else None


def _server_script():
    path = _app_root() / "pot_provider" / "server" / "build" / "main.js"
    return path if path.is_file() else None


def plugin_installed():
    """PO Token 플러그인이 설치되어 있는지 확인한다.

    실제 등록은 yt-dlp가 YoutubeDL 생성 시 자체적으로 자동 수행하므로,
    여기서는 직접 import하지 않는다 (직접 import하면 yt-dlp의 자동 등록과
    겹쳐 '이미 등록됨' 오류가 발생한다).
    """
    import importlib.util
    try:
        return importlib.util.find_spec("yt_dlp_plugins.extractor.getpot_bgutil_http") is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def _is_server_up(timeout=1.0):
    try:
        with urllib.request.urlopen(_PING_URL, timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


def is_available():
    """이 플랫폼에서 PO Token 서버를 실행할 수 있는지(파일이 준비되어 있는지) 확인한다."""
    return _node_executable() is not None and _server_script() is not None


def ensure_running(timeout=10.0):
    """PO Token 서버가 켜져 있는지 확인하고, 꺼져 있으면 실행한다.

    성공(이미 실행 중이거나 새로 실행됨) 시 True, 이 플랫폼에서 지원하지
    않거나 정해진 시간 안에 뜨지 않으면 False를 반환한다.
    """
    global _process

    if _is_server_up():
        return True

    node_exe = _node_executable()
    server_js = _server_script()
    if not node_exe or not server_js:
        return False

    if _process is None or _process.poll() is not None:
        creationflags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        try:
            _process = subprocess.Popen(
                [str(node_exe), str(server_js), "--port", str(PORT)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=str(server_js.parent.parent),
                creationflags=creationflags,
            )
        except OSError:
            return False

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _is_server_up():
            return True
        time.sleep(0.3)
    return False


def shutdown():
    """앱 종료 시 서버 프로세스를 정리한다."""
    global _process
    if _process is not None and _process.poll() is None:
        _process.terminate()
        try:
            _process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            _process.kill()
    _process = None

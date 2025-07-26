import os
import yt_dlp as youtube_dl
from pathlib import Path
import re
import threading
import platform
import shutil
import sys
from ffmpeg_installer import FFmpegInstaller

# PyQt5 관련 import
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QProgressBar, QMessageBox, QFileDialog
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject

class YouTubeDownloader:
    def __init__(self, url, status_callback=None, progress_callback=None):
        self.url = url
        self.video_path_template = str(Path.home() / "Videos" / "%(title)s.%(ext)s")
        self.last_percent = 0
        self.status_callback = status_callback  # 진행상황 텍스트 콜백
        self.progress_callback = progress_callback  # 프로그레스바 콜백

    def validate_url(self):
        if not re.match(r'^(https?://)?(www\.)?(youtube\.com|youtu\.be)/', self.url):
            raise ValueError("유효하지 않은 YouTube URL입니다.")
        video_id = None
        patterns = [
            r'(?:v=|/)([0-9A-Za-z_-]{11}).*',
            r'shorts/([0-9A-Za-z_-]{11})',
            r'embed/([0-9A-Za-z_-]{11})',
            r'v/([0-9A-Za-z_-]{11})'
        ]
        for pattern in patterns:
            match = re.search(pattern, self.url)
            if match:
                video_id = match.group(1)
                break
        if not video_id:
            raise ValueError("YouTube 영상 ID를 찾을 수 없습니다.")
        self.url = f"https://www.youtube.com/watch?v={video_id}"

    def get_ffmpeg_path(self):
        # Windows에서 ffmpeg.exe 찾기
        if platform.system() == "Windows":
            ffmpeg_path = shutil.which("ffmpeg.exe")
            if not ffmpeg_path:
                ffmpeg_path = shutil.which("ffmpeg")
        else:
            # Unix 계열에서 ffmpeg 찾기
            ffmpeg_path = shutil.which("ffmpeg")
            
        # 추가 경로 확인 (macOS Homebrew 등)
        if not ffmpeg_path and platform.system() == "Darwin":
            if os.path.exists("/opt/homebrew/bin/ffmpeg"):
                ffmpeg_path = "/opt/homebrew/bin/ffmpeg"
            elif os.path.exists("/usr/local/bin/ffmpeg"):
                ffmpeg_path = "/usr/local/bin/ffmpeg"
                
        # Windows에서 추가 경로 확인
        if not ffmpeg_path and platform.system() == "Windows":
            # 일반적인 설치 경로들 확인
            possible_paths = [
                "C:\\ffmpeg\\bin\\ffmpeg.exe",
                "C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe",
                "C:\\Program Files (x86)\\ffmpeg\\bin\\ffmpeg.exe",
                str(Path.home() / "ffmpeg" / "bin" / "ffmpeg.exe")
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    ffmpeg_path = path
                    break
                    
        return ffmpeg_path

    def download_video(self):
        try:
            self.validate_url()
        except ValueError as e:
            if self.status_callback:
                self.status_callback(f"오류: {e}")
            return
        ffmpeg_path = self.get_ffmpeg_path()
        if not ffmpeg_path:
            if self.status_callback:
                self.status_callback("\nFFmpeg가 설치되어 있지 않습니다.")
                self.status_callback("FFmpeg 설치 버튼을 눌러 설치 후 다운로드 버튼을 다시 눌러주세요.")
            return
        videos_dir = Path.home() / "Videos"
        videos_dir.mkdir(parents=True, exist_ok=True)
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4',
            'outtmpl': self.video_path_template,
            'progress_hooks': [self.my_hook],
            'noplaylist': True,
            'quiet': True,
            'merge_output_format': 'mp4',
            'ffmpeg_location': ffmpeg_path,
        }
        try:
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
            if self.status_callback:
                self.status_callback("\n성공: 영상이 성공적으로 다운로드되었습니다.")
            if self.progress_callback:
                self.progress_callback(100)
        except youtube_dl.utils.DownloadError as e:
            if self.status_callback:
                self.status_callback(f"\n다운로드 오류: {e}")
        except Exception as e:
            if self.status_callback:
                self.status_callback(f"\n예기치 못한 오류 발생: {e}")

    def my_hook(self, d):
        if d['status'] == 'downloading':
            percent_str = re.sub(r'\x1b\[[0-9;]*m', '', d.get('_percent_str', '0%'))
            try:
                percent = float(percent_str.strip('%'))
            except:
                percent = 0
            if self.progress_callback:
                self.progress_callback(percent)
            if self.status_callback:
                status = f"{percent_str} of {d.get('_total_bytes_str', '')} at {d.get('_speed_str', '')} ETA {d.get('_eta_str', '')}"
                self.status_callback(status, replace=True)

def check_ffmpeg_installed():
    """FFmpeg 설치 여부를 다양한 경로와 환경변수로 확인"""
    import subprocess
    
    # 디버깅을 위한 로그 함수
    def debug_log(msg):
        print(f"[FFmpeg Debug] {msg}")
    
    debug_log("FFmpeg 감지 시작...")
    
    # 1. shutil.which() 사용
    if platform.system() == "Windows":
        ffmpeg_path = shutil.which("ffmpeg.exe")
        debug_log(f"shutil.which('ffmpeg.exe'): {ffmpeg_path}")
        if not ffmpeg_path:
            ffmpeg_path = shutil.which("ffmpeg")
            debug_log(f"shutil.which('ffmpeg'): {ffmpeg_path}")
    else:
        ffmpeg_path = shutil.which("ffmpeg")
        debug_log(f"shutil.which('ffmpeg'): {ffmpeg_path}")
    
    # 2. macOS Homebrew 등 추가 경로
    if not ffmpeg_path and platform.system() == "Darwin":
        if os.path.exists("/opt/homebrew/bin/ffmpeg"):
            ffmpeg_path = "/opt/homebrew/bin/ffmpeg"
            debug_log(f"Found in /opt/homebrew/bin/ffmpeg")
        elif os.path.exists("/usr/local/bin/ffmpeg"):
            ffmpeg_path = "/usr/local/bin/ffmpeg"
            debug_log(f"Found in /usr/local/bin/ffmpeg")
    
    # 3. Windows 일반 경로
    if not ffmpeg_path and platform.system() == "Windows":
        possible_paths = [
            "C:\\ffmpeg\\bin\\ffmpeg.exe",
            "C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe",
            "C:\\Program Files (x86)\\ffmpeg\\bin\\ffmpeg.exe",
            str(Path.home() / "ffmpeg" / "bin" / "ffmpeg.exe"),
            "C:\\ffmpeg\\ffmpeg.exe",
            "C:\\Program Files\\ffmpeg\\ffmpeg.exe",
            "C:\\Program Files (x86)\\ffmpeg\\ffmpeg.exe"
        ]
        for path in possible_paths:
            if os.path.exists(path):
                ffmpeg_path = path
                debug_log(f"Found in: {path}")
                break
    
    # 4. 실제 실행 테스트
    if ffmpeg_path:
        try:
            debug_log(f"Testing execution: {ffmpeg_path}")
            result = subprocess.run([ffmpeg_path, "-version"], capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                debug_log(f"FFmpeg 실행 성공: {ffmpeg_path}")
                return ffmpeg_path
            else:
                debug_log(f"FFmpeg 실행 실패 (return code: {result.returncode})")
        except Exception as e:
            debug_log(f"FFmpeg 실행 예외: {e}")
    
    # 5. 환경변수 PATH 직접 탐색
    debug_log("PATH 환경변수 직접 탐색 시작...")
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    debug_log(f"PATH 디렉토리 수: {len(path_dirs)}")
    
    for p in path_dirs:
        if not p.strip():
            continue
        candidate = os.path.join(p, "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg")
        if os.path.exists(candidate):
            debug_log(f"Found candidate: {candidate}")
            try:
                result = subprocess.run([candidate, "-version"], capture_output=True, text=True, timeout=3)
                if result.returncode == 0:
                    debug_log(f"FFmpeg 실행 성공: {candidate}")
                    return candidate
                else:
                    debug_log(f"FFmpeg 실행 실패: {candidate} (return code: {result.returncode})")
            except Exception as e:
                debug_log(f"FFmpeg 실행 예외: {candidate} - {e}")
    
    debug_log("FFmpeg를 찾을 수 없습니다.")
    return None

# 기존 get_ffmpeg_path를 check_ffmpeg_installed로 대체
YouTubeDownloader.get_ffmpeg_path = staticmethod(check_ffmpeg_installed)

# PyQt5용 시그널 클래스
class SignalProxy(QObject):
    status_signal = pyqtSignal(str, bool)
    progress_signal = pyqtSignal(float)

class YouTubeDownloaderWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube 영상 다운로드 도구 (PyQt5)")
        self.setFixedSize(700, 400)
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # 입력창
        self.url_label = QLabel("YouTube 링크 입력:")
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://www.youtube.com/watch?v=...")
        self.layout.addWidget(self.url_label)
        self.layout.addWidget(self.url_edit)

        # 버튼들
        btn_layout = QHBoxLayout()
        self.paste_btn = QPushButton("링크 붙여넣기")
        self.download_btn = QPushButton("영상 다운로드")
        self.ffmpeg_btn = QPushButton("FFmpeg 설치")
        self.open_folder_btn = QPushButton("저장 폴더 열기")
        btn_layout.addWidget(self.paste_btn)
        btn_layout.addWidget(self.download_btn)
        btn_layout.addWidget(self.ffmpeg_btn)
        btn_layout.addWidget(self.open_folder_btn)
        self.layout.addLayout(btn_layout)

        # 진행바
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.layout.addWidget(self.progress)

        # 상태창
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.layout.addWidget(self.status_text)

        # 시그널 프록시 - 메인 스레드에서 생성
        self.signals = SignalProxy()
        self.signals.status_signal.connect(self.set_status)
        self.signals.progress_signal.connect(self.set_progress)

        # 이벤트 연결
        self.paste_btn.clicked.connect(self.on_paste_link)
        self.download_btn.clicked.connect(self.on_download)
        self.ffmpeg_btn.clicked.connect(self.on_install_ffmpeg)
        self.open_folder_btn.clicked.connect(self.on_open_folder)

        self.set_status("YouTube 링크를 입력하고 다운로드 버튼을 누르세요.")

    def set_status(self, msg, replace=False):
        if replace:
            cursor = self.status_text.textCursor()
            cursor.movePosition(cursor.End)
            cursor.select(cursor.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deletePreviousChar()
            self.status_text.setTextCursor(cursor)
        self.status_text.append(msg)
        self.status_text.moveCursor(self.status_text.textCursor().End)

    def set_progress(self, percent):
        self.progress.setValue(int(percent))

    def on_paste_link(self):
        clipboard = QApplication.clipboard()
        self.url_edit.setText(clipboard.text())

    def on_download(self):
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "입력 오류", "YouTube 링크를 입력하세요.")
            return
        self.set_status("다운로드를 시작합니다...")
        self.download_btn.setEnabled(False)
        self.progress.setValue(0)
        # 스레드로 다운로드 실행
        threading.Thread(target=self.download_thread, args=(url,), daemon=True).start()

    def download_thread(self, url):
        try:
            downloader = YouTubeDownloader(
                url,
                status_callback=self.thread_safe_status,
                progress_callback=self.thread_safe_progress
            )
            downloader.download_video()
        finally:
            self.download_btn.setEnabled(True)

    def thread_safe_status(self, msg, replace=False):
        self.signals.status_signal.emit(msg, replace)

    def thread_safe_progress(self, percent):
        self.signals.progress_signal.emit(percent)

    def on_install_ffmpeg(self):
        ffmpeg_path = check_ffmpeg_installed()
        if ffmpeg_path:
            QMessageBox.information(self, "안내", f"이미 FFmpeg가 설치되어 있습니다:\n{ffmpeg_path}")
            return
        # 디버깅 정보 출력
        debug_info = f"PATH: {os.environ.get('PATH')}\n"
        debug_info += f"홈 디렉토리: {Path.home()}\n"
        debug_info += "일반 경로 체크 결과: "
        if platform.system() == "Windows":
            debug_info += str([p for p in [
                'C:\\ffmpeg\\bin\\ffmpeg.exe',
                'C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe',
                'C:\\Program Files (x86)\\ffmpeg\\bin\\ffmpeg.exe',
                str(Path.home() / 'ffmpeg' / 'bin' / 'ffmpeg.exe')
            ] if os.path.exists(p)])
        elif platform.system() == "Darwin":
            debug_info += str([p for p in [
                '/opt/homebrew/bin/ffmpeg',
                '/usr/local/bin/ffmpeg'
            ] if os.path.exists(p)])
        else:
            debug_info += "(리눅스는 기본적으로 which만 사용)"
        self.set_status(f"[FFmpeg 디버깅 정보]\n{debug_info}")
        self.set_status("FFmpeg 설치를 시작합니다...")
        self.ffmpeg_btn.setEnabled(False)
        self.progress.setValue(0)
        def install_thread():
            try:
                installer = FFmpegInstaller(
                    status_callback=self.thread_safe_status,
                    progress_callback=self.thread_safe_progress
                )
                success = installer.install_ffmpeg()
                if success:
                    self.set_status("FFmpeg 설치가 완료되었습니다!")
                    self.set_status("⚠️  중요: PATH 환경변수가 적용되도록 PC를 재시작한 후 다운로드를 시도하세요.")
                    print("[FFmpeg 설치 완료] PC를 재시작하여 PATH 환경변수를 적용하세요.")
                else:
                    self.set_status("FFmpeg 설치에 실패했습니다.")
            finally:
                self.ffmpeg_btn.setEnabled(True)
        threading.Thread(target=install_thread, daemon=True).start()

    def on_open_folder(self):
        folder = str(Path.home() / "Videos")
        if os.path.exists(folder):
            if platform.system() == 'Darwin':
                os.system(f'open "{folder}"')
            elif platform.system() == 'Windows':
                os.startfile(folder)
            else:
                os.system(f'xdg-open "{folder}"')
        else:
            QMessageBox.information(self, "안내", "Videos 폴더가 존재하지 않습니다.")


def main():
    app = QApplication(sys.argv)
    win = YouTubeDownloaderWindow()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
"YouTube 다운로더 메인 애플리케이션"
import sys
import re
import threading
import time
from pathlib import Path

import yt_dlp as youtube_dl
from PySide6.QtCore import QObject, pyqtSignal
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton, QTextEdit, QVBoxLayout, QWidget
)

from config import Config
from ffmpeg_installer import FFmpegInstaller
from settings_dialog import SettingsDialog
from utils import check_ffmpeg_installed, open_folder, validate_youtube_url


class YouTubeDownloader:
    """YouTube 다운로더 로직 클래스"""

    def __init__(self, url, status_callback=None, progress_callback=None):
        self.url = url
        self.config = Config()
        self.last_percent = 0
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.max_retries = self.config.get_max_retries()
        self.retry_delay = self.config.get_retry_delay()

    def validate_url(self):
        """URL 유효성 검증"""
        is_valid, result = validate_youtube_url(self.url)
        if not is_valid:
            raise ValueError(result)
        self.url = result

    def get_ffmpeg_path(self):
        """FFmpeg 경로를 찾는 메서드"""
        ffmpeg_path = self.config.get("ffmpeg_path")
        if ffmpeg_path and Path(ffmpeg_path).is_file():
            return ffmpeg_path

        ffmpeg_path = check_ffmpeg_installed(debug=False)
        if ffmpeg_path:
            self.config.set("ffmpeg_path", ffmpeg_path)
        return ffmpeg_path

    def download_video(self):
        """비디오 다운로드"""
        try:
            self.validate_url()
        except ValueError as e:
            if self.status_callback:
                self.status_callback(f"오류: {e}")
            return False

        ffmpeg_path = self.get_ffmpeg_path()
        if not ffmpeg_path:
            if self.status_callback:
                self.status_callback("\nFFmpeg가 설치되어 있지 않습니다. 'FFmpeg 설치' 버튼을 눌러 설치해주세요.")
            return False

        download_path = self.config.get_download_path()
        try:
            download_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            if self.status_callback:
                self.status_callback(f"다운로드 경로 생성에 실패했습니다: {e}")
            return False

        ydl_opts = self.config.get_ydl_opts()
        ydl_opts.update({
            'progress_hooks': [self.my_hook],
            'ffmpeg_location': ffmpeg_path,
        })

        for attempt in range(self.max_retries):
            try:
                if self.status_callback:
                    self.status_callback(f"다운로드를 시작합니다... (시도 {attempt + 1}/{self.max_retries})")

                with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([self.url])

                if self.status_callback:
                    self.status_callback("\n성공적으로 다운로드되었습니다.")
                if self.progress_callback:
                    self.progress_callback(100)
                return True

            except youtube_dl.utils.DownloadError as e:
                error_msg = str(e).lower()
                user_message = f"\n다운로드 오류 (시도 {attempt + 1}/{self.max_retries}): "

                if "video unavailable" in error_msg:
                    user_message += "영상을 찾을 수 없거나 비공개 상태입니다."
                elif "sign in" in error_msg or "age restricted" in error_msg:
                    user_message += "연령 제한 영상입니다. 설정에서 쿠키 파일을 사용해 보세요."
                elif "copyright" in error_msg:
                    user_message += "저작권 문제로 다운로드할 수 없습니다."
                elif "private video" in error_msg:
                    user_message += "비공개 영상입니다. 접근 권한이 필요합니다."
                elif "geo-restricted" in error_msg:
                    user_message += "지역 제한으로 인해 다운로드할 수 없습니다."
                else:
                    user_message += "알 수 없는 다운로드 오류가 발생했습니다."

                if self.status_callback:
                    self.status_callback(user_message)

                if attempt < self.max_retries - 1:
                    if self.status_callback:
                        self.status_callback(f"{self.retry_delay}초 후 재시도합니다...")
                    time.sleep(self.retry_delay)
                else:
                    if self.status_callback:
                        self.status_callback("최대 재시도 횟수를 초과하여 다운로드를 중단합니다.")
                    return False

            except Exception as e:
                if self.status_callback:
                    self.status_callback(f"\n예상치 못한 오류가 발생했습니다: {e}")
                return False

        return False

    def my_hook(self, d):
        """yt-dlp 진행률 콜백"""
        if d['status'] == 'downloading':
            percent_str = re.sub(r'\x1b\[[0-9;]*m', '', d.get('_percent_str', '0%'))
            try:
                percent = float(percent_str.strip('%'))
            except (ValueError, AttributeError):
                percent = 0

            if self.config.should_show_progress() and (abs(percent - self.last_percent) >= 2.0 or percent == 100):
                if self.progress_callback:
                    self.progress_callback(percent)
                self.last_percent = percent

            if self.status_callback:
                status = f"{d.get('_percent_str', '')} of {d.get('_total_bytes_str', '')} at {d.get('_speed_str', '')} ETA {d.get('_eta_str', '')}"
                self.status_callback(status, replace=True)
        elif d['status'] == 'finished':
            if self.status_callback:
                self.status_callback("다운로드 완료. 후처리 중...")
            if self.progress_callback:
                self.progress_callback(100)


class SignalProxy(QObject):
    """GUI 업데이트를 위한 시그널 프록시"""
    status_signal = pyqtSignal(str, bool)
    progress_signal = pyqtSignal(float)


class YouTubeDownloaderWindow(QMainWindow):
    """메인 윈도우 클래스"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube 영상 다운로드 도구 (PySide6)")
        self.setFixedSize(700, 400)
        self.config = Config()
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.url_label = QLabel("YouTube 링크 입력:")
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://www.youtube.com/watch?v=...")
        self.layout.addWidget(self.url_label)
        self.layout.addWidget(self.url_edit)

        btn_layout = QHBoxLayout()
        paste_btn = QPushButton("링크 붙여넣기")
        self.download_btn = QPushButton("영상 다운로드")
        self.ffmpeg_btn = QPushButton("FFmpeg 설치")
        open_folder_btn = QPushButton("저장 폴더 열기")
        settings_btn = QPushButton("설정")
        btn_layout.addWidget(paste_btn)
        btn_layout.addWidget(self.download_btn)
        btn_layout.addWidget(self.ffmpeg_btn)
        btn_layout.addWidget(open_folder_btn)
        btn_layout.addWidget(settings_btn)
        self.layout.addLayout(btn_layout)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.layout.addWidget(self.progress)

        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.layout.addWidget(self.status_text)

        self.signals = SignalProxy()
        self.signals.status_signal.connect(self.set_status)
        self.signals.progress_signal.connect(self.set_progress)

        paste_btn.clicked.connect(self.on_paste_link)
        self.download_btn.clicked.connect(self.on_download)
        self.ffmpeg_btn.clicked.connect(self.on_install_ffmpeg)
        open_folder_btn.clicked.connect(self.on_open_folder)
        settings_btn.clicked.connect(self.on_open_settings)

        self.set_status("YouTube 링크를 입력하고 다운로드 버튼을 누르세요.")

    def set_status(self, msg, replace=False):
        """스레드 안전한 상태 메시지 업데이트"""
        try:
            if replace:
                cursor = self.status_text.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                cursor.select(cursor.SelectionType.BlockUnderCursor)
                cursor.removeSelectedText()
                cursor.deletePreviousChar()
                self.status_text.setTextCursor(cursor)
            self.status_text.append(msg)
            self.status_text.moveCursor(self.status_text.textCursor().MoveOperation.End)
        except RuntimeError as e:
            print(f"GUI 업데이트 실패: {e}")

    def set_progress(self, percent):
        """스레드 안전한 진행률 업데이트"""
        try:
            self.progress.setValue(int(percent))
        except RuntimeError as e:
            print(f"진행률 업데이트 실패: {e}")

    def on_paste_link(self):
        """클립보드에서 링크 붙여넣기"""
        clipboard = QApplication.clipboard()
        self.url_edit.setText(clipboard.text())

    def on_download(self):
        """다운로드 시작"""
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "입력 오류", "YouTube 링크를 입력하세요.")
            return
        self.set_status("다운로드를 시작합니다...")
        self.download_btn.setEnabled(False)
        self.progress.setValue(0)
        threading.Thread(target=self.download_thread, args=(url,), daemon=True).start()

    def download_thread(self, url):
        """다운로드 스레드"""
        try:
            downloader = YouTubeDownloader(
                url,
                status_callback=self.thread_safe_status,
                progress_callback=self.thread_safe_progress
            )
            success = downloader.download_video()
            if success:
                self.signals.status_signal.emit("다운로드가 완료되었습니다.", False)
                if self.config.should_auto_open_folder():
                    self.on_open_folder()
            else:
                self.signals.status_signal.emit("다운로드에 실패했습니다.", False)
        finally:
            self.download_btn.setEnabled(True)

    def thread_safe_status(self, msg, replace=False):
        """스레드 안전한 상태 시그널 발생"""
        self.signals.status_signal.emit(msg, replace)

    def thread_safe_progress(self, percent):
        """스레드 안전한 진행률 시그널 발생"""
        self.signals.progress_signal.emit(percent)

    def on_install_ffmpeg(self):
        """FFmpeg 설치"""
        ffmpeg_path = check_ffmpeg_installed(debug=True)
        if ffmpeg_path:
            QMessageBox.information(self, "FFmpeg 확인", f"FFmpeg가 이미 설치되어 있습니다:\n{ffmpeg_path}")
            return

        reply = QMessageBox.question(
            self, 
            "FFmpeg 설치", 
            "FFmpeg가 설치되어 있지 않습니다. 지금 다운로드하여 설치하시겠습니까? (약 50-100MB)", 
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.set_status("FFmpeg 설치를 시작합니다...")
        self.ffmpeg_btn.setEnabled(False)
        self.progress.setValue(0)

        def install_thread():
            try:
                installer = FFmpegInstaller(
                    status_callback=self.thread_safe_status,
                    progress_callback=self.thread_safe_progress
                )
                new_ffmpeg_path = installer.install_ffmpeg()
                if new_ffmpeg_path:
                    self.config.set("ffmpeg_path", new_ffmpeg_path)
                    self.signals.status_signal.emit(f"FFmpeg 설치 완료: {new_ffmpeg_path}", False)
                    QMessageBox.information(self, "설치 완료", "FFmpeg 설치가 완료되었습니다.")
                else:
                    self.signals.status_signal.emit("FFmpeg 설치에 실패했습니다.", False)
                    QMessageBox.warning(self, "설치 실패", "FFmpeg 설치에 실패했습니다. 수동으로 설치해주세요.")
            finally:
                self.ffmpeg_btn.setEnabled(True)

        threading.Thread(target=install_thread, daemon=True).start()

    def on_open_folder(self):
        """저장 폴더 열기"""
        folder = str(self.config.get_download_path())
        if not open_folder(folder):
            QMessageBox.warning(self, "폴더 열기 실패", f"폴더를 열 수 없습니다: {folder}")

    def on_open_settings(self):
        """설정 창 열기"""
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.set_status("설정이 저장되었습니다.")

def main():
    """애플리케이션 실행"""
    app = QApplication(sys.argv)
    win = YouTubeDownloaderWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()


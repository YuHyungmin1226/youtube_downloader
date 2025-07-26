import os
import yt_dlp as youtube_dl
from pathlib import Path
import re
import threading
import sys
from ffmpeg_installer import FFmpegInstaller
from config import Config
from utils import check_ffmpeg_installed, open_folder, validate_youtube_url

# PyQt5 관련 import
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QProgressBar, QMessageBox, QFileDialog
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject

class YouTubeDownloader:
    def __init__(self, url, status_callback=None, progress_callback=None):
        self.url = url
        self.config = Config()
        self.last_percent = 0
        self.status_callback = status_callback  # 진행상황 텍스트 콜백
        self.progress_callback = progress_callback  # 프로그레스바 콜백
        self.max_retries = self.config.get_max_retries()
        self.retry_delay = self.config.get_retry_delay()

    def validate_url(self):
        is_valid, result = validate_youtube_url(self.url)
        if not is_valid:
            raise ValueError(result)
        self.url = result

    def get_ffmpeg_path(self):
        """FFmpeg 경로를 찾는 메서드 - check_ffmpeg_installed 함수 사용"""
        return check_ffmpeg_installed()

    def download_video(self):
        try:
            self.validate_url()
        except ValueError as e:
            if self.status_callback:
                self.status_callback(f"오류: {e}")
            return False
        
        ffmpeg_path = self.get_ffmpeg_path()
        if not ffmpeg_path:
            if self.status_callback:
                self.status_callback("\nFFmpeg가 설치되어 있지 않습니다.")
                self.status_callback("FFmpeg 설치 버튼을 눌러 설치 후 다운로드 버튼을 다시 눌러주세요.")
            return False
        
        # 다운로드 경로 확인 및 생성
        download_path = self.config.get_download_path()
        download_path.mkdir(parents=True, exist_ok=True)
        
        # 설정에서 yt-dlp 옵션 가져오기
        ydl_opts = self.config.get_ydl_opts()
        ydl_opts.update({
            'progress_hooks': [self.my_hook],
            'ffmpeg_location': ffmpeg_path,
        })
        
        for attempt in range(self.max_retries):
            try:
                if self.status_callback:
                    self.status_callback(f"다운로드 시도 {attempt + 1}/{self.max_retries}...")
                
                with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([self.url])
                
                if self.status_callback:
                    self.status_callback("\n성공: 영상이 성공적으로 다운로드되었습니다.")
                if self.progress_callback:
                    self.progress_callback(100)
                return True
                
            except youtube_dl.utils.DownloadError as e:
                error_msg = str(e)
                if self.status_callback:
                    self.status_callback(f"\n다운로드 오류 (시도 {attempt + 1}/{self.max_retries}): {error_msg}")
                
                # 특정 오류에 대한 구체적인 처리
                if "Video unavailable" in error_msg:
                    if self.status_callback:
                        self.status_callback("영상이 비공개이거나 삭제되었습니다.")
                    return False
                elif "Sign in" in error_msg:
                    if self.status_callback:
                        self.status_callback("연령 제한 영상입니다. 로그인이 필요합니다.")
                    return False
                elif "copyright" in error_msg.lower():
                    if self.status_callback:
                        self.status_callback("저작권 문제로 다운로드할 수 없습니다.")
                    return False
                
                if attempt < self.max_retries - 1:
                    if self.status_callback:
                        self.status_callback(f"{self.retry_delay}초 후 재시도합니다...")
                    import time
                    time.sleep(self.retry_delay)
                else:
                    if self.status_callback:
                        self.status_callback("최대 재시도 횟수를 초과했습니다.")
                    return False
                    
            except Exception as e:
                if self.status_callback:
                    self.status_callback(f"\n예기치 못한 오류 발생: {e}")
                return False
        
        return False

    def my_hook(self, d):
        if d['status'] == 'downloading':
            percent_str = re.sub(r'\x1b\[[0-9;]*m', '', d.get('_percent_str', '0%'))
            try:
                percent = float(percent_str.strip('%'))
            except:
                percent = 0
            
            # 성능 최적화: 진행률 업데이트 빈도 조절
            if self.config.should_show_progress() and (abs(percent - self.last_percent) >= 1.0 or percent == 100):
                if self.progress_callback:
                    self.progress_callback(percent)
                self.last_percent = percent
            
            if self.status_callback:
                status = f"{percent_str} of {d.get('_total_bytes_str', '')} at {d.get('_speed_str', '')} ETA {d.get('_eta_str', '')}"
                self.status_callback(status, replace=True)

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
        
        # 설정 초기화
        self.config = Config()
        
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
        self.settings_btn = QPushButton("설정")
        btn_layout.addWidget(self.paste_btn)
        btn_layout.addWidget(self.download_btn)
        btn_layout.addWidget(self.ffmpeg_btn)
        btn_layout.addWidget(self.open_folder_btn)
        btn_layout.addWidget(self.settings_btn)
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
        self.settings_btn.clicked.connect(self.on_open_settings)

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
            success = downloader.download_video()
            if success:
                self.set_status("다운로드가 완료되었습니다.")
                # 자동 폴더 열기 설정이 활성화된 경우
                if self.config.should_auto_open_folder():
                    self.on_open_folder()
            else:
                self.set_status("다운로드에 실패했습니다.")
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
        import platform
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
        folder = str(self.config.get_download_path())
        if open_folder(folder):
            self.set_status(f"저장 폴더를 열었습니다: {folder}")
        else:
            QMessageBox.information(self, "안내", "저장 폴더를 열 수 없습니다.")

    def on_open_settings(self):
        """설정 창 열기"""
        from PyQt5.QtWidgets import QDialog, QFormLayout, QComboBox, QCheckBox, QSpinBox
        
        class SettingsDialog(QDialog):
            def __init__(self, config, parent=None):
                super().__init__(parent)
                self.config = config
                self.setWindowTitle("설정")
                self.setFixedSize(400, 500)
                self.setup_ui()
            
            def setup_ui(self):
                layout = QVBoxLayout(self)
                form_layout = QFormLayout()
                
                # 다운로드 경로
                self.path_edit = QLineEdit(str(self.config.get_download_path()))
                self.path_btn = QPushButton("찾아보기")
                path_layout = QHBoxLayout()
                path_layout.addWidget(self.path_edit)
                path_layout.addWidget(self.path_btn)
                form_layout.addRow("다운로드 경로:", path_layout)
                
                # 비디오 형식
                self.format_combo = QComboBox()
                self.format_combo.addItems(["mp4", "webm", "mkv"])
                self.format_combo.setCurrentText(self.config.get_video_format())
                form_layout.addRow("비디오 형식:", self.format_combo)
                
                # 품질
                self.quality_combo = QComboBox()
                self.quality_combo.addItems(["best", "worst"])
                self.quality_combo.setCurrentText(self.config.get_quality())
                form_layout.addRow("품질:", self.quality_combo)
                
                # 오디오만 다운로드
                self.audio_only_check = QCheckBox()
                self.audio_only_check.setChecked(self.config.is_audio_only())
                form_layout.addRow("오디오만 다운로드:", self.audio_only_check)
                
                # 자막 다운로드
                self.subtitle_check = QCheckBox()
                self.subtitle_check.setChecked(self.config.get("subtitle_download", False))
                form_layout.addRow("자막 다운로드:", self.subtitle_check)
                
                # 자동 폴더 열기
                self.auto_open_check = QCheckBox()
                self.auto_open_check.setChecked(self.config.should_auto_open_folder())
                form_layout.addRow("다운로드 후 폴더 자동 열기:", self.auto_open_check)
                
                # 최대 재시도 횟수
                self.retry_spin = QSpinBox()
                self.retry_spin.setRange(1, 10)
                self.retry_spin.setValue(self.config.get_max_retries())
                form_layout.addRow("최대 재시도 횟수:", self.retry_spin)
                
                # 재시도 지연 시간
                self.delay_spin = QSpinBox()
                self.delay_spin.setRange(1, 30)
                self.delay_spin.setValue(self.config.get_retry_delay())
                form_layout.addRow("재시도 지연 시간(초):", self.delay_spin)
                
                layout.addLayout(form_layout)
                
                # 버튼
                btn_layout = QHBoxLayout()
                self.save_btn = QPushButton("저장")
                self.cancel_btn = QPushButton("취소")
                btn_layout.addWidget(self.save_btn)
                btn_layout.addWidget(self.cancel_btn)
                layout.addLayout(btn_layout)
                
                # 이벤트 연결
                self.path_btn.clicked.connect(self.browse_path)
                self.save_btn.clicked.connect(self.save_settings)
                self.cancel_btn.clicked.connect(self.reject)
            
            def browse_path(self):
                folder = QFileDialog.getExistingDirectory(self, "다운로드 경로 선택")
                if folder:
                    self.path_edit.setText(folder)
            
            def save_settings(self):
                self.config.set("download_path", self.path_edit.text())
                self.config.set("video_format", self.format_combo.currentText())
                self.config.set("quality", self.quality_combo.currentText())
                self.config.set("download_audio_only", self.audio_only_check.isChecked())
                self.config.set("subtitle_download", self.subtitle_check.isChecked())
                self.config.set("auto_open_folder", self.auto_open_check.isChecked())
                self.config.set("max_retries", self.retry_spin.value())
                self.config.set("retry_delay", self.delay_spin.value())
                self.accept()
        
        dialog = SettingsDialog(self.config, self)
        if dialog.exec_() == QDialog.Accepted:
            self.set_status("설정이 저장되었습니다.")


def main():
    app = QApplication(sys.argv)
    win = YouTubeDownloaderWindow()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
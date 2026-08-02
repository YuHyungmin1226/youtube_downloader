"YouTube 다운로더 메인 애플리케이션"
import sys
import os
import argparse
import re
import threading
import time
from pathlib import Path

from PySide6.QtGui import QIcon

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

import yt_dlp as youtube_dl
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton, QTextEdit, QVBoxLayout, QWidget, QFrame
)

from config import Config
from ffmpeg_installer import FFmpegInstaller
from settings_dialog import SettingsDialog
from utils import check_ffmpeg_installed, open_folder, validate_url

STYLE = (
    "QMainWindow { background-color: #121212; }"
    "QDialog { background-color: #1e1e1e; }"
    "#TitleBar { background-color: #1e1e1e; border-bottom: 1px solid #333; }"
    "QPushButton { background-color: #2d2d2d; color: #eee; border: 1px solid #555; "
    "font-size: 13px; padding: 5px 12px; border-radius: 4px; outline: none; }"
    "QPushButton:hover { background-color: #3a3a3a; }"
    "QPushButton:pressed { background-color: #454545; }"
    "QPushButton:disabled { color: #555; background-color: #202020; border-color: #333; }"
    "#TitleBar QPushButton { background: transparent; border: none; font-size: 14px; padding: 0; border-radius: 0; }"
    "#TitleBar QPushButton:hover { background-color: rgba(255, 255, 255, 0.1); }"
    "#TitleBar QPushButton:pressed { background-color: rgba(255, 255, 255, 0.2); }"
    "QLineEdit { background-color: #1e1e1e; color: #eee; border: 1px solid #444; "
    "border-radius: 4px; padding: 6px; selection-background-color: #3578e5; }"
    "QLineEdit:focus { border: 1px solid #3578e5; }"
    "QLabel { color: #aaa; font-size: 13px; }"
    "#TitleLabel { color: #eee; font-weight: bold; font-size: 12px; }"
    "QProgressBar { border: 1px solid #444; border-radius: 3px; background-color: #222;"
    " color: #eee; text-align: center; font-size: 11px; height: 18px; }"
    "QProgressBar::chunk { background-color: #3578e5; }"
    "QTextEdit { background-color: #1e1e1e; color: #eee; border: 1px solid #444; "
    "border-radius: 4px; padding: 8px; font-family: Consolas, Monaco, monospace; font-size: 12px; }"
    "QTabWidget::pane { border: 1px solid #444; background: #1e1e1e; top: -1px; }"
    "QTabBar::tab { background: #2d2d2d; color: #aaa; border: 1px solid #444; border-bottom: none; "
    "border-top-left-radius: 4px; border-top-right-radius: 4px; padding: 6px 12px; margin-right: 2px; }"
    "QTabBar::tab:selected { background: #1e1e1e; color: #eee; border-bottom: 1px solid #1e1e1e; }"
    "QTabBar::tab:hover { background: #3a3a3a; color: #eee; }"
    "QComboBox { background-color: #2d2d2d; color: #eee; border: 1px solid #444; border-radius: 4px; padding: 4px 8px; }"
    "QComboBox:on { border: 1px solid #3578e5; }"
    "QComboBox QAbstractItemView { background-color: #1e1e1e; color: #eee; selection-background-color: #3578e5; border: 1px solid #444; }"
    "QSpinBox { background-color: #2d2d2d; color: #eee; border: 1px solid #444; border-radius: 4px; padding: 4px; padding-right: 18px; }"
    "QSpinBox::up-button { subcontrol-origin: border; subcontrol-position: top right; width: 16px; border-left: 1px solid #444; border-bottom: 1px solid #444; background: #202020; border-top-right-radius: 4px; }"
    "QSpinBox::up-button:hover { background: #3a3a3a; }"
    "QSpinBox::down-button { subcontrol-origin: border; subcontrol-position: bottom right; width: 16px; border-left: 1px solid #444; background: #202020; border-bottom-right-radius: 4px; }"
    "QSpinBox::down-button:hover { background: #3a3a3a; }"
    "QSpinBox::up-arrow { image: none; border-left: 4px solid transparent; border-right: 4px solid transparent; border-bottom: 4px solid #eee; width: 0; height: 0; }"
    "QSpinBox::down-arrow { image: none; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 4px solid #eee; width: 0; height: 0; }"
    "QCheckBox { color: #eee; }"
    "QCheckBox::indicator { width: 14px; height: 14px; border: 1px solid #444; background-color: #2d2d2d; border-radius: 2px; }"
    "QCheckBox::indicator:checked { background-color: #3578e5; border-color: #3578e5; }"
    "QCheckBox::indicator:hover { border: 1px solid #3578e5; }"
    "QGroupBox { border: 1px solid #444; border-radius: 6px; margin-top: 12px; font-weight: bold; color: #eee; padding-top: 12px; }"
    "QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 8px; padding: 0 3px; color: #4a9eff; }"
    "QMessageBox { background-color: #1e1e1e; }"
    "QMessageBox QLabel { color: #eee; font-size: 13px; }"
    "QMessageBox QPushButton { background-color: #2d2d2d; color: #eee; border: 1px solid #555; "
    "border-radius: 4px; min-width: 72px; min-height: 28px; padding: 2px 12px; }"
    "QMessageBox QPushButton:hover { background-color: #3a3a3a; }"
    "QMessageBox QPushButton:pressed { background-color: #454545; }"
    "QMessageBox QPushButton:default { border: 2px solid #3578e5; }"
    "QScrollBar:vertical { background: #121212; width: 12px; margin: 0; }"
    "QScrollBar::handle:vertical { background: #2d2d2d; min-height: 20px; border-radius: 6px; border: 2px solid #121212; }"
    "QScrollBar::handle:vertical:hover { background: #3a3a3a; }"
    "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { background: none; border: none; height: 0; }"
    "QScrollBar:horizontal { background: #121212; height: 12px; margin: 0; }"
    "QScrollBar::handle:horizontal { background: #2d2d2d; min-width: 20px; border-radius: 6px; border: 2px solid #121212; }"
    "QScrollBar::handle:horizontal:hover { background: #3a3a3a; }"
    "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { background: none; border: none; width: 0; }"
)



class YouTubeDownloader:
    """비디오 다운로더 로직 클래스 (YouTube, Pornhub 등 yt-dlp 지원 사이트)"""

    YOUTUBE_FALLBACK_CLIENT = "android_vr"
    YOUTUBE_CLIENT_FALLBACK_ERRORS = (
        "http error 403",
        "requested format is not available",
        "only images are available",
        "no video formats found",
        "no formats found",
    )

    def __init__(self, url, status_callback=None, progress_callback=None):
        self.url = url
        self.config = Config()
        self.last_percent = 0.0
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.max_retries = self.config.get_max_retries()
        self.retry_delay = self.config.get_retry_delay()
        self.is_youtube = False
        self.selected_quality = None

    def validate_url(self):
        """URL 유효성 검증"""
        is_valid, result = validate_url(self.url)
        if not is_valid:
            raise ValueError(result)
        self.is_youtube = 'youtube.com' in result or 'youtu.be' in result
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

        ydl_opts = self.config.get_ydl_opts(is_youtube=self.is_youtube)
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
                    quality_note = (
                        f" (선택 화질: {self.selected_quality})"
                        if self.selected_quality
                        else ""
                    )
                    self.status_callback(f"\n성공적으로 다운로드되었습니다.{quality_note}")
                if self.progress_callback:
                    self.progress_callback(100)
                return True

            except youtube_dl.utils.DownloadError as e:
                error_msg = str(e).lower()
                user_message = f"\n다운로드 오류 (시도 {attempt + 1}/{self.max_retries}): "
                format_unavailable = any(
                    message in error_msg
                    for message in self.YOUTUBE_CLIENT_FALLBACK_ERRORS[1:]
                )
                should_retry_client = self._should_retry_with_compatible_client(
                    error_msg,
                    ydl_opts,
                    attempt,
                )

                if format_unavailable:
                    if should_retry_client:
                        user_message += "현재 요청 방식으로 영상 포맷을 가져오지 못했습니다. YouTube 호환 모드로 전환해 재시도합니다."
                    else:
                        user_message += "요청한 영상 포맷을 사용할 수 없습니다. 재생 클라이언트 또는 화질 설정을 확인해주세요."
                elif "video unavailable" in error_msg or "this video is unavailable" in error_msg:
                    user_message += "영상을 찾을 수 없거나 비공개/삭제된 상태입니다."
                elif "sign in" in error_msg or "age restricted" in error_msg or "age-gate" in error_msg:
                    user_message += "연령 제한 콘텐츠입니다. 설정에서 쿠키 연동 또는 쿠키 파일을 사용해 보세요."
                elif "cookie" in error_msg:
                    user_message += "쿠키 설정에 오류가 있습니다. 설정의 '보안 및 쿠키' 탭에서 브라우저 연동 또는 쿠키 파일 경로가 올바른지 확인해주세요."
                elif "copyright" in error_msg:
                    user_message += "저작권 문제로 다운로드할 수 없습니다."
                elif "private" in error_msg:
                    user_message += "비공개 영상입니다. 접근 권한이 필요합니다."
                elif "geo-restricted" in error_msg or "geo restricted" in error_msg:
                    user_message += "지역 제한으로 인해 다운로드할 수 없습니다."
                elif "http error 403" in error_msg or "http error 401" in error_msg:
                    if should_retry_client:
                        user_message += "YouTube 파일 접근이 차단되었습니다. YouTube 호환 모드로 전환해 재시도합니다."
                    else:
                        user_message += "접근 권한이 없습니다. 설정에서 쿠키 또는 권장 요청 프로필을 사용해보세요."
                else:
                    user_message += "알 수 없는 다운로드 오류가 발생했습니다."

                if self.status_callback:
                    self.status_callback(user_message)

                if should_retry_client:
                    Config.set_youtube_player_client(
                        ydl_opts,
                        self.YOUTUBE_FALLBACK_CLIENT,
                    )

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

    def _should_retry_with_compatible_client(self, error_msg, ydl_opts, attempt):
        """YouTube 클라이언트 문제일 때 권장 호환 프로필 재시도 여부를 반환합니다."""
        current_client = Config.get_youtube_player_client(ydl_opts)
        return (
            self.is_youtube
            and current_client != self.YOUTUBE_FALLBACK_CLIENT
            and any(
                message in error_msg
                for message in self.YOUTUBE_CLIENT_FALLBACK_ERRORS
            )
            and attempt < self.max_retries - 1
        )

    def my_hook(self, d):
        """yt-dlp 진행률 콜백"""
        info = d.get('info_dict') or {}
        height = info.get('height')
        if height:
            fps = info.get('fps')
            fps_note = f", {fps:g}fps" if isinstance(fps, (int, float)) else ""
            self.selected_quality = f"{height}p{fps_note}"

        if d['status'] == 'downloading':
            percent_str = re.sub(r'\x1b\[[0-9;]*m', '', str(d.get('_percent_str', '0%') or '0%'))
            try:
                percent = float(percent_str.strip('%'))
            except (ValueError, AttributeError):
                percent = 0

            if self.config.should_show_progress() and (abs(percent - self.last_percent) >= 2.0 or percent == 100):
                if self.progress_callback:
                    self.progress_callback(percent)
                self.last_percent = percent

        elif d['status'] == 'finished':
            if self.status_callback:
                self.status_callback("다운로드 완료. 후처리 중...")
            if self.progress_callback:
                self.progress_callback(100)

    def inspect_formats(self, player_client=None):
        """다운로드 없이 제공 포맷과 현재 설정의 선택 결과를 반환합니다."""
        self.validate_url()
        ydl_opts = self.config.get_ydl_opts(is_youtube=self.is_youtube)
        if self.is_youtube and player_client:
            Config.set_youtube_player_client(ydl_opts, player_client)
        ydl_opts['skip_download'] = True

        ffmpeg_path = self.get_ffmpeg_path()
        if ffmpeg_path:
            ydl_opts['ffmpeg_location'] = ffmpeg_path

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(self.url, download=False)

        formats = info.get('formats') or []
        video_formats = [
            fmt for fmt in formats
            if fmt.get('vcodec') != 'none' and fmt.get('height')
        ]
        requested = info.get('requested_downloads') or [info]
        selected_video = next(
            (
                fmt for fmt in requested
                if fmt.get('vcodec') != 'none' and fmt.get('height')
            ),
            None,
        )
        return {
            'title': info.get('title') or '',
            'available_heights': sorted({
                int(fmt['height']) for fmt in video_formats
            }),
            'selected_height': (
                int(selected_video['height']) if selected_video else None
            ),
            'selected_format_id': (
                selected_video.get('format_id') if selected_video else None
            ),
        }


class SignalProxy(QObject):
    """GUI 업데이트를 위한 시그널 프록시"""
    status_signal = Signal(str)
    progress_signal = Signal(float)
    download_btn_state = Signal(bool)
    ffmpeg_btn_state = Signal(bool)
    show_message = Signal(str, str, str)
    open_folder = Signal()


class YouTubeDownloaderWindow(QMainWindow):
    """메인 윈도우 클래스"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("비디오 다운로드 도구 (PySide6)")
        self.setFixedSize(700, 435)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.config = Config()
        self._drag_pos = None

        # 윈도우 아이콘 설정
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")
        if getattr(sys, "frozen", False):
            icon_path = os.path.join(os.path.dirname(sys.executable), "icon.png")
            if not os.path.exists(icon_path):
                meipass = getattr(sys, "_MEIPASS", None)
                if meipass:
                    icon_path = os.path.join(meipass, "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 타이틀 바
        self.title_bar = QFrame()
        self.title_bar.setObjectName("TitleBar")
        self.title_bar.setFixedHeight(35)
        self.title_bar_layout = QHBoxLayout(self.title_bar)
        self.title_bar_layout.setContentsMargins(15, 0, 0, 0)
        self.title_bar_layout.setSpacing(0)

        self.title_label = QLabel("비디오 다운로드 도구 (PySide6)")
        self.title_label.setObjectName("TitleLabel")
        self.title_bar_layout.addWidget(self.title_label)
        self.title_bar_layout.addStretch()

        self.min_btn = QPushButton("-")
        self.min_btn.setFixedSize(40, 35)
        self.min_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.min_btn.clicked.connect(self.showMinimized)

        self.close_btn = QPushButton("x")
        self.close_btn.setFixedSize(40, 35)
        self.close_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.close_btn.clicked.connect(self.close)
        self.close_btn.setStyleSheet("QPushButton:hover { background-color: #e81123; color: white; }")

        self.title_bar_layout.addWidget(self.min_btn)
        self.title_bar_layout.addWidget(self.close_btn)
        self.main_layout.addWidget(self.title_bar)

        # 컨텐츠 영역
        self.content_widget = QWidget()
        self.layout = QVBoxLayout(self.content_widget)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(10)
        self.main_layout.addWidget(self.content_widget)

        self.url_label = QLabel("비디오 링크 입력:")
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("Input URL...")
        self.layout.addWidget(self.url_label)
        self.layout.addWidget(self.url_edit)

        btn_layout = QHBoxLayout()
        paste_btn = QPushButton("링크 붙여넣기")
        self.download_btn = QPushButton("다운로드")
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
        self.signals.download_btn_state.connect(self.download_btn.setEnabled)
        self.signals.ffmpeg_btn_state.connect(self.ffmpeg_btn.setEnabled)
        self.signals.show_message.connect(self.show_message_dialog)
        self.signals.open_folder.connect(self.on_open_folder)

        paste_btn.clicked.connect(self.on_paste_link)
        self.download_btn.clicked.connect(self.on_download)
        self.ffmpeg_btn.clicked.connect(self.on_install_ffmpeg)
        open_folder_btn.clicked.connect(self.on_open_folder)
        settings_btn.clicked.connect(self.on_open_settings)

        self.set_status("URL을 입력하고 다운로드 버튼을 누르세요.")

    def set_status(self, msg):
        """스레드 안전한 상태 메시지 업데이트"""
        try:
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

    def show_message_dialog(self, msg_type, title, msg):
        """스레드 안전한 메시지 박스"""
        if msg_type == "info":
            QMessageBox.information(self, title, msg)
        elif msg_type == "warning":
            QMessageBox.warning(self, title, msg)

    def on_paste_link(self):
        """클립보드에서 링크 붙여넣기"""
        clipboard = QApplication.clipboard()
        text = clipboard.text().strip()
        if text:
            self.url_edit.setText(text)
            self.url_edit.setFocus()

    def on_download(self):
        """다운로드 시작"""
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "입력 오류", "비디오 링크를 입력하세요.")
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
                self.signals.status_signal.emit("다운로드가 완료되었습니다.")
                if self.config.should_auto_open_folder():
                    self.signals.open_folder.emit()
            else:
                self.signals.status_signal.emit("다운로드에 실패했습니다.")
        finally:
            self.signals.download_btn_state.emit(True)

    def thread_safe_status(self, msg):
        """스레드 안전한 상태 시그널 발생"""
        self.signals.status_signal.emit(msg)

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
                    self.signals.status_signal.emit(f"FFmpeg 설치 완료: {new_ffmpeg_path}")
                    self.signals.show_message.emit("info", "설치 완료", "FFmpeg 설치가 완료되었습니다.")
                else:
                    self.signals.status_signal.emit("FFmpeg 설치에 실패했습니다.")
                    self.signals.show_message.emit("warning", "설치 실패", "FFmpeg 설치에 실패했습니다. 수동으로 설치해주세요.")
            finally:
                self.signals.ffmpeg_btn_state.emit(True)

        threading.Thread(target=install_thread, daemon=True).start()

    def on_open_folder(self):
        """저장 폴더 열기"""
        folder_path = self.config.get_download_path()
        try:
            folder_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            QMessageBox.warning(
                self,
                "폴더 열기 실패",
                f"저장 폴더를 만들 수 없습니다:\n{folder_path}\n\n{e}",
            )
            return
        if not open_folder(str(folder_path)):
            QMessageBox.warning(self, "폴더 열기 실패", f"폴더를 열 수 없습니다: {folder_path}")

    def on_open_settings(self):
        """설정 창 열기"""
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.set_status("설정이 저장되었습니다.")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.position().toPoint())
            draggable = {self.title_bar, self.title_label}
            if child is None or child in draggable:
                self._drag_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self._drag_pos = event.globalPosition().toPoint()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

def run_headless_download(url, download_path=None):
    """GUI 없이 동일한 다운로드 로직을 실행해 자동화 검증을 지원합니다."""
    def print_status(message):
        print(message, flush=True)

    downloader = YouTubeDownloader(url, status_callback=print_status)
    if download_path:
        downloader.config.config["download_path"] = str(Path(download_path).expanduser())
    return 0 if downloader.download_video() else 1


def run_headless_inspect(url, player_client=None):
    """GUI 없이 제공 해상도와 현재 선택 결과를 출력합니다."""
    try:
        result = YouTubeDownloader(url).inspect_formats(player_client)
    except (ValueError, youtube_dl.utils.DownloadError) as exc:
        print(f"포맷 확인 실패: {exc}", flush=True)
        return 1

    heights = ", ".join(f"{height}p" for height in result['available_heights'])
    selected = (
        f"{result['selected_height']}p"
        if result['selected_height']
        else "확인 불가"
    )
    print(f"제공 해상도: {heights or '확인 불가'}", flush=True)
    print(
        f"선택 해상도: {selected} "
        f"(format_id={result['selected_format_id'] or 'unknown'})",
        flush=True,
    )
    return 0


def main():
    """애플리케이션 실행"""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--headless-url")
    parser.add_argument("--inspect-url")
    parser.add_argument("--player-client")
    parser.add_argument("--download-path")
    args, _ = parser.parse_known_args()
    if args.inspect_url:
        sys.exit(run_headless_inspect(args.inspect_url, args.player_client))
    if args.headless_url:
        sys.exit(run_headless_download(args.headless_url, args.download_path))

    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    win = YouTubeDownloaderWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

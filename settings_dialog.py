"""
설정 다이얼로그 모듈
"""
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QPushButton, QHBoxLayout, QVBoxLayout, QComboBox, QCheckBox, QSpinBox, QFileDialog, QTabWidget, QWidget
)

QUALITY_OPTIONS = [
    ("최고 화질", ("best", "best")),
    ("2160p (4K)", ("best", "2160p")),
    ("1440p (2K)", ("best", "1440p")),
    ("1080p (FHD)", ("best", "1080p")),
    ("720p (HD)", ("best", "720p")),
    ("480p", ("best", "480p")),
    ("360p", ("best", "360p")),
    ("최저 화질 (용량 절약)", ("worst", "worst")),
]

class SettingsDialog(QDialog):
    """설정 다이얼로그 클래스"""
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("설정")
        self.setFixedSize(480, 460)
        self.setup_ui()

    def setup_ui(self):
        """UI 설정"""
        layout = QVBoxLayout(self)

        # 탭 위젯 생성
        self.tab_widget = QTabWidget()

        # ------------------ 탭 1: 기본 설정 ------------------
        tab_general = QWidget()
        form_general = QFormLayout(tab_general)

        # 다운로드 경로
        self.path_edit = QLineEdit(str(self.config.get_download_path()))
        path_btn = QPushButton("찾아보기")
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(path_btn)
        form_general.addRow("다운로드 경로:", path_layout)

        # 비디오 형식
        self.format_combo = QComboBox()
        self.format_combo.addItems(["mp4", "webm", "mkv"])
        self.format_combo.setCurrentText(self.config.get_video_format())
        form_general.addRow("비디오 형식:", self.format_combo)

        # 화질 (해상도 제한)
        self.pref_quality_combo = QComboBox()
        for label, data in QUALITY_OPTIONS:
            self.pref_quality_combo.addItem(label, data)
        current = (self.config.get_quality(), self.config.get("preferred_quality", "1080p"))
        if current[0] == "worst":
            target_index = len(QUALITY_OPTIONS) - 1
        else:
            target_index = next(
                (i for i, (_, data) in enumerate(QUALITY_OPTIONS) if data == current),
                3,  # 기본값: 1080p
            )
        self.pref_quality_combo.setCurrentIndex(target_index)
        form_general.addRow("화질:", self.pref_quality_combo)

        # 오디오만 다운로드
        self.audio_only_check = QCheckBox()
        self.audio_only_check.setChecked(self.config.is_audio_only())
        form_general.addRow("오디오만 다운로드:", self.audio_only_check)

        # 자동 폴더 열기
        self.auto_open_check = QCheckBox()
        self.auto_open_check.setChecked(self.config.should_auto_open_folder())
        form_general.addRow("다운로드 후 폴더 자동 열기:", self.auto_open_check)

        self.tab_widget.addTab(tab_general, "기본 설정")

        # ------------------ 탭 2: 자막/재생목록 ------------------
        tab_advanced = QWidget()
        form_advanced = QFormLayout(tab_advanced)

        # 자막 다운로드
        self.subtitle_check = QCheckBox()
        self.subtitle_check.setChecked(self.config.get("subtitle_download", False))
        form_advanced.addRow("자막 다운로드:", self.subtitle_check)

        # 자막 언어
        self.subtitle_lang_edit = QLineEdit(self.config.get("subtitle_language", "ko"))
        form_advanced.addRow("자막 언어 코드:", self.subtitle_lang_edit)

        # 재생목록/채널 다운로드
        self.playlist_check = QCheckBox()
        self.playlist_check.setChecked(self.config.get("playlist_download", False))
        form_advanced.addRow("재생목록/채널 다운로드:", self.playlist_check)

        # 재생목록/채널 최대 아이템 수
        self.playlist_max_spin = QSpinBox()
        self.playlist_max_spin.setRange(1, 100)
        self.playlist_max_spin.setValue(self.config.get("max_playlist_items", 10))
        form_advanced.addRow("재생목록/채널 최대 영상 수:", self.playlist_max_spin)

        self.tab_widget.addTab(tab_advanced, "자막/재생목록")

        layout.addWidget(self.tab_widget)

        # ------------------ 하단 버튼 ------------------
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("저장")
        cancel_btn = QPushButton("취소")
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        # 이벤트 연결
        path_btn.clicked.connect(self.browse_path)
        save_btn.clicked.connect(self.save_settings)
        cancel_btn.clicked.connect(self.reject)

        # 위젯 활성화/비활성화 연결
        self.subtitle_check.toggled.connect(self.subtitle_lang_edit.setEnabled)
        self.playlist_check.toggled.connect(self.playlist_max_spin.setEnabled)

        # 초기 상태에 맞게 위젯 활성화/비활성화 설정
        self.subtitle_lang_edit.setEnabled(self.subtitle_check.isChecked())
        self.playlist_max_spin.setEnabled(self.playlist_check.isChecked())

    def browse_path(self):
        """다운로드 경로 선택"""
        folder = QFileDialog.getExistingDirectory(self, "다운로드 경로 선택")
        if folder:
            self.path_edit.setText(folder)

    def save_settings(self):
        """설정 저장"""
        quality_val, preferred_val = self.pref_quality_combo.currentData()

        self.config.config.update({
            "download_path": self.path_edit.text(),
            "video_format": self.format_combo.currentText(),
            "quality": quality_val,
            "preferred_quality": preferred_val,
            "download_audio_only": self.audio_only_check.isChecked(),
            "subtitle_download": self.subtitle_check.isChecked(),
            "subtitle_language": self.subtitle_lang_edit.text(),
            "playlist_download": self.playlist_check.isChecked(),
            "max_playlist_items": self.playlist_max_spin.value(),
            "auto_open_folder": self.auto_open_check.isChecked(),
        })
        self.config.save_config()
        self.accept()

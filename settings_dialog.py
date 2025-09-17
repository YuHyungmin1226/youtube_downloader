"""
설정 다이얼로그 모듈
"""
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QPushButton, QHBoxLayout, QVBoxLayout, QComboBox, QCheckBox, QSpinBox, QFileDialog
)

class SettingsDialog(QDialog):
    """설정 다이얼로그 클래스"""
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("설정")
        self.setFixedSize(400, 500)
        self.setup_ui()

    def setup_ui(self):
        """UI 설정"""
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # 다운로드 경로
        self.path_edit = QLineEdit(str(self.config.get_download_path()))
        path_btn = QPushButton("찾아보기")
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(path_btn)
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
        save_btn = QPushButton("저장")
        cancel_btn = QPushButton("취소")
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        # 이벤트 연결
        path_btn.clicked.connect(self.browse_path)
        save_btn.clicked.connect(self.save_settings)
        cancel_btn.clicked.connect(self.reject)

    def browse_path(self):
        """다운로드 경로 선택"""
        folder = QFileDialog.getExistingDirectory(self, "다운로드 경로 선택")
        if folder:
            self.path_edit.setText(folder)

    def save_settings(self):
        """설정 저장"""
        self.config.set("download_path", self.path_edit.text())
        self.config.set("video_format", self.format_combo.currentText())
        self.config.set("quality", self.quality_combo.currentText())
        self.config.set("download_audio_only", self.audio_only_check.isChecked())
        self.config.set("subtitle_download", self.subtitle_check.isChecked())
        self.config.set("auto_open_folder", self.auto_open_check.isChecked())
        self.config.set("max_retries", self.retry_spin.value())
        self.config.set("retry_delay", self.delay_spin.value())
        self.accept()

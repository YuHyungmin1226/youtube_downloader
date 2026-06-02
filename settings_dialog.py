"""
설정 다이얼로그 모듈
"""
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QPushButton, QHBoxLayout, QVBoxLayout, QComboBox, QCheckBox, QSpinBox, QFileDialog, QTabWidget, QWidget, QGroupBox
)

class SettingsDialog(QDialog):
    """설정 다이얼로그 클래스"""
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("설정")
        self.setFixedSize(480, 500)
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

        # 품질
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["best", "worst"])
        self.quality_combo.setCurrentText(self.config.get_quality())
        form_general.addRow("품질:", self.quality_combo)

        # 선호 품질 (해상도 제한)
        self.pref_quality_combo = QComboBox()
        self.pref_quality_combo.addItems(["best", "2160p", "1440p", "1080p", "720p", "480p", "360p"])
        self.pref_quality_combo.setCurrentText(self.config.get("preferred_quality", "1080p"))
        form_general.addRow("선호 해상도:", self.pref_quality_combo)

        # 오디오만 다운로드
        self.audio_only_check = QCheckBox()
        self.audio_only_check.setChecked(self.config.is_audio_only())
        form_general.addRow("오디오만 다운로드:", self.audio_only_check)

        # 자동 폴더 열기
        self.auto_open_check = QCheckBox()
        self.auto_open_check.setChecked(self.config.should_auto_open_folder())
        form_general.addRow("다운로드 후 폴더 자동 열기:", self.auto_open_check)

        # 최대 재시도 횟수
        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(1, 10)
        self.retry_spin.setValue(self.config.get_max_retries())
        form_general.addRow("최대 재시도 횟수:", self.retry_spin)

        # 재시도 지연 시간
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(1, 30)
        self.delay_spin.setValue(self.config.get_retry_delay())
        form_general.addRow("재시도 지연 시간(초):", self.delay_spin)
        
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

        # 재생목록 다운로드
        self.playlist_check = QCheckBox()
        self.playlist_check.setChecked(self.config.get("playlist_download", False))
        form_advanced.addRow("재생목록 다운로드:", self.playlist_check)

        # 재생목록 최대 아이템 수
        self.playlist_max_spin = QSpinBox()
        self.playlist_max_spin.setRange(1, 100)
        self.playlist_max_spin.setValue(self.config.get("max_playlist_items", 10))
        form_advanced.addRow("재생목록 최대 영상 수:", self.playlist_max_spin)
        
        self.tab_widget.addTab(tab_advanced, "자막/재생목록")

        # ------------------ 탭 3: 보안 및 쿠키 ------------------
        tab_security = QWidget()
        vbox_security = QVBoxLayout(tab_security)
        
        # 1. 쿠키 설정 그룹
        cookies_group = QGroupBox("쿠키 설정 (우회 및 연령 제한용)")
        form_cookies = QFormLayout(cookies_group)
        
        self.cookies_check = QCheckBox()
        self.cookies_check.setChecked(self.config.get("use_cookies", False))
        form_cookies.addRow("쿠키 사용:", self.cookies_check)
        
        self.cookies_source_combo = QComboBox()
        self.cookies_source_combo.addItems(["텍스트 파일 사용", "웹 브라우저 연동"])
        source_val = "웹 브라우저 연동" if self.config.get("cookies_source", "file") == "browser" else "텍스트 파일 사용"
        self.cookies_source_combo.setCurrentText(source_val)
        form_cookies.addRow("쿠키 공급원:", self.cookies_source_combo)
        
        # 쿠키 파일 경로
        self.cookies_file_edit = QLineEdit(self.config.get("cookies_file", ""))
        self.cookies_file_btn = QPushButton("찾아보기")
        cookies_layout = QHBoxLayout()
        cookies_layout.addWidget(self.cookies_file_edit)
        cookies_layout.addWidget(self.cookies_file_btn)
        form_cookies.addRow("쿠키 파일 경로:", cookies_layout)
        
        # 브라우저 선택
        self.cookies_browser_combo = QComboBox()
        self.cookies_browser_combo.addItems(["chrome", "firefox", "edge", "safari", "opera", "vivaldi"])
        self.cookies_browser_combo.setCurrentText(self.config.get("cookies_browser", "chrome"))
        form_cookies.addRow("가져올 브라우저:", self.cookies_browser_combo)
        
        vbox_security.addWidget(cookies_group)
        
        # 2. PO Token 설정 그룹
        po_token_group = QGroupBox("유튜브 보안 우회 (PO Token)")
        form_po = QFormLayout(po_token_group)
        
        self.po_token_check = QCheckBox()
        self.po_token_check.setChecked(self.config.get("use_po_token", False))
        form_po.addRow("PO Token 사용:", self.po_token_check)
        
        self.po_token_edit = QLineEdit(self.config.get("po_token", ""))
        self.po_token_edit.setPlaceholderText("Visitor ID에 종속된 PO Token 입력")
        form_po.addRow("PO Token:", self.po_token_edit)
        
        self.visitor_data_edit = QLineEdit(self.config.get("visitor_data", ""))
        self.visitor_data_edit.setPlaceholderText("Visitor Data 입력")
        form_po.addRow("Visitor Data:", self.visitor_data_edit)
        
        self.player_client_combo = QComboBox()
        self.player_client_combo.addItems(["web", "mweb", "ios", "android"])
        self.player_client_combo.setCurrentText(self.config.get("player_client", "web"))
        form_po.addRow("재생 클라이언트:", self.player_client_combo)
        
        vbox_security.addWidget(po_token_group)
        self.tab_widget.addTab(tab_security, "보안 및 쿠키")
        
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
        self.cookies_file_btn.clicked.connect(self.browse_cookies_file)
        save_btn.clicked.connect(self.save_settings)
        cancel_btn.clicked.connect(self.reject)

        # 위젯 활성화/비활성화 연결
        self.subtitle_check.toggled.connect(self.subtitle_lang_edit.setEnabled)
        self.playlist_check.toggled.connect(self.playlist_max_spin.setEnabled)
        self.cookies_check.toggled.connect(self.on_cookies_toggled)
        self.cookies_source_combo.currentIndexChanged.connect(self.on_cookies_source_changed)
        self.po_token_check.toggled.connect(self.on_po_token_toggled)

        # 초기 상태에 맞게 위젯 활성화/비활성화 설정
        self.subtitle_lang_edit.setEnabled(self.subtitle_check.isChecked())
        self.playlist_max_spin.setEnabled(self.playlist_check.isChecked())
        self.on_cookies_toggled(self.cookies_check.isChecked())
        self.on_po_token_toggled(self.po_token_check.isChecked())

    def on_cookies_toggled(self, checked):
        """쿠키 사용 체크박스 상태 변경 처리"""
        self.cookies_source_combo.setEnabled(checked)
        if checked:
            self.on_cookies_source_changed(self.cookies_source_combo.currentIndex())
        else:
            self.cookies_file_edit.setEnabled(False)
            self.cookies_file_btn.setEnabled(False)
            self.cookies_browser_combo.setEnabled(False)

    def on_cookies_source_changed(self, index):
        """쿠키 소스 콤보박스 변경 처리"""
        if not self.cookies_check.isChecked():
            return
        is_file = (self.cookies_source_combo.currentText() == "텍스트 파일 사용")
        self.cookies_file_edit.setEnabled(is_file)
        self.cookies_file_btn.setEnabled(is_file)
        self.cookies_browser_combo.setEnabled(not is_file)

    def on_po_token_toggled(self, checked):
        """PO Token 사용 체크박스 상태 변경 처리"""
        self.po_token_edit.setEnabled(checked)
        self.visitor_data_edit.setEnabled(checked)
        self.player_client_combo.setEnabled(checked)

    def browse_path(self):
        """다운로드 경로 선택"""
        folder = QFileDialog.getExistingDirectory(self, "다운로드 경로 선택")
        if folder:
            self.path_edit.setText(folder)

    def browse_cookies_file(self):
        """쿠키 파일 선택"""
        file_path, _ = QFileDialog.getOpenFileName(self, "쿠키 파일 선택", "", "텍스트 파일 (*.txt);;모든 파일 (*)")
        if file_path:
            self.cookies_file_edit.setText(file_path)

    def save_settings(self):
        """설정 저장"""
        cookies_source_val = "browser" if self.cookies_source_combo.currentText() == "웹 브라우저 연동" else "file"
        
        self.config.config.update({
            "download_path": self.path_edit.text(),
            "video_format": self.format_combo.currentText(),
            "quality": self.quality_combo.currentText(),
            "preferred_quality": self.pref_quality_combo.currentText(),
            "download_audio_only": self.audio_only_check.isChecked(),
            "subtitle_download": self.subtitle_check.isChecked(),
            "subtitle_language": self.subtitle_lang_edit.text(),
            "playlist_download": self.playlist_check.isChecked(),
            "max_playlist_items": self.playlist_max_spin.value(),
            "use_cookies": self.cookies_check.isChecked(),
            "cookies_source": cookies_source_val,
            "cookies_file": self.cookies_file_edit.text(),
            "cookies_browser": self.cookies_browser_combo.currentText(),
            "use_po_token": self.po_token_check.isChecked(),
            "po_token": self.po_token_edit.text(),
            "visitor_data": self.visitor_data_edit.text(),
            "player_client": self.player_client_combo.currentText(),
            "auto_open_folder": self.auto_open_check.isChecked(),
            "max_retries": self.retry_spin.value(),
            "retry_delay": self.delay_spin.value()
        })
        self.config.save_config()
        self.accept()

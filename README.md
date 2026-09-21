# YouTube 최고화질 다운로더 (YouTube Best Quality Downloader)

YouTube 영상 링크(URL)를 입력하면 해당 영상이 제공하는 **최고화질(4K UHD, 2K QHD, 1080p60 등)**을 자동으로 분석하여 무손실로 병합 다운로드해주는 고성능 단일 포터블 데스크톱 프로그램입니다.

최근 업데이트를 통해 **YouTube 403 Forbidden 차단 완벽 우회(QuickJS 내장)** 및 **유튜브 채널 전체 동영상/재생목록 일괄 순차 다운로드 & 실시간 중지 기능**을 탑재하였습니다.

---

## ✨ 주요 기능

- **🎬 최고화질(4K / 2K / 1080p60) 자동 다운로드**:
  - 원본 영상이 지원하는 최대 화질 비디오 스트림과 최고 음질 오디오 스트림을 자동 탐색하여 무손실 병합합니다.
- **🛡️ YouTube 차단 완벽 방지 (HTTP 403 Forbidden 및 최신 JS 서명 우회)**:
  - 초경량 포터블 QuickJS 엔진(`bin/qjs.exe`, 2.1MB)을 내장하여 무거운 Node.js 설치 없이도 YouTube 최신 JS 챌린지(`n` 파라미터)를 즉각 해결합니다.
  - 네트워크 이상이나 일시적 차단 발생 시 `Android` 호환 프로필로 자동 전환하는 스마트 대체(Fallback) 엔진이 내장되어 있습니다.
- **📺 유튜브 채널 전체 동영상 & 재생목록 일괄 순차 다운로드 (NEW)**:
  - 채널 핸들(@채널명), 채널 홈, 재생목록 URL을 자동 감지하여 채널 동영상 탭(`/@채널명/videos`)으로 자동 정규화합니다.
  - 채널별 전용 하위 폴더(`Downloads/[채널명]/[영상제목].mp4`)를 자동으로 생성하여 영상을 체계적으로 분류 저장합니다.
  - 이미 다운로드받은 영상은 건너뛰는 **중복 다운로드 방지(`nooverwrites`)** 및 비공개/삭제된 영상 건너뛰기(`ignoreerrors`)가 적용됩니다.
  - `extract_flat` 기반 초고속 메타데이터 분석 및 실시간 순차 다운로드 진행률(`[현재번호/총개수]`)을 제공합니다.
  - 다운로드 도중 언제든지 안전하게 즉시 중단할 수 있는 **실시간 중지(Cancel)** 기능을 지원합니다.
- **📦 완전 무설치 포터블 (Portable)**:
  - `imageio-ffmpeg` 패키지 및 로컬/사용자 홈 폴더 자동 감지 지원.
  - PC에 FFmpeg나 JS 엔진이 없더라도 관리자 권한 없이 로컬 공간에 자동 준비하여 중단 없이 즉시 다운로드를 완료합니다.
- **🖼️ 실시간 영상 미리보기 카드 UI**:
  - URL을 입력하면 영상 썸네일, 제목, 채널명, 재생 시간 및 **`✨ 지원 최고화질 배지`**를 즉시 분석하여 표시합니다.
- **🎵 고음질 MP3 음원 추출**:
  - 원클릭으로 영상뿐만 아니라 최고 음질(320kbps) 오디오 파일만 추출할 수 있습니다.
- **🎨 깔끔한 모던 다크 UI/UX**:
  - 직관적인 상태 알림, 실시간 다운로드 속도·남은 시간·용량 표시, 다운로드 완료 후 원클릭 영상 재생 및 저장 폴더 열기 지원.
  - 상세한 터미널 로그는 기본적으로 숨겨져 있으며, 원클릭으로 펼쳐서 확인할 수 있습니다.

---

## 🚀 빠른 시작

### 방법 1. 빌드된 무설치 실행 파일 사용 (가장 간편함)
별도의 Python이나 라이브러리 설치 없이 즉시 사용할 수 있습니다.
1. [`release/`](release/) 폴더에서 `YouTube_Downloader.exe`를 직접 실행하거나 최신 ZIP 압축 패키지(`YouTube_Downloader_vYYYY.MM.DD_Windows.zip`)를 내려받아 압축을 풉니다.
2. `YouTube_Downloader.exe`를 실행합니다.

### 방법 2. 간편 실행 스크립트 사용 (run.bat)
저장소를 클론한 후 배치 파일을 더블 클릭하면 의존성 확인/설치 후 프로그램이 실행됩니다.
```cmd
run.bat
```

### 방법 3. 소스 코드에서 직접 실행
```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 프로그램 실행
python youtube_downloader.py
```

### 방법 4. CLI (터미널) 모드 실행
GUI 창 없이 콘솔 명령어만으로 바로 다운로드할 수도 있습니다:
```bash
# 최고화질 영상 다운로드
python youtube_downloader.py --url "https://www.youtube.com/watch?v=..."

# 고음질 MP3 음원만 추출
python youtube_downloader.py --url "https://www.youtube.com/watch?v=..." --audio-only
```

---

## 🔨 독립 실행 파일(.exe) 빌드 방법

프로젝트에 내장된 [`build.py`](build.py) 스크립트를 사용하여 PyInstaller 기반의 배포용 단일 실행 파일 및 ZIP 패키지를 손쉽게 빌드할 수 있습니다:

```bash
python build.py
```

- **완전 독립 패키징**: QuickJS 바이너리(`bin/qjs.exe`), `imageio-ffmpeg`, 고해상도 앱 아이콘이 하나의 `.exe` 내부에 자동 번들링됩니다.
- **용량 최적화**: 사용하지 않는 Qt 대용량 모듈(Qt3D, QtWebEngine 등)을 자동 배제하여 실행 속도와 파일 크기를 최적화합니다.
- **산출물**:
  - `release/YouTube_Downloader.exe` (독립 실행 파일)
  - `release/YouTube_Downloader_vYYYY.MM.DD_Windows.zip` (배포용 압축 패키지)

---

## ⚙️ 설정 옵션

프로그램 우측 상단의 **⚙️ 설정 버튼**을 통해 사용자 환경을 맞춤 설정할 수 있습니다:
- **저장 폴더**: 영상 및 음원이 저장될 경로 지정 (기본값: 사용자 `Downloads` 폴더)
- **다운로드 완료 후 폴더 자동 열기**: 체크 시 완료와 동시에 탐색기가 열립니다.
- **네트워크 재시도 횟수**: 불안정한 네트워크 환경에서 다운로드 재시도 횟수 조절.

설정 정보는 사용자 홈 디렉토리의 `youtube_downloader_config.json`에 안전하게 저장됩니다.

---

## 🏗️ 프로젝트 구조

```
youtube_downloader/
├── youtube_downloader.py  # 메인 애플리케이션 (GUI, 엔진, 다운로더 단일 파일 통합)
├── build.py               # PyInstaller 자동 빌드 및 릴리스 ZIP 생성 스크립트
├── run.bat                # 원클릭 의존성 확인 및 실행기
├── icon.png               # 고해상도 앱 아이콘 (1024x1024)
├── icon.ico               # Windows 실행 파일용 다중 해상도 아이콘
├── requirements.txt       # Python 패키지 의존성 목록
├── README.md              # 프로젝트 안내 문서
├── bin/
│   └── qjs.exe            # YouTube JS 서명 우회용 초경량 QuickJS 런타임 (2.1MB)
└── release/               # 배포 산출물 디렉토리
    ├── YouTube_Downloader.exe
    └── YouTube_Downloader_vYYYY.MM.DD_Windows.zip
```

---

## 📝 시스템 요구사항

- **운영체제**: Windows 10/11 (64-bit), macOS 11+, Linux
- **Python 버전**: Python 3.10 이상 (소스 코드 실행 및 빌드 시에만 필요)
- **네트워크**: 인터넷 연결 필수

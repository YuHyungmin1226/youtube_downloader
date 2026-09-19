# YouTube 최고화질 다운로더 (YouTube Best Quality Downloader)

YouTube 영상 링크(URL)를 입력하면 해당 영상이 제공하는 **최고화질(4K UHD, 2K QHD, 1080p60 등)**을 자동으로 분석하여 무손실로 병합 다운로드해주는 깔끔하고 세련된 데스크톱 프로그램입니다.

---

## ✨ 주요 기능

- **🎬 최고화질(4K / 2K / 1080p60) 자동 다운로드**: 해상도 제한 없이 원본 영상이 지원하는 최대 화질 스트림과 최고 음질 오디오를 자동 선택 및 무손실 병합합니다.
- **🛡️ YouTube 차단 완벽 방지 (HTTP 403 Forbidden 방지)**:
  - 초경량 포터블 QuickJS 엔진(`qjs.exe`, 2.1MB) 내장 및 `web_embedded` 최적화 클라이언트를 적용하여 YouTube의 최신 JS 챌린지(`n` 파라미터)를 완벽히 해결합니다.
  - 네트워크 이상이나 일시적 차단 감지 시 `Android` 호환 프로필로 자동 전환되는 스마트 대체(Fallback) 엔진이 탑재되어 있습니다.
- **🖼️ 실시간 영상 미리보기 카드**: URL을 입력하면 영상 썸네일, 제목, 채널명, 재생 시간 및 **`✨ 지원 최고화질 배지`**를 즉시 표시합니다.
- **📦 완전 무설치 포터블 (Portable)**: 
  - `imageio-ffmpeg` 패키지 및 포터블 폴더 자동 감지 지원.
  - PC에 FFmpeg나 JS 엔진이 없더라도, 관리자 권한 없이 로컬 공간에 자동 준비하여 중단 없이 즉시 다운로드를 완료합니다.
- **🎵 고음질 MP3 음원 추출**: 원클릭으로 영상뿐만 아니라 최고 음질(320kbps) 오디오 파일만 추출할 수 있습니다.
- **🎨 깔끔하고 단순한 모던 UI/UX**: 군더더기 없는 다크 테마, 실시간 속도 및 잔여 시간 표시, 완료 후 원클릭 영상 재생/폴더 열기 지원.
- **접이식 상세 로그**: 복잡한 터미널 로그는 기본적으로 숨겨져 있으며, 필요할 때만 펼쳐서 확인할 수 있습니다.

---

## 🚀 빠른 시작

### 1. 간편 실행 (권장)
`run.bat` 파일을 더블 클릭하면 자동으로 환경을 확인하고 프로그램을 실행합니다.
```cmd
run.bat
```

### 2. 수동 설치 및 실행
```bash
pip install -r requirements.txt
python youtube_downloader.py
```

### 3. CLI (터미널) 모드 실행 지원
GUI 없이 터미널 명령어로 바로 다운로드할 수도 있습니다:
```bash
# 최고화질 영상 다운로드
python youtube_downloader.py --url "https://www.youtube.com/watch?v=..."

# 고음질 MP3 음원만 추출
python youtube_downloader.py --url "https://www.youtube.com/watch?v=..." --audio-only
```

# YouTube 영상 다운로드 도구 v2.1.0

PySide6를 사용한 GUI 기반 YouTube 영상 다운로드 애플리케이션입니다.

## 🚀 주요 기능

- **간편한 GUI**: 직관적인 사용자 인터페이스
- **자동 FFmpeg 설치**: FFmpeg가 없어도 자동으로 설치
- **실시간 진행률**: 다운로드 진행 상황을 실시간으로 표시
- **크로스 플랫폼**: Windows, macOS, Linux 지원
- **고품질 다운로드**: 최고 품질의 MP4 형식으로 다운로드
- **설정 시스템**: 다운로드 경로, 품질, 형식 등 사용자 정의 가능
- **오디오만 다운로드**: 음성 파일만 추출 가능
- **자막 다운로드**: 한국어 자막 자동 다운로드
- **재시도 메커니즘**: 네트워크 오류 시 자동 재시도
- **성능 최적화**: 메모리 사용량 및 진행률 업데이트 최적화
- **재생목록 지원**: YouTube 재생목록 다운로드
- **쿠키 지원**: 로그인이 필요한 영상 다운로드

## 📋 시스템 요구사항

- Python 3.7 이상 (Python 3.13 권장)
- 인터넷 연결
- 관리자 권한 (FFmpeg 설치 시)
- 최소 100MB 여유 디스크 공간

## 🔧 설치 방법

### 1. 저장소 클론
```bash
git clone <repository-url>
cd youtube_downloader
```

### 2. 가상환경 생성 (권장)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. 의존성 설치
```bash
pip install -r requirements.txt
```

### 4. 애플리케이션 실행
```bash
python youtube_downloader.py
```

## 📖 사용 방법

### 기본 사용법
1. **YouTube 링크 입력**: YouTube 영상 URL을 입력창에 붙여넣기
2. **FFmpeg 설치** (필요시): FFmpeg 설치 버튼 클릭
3. **설정 조정** (선택사항): 설정 버튼을 눌러 다운로드 옵션 조정
4. **다운로드 시작**: "영상 다운로드" 버튼 클릭
5. **완료**: 다운로드된 영상은 설정된 폴더에 저장

### 고급 기능
- **재생목록 다운로드**: 재생목록 URL 입력 시 설정에서 활성화
- **자막 다운로드**: 설정에서 자막 다운로드 활성화
- **쿠키 파일 사용**: 로그인이 필요한 영상의 경우 쿠키 파일 설정

## ⚙️ 설정 옵션

### 기본 설정
- **다운로드 경로**: 영상이 저장될 폴더
- **비디오 형식**: MP4, WebM, MKV 중 선택
- **품질**: 최고 품질 또는 최저 품질
- **선호 품질**: 1080p, 720p, 480p 등 특정 해상도 선택

### 고급 설정
- **오디오만 다운로드**: 음성 파일만 추출
- **자막 다운로드**: 한국어 자막 자동 다운로드
- **자동 폴더 열기**: 다운로드 완료 후 폴더 자동 열기
- **재시도 설정**: 최대 재시도 횟수 및 지연 시간
- **재생목록 제한**: 다운로드할 영상 개수 제한
- **쿠키 파일**: 로그인 세션 유지를 위한 쿠키 파일 경로

## 🛠️ 문제 해결

### FFmpeg 관련 문제
- FFmpeg 설치 후 PC를 재시작하여 환경변수를 적용하세요
- 관리자 권한으로 실행해보세요
- 수동으로 FFmpeg를 설치한 경우 PATH에 추가되었는지 확인하세요

### 다운로드 실패
- 인터넷 연결을 확인하세요
- YouTube 링크가 유효한지 확인하세요
- yt-dlp 라이브러리를 최신 버전으로 업데이트하세요: `pip install --upgrade yt-dlp`
- 설정에서 재시도 횟수를 늘려보세요
- 연령 제한 영상의 경우 쿠키 파일을 사용해보세요

### 성능 문제
- 설정에서 진행률 표시를 비활성화해보세요
- 다운로드 경로를 SSD로 변경해보세요
- 동시 다운로드 수를 줄여보세요

### GUI 문제
- PySide6가 제대로 설치되었는지 확인하세요
- 가상환경을 사용하는 경우 활성화되었는지 확인하세요

## 🔄 업데이트 내역

### v2.1.0 (최신)
- ✅ yt-dlp 최신 버전 (2025.7.21) 지원
- ✅ PySide6 최신 버전 (6.x.x) 지원
- ✅ requirements.txt 최신화 및 정리
- ✅ README.md 상세 업데이트
- ✅ 재생목록 다운로드 기능 개선
- ✅ 쿠키 파일 지원 강화
- ✅ 에러 처리 개선

### v2.0.0
- ✅ 설정 시스템 완전 통합
- ✅ 코드 중복 제거 및 모듈화
- ✅ 에러 처리 및 재시도 메커니즘 강화
- ✅ 성능 최적화 (메모리 사용량, 진행률 업데이트)
- ✅ 오디오만 다운로드 기능 추가
- ✅ 자막 다운로드 기능 추가
- ✅ 설정 UI 추가
- ✅ 유틸리티 모듈 분리

### v1.0.0
- 기본 YouTube 다운로드 기능
- FFmpeg 자동 설치
- GUI 인터페이스

## 🏗️ 프로젝트 구조

```
youtube_downloader/
├── youtube_downloader.py  # 메인 애플리케이션
├── config.py              # 설정 관리
├── utils.py               # 유틸리티 함수
├── ffmpeg_installer.py    # FFmpeg 설치 관리
├── requirements.txt       # Python 의존성
├── README.md             # 프로젝트 문서
└── release/              # 배포 파일
    ├── YouTube_Downloader.exe
    ├── INSTALL.txt
    └── README.md
```

## 🤝 기여하기

### 버그 리포트
- GitHub Issues를 통해 버그를 리포트해주세요
- 가능한 한 상세한 정보를 포함해주세요:
  - 운영체제 및 버전
  - Python 버전
  - 오류 메시지
  - 재현 단계

### 기능 제안
- 새로운 기능 아이디어는 GitHub Issues로 제안해주세요
- 구현 가능성과 우선순위를 고려하여 검토하겠습니다

### 코드 기여
1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## ⚠️ 면책 조항

이 도구는 교육 및 개인 사용 목적으로만 사용해야 합니다. 저작권이 있는 콘텐츠의 상업적 사용은 법적 문제를 야기할 수 있습니다. 사용자는 관련 법률을 준수할 책임이 있습니다.

## 📞 지원

- **GitHub Issues**: [프로젝트 이슈 페이지](https://github.com/your-username/youtube_downloader/issues)
- **문서**: 이 README 파일과 코드 내 주석을 참조하세요
- **커뮤니티**: GitHub Discussions를 통해 다른 사용자들과 소통하세요

---

**Made with ❤️ for the YouTube community** 
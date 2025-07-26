# YouTube 영상 다운로드 도구

PyQt5를 사용한 GUI 기반 YouTube 영상 다운로드 애플리케이션입니다.

## 🚀 주요 기능

- **간편한 GUI**: 직관적인 사용자 인터페이스
- **자동 FFmpeg 설치**: FFmpeg가 없어도 자동으로 설치
- **실시간 진행률**: 다운로드 진행 상황을 실시간으로 표시
- **크로스 플랫폼**: Windows, macOS, Linux 지원
- **고품질 다운로드**: 최고 품질의 MP4 형식으로 다운로드

## 📋 시스템 요구사항

- Python 3.7 이상
- 인터넷 연결
- 관리자 권한 (FFmpeg 설치 시)

## 🔧 설치 방법

1. **저장소 클론**
   ```bash
   git clone <repository-url>
   cd youtube_downloader
   ```

2. **의존성 설치**
   ```bash
   pip install -r requirements.txt
   ```

3. **애플리케이션 실행**
   ```bash
   python youtube_downloader.py
   ```

## 📖 사용 방법

1. **YouTube 링크 입력**: YouTube 영상 URL을 입력창에 붙여넣기
2. **FFmpeg 설치** (필요시): FFmpeg 설치 버튼 클릭
3. **다운로드 시작**: "영상 다운로드" 버튼 클릭
4. **완료**: 다운로드된 영상은 `~/Videos` 폴더에 저장

## 🛠️ 문제 해결

### FFmpeg 관련 문제
- FFmpeg 설치 후 PC를 재시작하여 환경변수를 적용하세요
- 관리자 권한으로 실행해보세요

### 다운로드 실패
- 인터넷 연결을 확인하세요
- YouTube 링크가 유효한지 확인하세요
- yt-dlp 라이브러리를 최신 버전으로 업데이트하세요

## 📝 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 🤝 기여하기

버그 리포트나 기능 제안은 이슈를 통해 제출해주세요. 
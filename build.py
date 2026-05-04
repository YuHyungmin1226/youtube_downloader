#!/usr/bin/env python3
"""
YouTube 다운로더 빌드 스크립트
PyInstaller를 사용하여 실행 파일을 생성합니다.
"""

import os
import sys
import shutil
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

def clean_build_dirs():
    """빌드 디렉토리들과 임시 파일들을 정리합니다."""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"{dir_name} 디렉토리 정리 중...")
            shutil.rmtree(dir_name, ignore_errors=True)
    
    # .spec 파일 정리
    for spec_file in Path('.').glob('*.spec'):
        print(f"{spec_file} 파일 정리 중...")
        os.remove(spec_file)

def build_executable():
    """PyInstaller를 사용하여 실행 파일을 빌드합니다."""
    print("YouTube 다운로더 빌드 시작...")

    # PyInstaller 명령어 구성
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',                    # 단일 실행 파일로 생성
        '--windowed',                   # 콘솔 창 숨김
        '--name=YouTube_Downloader',    # 실행 파일 이름
        '--clean',                      # 빌드 전 캐시 정리
        '--noconfirm',                  # 확인 절차 생략
        '--icon=icon.ico',              # 아이콘 (있는 경우)
        '--add-data=config.py;.',       # 설정 파일 포함
        '--add-data=utils.py;.',        # 유틸리티 파일 포함
        '--add-data=ffmpeg_installer.py;.',  # FFmpeg 설치 파일 포함
        '--hidden-import=PySide6.QtCore',
        '--hidden-import=PySide6.QtWidgets',
        '--hidden-import=PySide6.QtGui',
        '--hidden-import=yt_dlp',
        '--hidden-import=requests',
        '--hidden-import=pathlib',
        '--hidden-import=threading',
        '--hidden-import=re',
        '--hidden-import=json',
        '--hidden-import=platform',
        '--hidden-import=subprocess',
        '--hidden-import=shutil',
        '--hidden-import=zipfile',
        '--hidden-import=tempfile',
        '--hidden-import=urllib.request',
        '--hidden-import=urllib.parse',
        '--collect-all=yt_dlp',
        '--collect-all=PySide6',
        'youtube_downloader.py'
    ]

    # 아이콘이 없는 경우 제거
    if not os.path.exists('icon.ico'):
        try:
            cmd.remove('--icon=icon.ico')
        except ValueError:
            pass

    print("PyInstaller 명령어 실행 중...")
    print(f"명령어: {' '.join(cmd)}")

    try:
        # 빌드 과정의 상세 출력을 위해 capture_output=False (기본값) 사용
        result = subprocess.run(cmd, check=True)
        print("빌드 성공!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"빌드 실패: {e}")
        return False

def copy_to_release():
    """빌드된 파일을 release 디렉토리로 복사합니다."""
    dist_exe = Path('dist/YouTube_Downloader.exe')
    if not dist_exe.exists():
        print("빌드된 실행 파일을 찾을 수 없습니다.")
        return False

    # release 디렉토리 생성
    release_dir = Path('release')
    release_dir.mkdir(exist_ok=True)

    # 기존 파일 백업 (선택 사항, 필요 없으면 삭제 가능)
    old_exe = release_dir / 'YouTube_Downloader.exe'
    if old_exe.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = release_dir / f'YouTube_Downloader_backup_{timestamp}.exe'
        print(f"기존 파일 백업: {backup_name}")
        shutil.move(str(old_exe), str(backup_name))

    # 새 파일 복사
    print("release 디렉토리로 복사 중...")
    shutil.copy2(str(dist_exe), str(old_exe))

    # 파일 크기 확인
    file_size = os.path.getsize(str(old_exe)) / (1024 * 1024)
    print(f"복사 완료! 파일 크기: {file_size:.1f} MB")

    return True

def create_zip_package():
    """배포용 ZIP 패키지를 생성합니다."""
    print("ZIP 패키지 생성 중...")

    # 버전 정보 (간단한 날짜 기반)
    version = datetime.now().strftime("%Y.%m.%d")
    zip_name = f"release/YouTube_Downloader_v{version}_Windows.zip"

    try:
        with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 실행 파일 추가
            if os.path.exists('release/YouTube_Downloader.exe'):
                zipf.write('release/YouTube_Downloader.exe', 'YouTube_Downloader.exe')

            # README 파일 추가 (있는 경우)
            if os.path.exists('README.md'):
                zipf.write('README.md', 'README.md')

            # requirements.txt 추가
            if os.path.exists('requirements.txt'):
                zipf.write('requirements.txt', 'requirements.txt')

        zip_size = os.path.getsize(zip_name) / (1024 * 1024)
        print(f"ZIP 패키지 생성 완료: {zip_name} ({zip_size:.1f} MB)")
        return zip_name
    except Exception as e:
        print(f"ZIP 패키지 생성 실패: {e}")
        return None

def main():
    """메인 빌드 프로세스"""
    print("YouTube 다운로더 빌드 프로세스 시작")
    print("=" * 50)

    # 1. 빌드 디렉토리 정리 (시작 전)
    clean_build_dirs()

    # 2. 실행 파일 빌드
    if not build_executable():
        print("빌드 실패로 프로세스를 중단합니다.")
        return False

    # 3. release 디렉토리로 복사
    if not copy_to_release():
        print("파일 복사 실패.")
        # 실패하더라도 빌드 시 생성된 파일들은 정리하는 것이 좋음
        clean_build_dirs()
        return False

    # 4. ZIP 패키지 생성
    zip_name = create_zip_package()

    # 5. 최종 정리 (빌드 중 생성된 모든 임시 파일/폴더 제거)
    print("최종 정리 중 (빌드 임시 파일 제거)...")
    clean_build_dirs()

    print("=" * 50)
    print("빌드 프로세스 완료!")
    print(f"실행 파일: release/YouTube_Downloader.exe")
    if zip_name:
        print(f"배포 패키지: {zip_name}")
    print("=" * 50)

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
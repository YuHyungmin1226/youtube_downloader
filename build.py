#!/usr/bin/env python3
"""
YouTube 다운로더 빌드 스크립트
PyInstaller를 사용하여 실행 파일을 생성합니다.
"""

import os
import platform
import stat
import sys
import shutil
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

APP_NAME = 'YouTube_Downloader'
SYSTEM_NAME = platform.system()
EXCLUDED_QT_MODULES = [
    'PySide6.Qt3DAnimation',
    'PySide6.Qt3DCore',
    'PySide6.Qt3DExtras',
    'PySide6.Qt3DInput',
    'PySide6.Qt3DLogic',
    'PySide6.Qt3DRender',
    'PySide6.QtAsyncio',
    'PySide6.QtBluetooth',
    'PySide6.QtCharts',
    'PySide6.QtConcurrent',
    'PySide6.QtDataVisualization',
    'PySide6.QtDesigner',
    'PySide6.QtGraphs',
    'PySide6.QtGraphsWidgets',
    'PySide6.QtHelp',
    'PySide6.QtHttpServer',
    'PySide6.QtLocation',
    'PySide6.QtMultimedia',
    'PySide6.QtMultimediaWidgets',
    'PySide6.QtNetworkAuth',
    'PySide6.QtNfc',
    'PySide6.QtOpenGL',
    'PySide6.QtOpenGLWidgets',
    'PySide6.QtPdf',
    'PySide6.QtPdfWidgets',
    'PySide6.QtPositioning',
    'PySide6.QtPrintSupport',
    'PySide6.QtQml',
    'PySide6.QtQuick',
    'PySide6.QtQuick3D',
    'PySide6.QtQuickControls2',
    'PySide6.QtQuickTest',
    'PySide6.QtQuickWidgets',
    'PySide6.QtRemoteObjects',
    'PySide6.QtScxml',
    'PySide6.QtSensors',
    'PySide6.QtSerialBus',
    'PySide6.QtSerialPort',
    'PySide6.QtSpatialAudio',
    'PySide6.QtSql',
    'PySide6.QtStateMachine',
    'PySide6.QtSvg',
    'PySide6.QtSvgWidgets',
    'PySide6.QtTest',
    'PySide6.QtTextToSpeech',
    'PySide6.QtUiTools',
    'PySide6.QtWebChannel',
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineQuick',
    'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebSockets',
    'PySide6.QtWebView',
    'PySide6.QtXml',
]

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
    data_separator = ';' if SYSTEM_NAME == 'Windows' else ':'

    # PyInstaller 명령어 구성
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--windowed',                   # 콘솔 창 숨김
        f'--name={APP_NAME}',           # 실행 파일 이름
        '--clean',                      # 빌드 전 캐시 정리
        '--noconfirm',                  # 확인 절차 생략
        f'--add-data=config.py{data_separator}.',       # 설정 파일 포함
        f'--add-data=utils.py{data_separator}.',        # 유틸리티 파일 포함
        f'--add-data=ffmpeg_installer.py{data_separator}.',  # FFmpeg 설치 파일 포함
        f'--add-data=settings_dialog.py{data_separator}.',   # 설정 창 포함
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
        'youtube_downloader.py'
    ]

    if SYSTEM_NAME == 'Darwin':
        cmd.insert(4, '--onedir')
    else:
        cmd.insert(4, '--onefile')

    for module_name in EXCLUDED_QT_MODULES:
        cmd.insert(-1, f'--exclude-module={module_name}')

    # 플랫폼별 아이콘이 있는 경우만 포함
    if SYSTEM_NAME == 'Darwin' and os.path.exists('icon.icns'):
        cmd.insert(-1, '--icon=icon.icns')
    elif SYSTEM_NAME == 'Windows' and os.path.exists('icon.ico'):
        cmd.insert(-1, '--icon=icon.ico')

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

def get_build_artifact():
    """현재 OS에서 PyInstaller가 생성한 배포 산출물을 반환합니다."""
    if SYSTEM_NAME == 'Windows':
        artifact = Path('dist') / f'{APP_NAME}.exe'
    elif SYSTEM_NAME == 'Darwin':
        app_bundle = Path('dist') / f'{APP_NAME}.app'
        artifact = app_bundle if app_bundle.exists() else Path('dist') / APP_NAME
    else:
        artifact = Path('dist') / APP_NAME
    return artifact if artifact.exists() else None

def artifact_release_name(artifact):
    """release 디렉토리에 저장할 산출물 이름을 반환합니다."""
    if artifact.suffix == '.app':
        return artifact.name
    if SYSTEM_NAME == 'Windows':
        return f'{APP_NAME}.exe'
    return APP_NAME

def copy_to_release():
    """빌드된 파일을 release 디렉토리로 복사합니다."""
    artifact = get_build_artifact()
    if not artifact:
        print("빌드된 실행 파일을 찾을 수 없습니다.")
        return None

    # release 디렉토리 생성
    release_dir = Path('release')
    release_dir.mkdir(exist_ok=True)

    release_artifact = release_dir / artifact_release_name(artifact)
    if release_artifact.exists():
        print(f"기존 산출물 교체: {release_artifact}")
        if release_artifact.is_dir():
            shutil.rmtree(release_artifact)
        else:
            release_artifact.unlink()

    # 새 파일 복사
    print("release 디렉토리로 복사 중...")
    if artifact.is_dir():
        shutil.copytree(str(artifact), str(release_artifact), symlinks=True)
    else:
        shutil.copy2(str(artifact), str(release_artifact))

    # 파일 크기 확인
    file_size = get_path_size(release_artifact) / (1024 * 1024)
    print(f"복사 완료! 파일 크기: {file_size:.1f} MB")

    return release_artifact

def sync_release_docs():
    """release 폴더의 안내 문서와 의존성 파일을 최신 상태로 맞춥니다."""
    release_dir = Path('release')
    release_dir.mkdir(exist_ok=True)
    for file_name in ('README.md', 'requirements.txt'):
        source = Path(file_name)
        if source.exists():
            shutil.copy2(source, release_dir / file_name)

def get_path_size(path):
    """파일 또는 디렉토리 전체 크기를 바이트 단위로 반환합니다."""
    path = Path(path)
    if path.is_file():
        return path.stat().st_size
    return sum(
        p.stat().st_size
        for p in path.rglob('*')
        if p.is_file() and not p.is_symlink()
    )


def write_path_to_zip(zipf, file_path, arcname):
    """파일 또는 심볼릭 링크를 원래 형태로 ZIP에 기록합니다."""
    if file_path.is_symlink():
        info = zipfile.ZipInfo(arcname.as_posix())
        info.create_system = 3
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        zipf.writestr(info, os.readlink(file_path))
        return

    if file_path.is_file():
        zipf.write(file_path, arcname)

def create_zip_package(release_artifact):
    """배포용 ZIP 패키지를 생성합니다."""
    print("ZIP 패키지 생성 중...")

    # 버전 정보 (간단한 날짜 기반)
    version = datetime.now().strftime("%Y.%m.%d")
    platform_label = {
        'Windows': 'Windows',
        'Darwin': 'macOS',
        'Linux': 'Linux',
    }.get(SYSTEM_NAME, SYSTEM_NAME or 'Unknown')
    zip_name = f"release/{APP_NAME}_v{version}_{platform_label}.zip"

    try:
        with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            if release_artifact.is_dir():
                for file_path in release_artifact.rglob('*'):
                    write_path_to_zip(
                        zipf,
                        file_path,
                        file_path.relative_to(release_artifact.parent),
                    )
            else:
                zipf.write(release_artifact, release_artifact.name)

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
    if sys.version_info < (3, 10):
        print("빌드 오류: 최신 yt-dlp는 Python 3.10 이상이 필요합니다.")
        print("Python 3.12 가상환경에서 build.py를 다시 실행해주세요.")
        return

    print("YouTube 다운로더 빌드 프로세스 시작")
    print("=" * 50)

    # 1. 빌드 디렉토리 정리 (시작 전)
    clean_build_dirs()

    # 2. 실행 파일 빌드
    if not build_executable():
        print("빌드 실패로 프로세스를 중단합니다.")
        return False

    # 3. release 디렉토리로 복사
    release_artifact = copy_to_release()
    if not release_artifact:
        print("파일 복사 실패.")
        # 실패하더라도 빌드 시 생성된 파일들은 정리하는 것이 좋음
        clean_build_dirs()
        return False

    # 4. ZIP 패키지 생성
    sync_release_docs()
    zip_name = create_zip_package(release_artifact)

    # 5. 최종 정리 (빌드 중 생성된 모든 임시 파일/폴더 제거)
    print("최종 정리 중 (빌드 임시 파일 제거)...")
    clean_build_dirs()

    print("=" * 50)
    print("빌드 프로세스 완료!")
    print(f"실행 파일: {release_artifact}")
    if zip_name:
        print(f"배포 패키지: {zip_name}")
    print("=" * 50)

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""
YouTube 다운로더 빌드 스크립트
PyInstaller를 사용하여 독립 실행 파일(.exe) 및 배포용 ZIP 패키지를 생성합니다.
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

APP_NAME = "YouTube_Downloader"
SYSTEM_NAME = platform.system()

# 불필요한 대용량 Qt 모듈을 제외하여 빌드 속도 및 용량 최적화
EXCLUDED_QT_MODULES = [
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtAsyncio",
    "PySide6.QtBluetooth",
    "PySide6.QtCharts",
    "PySide6.QtConcurrent",
    "PySide6.QtDataVisualization",
    "PySide6.QtDesigner",
    "PySide6.QtGraphs",
    "PySide6.QtGraphsWidgets",
    "PySide6.QtHelp",
    "PySide6.QtHttpServer",
    "PySide6.QtLocation",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNetworkAuth",
    "PySide6.QtNfc",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtPositioning",
    "PySide6.QtPrintSupport",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickControls2",
    "PySide6.QtQuickTest",
    "PySide6.QtQuickWidgets",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
    "PySide6.QtSerialBus",
    "PySide6.QtSerialPort",
    "PySide6.QtSpatialAudio",
    "PySide6.QtSql",
    "PySide6.QtStateMachine",
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
    "PySide6.QtTest",
    "PySide6.QtTextToSpeech",
    "PySide6.QtUiTools",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
    "PySide6.QtWebView",
    "PySide6.QtXml",
]


def ensure_icon():
    """icon.png로부터 icon.ico 생성 (Windows 실행 파일 아이콘용)"""
    icon_png = Path("icon.png")
    icon_ico = Path("icon.ico")
    if not icon_png.exists():
        return
    if not icon_ico.exists() or icon_png.stat().st_mtime > icon_ico.stat().st_mtime:
        try:
            from PIL import Image
            img = Image.open(icon_png)
            img.save(
                icon_ico,
                format="ICO",
                sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
            )
            print("[INFO] icon.ico 생성 완료")
        except Exception as e:
            print(f"[WARN] icon.ico 생성 건너뜀: {e}")


def clean_build_dirs():
    """빌드 디렉토리 및 임시 파일 정리"""
    dirs_to_clean = ["build", "dist", "__pycache__"]
    for dir_name in dirs_to_clean:
        p = Path(dir_name)
        if p.exists():
            print(f"[INFO] {dir_name} 디렉토리 삭제 중...")
            shutil.rmtree(p, ignore_errors=True)

    for spec_file in Path(".").glob("*.spec"):
        print(f"[INFO] {spec_file} 스펙 파일 삭제 중...")
        try:
            spec_file.unlink()
        except OSError:
            pass


def build_executable():
    """PyInstaller를 사용하여 단일 실행 파일 빌드"""
    print("=" * 60)
    print("YouTube 다운로더 빌드 시작 (PyInstaller)")
    print("=" * 60)

    data_separator = ";" if SYSTEM_NAME == "Windows" else ":"

    ensure_icon()

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--windowed",
        f"--name={APP_NAME}",
        "--clean",
        "--noconfirm",
        f"--add-data=icon.png{data_separator}.",
        "--collect-all=yt_dlp",
        "--collect-all=imageio_ffmpeg",
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtWidgets",
        "--hidden-import=PySide6.QtGui",
        "--hidden-import=truststore",
        "--hidden-import=requests",
        "--hidden-import=urllib.request",
        "--hidden-import=urllib.parse",
        "youtube_downloader.py",
    ]

    # QuickJS 런타임 번들 추가
    qjs_bin = Path("bin/qjs.exe" if SYSTEM_NAME == "Windows" else "bin/qjs")
    if qjs_bin.exists():
        cmd.insert(6, f"--add-binary={qjs_bin}{data_separator}bin")

    # 원파일 모드 (Windows/Linux: --onefile, macOS: --onedir 번들)
    if SYSTEM_NAME == "Darwin":
        cmd.insert(4, "--onedir")
    else:
        cmd.insert(4, "--onefile")

    # 불필요한 Qt 서브모듈 제외
    for mod in EXCLUDED_QT_MODULES:
        cmd.insert(-1, f"--exclude-module={mod}")

    # 아이콘 설정
    if SYSTEM_NAME == "Windows" and Path("icon.ico").exists():
        cmd.insert(-1, "--icon=icon.ico")
    elif SYSTEM_NAME == "Darwin" and Path("icon.icns").exists():
        cmd.insert(-1, "--icon=icon.icns")

    # Windows 환경에서 시스템 기본 DLL 우선 탐색 환경 설정
    build_env = os.environ.copy()
    if SYSTEM_NAME == "Windows":
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        build_env["PATH"] = os.pathsep.join([
            str(Path(system_root) / "System32"),
            system_root,
            build_env.get("PATH", ""),
        ])

    print("실행 명령어:", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True, env=build_env)
        print("[SUCCESS] PyInstaller 빌드 성공!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] 빌드 실패: {e}")
        return False


def get_build_artifact():
    """빌드 결과물 경로 반환"""
    if SYSTEM_NAME == "Windows":
        artifact = Path("dist") / f"{APP_NAME}.exe"
    elif SYSTEM_NAME == "Darwin":
        app_bundle = Path("dist") / f"{APP_NAME}.app"
        artifact = app_bundle if app_bundle.exists() else Path("dist") / APP_NAME
    else:
        artifact = Path("dist") / APP_NAME
    return artifact if artifact.exists() else None


def copy_to_release():
    """빌드된 결과물을 release 폴더에 복사"""
    artifact = get_build_artifact()
    if not artifact:
        print("[ERROR] 빌드 산출물을 찾을 수 없습니다.")
        return None

    release_dir = Path("release")
    release_dir.mkdir(exist_ok=True)

    target_name = f"{APP_NAME}.exe" if SYSTEM_NAME == "Windows" else artifact.name
    release_artifact = release_dir / target_name

    if release_artifact.exists():
        print(f"[INFO] 기존 릴리스 파일 교체: {release_artifact}")
        if release_artifact.is_dir():
            shutil.rmtree(release_artifact)
        else:
            release_artifact.unlink()

    print(f"[INFO] release 디렉토리로 복사 중: {release_artifact}")
    if artifact.is_dir():
        shutil.copytree(str(artifact), str(release_artifact), symlinks=True)
    else:
        shutil.copy2(str(artifact), str(release_artifact))

    size_mb = release_artifact.stat().st_size / (1024 * 1024)
    print(f"[SUCCESS] 실행 파일 복사 완료 (크기: {size_mb:.1f} MB)")
    return release_artifact


def create_zip_package(release_artifact):
    """배포용 ZIP 압축 파일 생성"""
    version = datetime.now().strftime("%Y.%m.%d")
    platform_label = {
        "Windows": "Windows",
        "Darwin": "macOS",
        "Linux": "Linux",
    }.get(SYSTEM_NAME, SYSTEM_NAME or "Unknown")

    zip_path = Path("release") / f"{APP_NAME}_v{version}_{platform_label}.zip"
    print(f"[INFO] 배포용 ZIP 압축 생성 중: {zip_path}")

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            if release_artifact.is_dir():
                for p in release_artifact.rglob("*"):
                    zipf.write(p, p.relative_to(release_artifact.parent))
            else:
                zipf.write(release_artifact, release_artifact.name)

            for extra in ["README.md", "run.bat", "requirements.txt"]:
                ep = Path(extra)
                if ep.exists():
                    zipf.write(ep, ep.name)

            qjs_path = Path("bin/qjs.exe" if SYSTEM_NAME == "Windows" else "bin/qjs")
            if qjs_path.exists():
                zipf.write(qjs_path, f"bin/{qjs_path.name}")

        zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"[SUCCESS] 배포 ZIP 패키지 생성 완료: {zip_path} ({zip_size_mb:.1f} MB)")
        return zip_path
    except Exception as e:
        print(f"[ERROR] ZIP 패키지 생성 실패: {e}")
        return None


def main():
    os.chdir(Path(__file__).resolve().parent)
    clean_build_dirs()

    if not build_executable():
        clean_build_dirs()
        return False

    artifact = copy_to_release()
    if not artifact:
        clean_build_dirs()
        return False

    zip_pkg = create_zip_package(artifact)
    clean_build_dirs()

    print("=" * 60)
    print("모든 빌드 프로세스가 정상적으로 완료되었습니다.")
    print(f"- 실행 파일: {artifact}")
    if zip_pkg:
        print(f"- 배포 압축: {zip_pkg}")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

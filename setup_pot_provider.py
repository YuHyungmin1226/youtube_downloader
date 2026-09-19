#!/usr/bin/env python3
"""
PO Token 제공 서버(bgutil-ytdlp-pot-provider) 준비 스크립트.

YouTube가 요구하는 PO Token을 로컬에서 자동으로 발급해주는 서버를
pot_provider/ 디렉터리에 준비한다. 용량이 크기 때문에(약 190MB) 저장소에는
커밋하지 않고, 빌드 전에 이 스크립트를 한 번 실행해서 생성한다.

요구 사항: git, Node.js(>=22)/npm 이 PATH에 있어야 한다 (실행 자체에만 필요하며,
결과물에는 Node.js 실행 파일이 포함되어 최종 사용자는 설치할 필요가 없다).
"""
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import requests

REPO_URL = "https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git"
REPO_TAG = "2.0.0"  # requirements.txt의 bgutil-ytdlp-pot-provider 버전과 맞출 것
NODE_VERSION = "22.11.0"

ROOT = Path(__file__).resolve().parent
POT_DIR = ROOT / "pot_provider"
SERVER_DIR = POT_DIR / "server"
RUNTIME_DIR = POT_DIR / "runtime"


def run(cmd, cwd=None):
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd, check=True, shell=(platform.system() == "Windows"))


def fetch_server_source(tmp_dir):
    clone_dir = tmp_dir / "bgutil-ytdlp-pot-provider"
    run(["git", "clone", "--depth", "1", "--branch", REPO_TAG, REPO_URL, str(clone_dir)])
    return clone_dir / "server"


def build_server(src_server_dir):
    run(["npm", "install", "--omit=dev"], cwd=str(src_server_dir))
    run(["npx", "tsc"], cwd=str(src_server_dir))

    if SERVER_DIR.exists():
        shutil.rmtree(SERVER_DIR)
    SERVER_DIR.mkdir(parents=True)

    shutil.copytree(src_server_dir / "build", SERVER_DIR / "build")
    for map_file in (SERVER_DIR / "build").glob("*.map"):
        map_file.unlink()
    shutil.copytree(src_server_dir / "node_modules", SERVER_DIR / "node_modules")

    license_src = src_server_dir.parent / "LICENSE"
    if license_src.exists():
        shutil.copy2(license_src, POT_DIR / "LICENSE")


def download_node_windows():
    dest_dir = RUNTIME_DIR / "win"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_exe = dest_dir / "node.exe"

    zip_name = f"node-v{NODE_VERSION}-win-x64"
    url = f"https://nodejs.org/dist/v{NODE_VERSION}/{zip_name}.zip"
    tmp_zip = RUNTIME_DIR / f"{zip_name}.zip"

    print(f"Node.js 다운로드 중: {url}")
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()
    with open(tmp_zip, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)

    with zipfile.ZipFile(tmp_zip) as zf:
        member = f"{zip_name}/node.exe"
        with zf.open(member) as src, open(dest_exe, "wb") as dst:
            shutil.copyfileobj(src, dst)

    tmp_zip.unlink()


def main():
    if platform.system() != "Windows":
        print(
            "현재 Node.js 자동 다운로드는 Windows만 지원합니다. "
            "macOS/Linux는 pot_provider/runtime/<os>/에 해당 OS용 "
            "Node.js 실행 파일을 직접 받아 배치해주세요."
        )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        print("bgutil-ytdlp-pot-provider 서버 소스 가져오는 중...")
        src_server_dir = fetch_server_source(tmp_path)
        print("서버 빌드 중 (npm install --omit=dev, tsc)...")
        build_server(src_server_dir)

    if platform.system() == "Windows":
        print("Node.js 런타임 다운로드 중...")
        download_node_windows()

    print("완료! pot_provider/ 디렉터리가 준비되었습니다.")
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)

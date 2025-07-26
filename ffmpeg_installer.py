import os
import platform
import sys
import zipfile
import tarfile
import requests
import subprocess
import shutil
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
import threading

class FFmpegInstaller:
    def __init__(self, status_callback=None, progress_callback=None):
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.system = platform.system()
        self.machine = platform.machine()
        self.ffmpeg_path = None
        
    def get_ffmpeg_url(self):
        """OS별 FFmpeg 다운로드 URL 반환"""
        base_url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest"
        
        if self.system == "Windows":
            if "64" in self.machine or "AMD64" in self.machine:
                return f"{base_url}/ffmpeg-master-latest-win64-gpl.zip"
            else:
                return f"{base_url}/ffmpeg-master-latest-win32-gpl.zip"
        
        elif self.system == "Darwin":  # macOS
            if "arm" in self.machine.lower():
                return f"{base_url}/ffmpeg-master-latest-macos64-gpl.zip"
            else:
                return f"{base_url}/ffmpeg-master-latest-macos64-gpl.zip"
        
        elif self.system == "Linux":
            if "64" in self.machine or "x86_64" in self.machine:
                return f"{base_url}/ffmpeg-master-latest-linux64-gpl.tar.xz"
            else:
                return f"{base_url}/ffmpeg-master-latest-linux32-gpl.tar.xz"
        
        else:
            raise ValueError(f"지원하지 않는 운영체제: {self.system}")
    
    def get_install_path(self):
        """FFmpeg 설치 경로 반환"""
        if self.system == "Windows":
            return Path.home() / "ffmpeg"
        else:
            return Path.home() / ".local" / "ffmpeg"
    
    def download_file(self, url, filepath):
        """파일 다운로드"""
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0 and self.progress_callback:
                            progress = (downloaded / total_size) * 100
                            self.progress_callback(progress)
            
            return True
        except Exception as e:
            if self.status_callback:
                self.status_callback(f"다운로드 오류: {e}")
            return False
    
    def extract_archive(self, archive_path, extract_path):
        """압축 파일 해제"""
        try:
            if archive_path.suffix == '.zip':
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_path)
            elif archive_path.suffix in ['.tar.xz', '.tar.gz']:
                with tarfile.open(archive_path, 'r:*') as tar_ref:
                    tar_ref.extractall(extract_path)
            return True
        except Exception as e:
            if self.status_callback:
                self.status_callback(f"압축 해제 오류: {e}")
            return False
    
    def find_ffmpeg_binary(self, extract_path):
        """압축 해제된 폴더에서 ffmpeg 실행 파일 찾기"""
        for root, dirs, files in os.walk(extract_path):
            for file in files:
                if file == 'ffmpeg' or file == 'ffmpeg.exe':
                    return Path(root) / file
        return None
    
    def add_to_path(self, ffmpeg_path):
        """환경변수 PATH에 FFmpeg 경로 추가"""
        try:
            if self.system == "Windows":
                # Windows 환경변수 설정
                bin_path = ffmpeg_path.parent
                current_path = os.environ.get('PATH', '')
                if str(bin_path) not in current_path:
                    new_path = f"{bin_path};{current_path}"
                    subprocess.run(['setx', 'PATH', new_path], check=True)
            else:
                # Unix 계열은 .bashrc 또는 .zshrc에 추가
                shell_rc = Path.home() / ('.zshrc' if os.path.exists(Path.home() / '.zshrc') else '.bashrc')
                export_line = f'\nexport PATH="{ffmpeg_path.parent}:$PATH"\n'
                
                if not shell_rc.exists() or export_line not in shell_rc.read_text():
                    with open(shell_rc, 'a') as f:
                        f.write(export_line)
            
            return True
        except Exception as e:
            if self.status_callback:
                self.status_callback(f"환경변수 설정 오류: {e}")
            return False
    
    def install_ffmpeg(self):
        """FFmpeg 설치 메인 함수"""
        try:
            # 1. URL 가져오기
            if self.status_callback:
                self.status_callback("FFmpeg 다운로드 URL을 확인하는 중...")
            url = self.get_ffmpeg_url()
            
            # 2. 설치 경로 설정
            install_path = self.get_install_path()
            install_path.mkdir(parents=True, exist_ok=True)
            
            # 3. 임시 파일 경로
            archive_name = url.split('/')[-1]
            archive_path = install_path / archive_name
            
            # 4. 다운로드
            if self.status_callback:
                self.status_callback(f"FFmpeg 다운로드 중... ({archive_name})")
            if not self.download_file(url, archive_path):
                return False
            
            # 5. 압축 해제
            if self.status_callback:
                self.status_callback("압축 파일 해제 중...")
            if not self.extract_archive(archive_path, install_path):
                return False
            
            # 6. ffmpeg 실행 파일 찾기
            ffmpeg_binary = self.find_ffmpeg_binary(install_path)
            if not ffmpeg_binary:
                if self.status_callback:
                    self.status_callback("FFmpeg 실행 파일을 찾을 수 없습니다.")
                return False
            
            # 7. 환경변수에 추가
            if self.status_callback:
                self.status_callback("환경변수 설정 중...")
            if not self.add_to_path(ffmpeg_binary):
                return False
            
            # 8. 임시 파일 정리
            try:
                archive_path.unlink()
            except:
                pass
            
            self.ffmpeg_path = str(ffmpeg_binary)
            
            if self.status_callback:
                self.status_callback("FFmpeg 설치가 완료되었습니다!")
                self.status_callback(f"설치 경로: {self.ffmpeg_path}")
            
            return True
            
        except Exception as e:
            if self.status_callback:
                self.status_callback(f"설치 중 오류 발생: {e}")
            return False
    
    def check_ffmpeg(self):
        """FFmpeg 설치 여부 확인"""
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            return ffmpeg_path
        return None

class FFmpegInstallerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("FFmpeg 자동 설치 도구")
        self.root.geometry("500x300")
        self.root.resizable(False, False)
        self.create_widgets()
    
    def create_widgets(self):
        # 제목
        title_label = tk.Label(self.root, text="FFmpeg 자동 설치 도구", font=('Arial', 16, 'bold'))
        title_label.pack(pady=20)
        
        # 시스템 정보
        system_info = f"운영체제: {platform.system()} {platform.release()}"
        arch_info = f"아키텍처: {platform.machine()}"
        
        tk.Label(self.root, text=system_info).pack()
        tk.Label(self.root, text=arch_info).pack(pady=(0, 20))
        
        # 진행바
        self.progress = ttk.Progressbar(self.root, orient=tk.HORIZONTAL, length=400, mode='determinate')
        self.progress.pack(pady=10)
        
        # 상태 텍스트
        self.status_text = tk.Text(self.root, height=8, width=60, wrap=tk.WORD)
        self.status_text.pack(pady=10, padx=20)
        self.status_text.insert(tk.END, "FFmpeg 설치 상태를 확인하는 중...\n")
        
        # 버튼들
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)
        
        self.check_btn = tk.Button(button_frame, text="FFmpeg 확인", command=self.check_ffmpeg)
        self.check_btn.pack(side=tk.LEFT, padx=5)
        
        self.install_btn = tk.Button(button_frame, text="FFmpeg 설치", command=self.install_ffmpeg)
        self.install_btn.pack(side=tk.LEFT, padx=5)
        
        self.close_btn = tk.Button(button_frame, text="닫기", command=self.root.destroy)
        self.close_btn.pack(side=tk.LEFT, padx=5)
        
        # 초기 상태 확인
        self.check_ffmpeg()
    
    def set_status(self, message):
        self.status_text.insert(tk.END, message + '\n')
        self.status_text.see(tk.END)
        self.root.update()
    
    def set_progress(self, value):
        self.progress['value'] = value
        self.root.update_idletasks()
    
    def check_ffmpeg(self):
        installer = FFmpegInstaller()
        ffmpeg_path = installer.check_ffmpeg()
        
        if ffmpeg_path:
            self.set_status(f"✓ FFmpeg가 이미 설치되어 있습니다: {ffmpeg_path}")
            self.install_btn.config(state=tk.DISABLED)
        else:
            self.set_status("✗ FFmpeg가 설치되어 있지 않습니다.")
            self.install_btn.config(state=tk.NORMAL)
    
    def install_ffmpeg(self):
        self.install_btn.config(state=tk.DISABLED)
        self.check_btn.config(state=tk.DISABLED)
        self.progress['value'] = 0
        
        def install_thread():
            try:
                installer = FFmpegInstaller(
                    status_callback=self.thread_safe_status,
                    progress_callback=self.thread_safe_progress
                )
                success = installer.install_ffmpeg()
                
                if success:
                    self.root.after(0, lambda: messagebox.showinfo("성공", "FFmpeg 설치가 완료되었습니다!\n프로그램을 재시작하면 사용할 수 있습니다."))
                else:
                    self.root.after(0, lambda: messagebox.showerror("오류", "FFmpeg 설치에 실패했습니다."))
                
            finally:
                self.root.after(0, lambda: self.install_btn.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.check_btn.config(state=tk.NORMAL))
        
        threading.Thread(target=install_thread, daemon=True).start()
    
    def thread_safe_status(self, message):
        self.root.after(0, self.set_status, message)
    
    def thread_safe_progress(self, value):
        self.root.after(0, self.set_progress, value)

def main():
    root = tk.Tk()
    app = FFmpegInstallerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main() 
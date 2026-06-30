import os
import threading
import urllib.request
import json

class ModelManager:
    def __init__(self):
        self.local_app_data = os.getenv('LOCALAPPDATA', os.path.expanduser('~'))
        self.model_dir = os.path.join(self.local_app_data, 'BerestaAI')
        self.config_path = os.path.join(self.model_dir, 'config.json')
        os.makedirs(self.model_dir, exist_ok=True)
        
        # Example models
        self.models = {
            "accurate_9b": {"repo_id": "unsloth/Qwen3.5-9B-GGUF", "filename": "Qwen3.5-9B-Q4_K_M.gguf"}
        }
        self.gemini_models = {}

    def get_model_path(self, model_type):
        return os.path.join(self.model_dir, "accurate_9b.gguf")

    def check_model_exists(self, model_type):
        return os.path.exists(self.get_model_path("accurate_9b"))

    def get_active_model_type(self):
        return "accurate_9b"

    def set_active_model_type(self, model_type):
        config = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
            except:
                pass
        config["active_model"] = "accurate_9b"
        try:
            with open(self.config_path, 'w') as f:
                json.dump(config, f)
        except:
            pass

    def get_gemini_config(self):
        return {"api_key": "", "model": ""}

    def set_gemini_config(self, api_key, model):
        pass

    def get_ollama_config(self):
        config = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
            except:
                pass
        return {
            "model": config.get("ollama_model_name", "saiga:4b"),
            "base_url": config.get("ollama_base_url", "http://localhost:11434")
        }

    def set_ollama_config(self, model, base_url):
        config = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
            except:
                pass
        config["ollama_model_name"] = model
        config["ollama_base_url"] = base_url
        with open(self.config_path, 'w') as f:
            json.dump(config, f)

    def download_model(self, model_type, progress_callback=None):
        """
        Downloads the model in a separate thread.
        progress_callback should accept a string message.
        """
        if model_type not in self.models:
            raise ValueError("Unknown model type")

        repo_id = self.models[model_type]["repo_id"]
        filename = self.models[model_type]["filename"]

        target_path = self.get_model_path(model_type)

        def download_task():
            if progress_callback:
                progress_callback("Начинаем скачивание...")
            try:
                url = f"https://huggingface.co/{repo_id}/resolve/main/{filename}"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response:
                    total_size = int(response.headers.get('content-length', 0))
                    
                    if progress_callback:
                        progress_callback("Скачивание файлов нейросети: 0%")
                        
                    downloaded = 0
                    temp_path = target_path + '.tmp'
                    
                    with open(temp_path, 'wb') as f:
                        while True:
                            chunk = response.read(1024*1024) # 1MB chunks
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0 and progress_callback:
                                percent = int((downloaded / total_size) * 100)
                                progress_callback(f"Скачивание файлов нейросети: {percent}%")
                                
                # Move to final location
                if os.path.exists(target_path):
                    os.remove(target_path)
                os.rename(temp_path, target_path)
                
                self.set_active_model_type(model_type)
                
                if progress_callback:
                    progress_callback("Скачивание завершено. Модель готова.")
            except Exception as e:
                if progress_callback:
                    progress_callback(f"Ошибка скачивания: {str(e)}")

        download_task()
        return "Done"

    def check_llama_server_exists(self):
        import sys
        bin_dir = os.path.join(self.model_dir, 'bin')
        name = 'llama-server.exe' if sys.platform == 'win32' else 'llama-server'
        server_path = os.path.join(bin_dir, name)
        return os.path.exists(server_path) and (sys.platform == 'win32' or os.access(server_path, os.X_OK))

    def get_llama_server_path(self):
        import sys
        bin_dir = os.path.join(self.model_dir, 'bin')
        name = 'llama-server.exe' if sys.platform == 'win32' else 'llama-server'
        return os.path.join(bin_dir, name)

    def download_llama_server(self, progress_callback=None):
        """
        Downloads llama-server for the current architecture and platform, then extracts it.
        """
        import sys
        import platform
        import tarfile
        import zipfile
        import shutil
        import urllib.request
        
        bin_dir = os.path.join(self.model_dir, 'bin')
        os.makedirs(bin_dir, exist_ok=True)
        server_path = self.get_llama_server_path()
        
        if self.check_llama_server_exists():
            if progress_callback:
                progress_callback("Движок llama-server уже готов.")
            return True
            
        version = "b9771"
        is_win = sys.platform == 'win32'
        
        if is_win:
            filename = f"llama-{version}-bin-win-cpu-x64.zip"
            temp_archive_path = os.path.join(bin_dir, 'llama_server_temp.zip')
        else:
            machine = platform.machine().lower()
            if "arm" in machine or "aarch64" in machine:
                arch = "arm64"
                filename = f"llama-{version}-bin-macos-arm64.tar.gz"
            else:
                arch = "x64"
                filename = f"llama-{version}-bin-macos-x64.tar.gz"
            temp_archive_path = os.path.join(bin_dir, 'llama_server_temp.tar.gz')
            
        url = f"https://github.com/ggml-org/llama.cpp/releases/download/{version}/{filename}"
        
        if progress_callback:
            progress_callback("Скачивание движка llama-server...")
            
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                with open(temp_archive_path, 'wb') as f:
                    while True:
                        chunk = response.read(1024*128)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0 and progress_callback:
                            percent = int((downloaded / total_size) * 100)
                            progress_callback(f"Скачивание движка llama-server: {percent}%")
                            
            if progress_callback:
                progress_callback("Распаковка движка...")
                
            temp_extract_dir = os.path.join(bin_dir, 'extract_temp')
            os.makedirs(temp_extract_dir, exist_ok=True)
            
            if is_win:
                with zipfile.ZipFile(temp_archive_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_extract_dir)
            else:
                with tarfile.open(temp_archive_path, 'r:gz') as tar:
                    tar.extractall(path=temp_extract_dir)
                
            for root, dirs, files in os.walk(temp_extract_dir):
                for file in files:
                    file_src = os.path.join(root, file)
                    file_dst = os.path.join(bin_dir, file)
                    if os.path.exists(file_dst):
                        os.remove(file_dst)
                    shutil.move(file_src, file_dst)
                    
            shutil.rmtree(temp_extract_dir)
                
            # Clean up temp archive
            if os.path.exists(temp_archive_path):
                os.remove(temp_archive_path)
                
            # Remove any subfolders in bin_dir that were left
            for entry in os.listdir(bin_dir):
                entry_path = os.path.join(bin_dir, entry)
                if os.path.isdir(entry_path):
                    shutil.rmtree(entry_path)
                    
            if os.path.exists(server_path):
                if not is_win:
                    # chmod +x для исполняемых файлов
                    os.chmod(server_path, 0o755)
                    # Даем права запуска всем dylib тоже
                    for entry in os.listdir(bin_dir):
                        if entry.endswith('.dylib') or entry == 'llama-server':
                            os.chmod(os.path.join(bin_dir, entry), 0o755)
                    
                    # Remove macOS quarantine
                    try:
                        import subprocess
                        for entry in os.listdir(bin_dir):
                            entry_path = os.path.join(bin_dir, entry)
                            subprocess.run(["xattr", "-d", "com.apple.quarantine", entry_path], stderr=subprocess.DEVNULL)
                    except Exception as ex:
                        print(f"Quarantine removal warning: {ex}")
                
                if progress_callback:
                    progress_callback("Движок llama-server успешно установлен.")
                return True
            else:
                raise FileNotFoundError("Не удалось найти llama-server в скачанном архиве.")
        except Exception as e:
            if os.path.exists(temp_archive_path):
                os.remove(temp_archive_path)
            if progress_callback:
                progress_callback(f"Ошибка установки движка: {str(e)}")
            print(f"Error downloading/extracting llama-server: {e}")
            return False


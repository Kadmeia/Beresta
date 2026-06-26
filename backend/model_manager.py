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
            "fast": {"repo_id": "Vikhrmodels/QVikhr-3-4B-Instruction-GGUF", "filename": "QVikhr-3-4B-Instruction-Q4_K_M.gguf"},
            "accurate": {"repo_id": "RichardErkhov/Defetya_-_qwen-4B-saiga-gguf", "filename": "qwen-4B-saiga.Q4_K_M.gguf"},
            "accurate_9b": {"repo_id": "unsloth/Qwen3.5-9B-GGUF", "filename": "Qwen3.5-9B-Q4_K_M.gguf"}
        }
        
        self.gemini_models = {
            "gemini-2.5-flash": "Google Gemini 2.5 Flash (Рекомендуется)",
            "gemini-2.5-flash-lite": "Google Gemini 2.5 Flash-Lite (Экономичный)",
            "gemini-1.5-flash": "Google Gemini 1.5 Flash (Устаревшая)"
        }

        
        # Migrate old model if it exists
        old_model = os.path.join(self.model_dir, 'model.gguf')
        if os.path.exists(old_model):
            os.rename(old_model, self.get_model_path('fast'))

    def get_model_path(self, model_type):
        if model_type not in self.models:
            model_type = "fast"
        return os.path.join(self.model_dir, f"{model_type}.gguf")

    def check_model_exists(self, model_type):
        return os.path.exists(self.get_model_path(model_type))

    def get_active_model_type(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    active = config.get("active_model", "fast")
                    if active in self.gemini_models:
                        return active
                    if active == "smolagents_local":
                        return active
                    if active in self.models and self.check_model_exists(active):
                        return active
            except:
                pass
        
        for m_type in self.models:
            if self.check_model_exists(m_type):
                self.set_active_model_type(m_type)
                return m_type
        return "fast"
        
    def set_active_model_type(self, model_type):
        if model_type in self.models or model_type in self.gemini_models or model_type == "smolagents_local":
            config = {}
            if os.path.exists(self.config_path):
                try:
                    with open(self.config_path, 'r') as f:
                        config = json.load(f)
                except:
                    pass
            config["active_model"] = model_type
            with open(self.config_path, 'w') as f:
                json.dump(config, f)

    def get_gemini_config(self):
        config = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
            except:
                pass
        return {
            "api_key": config.get("gemini_api_key", ""),
            "model": config.get("selected_gemini_model", "gemini-2.5-flash")
        }

    def set_gemini_config(self, api_key, model):
        config = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
            except:
                pass
        config["gemini_api_key"] = api_key
        if model in self.gemini_models:
            config["selected_gemini_model"] = model
        with open(self.config_path, 'w') as f:
            json.dump(config, f)

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
        bin_dir = os.path.join(self.model_dir, 'bin')
        server_path = os.path.join(bin_dir, 'llama-server')
        return os.path.exists(server_path) and os.access(server_path, os.X_OK)

    def get_llama_server_path(self):
        bin_dir = os.path.join(self.model_dir, 'bin')
        return os.path.join(bin_dir, 'llama-server')

    def download_llama_server(self, progress_callback=None):
        """
        Downloads llama-server for the current architecture and extracts it.
        """
        import platform
        import tarfile
        import shutil
        import urllib.request
        
        bin_dir = os.path.join(self.model_dir, 'bin')
        os.makedirs(bin_dir, exist_ok=True)
        server_path = self.get_llama_server_path()
        
        if self.check_llama_server_exists():
            if progress_callback:
                progress_callback("Движок llama-server уже готов.")
            return True
            
        machine = platform.machine().lower()
        # GitHub release URLs for llama.cpp b9771
        version = "b9771"
        if "arm" in machine or "aarch64" in machine:
            arch = "arm64"
            filename = f"llama-{version}-bin-macos-arm64.tar.gz"
        else:
            arch = "x64"
            filename = f"llama-{version}-bin-macos-x64.tar.gz"
            
        url = f"https://github.com/ggml-org/llama.cpp/releases/download/{version}/{filename}"
        temp_tar_path = os.path.join(bin_dir, 'llama_server_temp.tar.gz')
        
        if progress_callback:
            progress_callback(f"Скачивание движка llama-server ({arch})...")
            
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                with open(temp_tar_path, 'wb') as f:
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
                
            # Extract tar.gz flatly into bin_dir
            with tarfile.open(temp_tar_path, 'r:gz') as tar:
                temp_extract_dir = os.path.join(bin_dir, 'extract_temp')
                os.makedirs(temp_extract_dir, exist_ok=True)
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
            if os.path.exists(temp_tar_path):
                os.remove(temp_tar_path)
                
            # Remove any subfolders in bin_dir that were left
            for entry in os.listdir(bin_dir):
                entry_path = os.path.join(bin_dir, entry)
                if os.path.isdir(entry_path):
                    shutil.rmtree(entry_path)
                    
            if os.path.exists(server_path):
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
            if os.path.exists(temp_tar_path):
                os.remove(temp_tar_path)
            if progress_callback:
                progress_callback(f"Ошибка установки движка: {str(e)}")
            print(f"Error downloading/extracting llama-server: {e}")
            return False


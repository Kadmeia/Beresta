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
            "accurate": {"repo_id": "RichardErkhov/Defetya_-_qwen-4B-saiga-gguf", "filename": "qwen-4B-saiga.Q4_K_M.gguf"}
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
        if model_type in self.models:
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

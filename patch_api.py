import re

with open('backend/api.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Add lock state
code = code.replace("        self.window = None\n", "        self.window = None\n        self.is_processing = False\n")

# Decorator definition
decorator = """
    def _lock(func):
        def wrapper(self, *args, **kwargs):
            if self.is_processing:
                return {"error": "Система уже обрабатывает другой запрос. Дождитесь завершения."} if func.__name__ == "process_files" else [] if func.__name__ == "save_documents" else False
            self.is_processing = True
            try:
                return func(self, *args, **kwargs)
            finally:
                self.is_processing = False
        return wrapper
"""

code = code.replace("    def set_window(self, window):", decorator + "\n    def set_window(self, window):")

# Apply decorator
code = code.replace("    def delete_model(self, model_type):", "    @_lock\n    def delete_model(self, model_type):")
code = code.replace("    def download_model(self, model_type=\"fast\"):", "    @_lock\n    def download_model(self, model_type=\"fast\"):")
code = code.replace("    def process_files(self, file_paths, mode=\"split\"):", "    @_lock\n    def process_files(self, file_paths, mode=\"split\"):")
code = code.replace("    def save_documents(self, preview_data, output_dir):", "    @_lock\n    def save_documents(self, preview_data, output_dir):")

with open('backend/api.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Patch applied.")

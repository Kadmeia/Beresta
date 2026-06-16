import re

with open('backend/api.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_method = """
    def open_file_dialog(self):
        import webview
        if self.window:
            file_types = ('PDF Грамоты (*.pdf)', 'Все файлы (*.*)')
            result = self.window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True, file_types=file_types)
            return result if result else []
        return []
"""

if "def open_file_dialog" not in content:
    content = content.replace("def check_model(self):", new_method.lstrip() + "\n    def check_model(self):")
    with open('backend/api.py', 'w', encoding='utf-8') as f:
        f.write(content)

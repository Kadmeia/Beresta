import warnings
try:
    from urllib3.exceptions import NotOpenSSLWarning
    warnings.filterwarnings("ignore", category=NotOpenSSLWarning)
except ImportError:
    pass

import webview
import os
import sys
import threading
import traceback
import json

# Fix proxy for httpx IPv6 parsing bug (affects huggingface_hub model downloads in Docling)
for k in ["http_proxy", "https_proxy", "no_proxy", "NO_PROXY", "HTTP_PROXY", "HTTPS_PROXY"]:
    if k in os.environ and "::1" in os.environ[k]:
        os.environ[k] = os.environ[k].replace("::1", "127.0.0.1")

from backend.api import Api

def main():
    api = Api()
    
    # Path to frontend directory
    # Depending on PyInstaller --onedir, we might need sys._MEIPASS
    current_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(current_dir, 'frontend', 'index.html')
    
    # Ensure frontend directory exists for dev
    os.makedirs(os.path.join(current_dir, 'frontend'), exist_ok=True)
    
    # Create an empty placeholder if index.html doesn't exist
    if not os.path.exists(html_path):
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write("<h1>Beresta.AI Placeholder</h1><p>Please provide your HTML file here.</p>")
            
    # Create window
    window = webview.create_window(
        title='Береста.ИИ v1.0', 
        url=f'file://{html_path}', 
        js_api=api,
        width=650,
        height=920,
        resizable=True,
        background_color='#F5F5DC' # Береста color fallback
    )
    
    api.set_window(window)
    
    # Start webview loop with persistent storage
    local_app_data = os.getenv('LOCALAPPDATA', os.path.expanduser('~'))
    model_dir = os.path.join(local_app_data, 'BerestaAI')
    storage_path = os.path.join(model_dir, 'web_storage')
    os.makedirs(storage_path, exist_ok=True)
    
    webview.start(private_mode=False, storage_path=storage_path)

if __name__ == '__main__':
    main()

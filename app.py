import webview
import os
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
        title='Береста.ИИ', 
        url=f'file://{html_path}', 
        js_api=api,
        width=650,
        height=920,
        resizable=True,
        background_color='#F5F5DC' # Береста color fallback
    )
    
    api.set_window(window)
    
    # Start webview loop
    webview.start()

if __name__ == '__main__':
    main()

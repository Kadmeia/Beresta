import re

with open('frontend/styles_old.css', 'r', encoding='utf-8') as f:
    css = f.read()

# Replace variables
css = css.replace("""        :root {
            /* Светлая тема (Береста и Хвоя) */
            --bg-color: #fcfaf6;
            /* Неотбеленный лен / береста */
            --container-bg: #ffffff;
            --text-main: #1c1917;
            /* Цвет чернил */
            --text-muted: #78716c;
            --accent: #2d6a4f;
            /* Хвойный зеленый */
            --accent-hover: #1b4332;
            --border-color: #e7e5e4;
            --drop-bg: #f5f5f4;
            --drop-border: #d6d3d1;
            --toggle-bg: #e7e5e4;
            --theme-switch-bg: #f5f5f4;
            --theme-switch-active: #ffffff;
            --input-bg: #fafaf9;
            --shadow: 0 10px 30px -5px rgba(45, 106, 79, 0.08);
            --transition: all 0.3s ease;
        }""", """        :root {
            /* Premium Light Theme */
            --bg-color: transparent;
            --container-bg: rgba(255, 255, 255, 0.65);
            --container-border: rgba(255, 255, 255, 0.5);
            --text-main: #0f172a;
            --text-muted: #64748b;
            --accent: #10b981;
            --accent-hover: #059669;
            --border-color: rgba(255, 255, 255, 0.4);
            --drop-bg: rgba(255, 255, 255, 0.5);
            --drop-border: #cbd5e1;
            --toggle-bg: rgba(255, 255, 255, 0.7);
            --theme-switch-bg: rgba(255, 255, 255, 0.6);
            --theme-switch-active: #ffffff;
            --input-bg: rgba(255, 255, 255, 0.8);
            --shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.1);
            --transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            --glass-blur: blur(20px);
        }""")

css = css.replace("""        [data-theme="dark"] {
            /* Темная тема (Приглушенный светло-оливковый) */
            --bg-color: #2a2d24;
            /* Приглушенный оливковый фон */
            --container-bg: #33382d;
            --text-main: #ffffff;
            /* Более яркий белый для текста */
            --text-muted: #e7e5e4;
            /* Более светлый серый для неактивных элементов */
            --accent: #f59e0b;
            /* Янтарный / свет лучины */
            --accent-hover: #d97706;
            --border-color: #4d5445;
            --drop-bg: #2e3329;
            --drop-border: #4d5445;
            --toggle-bg: #4d5445;
            --theme-switch-bg: #2a2d24;
            --theme-switch-active: #4d5445;
            --input-bg: #2a2d24;
            --shadow: 0 10px 30px -5px rgba(0, 0, 0, 0.6);
        }""", """        [data-theme="dark"] {
            /* Premium Dark Theme */
            --bg-color: transparent;
            --container-bg: rgba(15, 23, 42, 0.65);
            --container-border: rgba(255, 255, 255, 0.1);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent: #38bdf8;
            --accent-hover: #0284c7;
            --border-color: rgba(255, 255, 255, 0.1);
            --drop-bg: rgba(30, 41, 59, 0.5);
            --drop-border: rgba(255, 255, 255, 0.2);
            --toggle-bg: rgba(30, 41, 59, 0.7);
            --theme-switch-bg: rgba(15, 23, 42, 0.6);
            --theme-switch-active: rgba(51, 65, 85, 0.9);
            --input-bg: rgba(15, 23, 42, 0.8);
            --shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.5);
            --glass-blur: blur(20px);
        }""")

css = css.replace("font-family: 'Segoe UI', system-ui, sans-serif;", "font-family: 'Inter', system-ui, sans-serif;")

css = css.replace("""        body {
            background-color: var(--bg-color);""", """        @keyframes gradientBG {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        
        body {
            background: linear-gradient(-45deg, #e0f2fe, #dcfce7, #fef9c3, #fce7f3);
            background-size: 400% 400%;
            animation: gradientBG 15s ease infinite;""")

css = css.replace("""        .app-container {
            background-color: var(--container-bg);""", """        [data-theme="dark"] body {
            background: linear-gradient(-45deg, #0f172a, #064e3b, #451a03, #4c1d95);
            background-size: 400% 400%;
            animation: gradientBG 15s ease infinite;
        }

        .app-container {
            background: var(--container-bg);
            backdrop-filter: var(--glass-blur);
            -webkit-backdrop-filter: var(--glass-blur);""")

css = css.replace("""        .modal-content {
            background-color: var(--container-bg);""", """        .modal-content {
            background: var(--container-bg);
            backdrop-filter: var(--glass-blur);
            -webkit-backdrop-filter: var(--glass-blur);
            border: 1px solid var(--container-border);""")

# Dropzone glow
css = css.replace("""        .drop-zone.dragover {
            background-color: var(--theme-switch-bg);
            border-color: var(--accent);
        }""", """        .drop-zone.dragover {
            background-color: var(--theme-switch-bg);
            border-color: var(--accent);
            box-shadow: 0 0 20px var(--accent);
            transform: scale(1.02);
        }""")

# Fade in animations for items
css += """
        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(15px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .preview-item {
            animation: fadeInUp 0.4s ease forwards;
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
            transition: var(--transition);
        }
        
        .preview-item:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow);
            border-color: var(--accent);
        }
        
        .btn-primary:hover, .btn-secondary:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }
"""

# Strip out <style> tags if they exist
css = css.replace("<style>", "").replace("</style>", "").strip()

with open('frontend/styles.css', 'w', encoding='utf-8') as f:
    f.write(css)

print("styles.css updated")

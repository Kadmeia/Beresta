import PyInstaller.__main__
import os

# СТРОГО БЕЗ сжатия UPX (во избежание ложных срабатываний Windows Defender)
PyInstaller.__main__.run([
    'app.py',
    '--name=BerestaAI',
    '--onedir',          # Режим директории
    '--windowed',        # Без консоли
    '--noconfirm',       # Перезаписывать старые сборки
    '--noupx',           # Отключить UPX
    '--add-data=frontend:frontend', # Включить HTML файлы
])

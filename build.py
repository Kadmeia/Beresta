import PyInstaller.__main__
import os

# Устанавливаем минимальную поддерживаемую версию macOS (13.0 Ventura)
os.environ['MACOSX_DEPLOYMENT_TARGET'] = '13.0'

# Путь к иконке
icon_path = os.path.join('assets', 'beresta.icns')

args = [
    'app.py',
    '--name=BerestaAI',
    '--onedir',          # Режим директории
    '--windowed',        # Без консоли
    '--noconfirm',       # Перезаписывать старые сборки
    '--noupx',           # Отключить UPX для стабильности
    '--add-data=frontend:frontend', # Включить HTML-файлы
    
    # Исключаем тяжелые библиотеки машинного обучения, чтобы они не попали в сборку
    '--exclude-module=torch',
    '--exclude-module=torchvision',
    '--exclude-module=docling',
    '--exclude-module=docling_core',
    '--exclude-module=paddleocr',
    '--exclude-module=paddlepaddle',
    '--exclude-module=paddlex',
    '--exclude-module=llama_cpp',
    '--exclude-module=llama_cpp_python',
    '--exclude-module=transformers',
    '--exclude-module=cv2',
    '--exclude-module=numpy',
    '--exclude-module=matplotlib',
    '--exclude-module=scipy',
    '--exclude-module=scikit-image',
    '--exclude-module=pandas',
    '--exclude-module=playwright',
    '--exclude-module=pytest',
    
    # Исключаем компиляторы и сборочные утилиты во избежание конфликтов
    '--exclude-module=Cython',
    '--exclude-module=cython',
    '--exclude-module=setuptools',
    '--exclude-module=distutils',
    '--exclude-module=pip',
]

if os.path.exists(icon_path):
    args.append(f'--icon={icon_path}')

PyInstaller.__main__.run(args)

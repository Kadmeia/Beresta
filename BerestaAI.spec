# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('frontend', 'frontend')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'torchvision', 'docling', 'docling_core', 'paddleocr', 'paddlepaddle', 'paddlex', 'llama_cpp', 'llama_cpp_python', 'transformers', 'cv2', 'numpy', 'matplotlib', 'scipy', 'scikit-image', 'pandas', 'playwright', 'pytest', 'Cython', 'cython', 'setuptools', 'distutils', 'pip'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BerestaAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/beresta.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='BerestaAI',
)
app = BUNDLE(
    coll,
    name='BerestaAI.app',
    icon='assets/beresta.icns',
    bundle_identifier=None,
)

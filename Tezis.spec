# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['ui_flet\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('data\\state_exam_public_admin_demo.db', 'data'), ('ui_flet\\theme\\fonts\\*.ttf', 'ui_flet\\theme\\fonts')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Tezis',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='C:\\Users\\tutor\\AppData\\Local\\Temp\\eb039bd5-a164-40d4-abf9-7c1dc6f8f092',
    icon=['assets\\icon.ico'],
)

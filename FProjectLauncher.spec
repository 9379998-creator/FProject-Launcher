# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hidden_imports = [
    'app.backend.server',
    'app.backend.dwg_engine',
    'app.backend.excel_engine',
    'app.backend.analytics_parser',
    'app.backend.background_sync',
    'app.backend.db',
    'app.cad.pdf_cad_extractor',
    'app.cad.component_assembler',
    'app.rendering.dispatcher',
    'app.rendering.engine_dwg_pdf',
    'app.rendering.engine_excel',
    'app.rendering.engine_media',
    'app.rendering.engine_word',
    'app.rendering._sheet_shell',
    'app.shared.version_info',
    'app.updater',
    'fitz',
    'pymupdf',
    'ezdxf',
    'numpy',
    'scipy.spatial',
    'scipy.spatial._ckdtree',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'openpyxl',
    'et_xmlfile',
    'pypdf',
    'docx',
    'psutil',
    'webview',
    'clr',
    'clr_loader',
    'bottle',
    'proxy_tools',
    'win32com',
    'win32com.client',
    'pythoncom',
    'pywintypes',
    'win32api',
    'win32con',
    'win32gui',
    'win32process',
    'sqlite3',
    'unittest',
    'tkinter',
    'tkinter.filedialog',
    'runpy',
]
hidden_imports += collect_submodules('ezdxf')
hidden_imports += collect_submodules('webview')

datas = [
    ('app', 'app'),
    ('scripts', 'scripts'),
    ('version.json', '.'),
]
datas += collect_data_files('ezdxf')
datas += collect_data_files('webview')

a = Analysis(
    ['app/flauncher.pyw'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'idlelib', 'turtledemo', 'matplotlib', 'pandas'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FEngineeringLauncher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['app/frontend/assets/flauncher.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FEngineeringLauncher',
)

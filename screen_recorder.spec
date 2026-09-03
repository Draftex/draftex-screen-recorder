# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec – Draftex Screen Recorder (onedir, bez konzoly)
# Build:  pyinstaller --noconfirm --clean screen_recorder.spec

APP_NAME = "DraftexScreenRecorder"

a = Analysis(
    ["screen_recorder.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # nepoužívané Qt moduly – menší balík
        "PyQt6.QtQml", "PyQt6.QtQuick", "PyQt6.QtQuickWidgets", "PyQt6.QtWebEngineCore",
        "PyQt6.QtWebEngineWidgets", "PyQt6.QtMultimedia", "PyQt6.QtMultimediaWidgets",
        "PyQt6.QtBluetooth", "PyQt6.QtNfc", "PyQt6.QtPositioning", "PyQt6.QtSensors",
        "PyQt6.QtSerialPort", "PyQt6.QtSql", "PyQt6.QtTest", "PyQt6.QtXml",
        "PyQt6.QtDesigner", "PyQt6.QtHelp", "PyQt6.QtOpenGL", "PyQt6.QtOpenGLWidgets",
        "PyQt6.QtPdf", "PyQt6.QtPdfWidgets", "PyQt6.QtSvg", "PyQt6.QtSvgWidgets",
        "PyQt6.QtPrintSupport", "PyQt6.QtNetwork", "PyQt6.QtDBus",
        "tkinter", "unittest", "pydoc", "doctest", "xmlrpc",
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                 # UPX zvyšuje falošné poplachy antivírov – radšej nie
    console=False,             # bez konzolového okna
    disable_windowed_traceback=False,
    icon="icon.ico",
    version="version_info.txt",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name=APP_NAME,
)

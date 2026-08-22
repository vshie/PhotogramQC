# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

spec_dir = Path(SPECPATH)
icon_path = spec_dir / "photogramqc.ico"
version_path = spec_dir / "VERSION"
datas = [
    (str(spec_dir / "image_review" / "static"), "image_review/static"),
]
if version_path.is_file():
    datas.append((str(version_path), "."))

a = Analysis(
    [str(spec_dir / "photogramqc.py")],
    pathex=[str(spec_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "image_review",
        "image_review.app",
        "image_review.desktop",
        "image_review.roll_filter",
        "flask",
        "jinja2",
        "werkzeug",
        "werkzeug.serving",
        "PIL",
        "PIL.Image",
        "PIL.JpegImagePlugin",
        "PIL.PngImagePlugin",
        "PIL.TiffImagePlugin",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe_kwargs = dict(
    name="PhotogramQC",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
)
if icon_path.is_file():
    exe_kwargs["icon"] = str(icon_path)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    **exe_kwargs,
)

# macOS: wrap the same onefile binary in an .app. Windows/Linux keep the raw EXE.
if sys.platform == "darwin":
    version = "1.0.0"
    if version_path.is_file():
        version = version_path.read_text(encoding="utf-8").strip() or version
    app = BUNDLE(
        exe,
        name="PhotogramQC.app",
        icon=str(icon_path) if icon_path.is_file() else None,
        bundle_identifier="com.vshie.photogramqc",
        info_plist={
            "CFBundleName": "PhotogramQC",
            "CFBundleDisplayName": "PhotogramQC",
            "CFBundleShortVersionString": version,
            "CFBundleVersion": version,
            "NSHighResolutionCapable": True,
        },
    )

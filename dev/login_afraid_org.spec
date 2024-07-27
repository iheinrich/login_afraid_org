# -*- mode: python ; coding: utf-8 -*-
#
# Pyinstaller spec file for standalone binary.
#
# (c) 2024 Ingo Heinrich
# See LICENSE file for full license.
#

a = Analysis(
    ["../src/login_afraid_org.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

# --- remove modules and libraries we don't use
exclude_binaries = (
    "lib-dynload/termios",
    "lib-dynload/_hashlib",
    "lib-dynload/_contextvars",
    "lib-dynload/_decimal",
    "lib-dynload/resource",
    "lib-dynload/_lzma",
    "lib-dynload/_bz2",
    "lib-dynload/mmap",
    "lib-dynload/_ctypes",
    "lib-dynload/_queue",
    "lib-dynload/_multibytecodec",
    "lib-dynload/_codecs",
    "lib-dynload/_asyncio",
    "lib-dynload/readline",
    "lib-dynload/_json",
    "libz.so",
    "libexpat.so",
    "libcrypto.so",
    "libzstd.so",
    "liblzma.so",
    "libbz2.so",
    "libffi.so",
    "libreadline.so",
    "libtinfo.so",
)
remove_binaries = []
for binary in a.binaries:
    if binary[0].startswith(exclude_binaries):
        remove_binaries.append(binary)
a.binaries = a.binaries - TOC(remove_binaries)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="login_afraid_org",
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

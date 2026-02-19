# -*- mode: python ; coding: utf-8 -*-

from __future__ import annotations

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Streamlit needs its frontend assets (streamlit/static) and has many dynamic imports.
streamlit_datas = collect_data_files("streamlit")
streamlit_hidden = collect_submodules(
    "streamlit",
    on_error="ignore",
)

plotly_datas = collect_data_files("plotly")
plotly_hidden = collect_submodules(
    "plotly",
    on_error="ignore",
)

yfinance_hidden = collect_submodules(
    "yfinance",
    on_error="ignore",
)

hiddenimports = []
for xs in (streamlit_hidden, plotly_hidden, yfinance_hidden):
    hiddenimports.extend(xs)

# Reduce risk of missing packages that are imported dynamically.
# (pandas/numpy typically have their own PyInstaller hooks)

datas = []
datas += streamlit_datas
datas += plotly_datas

# Entry: packaged launcher (starts streamlit + opens browser)

from PyInstaller.building.build_main import Analysis, EXE, PYZ

analysis = Analysis(
    ["../src/etf_dashboard/gui_launcher.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(analysis.pure, analysis.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="etf-dashboard-gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # user approved: hide console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    onefile=True,
)

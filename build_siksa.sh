#!/bin/bash

# Install PyInstaller if not installed
pip install pyinstaller

# Clean previous builds
rm -rf build dist *.spec

# Build command
# --noconfirm: overwrite existing
# --onedir: folder output (better for debugging/assets initially)
# --windowed: no terminal window
# --name "RevolutionarySicksa": User selected name
# --collect-all customtkinter: Required for CTk assets
# --add-data menus.json:. : bundle menu DB
# --icon "SikSa.icns": Custom rounded icon
pyinstaller --noconfirm --onedir --windowed --name "RevolutionarySicksa" --icon "SikSa.icns" --collect-all customtkinter --add-data "menus.json:." main.py

echo "Build Complete! You can find the app in the 'dist/RevolutionarySicksa' folder."

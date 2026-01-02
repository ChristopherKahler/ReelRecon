#!/usr/bin/env python3
"""Build the installer exe"""
import subprocess
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

print("Installing PyInstaller...")
subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller', '-q'])

print("Building installer exe...")
cmd = [
    sys.executable, '-m', 'PyInstaller',
    '--onefile',
    '--windowed',
    '--name', 'ReelRecon-Setup',
    '--clean',
    '--noconfirm',
    'ReelRecon-Installer.pyw'
]

result = subprocess.run(cmd)

if result.returncode == 0:
    print("\nSUCCESS! Installer created: dist/ReelRecon-Setup.exe")
else:
    print("\nBUILD FAILED")

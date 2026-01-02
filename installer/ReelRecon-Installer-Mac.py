#!/usr/bin/env python3
"""
ReelRecon Mac Installer
- Choose install location
- Git clone the repo
- Install dependencies
- Create application launcher

Double-click to run, or: python3 ReelRecon-Installer-Mac.py
"""
import sys
import os
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
import shutil

REPO_URL = "https://github.com/ChristopherKahler/ReelRecon.git"
APP_NAME = "ReelRecon"


def get_applications_path():
    """Get user's Applications folder"""
    return os.path.expanduser("~/Applications")


def get_desktop_path():
    """Get user's Desktop folder"""
    return os.path.expanduser("~/Desktop")


def create_mac_app(install_dir, app_path):
    """Create a macOS .app bundle that launches ReelRecon"""
    app_name = "ReelRecon.app"
    app_full_path = os.path.join(app_path, app_name)

    # Remove existing app if present
    if os.path.exists(app_full_path):
        shutil.rmtree(app_full_path)

    # Create .app bundle structure
    contents_dir = os.path.join(app_full_path, "Contents")
    macos_dir = os.path.join(contents_dir, "MacOS")
    resources_dir = os.path.join(contents_dir, "Resources")

    os.makedirs(macos_dir, exist_ok=True)
    os.makedirs(resources_dir, exist_ok=True)

    # Create Info.plist
    info_plist = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>ReelRecon</string>
    <key>CFBundleIdentifier</key>
    <string>com.reelrecon.app</string>
    <key>CFBundleName</key>
    <string>ReelRecon</string>
    <key>CFBundleDisplayName</key>
    <string>ReelRecon</string>
    <key>CFBundleVersion</key>
    <string>3.0</string>
    <key>CFBundleShortVersionString</key>
    <string>3.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleIconFile</key>
    <string>ReelRecon</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>'''

    with open(os.path.join(contents_dir, "Info.plist"), 'w') as f:
        f.write(info_plist)

    # Create launcher script
    launcher_script = f'''#!/bin/bash
cd "{install_dir}"
/usr/bin/python3 ReelRecon-Mac.py
'''

    launcher_path = os.path.join(macos_dir, "ReelRecon")
    with open(launcher_path, 'w') as f:
        f.write(launcher_script)

    # Make executable
    os.chmod(launcher_path, 0o755)

    # Copy icon if exists (convert PNG to icns if needed)
    icon_src = os.path.join(install_dir, "ReelRecon.png")
    if os.path.exists(icon_src):
        # For now, just copy the PNG - macOS can use it
        # For proper .icns, would need iconutil or pillow
        icon_dest = os.path.join(resources_dir, "ReelRecon.icns")
        try:
            # Try to create .icns using sips (built into macOS)
            iconset_dir = os.path.join(resources_dir, "ReelRecon.iconset")
            os.makedirs(iconset_dir, exist_ok=True)

            # Create iconset with multiple sizes
            sizes = [16, 32, 64, 128, 256, 512]
            for size in sizes:
                subprocess.run([
                    'sips', '-z', str(size), str(size), icon_src,
                    '--out', os.path.join(iconset_dir, f'icon_{size}x{size}.png')
                ], capture_output=True)
                # Also create @2x versions
                size2x = size * 2
                if size2x <= 1024:
                    subprocess.run([
                        'sips', '-z', str(size2x), str(size2x), icon_src,
                        '--out', os.path.join(iconset_dir, f'icon_{size}x{size}@2x.png')
                    ], capture_output=True)

            # Convert iconset to icns
            subprocess.run([
                'iconutil', '-c', 'icns', iconset_dir,
                '-o', icon_dest
            ], capture_output=True)

            # Clean up iconset
            shutil.rmtree(iconset_dir, ignore_errors=True)
        except Exception as e:
            print(f"Icon conversion failed (non-critical): {e}")

    return app_full_path


class InstallerApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("ReelRecon Installer")
        self.root.geometry("500x450")
        self.root.configure(bg='#18181b')
        self.root.resizable(False, False)

        # Center window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - 500) // 2
        y = (self.root.winfo_screenheight() - 450) // 2
        self.root.geometry(f"500x450+{x}+{y}")

        self.install_path = tk.StringVar(value=os.path.expanduser("~/Documents/ReelRecon"))
        self.create_app_var = tk.BooleanVar(value=True)
        self.app_location = tk.StringVar(value="applications")  # "applications" or "desktop"

        self.setup_ui()

    def setup_ui(self):
        # Title
        title = tk.Label(self.root, text="REELRECON", font=('Arial', 24, 'bold'),
                        fg='#10b981', bg='#18181b')
        title.pack(pady=(30, 5))

        subtitle = tk.Label(self.root, text="// MAC INSTALLER", font=('Arial', 10),
                           fg='#71717a', bg='#18181b')
        subtitle.pack()

        # Install location frame
        frame = tk.Frame(self.root, bg='#18181b')
        frame.pack(pady=20, padx=30, fill='x')

        tk.Label(frame, text="Install Location:", font=('Arial', 10),
                fg='#a1a1aa', bg='#18181b').pack(anchor='w')

        path_frame = tk.Frame(frame, bg='#18181b')
        path_frame.pack(fill='x', pady=(5, 0))

        self.path_entry = tk.Entry(path_frame, textvariable=self.install_path,
                                   font=('Arial', 10), bg='#27272a', fg='white',
                                   insertbackground='white', relief='flat')
        self.path_entry.pack(side='left', fill='x', expand=True, ipady=8)

        browse_btn = tk.Button(path_frame, text="Browse", command=self.browse,
                              bg='#3f3f46', fg='white', relief='flat',
                              font=('Arial', 10), padx=15)
        browse_btn.pack(side='right', padx=(10, 0))

        # Options
        options_frame = tk.Frame(self.root, bg='#18181b')
        options_frame.pack(pady=10, padx=30, fill='x')

        tk.Checkbutton(options_frame, text="Create Application Launcher",
                      variable=self.create_app_var, bg='#18181b',
                      fg='#a1a1aa', selectcolor='#27272a', activebackground='#18181b',
                      font=('Arial', 10), command=self.toggle_app_options).pack(anchor='w')

        # App location options
        self.app_options_frame = tk.Frame(options_frame, bg='#18181b')
        self.app_options_frame.pack(fill='x', padx=20, pady=(5, 0))

        tk.Radiobutton(self.app_options_frame, text="Add to Applications folder",
                      variable=self.app_location, value="applications",
                      bg='#18181b', fg='#71717a', selectcolor='#27272a',
                      activebackground='#18181b', font=('Arial', 9)).pack(anchor='w')

        tk.Radiobutton(self.app_options_frame, text="Add to Desktop",
                      variable=self.app_location, value="desktop",
                      bg='#18181b', fg='#71717a', selectcolor='#27272a',
                      activebackground='#18181b', font=('Arial', 9)).pack(anchor='w')

        # Status
        self.status_var = tk.StringVar(value="")
        self.status_label = tk.Label(self.root, textvariable=self.status_var,
                                     font=('Arial', 9), fg='#71717a', bg='#18181b')
        self.status_label.pack(pady=10)

        # Progress
        self.progress_frame = tk.Frame(self.root, bg='#27272a', height=4)
        self.progress_frame.pack(fill='x', padx=30, pady=5)
        self.progress_bar = tk.Frame(self.progress_frame, bg='#10b981', height=4, width=0)
        self.progress_bar.place(x=0, y=0, height=4)

        # Install button
        self.install_btn = tk.Button(self.root, text="Install", command=self.install,
                                     bg='#10b981', fg='white', relief='flat',
                                     font=('Arial', 12, 'bold'), padx=40, pady=10)
        self.install_btn.pack(pady=20)

        # Note
        note = tk.Label(self.root, text="Requires: Git, Python 3.8+",
                       font=('Arial', 9), fg='#52525b', bg='#18181b')
        note.pack()

    def toggle_app_options(self):
        if self.create_app_var.get():
            self.app_options_frame.pack(fill='x', padx=20, pady=(5, 0))
        else:
            self.app_options_frame.pack_forget()

    def browse(self):
        folder = filedialog.askdirectory(title="Select Install Location")
        if folder:
            self.install_path.set(os.path.join(folder, "ReelRecon"))

    def update_status(self, msg, progress=0):
        self.status_var.set(msg)
        self.progress_bar.configure(width=int(440 * progress / 100))
        self.root.update()

    def install(self):
        self.install_btn.configure(state='disabled')
        install_dir = self.install_path.get()

        try:
            # Check for git
            self.update_status("Checking for Git...", 5)
            result = subprocess.run(['git', '--version'], capture_output=True)
            if result.returncode != 0:
                messagebox.showerror("Error",
                    "Git is not installed.\n\n"
                    "Install with: brew install git\n"
                    "Or download from: https://git-scm.com/download/mac")
                self.install_btn.configure(state='normal')
                return

            # Check for Python 3
            self.update_status("Checking for Python 3...", 10)
            result = subprocess.run(['python3', '--version'], capture_output=True, text=True)
            if result.returncode != 0:
                messagebox.showerror("Error",
                    "Python 3 is not installed.\n\n"
                    "Install with: brew install python3\n"
                    "Or download from: https://python.org/downloads")
                self.install_btn.configure(state='normal')
                return

            # Create parent directory
            self.update_status("Creating install directory...", 15)
            parent_dir = os.path.dirname(install_dir)
            if not os.path.exists(parent_dir):
                os.makedirs(parent_dir)

            # Clone repo
            self.update_status("Downloading ReelRecon (this may take a minute)...", 20)
            if os.path.exists(install_dir):
                # Already exists - do git pull instead
                self.update_status("Updating existing installation...", 25)
                result = subprocess.run(['git', 'pull'], cwd=install_dir,
                                       capture_output=True, text=True)
            else:
                result = subprocess.run(['git', 'clone', REPO_URL, install_dir],
                                       capture_output=True, text=True)

            if result.returncode != 0:
                messagebox.showerror("Error", f"Git clone failed:\n{result.stderr}")
                self.install_btn.configure(state='normal')
                return

            # Install dependencies
            self.update_status("Installing dependencies...", 50)
            subprocess.run(['python3', '-m', 'pip', 'install', '--upgrade', 'pip', '-q'],
                          capture_output=True)
            subprocess.run(['python3', '-m', 'pip', 'install',
                          'flask', 'requests', 'pystray', 'Pillow', 'pywebview', '-q'],
                          cwd=install_dir, capture_output=True)

            # Create app bundle
            app_path = None
            if self.create_app_var.get():
                self.update_status("Creating application launcher...", 80)
                if self.app_location.get() == "applications":
                    app_dest = get_applications_path()
                else:
                    app_dest = get_desktop_path()

                os.makedirs(app_dest, exist_ok=True)
                app_path = create_mac_app(install_dir, app_dest)

            self.update_status("Installation complete!", 100)

            # Success message
            msg = f"ReelRecon installed successfully!\n\nLocation: {install_dir}"
            if app_path:
                msg += f"\n\nApplication: {app_path}\n\nYou can drag this to your Dock for easy access."

            messagebox.showinfo("Success", msg)

            # Ask to launch
            if messagebox.askyesno("Launch", "Would you like to launch ReelRecon now?"):
                if app_path and os.path.exists(app_path):
                    subprocess.Popen(['open', app_path])
                else:
                    subprocess.Popen(['python3', 'ReelRecon-Mac.py'], cwd=install_dir)

            self.root.quit()

        except Exception as e:
            messagebox.showerror("Error", f"Installation failed:\n{str(e)}")
            self.install_btn.configure(state='normal')

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    app = InstallerApp()
    app.run()

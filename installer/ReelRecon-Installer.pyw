#!/usr/bin/env python3
"""
ReelRecon Windows Installer
- Choose install location
- Git clone the repo
- Create desktop shortcut with icon
"""
import sys
import os

# PyInstaller protection
if getattr(sys, 'frozen', False):
    from multiprocessing import freeze_support
    freeze_support()

import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
import winreg

REPO_URL = "https://github.com/ChristopherKahler/ReelRecon.git"  # Update this
APP_NAME = "ReelRecon"


def get_desktop_path():
    """Get Windows desktop path"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders")
        desktop = winreg.QueryValueEx(key, "Desktop")[0]
        winreg.CloseKey(key)
        return desktop
    except:
        return os.path.join(os.path.expanduser("~"), "Desktop")


def find_pythonw():
    """Find pythonw.exe path"""
    candidates = [
        r'C:\Python312\pythonw.exe',
        r'C:\Python311\pythonw.exe',
        r'C:\Python310\pythonw.exe',
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    # Try to find in PATH
    result = subprocess.run(['where', 'pythonw.exe'], capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout.strip().split('\n')[0]
    return None


def create_shortcut(install_dir, shortcut_path):
    """Create Windows shortcut pointing to pythonw.exe + launcher.pyw (pinnable to taskbar)"""
    pythonw = find_pythonw()
    if not pythonw:
        # Fallback to bat file approach
        target = os.path.join(install_dir, "ReelRecon.bat")
        working_dir = install_dir
        icon_path = os.path.join(install_dir, "ReelRecon.ico")
        args = ""
    else:
        # Native approach - pythonw.exe with launcher.pyw
        target = pythonw
        working_dir = install_dir
        icon_path = os.path.join(install_dir, "ReelRecon.ico")
        args = "launcher.pyw"

    ps_script = f'''
$WScriptShell = New-Object -ComObject WScript.Shell
$Shortcut = $WScriptShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{target}"
$Shortcut.Arguments = "{args}"
$Shortcut.WorkingDirectory = "{working_dir}"
$Shortcut.Description = "ReelRecon - Instagram Reel Research Tool"
'''
    if icon_path and os.path.exists(icon_path):
        ps_script += f'$Shortcut.IconLocation = "{icon_path},0"\n'
    ps_script += '$Shortcut.Save()'

    result = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', ps_script],
                           capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Shortcut error: {result.stderr}")
    return result.returncode == 0


class InstallerApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("ReelRecon Installer")
        self.root.geometry("500x400")
        self.root.configure(bg='#18181b')
        self.root.resizable(False, False)

        # Center window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - 500) // 2
        y = (self.root.winfo_screenheight() - 400) // 2
        self.root.geometry(f"500x400+{x}+{y}")

        self.install_path = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Documents", "ReelRecon"))
        self.create_shortcut_var = tk.BooleanVar(value=True)

        self.setup_ui()

    def setup_ui(self):
        # Title
        title = tk.Label(self.root, text="REELRECON", font=('Arial', 24, 'bold'),
                        fg='#10b981', bg='#18181b')
        title.pack(pady=(30, 5))

        subtitle = tk.Label(self.root, text="// INSTALLER", font=('Arial', 10),
                           fg='#71717a', bg='#18181b')
        subtitle.pack()

        # Install location frame
        frame = tk.Frame(self.root, bg='#18181b')
        frame.pack(pady=30, padx=30, fill='x')

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

        tk.Checkbutton(options_frame, text="Create Desktop Shortcut",
                      variable=self.create_shortcut_var, bg='#18181b',
                      fg='#a1a1aa', selectcolor='#27272a', activebackground='#18181b',
                      font=('Arial', 10)).pack(anchor='w')

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
                messagebox.showerror("Error", "Git is not installed. Please install Git first.\nhttps://git-scm.com/download/win")
                self.install_btn.configure(state='normal')
                return

            # Check for Python
            self.update_status("Checking for Python...", 10)
            python_exe = r'C:\Python312\python.exe'
            if not os.path.exists(python_exe):
                # Try to find Python
                result = subprocess.run(['where', 'python'], capture_output=True, text=True)
                if result.returncode == 0:
                    python_exe = result.stdout.strip().split('\n')[0]
                else:
                    messagebox.showerror("Error", "Python not found. Please install Python 3.12.\nhttps://python.org/downloads")
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
                result = subprocess.run(['git', 'pull'], cwd=install_dir, capture_output=True, text=True)
            else:
                result = subprocess.run(['git', 'clone', REPO_URL, install_dir],
                                       capture_output=True, text=True)

            if result.returncode != 0:
                messagebox.showerror("Error", f"Git clone failed:\n{result.stderr}")
                self.install_btn.configure(state='normal')
                return

            self.update_status("Installing dependencies...", 60)
            subprocess.run([python_exe, '-m', 'pip', 'install', 'flask', 'requests',
                          'pystray', 'Pillow', 'pywebview', '-q'], cwd=install_dir, capture_output=True)

            # Create desktop shortcut
            if self.create_shortcut_var.get():
                self.update_status("Creating desktop shortcut...", 80)
                desktop = get_desktop_path()
                shortcut_path = os.path.join(desktop, "ReelRecon.lnk")
                create_shortcut(install_dir, shortcut_path)

            self.update_status("Installation complete!", 100)
            messagebox.showinfo("Success",
                              f"ReelRecon installed successfully!\n\n"
                              f"Location: {install_dir}\n\n"
                              f"Double-click 'ReelRecon' on your desktop to start.")

            # Ask to launch
            if messagebox.askyesno("Launch", "Would you like to launch ReelRecon now?"):
                pythonw = find_pythonw()
                if pythonw:
                    subprocess.Popen([pythonw, 'launcher.pyw'], cwd=install_dir)
                else:
                    bat_path = os.path.join(install_dir, "ReelRecon.bat")
                    subprocess.Popen(['cmd', '/c', bat_path], cwd=install_dir)

            self.root.quit()

        except Exception as e:
            messagebox.showerror("Error", f"Installation failed:\n{str(e)}")
            self.install_btn.configure(state='normal')

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    app = InstallerApp()
    app.run()

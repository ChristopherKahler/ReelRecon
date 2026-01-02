#!/usr/bin/env python3
"""
ReelRecon Desktop Launcher
- Splash screen during startup
- System tray icon with menu
- Cross-platform (Windows/Mac)

Double-click to run, or: python launcher.pyw
"""
import sys
import os

import time

# CRITICAL: Prevent infinite spawn when bundled with PyInstaller
if getattr(sys, 'frozen', False):
    # Running as compiled exe
    from multiprocessing import freeze_support
    freeze_support()

    # Prevent re-entry - check if we're already running
    import tempfile
    lock_file = os.path.join(tempfile.gettempdir(), 'reelrecon_launcher.lock')
    if os.path.exists(lock_file):
        # Check if lock is stale (older than 60 seconds)
        try:
            if time.time() - os.path.getmtime(lock_file) < 60:
                sys.exit(0)  # Already running, exit silently
        except:
            pass
    # Create lock file
    try:
        with open(lock_file, 'w') as f:
            f.write(str(os.getpid()))
    except:
        pass

import threading
import webbrowser
import subprocess
import shutil

# Change to script directory (or exe directory if frozen)
if getattr(sys, 'frozen', False):
    SCRIPT_DIR = os.path.dirname(sys.executable)
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

# Platform detection
IS_WINDOWS = sys.platform == 'win32'
IS_MAC = sys.platform == 'darwin'

# Server config
PORT = 5000 if IS_WINDOWS else 5001
SERVER_URL = f"http://localhost:{PORT}/workspace"

# Global state
server_process = None
tray_icon = None


def install_dependencies():
    """Install required packages for launcher"""
    packages = ['pystray', 'Pillow', 'pywebview']
    for pkg in packages:
        try:
            __import__(pkg.lower().replace('-', '_').split('[')[0])
        except ImportError:
            subprocess.run([sys.executable, '-m', 'pip', 'install', pkg, '-q'],
                         capture_output=True)


def create_icon_image():
    """Create a simple icon for system tray"""
    from PIL import Image, ImageDraw

    # Create 64x64 icon with ReelRecon colors (emerald on dark)
    size = 64
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Dark circle background
    draw.ellipse([2, 2, size-2, size-2], fill=(39, 39, 42, 255))

    # Emerald "R" shape (simplified)
    emerald = (16, 185, 129, 255)
    # Vertical bar
    draw.rectangle([18, 16, 26, 48], fill=emerald)
    # Top arc (simplified as lines)
    draw.rectangle([18, 16, 40, 24], fill=emerald)
    draw.rectangle([36, 16, 44, 36], fill=emerald)
    draw.rectangle([18, 28, 40, 36], fill=emerald)
    # Diagonal leg
    draw.polygon([(26, 36), (34, 36), (46, 48), (38, 48)], fill=emerald)

    return img


def show_splash():
    """Show splash screen during startup"""
    try:
        import tkinter as tk
    except ImportError:
        print("[SPLASH] tkinter not available, skipping splash")
        return None

    splash = tk.Tk()
    splash.title("ReelRecon")
    splash.overrideredirect(True)  # No window decorations

    # Window size and centering
    width, height = 400, 250
    screen_w = splash.winfo_screenwidth()
    screen_h = splash.winfo_screenheight()
    x = (screen_w - width) // 2
    y = (screen_h - height) // 2
    splash.geometry(f"{width}x{height}+{x}+{y}")

    # Dark theme
    splash.configure(bg='#18181b')

    # Main frame
    frame = tk.Frame(splash, bg='#18181b')
    frame.pack(expand=True, fill='both', padx=20, pady=20)

    # Title
    title = tk.Label(frame, text="REELRECON", font=('Arial', 28, 'bold'),
                    fg='#10b981', bg='#18181b')
    title.pack(pady=(20, 5))

    # Subtitle
    subtitle = tk.Label(frame, text="// TACTICAL", font=('Arial', 12),
                       fg='#71717a', bg='#18181b')
    subtitle.pack()

    # Status
    status_var = tk.StringVar(value="Starting server...")
    status = tk.Label(frame, textvariable=status_var, font=('Arial', 10),
                     fg='#a1a1aa', bg='#18181b')
    status.pack(pady=(30, 10))

    # Progress dots animation
    dots_var = tk.StringVar(value="")
    dots = tk.Label(frame, textvariable=dots_var, font=('Arial', 14),
                   fg='#10b981', bg='#18181b')
    dots.pack()

    # Store references for updates
    splash.status_var = status_var
    splash.dots_var = dots_var

    return splash


def animate_splash(splash, stop_event):
    """Animate the splash screen dots"""
    if not splash:
        return

    dot_states = ['', '.', '..', '...']
    i = 0
    while not stop_event.is_set():
        try:
            splash.dots_var.set(dot_states[i % 4])
            splash.update()
            i += 1
            time.sleep(0.3)
        except:
            break


def update_splash_status(splash, message):
    """Update splash screen status message"""
    if splash:
        try:
            splash.status_var.set(message)
            splash.update()
        except:
            pass


def close_splash(splash):
    """Close the splash screen"""
    if splash:
        try:
            splash.destroy()
        except:
            pass


def start_server():
    """Start the Flask server as a subprocess"""
    global server_process

    # Determine Python executable
    if IS_WINDOWS:
        python_exe = r'C:\Python312\python.exe'
        if not os.path.exists(python_exe):
            python_exe = sys.executable
    else:
        python_exe = sys.executable

    # Start server with output hidden but logged to file
    startupinfo = None
    if IS_WINDOWS:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

    app_path = os.path.join(SCRIPT_DIR, 'app.py')
    log_file = os.path.join(SCRIPT_DIR, 'server.log')

    # Open log file for writing (append mode)
    log_handle = open(log_file, 'a')

    server_process = subprocess.Popen(
        [python_exe, '-u', app_path],  # -u for unbuffered output
        cwd=SCRIPT_DIR,
        stdout=log_handle,
        stderr=log_handle,
        startupinfo=startupinfo
    )

    return server_process


def wait_for_server(timeout=30):
    """Wait for server to be ready"""
    import urllib.request
    import urllib.error

    start = time.time()
    while time.time() - start < timeout:
        try:
            url = f"http://localhost:{PORT}/"
            urllib.request.urlopen(url, timeout=1)
            return True
        except (urllib.error.URLError, Exception):
            time.sleep(0.5)
    return False


def stop_server():
    """Stop the Flask server"""
    global server_process
    if server_process:
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except:
            server_process.kill()
        server_process = None


webview_window = None

def open_browser():
    """Open the app in a native window using PyWebView"""
    global webview_window
    try:
        import webview

        # Create native window (will be started later in main)
        webview_window = webview.create_window(
            'ReelRecon',
            SERVER_URL,
            width=1400,
            height=900,
            min_size=(800, 600)
        )

    except Exception as e:
        print(f"[WEBVIEW] Failed to create window: {e}")
        # Fallback to default browser
        webbrowser.open(SERVER_URL)


def set_window_icon():
    """Set window icon using Windows API (runs after window created)"""
    if not IS_WINDOWS:
        return
    try:
        import ctypes
        from ctypes import wintypes

        # Load icon from file
        icon_path = os.path.join(SCRIPT_DIR, 'ReelRecon.ico')
        if not os.path.exists(icon_path):
            return

        # Windows API constants
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x0010
        LR_DEFAULTSIZE = 0x0040

        user32 = ctypes.windll.user32

        # Find the ReelRecon window
        hwnd = user32.FindWindowW(None, "ReelRecon")
        if hwnd:
            # Load icons
            hicon_big = user32.LoadImageW(0, icon_path, IMAGE_ICON, 48, 48, LR_LOADFROMFILE)
            hicon_small = user32.LoadImageW(0, icon_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)

            if hicon_big:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)
            if hicon_small:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
    except Exception as e:
        print(f"[ICON] Failed to set icon: {e}")


def start_webview():
    """Start the webview (blocking call)"""
    global webview_window
    if webview_window:
        try:
            import webview

            # Set icon after window is shown
            def on_shown():
                time.sleep(0.5)  # Wait for window to fully initialize
                set_window_icon()

            icon_thread = threading.Thread(target=on_shown, daemon=True)
            icon_thread.start()

            webview.start()
        except Exception as e:
            print(f"[WEBVIEW] Failed to start: {e}")


def view_logs(icon=None, item=None):
    """Open the server log file"""
    log_file = os.path.join(SCRIPT_DIR, 'server.log')
    if os.path.exists(log_file):
        if IS_WINDOWS:
            subprocess.Popen(['notepad', log_file])
        else:
            subprocess.Popen(['open', '-a', 'TextEdit', log_file])
    else:
        if IS_WINDOWS:
            subprocess.Popen(['notepad', log_file])  # Creates empty file
        else:
            subprocess.Popen(['touch', log_file])


def restart_app(icon=None, item=None):
    """Restart the application"""
    global tray_icon
    stop_server()
    if tray_icon:
        tray_icon.stop()

    # Relaunch the launcher with --no-browser flag (browser already open)
    if IS_WINDOWS:
        subprocess.Popen(['C:\\Python312\\pythonw.exe', os.path.join(SCRIPT_DIR, 'launcher.pyw'), '--no-browser'],
                        cwd=SCRIPT_DIR)
    else:
        subprocess.Popen([sys.executable, os.path.join(SCRIPT_DIR, 'launcher.pyw'), '--no-browser'],
                        cwd=SCRIPT_DIR)
    sys.exit(0)


def fetch_updates(icon=None, item=None):
    """Fetch updates from git"""
    try:
        result = subprocess.run(['git', 'pull'], cwd=SCRIPT_DIR, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            # Show notification or just restart
            restart_app(icon, item)
        else:
            print(f"[UPDATE] Git pull failed: {result.stderr}")
    except Exception as e:
        print(f"[UPDATE] Failed to fetch updates: {e}")


def quit_app(icon=None, item=None):
    """Quit the application"""
    global tray_icon
    stop_server()
    if tray_icon:
        tray_icon.stop()
    # Clean up lock file
    try:
        import tempfile
        lock_file = os.path.join(tempfile.gettempdir(), 'reelrecon_launcher.lock')
        if os.path.exists(lock_file):
            os.remove(lock_file)
    except:
        pass
    sys.exit(0)


def setup_tray():
    """Setup system tray icon"""
    global tray_icon

    try:
        import pystray
        from pystray import MenuItem as item
    except ImportError:
        print("[TRAY] pystray not available")
        return None

    icon_image = create_icon_image()

    menu = pystray.Menu(
        item('Open ReelRecon', lambda: open_browser(), default=True),
        item('Server Running', lambda: None, enabled=False),
        pystray.Menu.SEPARATOR,
        item('Restart', restart_app),
        item('Fetch Updates', fetch_updates),
        item('View Logs', view_logs),
        pystray.Menu.SEPARATOR,
        item('Quit', quit_app)
    )

    tray_icon = pystray.Icon(
        'ReelRecon',
        icon_image,
        'ReelRecon Server',
        menu
    )

    return tray_icon


def run_setup():
    """Run initial setup (migrations, etc)"""
    python_exe = sys.executable

    # Run migrations silently
    try:
        subprocess.run([python_exe, '-m', 'storage.migrate'],
                      capture_output=True, cwd=SCRIPT_DIR, timeout=30)
    except:
        pass

    try:
        subprocess.run([python_exe, '-m', 'storage.update_metadata'],
                      capture_output=True, cwd=SCRIPT_DIR, timeout=30)
    except:
        pass


def main():
    """Main launcher function"""
    global tray_icon

    # Check for --no-browser flag (used on restart when browser already open)
    skip_browser = '--no-browser' in sys.argv

    # Show splash screen IMMEDIATELY (tkinter is built-in)
    splash = show_splash()

    # Start animation in background
    stop_animation = threading.Event()
    if splash:
        anim_thread = threading.Thread(target=animate_splash, args=(splash, stop_animation))
        anim_thread.daemon = True
        anim_thread.start()

    # Install launcher dependencies (pystray, Pillow for tray icon)
    update_splash_status(splash, "Installing dependencies...")
    install_dependencies()

    # Run setup/migrations
    update_splash_status(splash, "Running migrations...")
    run_setup()

    # Start server
    update_splash_status(splash, "Starting server...")
    start_server()

    # Wait for server
    update_splash_status(splash, "Waiting for server...")
    if wait_for_server(timeout=30):
        update_splash_status(splash, "Server ready!")
        time.sleep(0.5)
    else:
        update_splash_status(splash, "Server may have failed to start")
        time.sleep(2)

    # Stop animation and close splash
    stop_animation.set()
    close_splash(splash)

    # Setup tray in background thread
    tray_icon = setup_tray()
    if tray_icon:
        tray_thread = threading.Thread(target=tray_icon.run, daemon=True)
        tray_thread.start()

    # Open window (skip on restart - window already open)
    if not skip_browser:
        open_browser()
        # Start webview (this blocks until window closed)
        start_webview()
        # When webview closes, quit the app
        quit_app()
    else:
        # On restart, just open browser normally and run tray
        webbrowser.open(SERVER_URL)
        if tray_icon:
            tray_icon.run()
        else:
            print(f"Server running at {SERVER_URL}")
            print("Press Ctrl+C to stop")
            try:
                while server_process and server_process.poll() is None:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
            finally:
                stop_server()


if __name__ == '__main__':
    main()

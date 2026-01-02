#!/usr/bin/env python3
"""
ReelRecon Desktop Launcher (Mac)
- Splash screen during startup
- Native window using PyWebView
- Menu bar icon with controls

Double-click to run, or: python3 ReelRecon-Mac.py
If this opens in a text editor: Right-click → Open With → Python Launcher

Fallback: Use START-HERE.py if this has issues
"""
import sys
import os
import threading
import time
import webbrowser
import subprocess
import shutil

# Change to script directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

# Server config
PORT = 5001
SERVER_URL = f"http://localhost:{PORT}/workspace"

# Global state
server_thread = None
server_running = False
tray_icon = None
webview_window = None


def install_launcher_deps():
    """Install pystray, Pillow, and pywebview for native app experience"""
    for pkg in ['pystray', 'Pillow', 'pywebview']:
        try:
            __import__(pkg.lower())
        except ImportError:
            print(f"[SETUP] Installing {pkg}...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', pkg, '-q'],
                         capture_output=True)


def install_app_deps():
    """Install app dependencies"""
    print("[SETUP] Installing core dependencies...")
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip', '-q'],
                  capture_output=True)
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'flask', 'requests', '-q'],
                  capture_output=True)
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'yt-dlp', '-q'],
                  capture_output=True)

    # Check for ffmpeg
    if shutil.which('ffmpeg'):
        print("[SETUP] Installing transcription support...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'openai-whisper', '-q'],
                      capture_output=True)


def create_config():
    """Create config.json if missing"""
    config_path = os.path.join(SCRIPT_DIR, 'config.json')
    template_path = os.path.join(SCRIPT_DIR, 'config.template.json')

    if not os.path.exists(config_path):
        if os.path.exists(template_path):
            shutil.copy(template_path, config_path)
            print("[CONFIG] Created config.json from template")
        else:
            import json
            default_config = {
                "ai_provider": "local",
                "local_model": "qwen3:8B",
                "openai_model": "gpt-4o-mini",
                "anthropic_model": "claude-3-5-haiku-20241022",
                "google_model": "gemini-1.5-flash",
                "openai_key": "",
                "anthropic_key": "",
                "google_key": ""
            }
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=2)
            print("[CONFIG] Created default config.json")


def run_migrations():
    """Run database migrations"""
    try:
        subprocess.run([sys.executable, '-m', 'storage.migrate'],
                      capture_output=True, cwd=SCRIPT_DIR, timeout=30)
    except:
        pass
    try:
        subprocess.run([sys.executable, '-m', 'storage.update_metadata'],
                      capture_output=True, cwd=SCRIPT_DIR, timeout=30)
    except:
        pass


def create_icon_image():
    """Create menu bar icon"""
    from PIL import Image, ImageDraw

    size = 64
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Dark circle background
    draw.ellipse([2, 2, size-2, size-2], fill=(39, 39, 42, 255))

    # Emerald "R"
    emerald = (16, 185, 129, 255)
    draw.rectangle([18, 16, 26, 48], fill=emerald)
    draw.rectangle([18, 16, 40, 24], fill=emerald)
    draw.rectangle([36, 16, 44, 36], fill=emerald)
    draw.rectangle([18, 28, 40, 36], fill=emerald)
    draw.polygon([(26, 36), (34, 36), (46, 48), (38, 48)], fill=emerald)

    return img


def show_splash(status_callback=None):
    """Show splash screen"""
    try:
        import tkinter as tk
    except ImportError:
        return None, None

    splash = tk.Tk()
    splash.title("ReelRecon")
    splash.overrideredirect(True)

    width, height = 400, 250
    screen_w = splash.winfo_screenwidth()
    screen_h = splash.winfo_screenheight()
    x = (screen_w - width) // 2
    y = (screen_h - height) // 2
    splash.geometry(f"{width}x{height}+{x}+{y}")
    splash.configure(bg='#18181b')

    frame = tk.Frame(splash, bg='#18181b')
    frame.pack(expand=True, fill='both', padx=20, pady=20)

    title = tk.Label(frame, text="REELRECON", font=('Arial', 28, 'bold'),
                    fg='#10b981', bg='#18181b')
    title.pack(pady=(20, 5))

    subtitle = tk.Label(frame, text="// TACTICAL", font=('Arial', 12),
                       fg='#71717a', bg='#18181b')
    subtitle.pack()

    status_var = tk.StringVar(value="Starting...")
    status = tk.Label(frame, textvariable=status_var, font=('Arial', 10),
                     fg='#a1a1aa', bg='#18181b')
    status.pack(pady=(30, 10))

    return splash, status_var


def update_splash(splash, status_var, message):
    """Update splash status"""
    if splash and status_var:
        try:
            status_var.set(message)
            splash.update()
        except:
            pass


def close_splash(splash):
    """Close splash"""
    if splash:
        try:
            splash.destroy()
        except:
            pass


def start_server_thread():
    """Start Flask server in thread"""
    global server_running
    server_running = True

    # Import and run Flask app
    from app import app
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)


def open_webview_window():
    """Create native window using PyWebView"""
    global webview_window
    try:
        import webview

        webview_window = webview.create_window(
            'ReelRecon',
            SERVER_URL,
            width=1400,
            height=900,
            min_size=(800, 600)
        )
    except Exception as e:
        print(f"[WEBVIEW] Failed to create window: {e}")
        webview_window = None


def start_webview():
    """Start the webview (blocking call)"""
    global webview_window
    if webview_window:
        try:
            import webview
            # On Mac, try to set dock icon via PyObjC if available
            try:
                from AppKit import NSApplication, NSImage
                icon_path = os.path.join(SCRIPT_DIR, 'ReelRecon.png')
                if os.path.exists(icon_path):
                    app = NSApplication.sharedApplication()
                    icon = NSImage.alloc().initWithContentsOfFile_(icon_path)
                    if icon:
                        app.setApplicationIconImage_(icon)
            except ImportError:
                pass  # PyObjC not installed, icon won't change
            except Exception as e:
                print(f"[ICON] Failed to set dock icon: {e}")

            webview.start()
        except Exception as e:
            print(f"[WEBVIEW] Failed to start: {e}")
            # Fallback to browser
            webbrowser.open(SERVER_URL)
    else:
        # Fallback to browser
        webbrowser.open(SERVER_URL)


def open_browser():
    """Open browser to app (fallback)"""
    webbrowser.open(SERVER_URL)


def restart_app(icon=None, item=None):
    """Restart the application"""
    global tray_icon
    if tray_icon:
        tray_icon.stop()
    # Relaunch with --no-browser flag (browser already open)
    subprocess.Popen([sys.executable, os.path.join(SCRIPT_DIR, 'ReelRecon-Mac.py'), '--no-browser'],
                    cwd=SCRIPT_DIR)
    os._exit(0)


def fetch_updates(icon=None, item=None):
    """Fetch updates from git"""
    try:
        result = subprocess.run(['git', 'pull'], cwd=SCRIPT_DIR, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            restart_app(icon, item)
        else:
            print(f"[UPDATE] Git pull failed: {result.stderr}")
    except Exception as e:
        print(f"[UPDATE] Failed to fetch updates: {e}")


def quit_app(icon=None, item=None):
    """Quit application"""
    global tray_icon
    if tray_icon:
        tray_icon.stop()
    os._exit(0)


def setup_menubar():
    """Setup menu bar icon"""
    global tray_icon

    try:
        import pystray
        from pystray import MenuItem as item
    except ImportError:
        return None

    icon_image = create_icon_image()

    menu = pystray.Menu(
        item('Open ReelRecon', lambda: open_browser(), default=True),
        item('Server Running', lambda: None, enabled=False),
        pystray.Menu.SEPARATOR,
        item('Restart', restart_app),
        item('Fetch Updates', fetch_updates),
        pystray.Menu.SEPARATOR,
        item('Quit', quit_app)
    )

    tray_icon = pystray.Icon('ReelRecon', icon_image, 'ReelRecon Server', menu)
    return tray_icon


def main():
    global server_thread, tray_icon

    # Check for --no-browser flag (used on restart when browser already open)
    skip_browser = '--no-browser' in sys.argv

    print("=" * 40)
    print("  REELRECON // TACTICAL")
    print("=" * 40)
    print()

    # Show splash
    splash, status_var = show_splash()

    # Install dependencies
    update_splash(splash, status_var, "Installing dependencies...")
    install_launcher_deps()
    install_app_deps()

    # Create config
    update_splash(splash, status_var, "Checking configuration...")
    create_config()

    # Run migrations
    update_splash(splash, status_var, "Running migrations...")
    run_migrations()

    # Create output directory
    os.makedirs('output', exist_ok=True)

    # Start server in thread
    update_splash(splash, status_var, "Starting server...")
    server_thread = threading.Thread(target=start_server_thread, daemon=True)
    server_thread.start()

    # Wait for server
    update_splash(splash, status_var, "Waiting for server...")
    time.sleep(3)

    update_splash(splash, status_var, "Ready!")
    time.sleep(0.5)

    # Close splash
    close_splash(splash)

    # Setup menu bar icon in background thread
    tray_icon = setup_menubar()
    if tray_icon:
        tray_thread = threading.Thread(target=tray_icon.run, daemon=True)
        tray_thread.start()

    # Open native window (skip on restart - window already open)
    if not skip_browser:
        open_webview_window()
        # Start webview (this blocks until window closed)
        start_webview()
        # When webview closes, quit the app
        quit_app()
    else:
        # On restart, just open browser normally and run menu bar
        open_browser()
        if tray_icon:
            # Run menu bar in main thread (keeps app alive)
            tray_icon.run()
        else:
            # Fallback - keep running
            print(f"[READY] Server running at {SERVER_URL}")
            print("Press Ctrl+C to stop")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass


if __name__ == '__main__':
    main()

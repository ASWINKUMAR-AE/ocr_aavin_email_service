import os
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / '.venv' / 'Scripts' / 'python.exe'
FRONTEND_DIR = ROOT / 'frontend'

# Set environment
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'


def free_port(port: int):
    """Check if a port is in use on Windows and terminate the listening process."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.4)
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return  # Port is already free
    except Exception:
        return

    print(f"Port {port} is currently in use. Releasing port...")
    try:
        cmd = f'powershell -Command "Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique"'
        output = subprocess.check_output(cmd, shell=True, text=True, errors='ignore')
        for pid_str in output.strip().splitlines():
            pid_str = pid_str.strip()
            if pid_str.isdigit() and int(pid_str) not in (0, os.getpid()):
                subprocess.run(f'powershell -Command "Stop-Process -Id {pid_str} -Force -ErrorAction SilentlyContinue"', shell=True, capture_output=True)
                print(f"Terminated stale process (PID {pid_str}) on port {port}.")
        time.sleep(1.2)
    except Exception:
        pass


def stream_logs(pipe, prefix, color_code):
    try:
        for line in iter(pipe.readline, ''):
            if not line:
                break
            clean_line = line.rstrip()
            if clean_line:
                # Colorized prefix for easy terminal distinction
                sys.stdout.write(f"\033[{color_code}m[{prefix}]\033[0m {clean_line}\n")
                sys.stdout.flush()
    except Exception:
        pass


def main():
    print("=" * 65)
    print("       Aavin Bilingual OCR Studio - Unified Launcher         ")
    print("=" * 65)
    print(f"Project Root : {ROOT}")
    print("Checking ports 8000 and 5173...")
    free_port(8000)
    free_port(5173)
    print("Starting FastAPI Backend (Port 8000) & Vite Frontend (Port 5173)...")
    print("-" * 65)

    enable_reload = '--reload' in sys.argv

    backend_cmd = [
        str(VENV_PYTHON),
        '-m', 'uvicorn',
        'app.main:app',
        '--app-dir', 'backend',
        '--host', '127.0.0.1',
        '--port', '8000',
        '--no-access-log'
    ]

    if enable_reload:
        backend_cmd.extend(['--reload', '--reload-dir', str(ROOT / 'backend' / 'app')])

    frontend_cmd = ['npm.cmd', 'run', 'dev']

    # On Windows, isolate child processes into their own process group so that
    # any CTRL_C_EVENT internally fired by uvicorn reloaders is never broadcast
    # to this parent launcher or the PowerShell terminal console.
    cflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0

    backend_proc = subprocess.Popen(
        backend_cmd,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        creationflags=cflags
    )

    frontend_proc = subprocess.Popen(
        frontend_cmd,
        cwd=str(FRONTEND_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        creationflags=cflags
    )

    t_back = threading.Thread(target=stream_logs, args=(backend_proc.stdout, "Backend", "36"), daemon=True)
    t_front = threading.Thread(target=stream_logs, args=(frontend_proc.stdout, "Frontend", "32"), daemon=True)
    t_back.start()
    t_front.start()

    time.sleep(1.5)
    print("\n-> Services Online:")
    print("   * Web Application : http://127.0.0.1:5173")
    print("   * Backend API Docs: http://127.0.0.1:8000/docs")
    print("   * API Health Check: http://127.0.0.1:8000/api/health")
    if enable_reload:
        print("   * Backend Hot-Reload: ACTIVE (watching backend/app)")
    else:
        print("   * Backend Mode      : STABLE (production-ready)")
    print("Press Ctrl+C to terminate both servers.\n" + "-" * 65)

    def shutdown_processes(signum=None, frame=None):
        print("\nStopping services...")
        for p in (backend_proc, frontend_proc):
            try:
                if sys.platform == 'win32':
                    subprocess.run(f'taskkill /F /T /PID {p.pid}', shell=True, capture_output=True)
                else:
                    p.terminate()
            except Exception:
                pass
        print("All services stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_processes)
    signal.signal(signal.SIGTERM, shutdown_processes)

    try:
        while True:
            # Check if any process exited unexpectedly
            b_code = backend_proc.poll()
            f_code = frontend_proc.poll()
            if b_code is not None:
                print(f"[Backend] Process terminated (code {b_code})")
                shutdown_processes()
            if f_code is not None:
                print(f"[Frontend] Process terminated (code {f_code})")
                shutdown_processes()
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown_processes()


if __name__ == '__main__':
    main()

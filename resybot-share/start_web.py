import os
import sys
import subprocess
import signal
import time
import webbrowser
import socket

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON3 = os.path.join(ROOT_DIR, 'venv', 'bin', 'python3')


def port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def wait_for_port(port, timeout=15):
    """Wait until a port is accepting connections."""
    start = time.time()
    while time.time() - start < timeout:
        if port_in_use(port):
            return True
        time.sleep(0.3)
    return False


def main():
    python = VENV_PYTHON3 if os.path.exists(VENV_PYTHON3) else sys.executable

    # Kill stale processes on our ports
    for port in (8000, 5001):
        if port_in_use(port):
            print(f"Port {port} in use, attempting to free it...")
            os.system(f"lsof -ti:{port} | xargs kill -9 2>/dev/null")
            time.sleep(0.5)

    # Start FastAPI server
    print("Starting Resy API server on port 8000...")
    server_proc = subprocess.Popen(
        [python, 'server.py'],
        cwd=os.path.join(ROOT_DIR, 'server'),
    )
    if not wait_for_port(8000):
        print("WARNING: FastAPI server may not have started.")

    # Start Flask web UI
    print("Starting web UI on port 5001...")
    flask_proc = subprocess.Popen(
        [python, 'web_app.py'],
        cwd=ROOT_DIR,
    )
    if wait_for_port(5001):
        webbrowser.open('http://127.0.0.1:5001')
        print("\nResyGrabber is running at http://127.0.0.1:5001")
    else:
        print("WARNING: Flask may not have started. Try opening http://127.0.0.1:5001 manually.")

    print("Press Ctrl+C to shut down.\n")

    def cleanup(*args):
        print("\nShutting down...")
        flask_proc.terminate()
        server_proc.terminate()
        flask_proc.wait()
        server_proc.wait()
        print("Done.")
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    try:
        flask_proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()


if __name__ == '__main__':
    main()

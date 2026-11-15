"""One command to run Vexo Kin: npm run dev"""
import os
import signal
import subprocess
import sys
import threading
import time
import webbrowser


PORT = 5050
URL = f"http://127.0.0.1:{PORT}"


def _free_port(port: int) -> None:
    try:
        out = subprocess.check_output(["lsof", "-ti", f":{port}"], stderr=subprocess.DEVNULL)
        for pid in out.decode().split():
            pid = pid.strip()
            if pid and pid != str(os.getpid()):
                subprocess.run(["kill", "-9", pid], check=False)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass


def main() -> None:
    _free_port(PORT)
    import server

    opened = threading.Event()

    def _open_browser():
        time.sleep(0.6)
        if not opened.is_set():
            webbrowser.open(URL)

    threading.Thread(target=_open_browser, daemon=True).start()

    def _shutdown(_signum, _frame):
        opened.set()
        server.band_controller.shutdown()
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        server.app.run(host="127.0.0.1", port=PORT, debug=False, threaded=True)
    except KeyboardInterrupt:
        pass
    finally:
        server.band_controller.shutdown()


if __name__ == "__main__":
    main()
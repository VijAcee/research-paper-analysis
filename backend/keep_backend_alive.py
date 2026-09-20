import subprocess
import time
import sys
import os
import urllib.request

backend_script = os.path.abspath(os.path.join(os.path.dirname(__file__), 'run.py'))
cwd = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def is_backend_healthy():
    try:
        res = urllib.request.urlopen("http://localhost:8000/api/health", timeout=2)
        return res.status == 200
    except Exception:
        return False

def main():
    print(f"[SUPERVISOR] Starting PaperLens Persistent Self-Healing Watchdog...")
    print(f"[SUPERVISOR] Target Script: {backend_script}")
    
    while True:
        if not is_backend_healthy():
            print("[SUPERVISOR] Backend on port 8000 is offline. Spawning backend process...")
            proc = subprocess.Popen([sys.executable, backend_script], cwd=cwd)
            
            # Wait up to 10 seconds for port 8000 to come online
            for _ in range(10):
                time.sleep(1)
                if is_backend_healthy():
                    print("[SUPERVISOR] Backend is ONLINE and healthy on http://localhost:8000.")
                    break
            
            # Monitor process while healthy
            while True:
                if proc.poll() is not None:
                    print(f"[SUPERVISOR] WARNING: Backend process exited with code {proc.returncode}. Restarting immediately...")
                    break
                if not is_backend_healthy():
                    print("[SUPERVISOR] WARNING: Health check failed. Terminating frozen instance...")
                    try:
                        proc.terminate()
                        proc.wait(timeout=3)
                    except Exception:
                        pass
                    break
                time.sleep(3)
        else:
            time.sleep(3)

if __name__ == "__main__":
    main()

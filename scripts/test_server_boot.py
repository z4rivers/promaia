import subprocess
import time
import urllib.request
import urllib.error
import sys
import os
import signal

def test_server():
    print("Starting Promaia server (libSQL mode)...")
    
    # We want to kill any existing process on 8000 (best effort)
    # On Windows it's netstat/taskkill, on WSL it's lsof/kill
    env = os.environ.copy()
    env['STORE_BACKEND'] = 'libsql'
    
    process = subprocess.Popen(
        ['uvicorn', 'promaia.web.main:app', '--port', '8005'],
        env=env,
        cwd=r'/mnt/c/Users/Zachary Turner/dev/promaia' if os.name != 'nt' else r'C:\Users\Zachary Turner\dev\promaia',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    print(f"Server started on port 8005 with PID {process.pid}")
    
    try:
        # Wait for boot
        max_retries = 20
        health_ok = False
        
        for i in range(max_retries):
            time.sleep(1)
            try:
                with urllib.request.urlopen('http://127.0.0.1:8005/api/health', timeout=2) as response:
                    if response.status == 200:
                        data = response.read().decode('utf-8')
                        print(f"Health Response: {data}")
                        if "true" in data.lower() or "connected" in data.lower():
                            print("✅ Server booted and database connected successfully!")
                            health_ok = True
                            break
                        else:
                            print(f"⚠️ Health endpoint reachable but returned: {data}")
                            break
            except urllib.error.URLError:
                # Still booting
                print(f"Waiting for server... ({i+1}/{max_retries})")
                pass
            except Exception as e:
                print(f"Error checking health: {e}")
                
        if not health_ok:
            print("❌ Failed to verify server health!")
            out, err = process.communicate(timeout=2)
            print("STDOUT:", out)
            print("STDERR:", err)
            
    finally:
        print("Shutting down test server...")
        if os.name == 'nt':
            process.send_signal(signal.CTRL_C_EVENT)
        else:
            process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()

if __name__ == '__main__':
    test_server()

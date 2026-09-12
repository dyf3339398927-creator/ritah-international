"""Native executable smoke check, without querying Apple or creating orders."""
import json
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import urllib.request

def main():
    root = Path(__file__).resolve().parent.parent / 'dist/iPhone18Stockroom'
    exe = root / ('iPhone18Stockroom.exe' if sys.platform == 'win32' else 'iPhone18Stockroom')
    with tempfile.TemporaryDirectory() as temp:
        process = subprocess.Popen([str(exe), '--no-browser', '--data-dir', temp], cwd=temp,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        lines = queue.Queue()
        def read():
            for line in process.stdout:
                lines.put(line.decode('utf-8', errors='replace').strip())
        threading.Thread(target=read, daemon=True).start()
        try:
            while True:
                line = lines.get(timeout=30)
                if line.startswith('http://127.0.0.1:'):
                    break
                if process.poll() is not None:
                    raise RuntimeError(line)
            address, token = line.split('#')
            req = urllib.request.Request(address + 'api/state', headers={'X-Session': token})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.load(response)
            assert list(data['regions'])[:2] == ['zh_HK', 'ja_JP']
            assert len(data['stores']['zh_HK']) == 6
            with urllib.request.urlopen(address, timeout=10) as response:
                assert b'stockroom' in response.read()
            print('PASS: native executable, assets, HK/JP data and session API')
        finally:
            process.terminate()
            process.wait(timeout=10)

if __name__ == '__main__': main()

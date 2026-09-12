"""Native executable smoke check, without querying Apple or creating orders."""
import json
from pathlib import Path
import queue
import platform
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import zipfile

def main():
    dist = Path(__file__).resolve().parent.parent / 'dist'
    target = 'windows-x64' if sys.platform == 'win32' else 'macos-' + platform.machine()
    archive = dist / f'iPhone18Stockroom-{target}.zip'
    with tempfile.TemporaryDirectory() as temp:
        if sys.platform == 'darwin':
            subprocess.run(['ditto', '-x', '-k', str(archive), temp], check=True)
        else:
            with zipfile.ZipFile(archive) as z:
                z.extractall(temp)
        root = Path(temp) / 'iPhone18Stockroom'
        exe = root / ('iPhone18Stockroom.exe' if sys.platform == 'win32' else 'iPhone18Stockroom')
        process = subprocess.Popen([str(exe), '--no-browser', '--data-dir', str(Path(temp)/'data')], cwd=temp,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        lines = queue.Queue()
        captured = []
        def read():
            for line in process.stdout:
                decoded = line.decode('utf-8', errors='replace').strip()
                captured.append(decoded)
                lines.put(decoded)
        threading.Thread(target=read, daemon=True).start()
        try:
            deadline = time.monotonic() + 120
            while True:
                try:
                    line = lines.get(timeout=1)
                except queue.Empty:
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError('Native startup failed: ' + repr(captured))
                    continue
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
